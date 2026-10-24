"""Live setup scanner (trade-suggestion alarm).

For the best-ranked (combo, config) rows of an asset it lists the 1h entry zones
that are still actionable on the latest bar: formed recently, not filled, not
invalidated, and carrying the combo's higher-timeframe confluence.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .config import STOPS


def _stop_price(ctx, i: int, entry: float, stop_name: str) -> float:
    tr = ctx.trig
    spec = next(s for s in STOPS if s.name == stop_name)
    t, d = int(tr.t[i]), int(tr.dir[i])
    a = float(ctx.atr1[t])
    if spec.kind == "zone":
        return tr.lo[i] - spec.value * a if d == 1 else tr.hi[i] + spec.value * a
    if spec.kind == "atr":
        return entry - spec.value * a if d == 1 else entry + spec.value * a
    if spec.kind == "swing":
        ref = ctx.swing_lo[t] if d == 1 else ctx.swing_hi[t]
        return ref - spec.value * a if d == 1 else ref + spec.value * a
    return tr.ext[i] - spec.value * a if d == 1 else tr.ext[i] + spec.value * a


def pending_setups(prep: dict, ranked: pd.DataFrame, top_k: int = 10,
                   min_score: float = 0.0) -> list[dict]:
    """Only rows whose lower confidence bound (final_score) clears `min_score` alert."""
    ctx = prep["ctx"]
    p = prep["p"]
    tr = ctx.trig
    h1 = ctx.h1
    last = len(h1) - 1
    lo_arr, hi_arr, c_arr = (h1[k].to_numpy() for k in ("low", "high", "close"))
    best = ranked[(ranked["stab"] > 0) & (ranked["final_score"] > min_score)].drop_duplicates(
        "combo_id").head(top_k)
    recent = np.nonzero(tr.t >= last - p.limit_valid_bars)[0]
    out = []
    for _, row in best.iterrows():
        mask, km = int(row["mask"]), int(row["kmask"])
        mode = row["entry"]
        for i in recent:
            if (int(tr.bits[i]) & mask) != mask or not (1 << int(tr.kind[i])) & km:
                continue
            t, d = int(tr.t[i]), int(tr.dir[i])
            if tr.inv[i] <= last:
                continue
            if mode == "market":
                if t != last:
                    continue
                entry = float(c_arr[last])
            else:
                entry = float(tr.hi[i] if d == 1 else tr.lo[i]) if mode == "limit_edge" \
                    else float(0.5 * (tr.lo[i] + tr.hi[i]))
                after = slice(t + 1, last + 1)
                touched = (lo_arr[after] <= entry).any() if d == 1 else (hi_arr[after] >= entry).any()
                if touched:
                    continue
            stop = _stop_price(ctx, i, entry, row["stop"])
            risk = (entry - stop) * d
            if not np.isfinite(risk) or risk <= 0:
                continue
            out.append({
                "asset": prep["key"], "time": str(h1.index[t]), "side": "LONG" if d == 1 else "SHORT",
                "combo": row["combo"], "entry_mode": mode, "entry": round(entry, 4),
                "stop": round(float(stop), 4), "target": round(entry + d * row["rr"] * risk, 4),
                "rr": float(row["rr"]), "mgmt": row["mgmt"],
                "expected_r": round(float(row["final_mean"]), 3),
                "score": round(float(row["final_score"]), 3),
                "expires_bar": int(t + p.limit_valid_bars) if mode != "market" else last,
            })
    return out


def notify(setups: list[dict]) -> None:
    """Console output; Telegram when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
    if not setups:
        print("No actionable setups.")
        return
    df = pd.DataFrame(setups)
    print(df.to_string(index=False))
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        import requests

        for s in setups:
            text = (f"{s['asset']} {s['side']} | {s['combo']}\n"
                    f"entry {s['entry']} ({s['entry_mode']}) stop {s['stop']} "
                    f"target {s['target']} (RR {s['rr']}, {s['mgmt']})\n"
                    f"E[R]={s['expected_r']} score={s['score']}")
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=20)


def save(setups: list[dict], path) -> None:
    with open(path, "w") as fh:
        json.dump(setups, fh, indent=2)

