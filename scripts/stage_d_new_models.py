"""Stage D - new ICT models (session / time-of-day models), 1h data, six assets.

D1 JUDAS  Asian range = high/low of the 1h bars 19:00-24:00 New York. During the
          London killzone (02:00-05:00 NY) a bar trades beyond one side and closes
          back inside the range -> trade the other way at that close.
D2 PO3    Power of three: midnight open (00:00 NY). Between 00:00 and 10:00 NY price
          trades below (above) the midnight open, then a 1h bar closes back above
          (below) it -> long (short).
D3 SOUP   Turtle soup: inside a killzone (02-05 or 07-11 NY) a bar trades beyond the
          previous day's high/low and closes back inside -> trade the other way.
D4 SB     Silver bullet: 10:00-11:00 NY, first 15m FVG -> market entry in its
          direction (15m data; assets with complete 15m data only).

Grid per model: stop {sweep/pattern extreme + 0.1 ATR, 1 x ATR beyond entry}
x RR {1, 1.5, 2, 3} x filter {none, BIAS_D (daily close vs 50-day EMA)}; trades
end at the target, the stop or after 24 hours (15m model: 96 bars). One trade
per model per day. The setting with the best pre-holdout mean R (>= 30 trades) is
chosen per asset and model, then the locked holdout is opened.

Usage: PYTHONPATH=.:scripts python3 scripts/stage_d_new_models.py
"""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from ictlab.config import ASSETS as SPECS
from ictlab.features import atr
from ictlab.simulate import _path
from stages_common import ASSETS, ROOT, growth, holdout_cut, verdict

OUT = ROOT / "results" / "stages"
CACHE = ROOT / "data" / "cache"
GRID = list(itertools.product(("extreme", "atr1"), (1.0, 1.5, 2.0, 3.0), ("none", "BIAS_D")))


def daily_bias(h1: pd.DataFrame) -> pd.Series:
    """+1 / -1 per 1h bar: last *completed* NY day close vs its 50-day EMA."""
    ny = h1["close"].tz_convert("America/New_York")
    d = ny.groupby(ny.index.date).last()
    side = np.sign(d - d.ewm(span=50, adjust=False).mean()).shift(1)  # previous day only
    day = pd.Index(h1.index.tz_convert("America/New_York").date)
    return pd.Series(side.reindex(day).to_numpy(), index=h1.index)


def signals(h1: pd.DataFrame, model: str) -> list[tuple[int, int, float]]:
    """(bar index of the signal close, direction, sweep extreme)."""
    ny = h1.index.tz_convert("America/New_York")
    hr = ny.hour.to_numpy()
    day = pd.Index(ny.date)
    o, h, l, c = (h1[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    out = []
    if model == "JUDAS":
        # session of day D: Asian range from 19:00 of the previous calendar day
        sess = pd.Index((ny + pd.Timedelta(hours=5)).date)
        asia = (hr >= 19)
        df = pd.DataFrame({"s": sess, "h": h, "l": l, "asia": asia})
        rng = df[df.asia].groupby("s").agg(ah=("h", "max"), al=("l", "min"))
        done = set()
        for i in np.nonzero((hr >= 2) & (hr < 5))[0]:
            s = sess[i]
            if s in done or s not in rng.index:
                continue
            ah, al = rng.loc[s, "ah"], rng.loc[s, "al"]
            if h[i] > ah and al < c[i] < ah:
                out.append((i, -1, h[i])); done.add(s)
            elif l[i] < al and al < c[i] < ah:
                out.append((i, 1, l[i])); done.add(s)
    elif model == "PO3":
        mo = pd.Series(o).groupby(day).transform("first").to_numpy()  # first bar of NY day
        first_hr = pd.Series(hr).groupby(day).transform("first").to_numpy()
        ok_day = first_hr == 0
        lo_run = pd.Series(l).groupby(day).cummin().to_numpy()
        hi_run = pd.Series(h).groupby(day).cummax().to_numpy()
        done = set()
        for i in np.nonzero(ok_day & (hr >= 1) & (hr < 10))[0]:
            if day[i] in done:
                continue
            if lo_run[i - 1] < mo[i] and c[i] > mo[i] and c[i - 1] <= mo[i]:
                out.append((i, 1, lo_run[i])); done.add(day[i])
            elif hi_run[i - 1] > mo[i] and c[i] < mo[i] and c[i - 1] >= mo[i]:
                out.append((i, -1, hi_run[i])); done.add(day[i])
    elif model == "SOUP":
        dh = pd.Series(h).groupby(day).max()
        dl = pd.Series(l).groupby(day).min()
        days = list(dh.index)
        prev = {d: k for d, k in zip(days[1:], days[:-1])}
        kz = ((hr >= 2) & (hr < 5)) | ((hr >= 7) & (hr < 11))
        done = set()
        for i in np.nonzero(kz)[0]:
            d = day[i]
            if d in done or d not in prev:
                continue
            ph, pl = dh[prev[d]], dl[prev[d]]
            if h[i] > ph and c[i] < ph:
                out.append((i, -1, h[i])); done.add(d)
            elif l[i] < pl and c[i] > pl:
                out.append((i, 1, l[i])); done.add(d)
    return out


def silver_bullet(ltf: pd.DataFrame) -> list[tuple[int, int, float]]:
    ny = ltf.index.tz_convert("America/New_York")
    hr = ny.hour.to_numpy()
    day = pd.Index(ny.date)
    h, l = ltf["high"].to_numpy(), ltf["low"].to_numpy()
    out, done = [], set()
    for j in np.nonzero(hr == 10)[0]:
        if j < 2 or day[j] in done:
            continue
        if l[j] > h[j - 2]:
            out.append((j, 1, min(l[j - 2], l[j - 1]))); done.add(day[j])
        elif h[j] < l[j - 2]:
            out.append((j, -1, max(h[j - 2], h[j - 1]))); done.add(day[j])
    return out


def simulate(df: pd.DataFrame, sig, bias: pd.Series, cost_bps: float, hold_bars: int, cut):
    o, h, l, c = (df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    a = atr(h, l, c, 14)
    res = []
    for stop_kind, rr, filt in GRID:
        rows = []
        for i, d, ext in sig:
            if i >= len(c) - 2 or not np.isfinite(a[i]):
                continue
            if filt == "BIAS_D" and bias.iloc[i] != d:
                continue
            entry = c[i]
            stop = (ext - d * 0.1 * a[i]) if stop_kind == "extreme" else entry - d * a[i]
            risk = (entry - stop) * d
            if risk <= 0.05 * a[i]:
                continue
            xp, _ = _path(d, i, entry, stop, entry + d * rr * risk, 0, o, h, l, c, hold_bars,
                          False, 0.0)
            rows.append((df.index[i], (xp - entry) * d / risk - cost_bps * 1e-4 * entry / risk))
        t = pd.DataFrame(rows, columns=["t", "R"])
        pre, hold = t[t.t < cut], t[t.t >= cut]
        res.append({"stop": stop_kind, "rr": rr, "filter": filt, "pre_n": len(pre),
                    "pre_mean": float(pre.R.mean()) if len(pre) else np.nan,
                    "hold_r": hold.R.to_numpy()})
    best = max((x for x in res if x["pre_n"] >= 30), key=lambda x: x["pre_mean"], default=None)
    return res, best


def run() -> dict:
    out = {"stage": "D", "method": "new ICT session models", "assets": {}, "verdict": {}}
    per_model = {m: {} for m in ("JUDAS", "PO3", "SOUP", "SB")}
    for key in ASSETS:
        h1 = pd.read_parquet(CACHE / f"{key}_1h.parquet")
        cut = holdout_cut(h1)
        bias = daily_bias(h1)
        out["assets"][key] = {}
        for m in ("JUDAS", "PO3", "SOUP"):
            sig = signals(h1, m)
            grid, best = simulate(h1, sig, bias, SPECS[key].cost_bps, 24, cut)
            out["assets"][key][m] = summarize(sig, grid, best)
            if best is not None:
                per_model[m][key] = best["hold_r"]
        f15 = CACHE / f"{key}_15m.parquet"
        if f15.exists():  # complete 15m history (crypto)
            ltf = pd.read_parquet(f15)
            b15 = daily_bias(ltf)
            sig = silver_bullet(ltf)
            grid, best = simulate(ltf, sig, b15, SPECS[key].cost_bps, 96, cut)
            out["assets"][key]["SB"] = summarize(sig, grid, best)
            if best is not None:
                per_model["SB"][key] = best["hold_r"]
        print(f"[D] {key}: " + ", ".join(
            f"{m} hold {v.get('best', {}).get('hold_mean') if v.get('best') else None}"
            for m, v in out["assets"][key].items()), flush=True)
    out["verdict"] = {m: verdict(v) for m, v in per_model.items()}
    out["positive"] = any(v["positive"] for v in out["verdict"].values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage_d.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def summarize(sig, grid, best) -> dict:
    b = None
    if best is not None:
        hr = best["hold_r"]
        b = {k: v for k, v in best.items() if k != "hold_r"} | {
            "hold_n": int(len(hr)), "hold_mean": float(hr.mean()) if len(hr) else None,
            "hold_wr": float((hr > 0).mean()) if len(hr) else None,
            "hold_unit_1pct": growth(hr)[0]}
    return {"signals": len(sig), "grid": [{k: v for k, v in g.items() if k != "hold_r"}
                                          for g in grid], "best": b}


if __name__ == "__main__":
    r = run()
    for m, v in r["verdict"].items():
        print(f"{m:6s} trades={v['trades']:5d} mean={v['mean_r']:+.3f} t={v['t']:+.2f} "
              f"assets+={v['assets_positive']}/{v['assets']} positive={v['positive']}")
    print("STAGE D POSITIVE:", r["positive"])
