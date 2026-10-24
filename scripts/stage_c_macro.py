"""Stage C - news and macro calendar (CPI, NFP 08:30 NY; FOMC 14:00 NY).

C-filters on the earlier candidate rules (trades unchanged, some removed):
  NONE   all trades (baseline)
  AVOID  drop trades filled from 12 h before to 4 h after any event
  POST   keep only trades filled within 48 h after an event
  The variant used per asset is the one with the best pre-holdout mean R over
  all candidate rules of that asset (selection on pre-holdout data only).

C-event strategy (NEWS): at the close of the 1h candle that contains the event,
  if |close - open| >= k x ATR(1h), enter at market in the candle direction
  (FOLLOW) or against it (FADE); stop s x ATR, target RR x risk, exit after 24 h.
  Grid k {0.5, 1} x {FOLLOW, FADE} x s {1, 1.5, 2} x RR {1, 1.5, 2, 3} = 48;
  the setting with the best pre-holdout mean R (>= 30 trades) is chosen per asset.

Usage: PYTHONPATH=.:scripts python3 scripts/stage_c_macro.py
"""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from ictlab.config import ASSETS as SPECS
from ictlab.simulate import _path
from stages_common import (ASSETS, ROOT, candidates, full_prep, growth, holdout_cut, trades_for,
                           verdict)

OUT = ROOT / "results" / "stages"
TIMES = {"CPI": (8, 30), "NFP": (8, 30), "FOMC": (14, 0)}


def events() -> pd.DatetimeIndex:
    d = json.loads((ROOT / "data" / "macro" / "release_dates.json").read_text())
    ts = []
    for k, (hh, mm) in TIMES.items():
        for day in d[k]:
            ts.append(pd.Timestamp(f"{day} {hh:02d}:{mm:02d}", tz="America/New_York"))
    return pd.DatetimeIndex(sorted(ts)).tz_convert("UTC")


def near(times: pd.DatetimeIndex, ev: pd.DatetimeIndex, before_h: float, after_h: float):
    """True where an event lies in [t - after_h, t + before_h] (t relative to the event)."""
    e = ev.as_unit("ns").asi8
    t = times.as_unit("ns").asi8
    lo = np.searchsorted(e, t - int(after_h * 3600e9), side="left")
    hi = np.searchsorted(e, t + int(before_h * 3600e9), side="right")
    return hi > lo


def news_strategy(h1: pd.DataFrame, a1: np.ndarray, ev: pd.DatetimeIndex, cost_bps: float,
                  cut) -> dict:
    o, h, l, c = (h1[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    idx = h1.index
    bars = np.searchsorted(idx, ev.floor("h"), side="left")
    ok = (bars < len(idx)) & (idx[np.clip(bars, 0, len(idx) - 1)] == ev.floor("h"))
    bars = bars[ok]
    res = []
    for k, mode, s, rr in itertools.product((0.5, 1.0), ("FOLLOW", "FADE"), (1.0, 1.5, 2.0),
                                            (1.0, 1.5, 2.0, 3.0)):
        rows = []
        for b in bars:
            a = a1[b]
            body = c[b] - o[b]
            if not np.isfinite(a) or abs(body) < k * a or b >= len(c) - 2:
                continue
            d = 1 if body > 0 else -1
            d = d if mode == "FOLLOW" else -d
            entry = c[b]
            stop = entry - d * s * a
            risk = s * a
            target = entry + d * rr * risk
            xp, _ = _path(d, b, entry, stop, target, 0, o, h, l, c, 24, False, 0.0)
            r = (xp - entry) * d / risk - cost_bps * 1e-4 * entry / risk
            rows.append((idx[b], r))
        df = pd.DataFrame(rows, columns=["t", "R"])
        pre, hold = df[df.t < cut], df[df.t >= cut]
        res.append({"k": k, "mode": mode, "stop_atr": s, "rr": rr, "pre_n": len(pre),
                    "pre_mean": float(pre.R.mean()) if len(pre) else np.nan,
                    "hold_r": hold.R.to_numpy()})
    best = max((x for x in res if x["pre_n"] >= 30), key=lambda x: x["pre_mean"], default=None)
    return {"grid": [{k2: v for k2, v in x.items() if k2 != "hold_r"} for x in res],
            "best": best}


def run() -> dict:
    ev = events()
    res = {"stage": "C", "method": "news and macro calendar", "events": len(ev), "assets": {}}
    prim = {"NONE": {}, "AVOID": {}, "POST": {}, "CHOSEN": {}}
    allc = {"NONE": {}, "CHOSEN": {}}
    news = {}
    for key in ASSETS:
        prep, h1 = full_prep(key)
        cut = holdout_cut(h1)
        pre_pool = {"NONE": [], "AVOID": [], "POST": []}
        rules = []
        for c in candidates(key):
            tr = trades_for(prep, c)
            if tr is None or tr.empty:
                continue
            ft = pd.DatetimeIndex(tr["entry_time"])
            masks = {"NONE": np.ones(len(tr), bool),
                     "AVOID": ~near(ft, ev, before_h=12, after_h=4),
                     "POST": near(ft, ev, before_h=0, after_h=48)}
            pre = (ft < cut)
            for v, m in masks.items():
                pre_pool[v].append(tr["R"].to_numpy()[m & pre])
            rules.append((c, tr, masks, ~pre))
        pre_mean = {v: float(np.concatenate(x).mean()) if x else np.nan
                    for v, x in pre_pool.items()}
        chosen = max(pre_mean, key=lambda v: pre_mean[v])
        rows = []
        for c, tr, masks, hold in rules:
            r = tr["R"].to_numpy()
            row = {"source": c["source"], "combo": c["combo"], "primary": c["primary"]}
            for v, m in masks.items():
                hr = r[m & hold]
                row[f"{v}_n"], row[f"{v}_mean"] = int(len(hr)), (float(hr.mean()) if len(hr) else None)
                if c["primary"]:
                    prim[v][key] = hr
            hc = r[masks[chosen] & hold]
            allc["NONE"].setdefault(key, []).append(r[hold])
            allc["CHOSEN"].setdefault(key, []).append(hc)
            if c["primary"]:
                prim["CHOSEN"][key] = hc
            rows.append(row)
        ns = news_strategy(h1, prep["ctx"].atr1, ev, SPECS[key].cost_bps, cut)
        if ns["best"] is not None:
            news[key] = ns["best"]["hold_r"]
        res["assets"][key] = {"pre_holdout_mean_by_variant": pre_mean, "chosen_variant": chosen,
                              "rules": rows, "news_grid": ns["grid"],
                              "news_best": None if ns["best"] is None else {
                                  k2: v for k2, v in ns["best"].items() if k2 != "hold_r"} | {
                                  "hold_n": int(len(ns["best"]["hold_r"])),
                                  "hold_mean": float(ns["best"]["hold_r"].mean())
                                  if len(ns["best"]["hold_r"]) else None,
                                  "hold_unit_1pct": growth(ns["best"]["hold_r"])[0]}}
        print(f"[C] {key}: chosen {chosen}, pre-holdout means {pre_mean}", flush=True)
    res["verdict_primary"] = {v: verdict(d) for v, d in prim.items()}
    res["verdict_all_candidates"] = {v: verdict({k: np.concatenate(x) for k, x in d.items()})
                                     for v, d in allc.items()}
    res["verdict_news_strategy"] = verdict(news)
    res["positive"] = bool(res["verdict_primary"]["CHOSEN"]["positive"]
                           or res["verdict_news_strategy"]["positive"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage_c.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    r = run()
    for scope in ("verdict_primary", "verdict_all_candidates"):
        print(scope)
        for s, v in r[scope].items():
            print(f"  {s:7s} trades={v['trades']:5d} mean={v['mean_r']:+.3f} t={v['t']:+.2f} "
                  f"assets+={v['assets_positive']}/{v['assets']} positive={v['positive']}")
    v = r["verdict_news_strategy"]
    print(f"news strategy: trades={v['trades']} mean={v['mean_r']:+.3f} t={v['t']:+.2f} "
          f"assets+={v['assets_positive']}/{v['assets']} positive={v['positive']}")
    print("STAGE C POSITIVE:", r["positive"])
