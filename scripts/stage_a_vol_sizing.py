"""Stage A - volatility-regime dynamic position sizing.

The trades of each candidate rule stay the same; only the risk per trade changes.
Regime at the fill bar (causal): 1h ATR / price, ranked against the trailing
~1 year (6000 1h bars) -> percentile in [0, 1]; terciles low / mid / high.

Sizing rules, all fitted on pre-holdout trades only:
  CONST    1.0 for every trade (baseline).
  INVVOL   volatility targeting: w = clip(median NATR of the trailing year / current
           NATR, 0.5, 2).
  REGIME   w proportional to the shrunk mean R of the trade's tercile (all candidate
           trades of the asset pooled, shrinkage 100 trades); negative tercile -> 0;
           scaled so the average pre-holdout weight is 1.
Result: holdout R stream w * R for each rule, judged with the pre-registered
criterion on the primary rule of every asset (robust #1).

Usage: PYTHONPATH=. python3 scripts/stage_a_vol_sizing.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from stages_common import (ASSETS, ROOT, candidates, full_prep, growth, holdout_cut, trades_for,
                           verdict)

OUT = ROOT / "results" / "stages"
WIN = 6000


def regime_features(prep: dict) -> pd.DataFrame:
    h1 = prep["ctx"].h1
    natr = pd.Series(prep["ctx"].atr1 / h1["close"].to_numpy(), index=h1.index)
    pct = natr.rolling(WIN, min_periods=500).rank(pct=True)
    med = natr.rolling(WIN, min_periods=500).median()
    return pd.DataFrame({"natr": natr, "pct": pct, "med": med})


def run() -> dict:
    res = {"stage": "A", "method": "volatility-regime dynamic position sizing", "assets": {}}
    hold = {s: {} for s in ("CONST", "INVVOL", "REGIME")}
    hold_all = {s: {} for s in ("CONST", "INVVOL", "REGIME")}
    for key in ASSETS:
        prep, h1 = full_prep(key)
        cut = holdout_cut(h1)
        feat = regime_features(prep)
        rows, pool = [], []
        trades = {}
        for c in candidates(key):
            tr = trades_for(prep, c)
            if tr is None or tr.empty:
                continue
            f = feat.iloc[tr["fill_bar"].to_numpy()]
            tr = tr.assign(pct=f["pct"].to_numpy(), natr=f["natr"].to_numpy(),
                           med=f["med"].to_numpy()).dropna(subset=["pct"])
            tr["terc"] = np.digitize(tr["pct"], [1 / 3, 2 / 3])
            trades[c["source"]] = (c, tr)
            pool.append(tr[tr.entry_time < cut])
        if not trades:
            continue
        pre = pd.concat(pool)
        m_all = pre["R"].mean()
        shrunk = {}
        for t in range(3):
            g = pre.loc[pre["terc"] == t, "R"]
            shrunk[t] = (g.sum() + 100 * m_all) / (len(g) + 100)
        raw = {t: max(v, 0.0) for t, v in shrunk.items()}
        mean_w = np.mean([raw[t] for t in pre["terc"]]) if len(pre) else 0
        regime_w = {t: (raw[t] / mean_w if mean_w > 0 else 0.0) for t in range(3)}
        for src, (c, tr) in trades.items():
            w = {"CONST": np.ones(len(tr)),
                 "INVVOL": np.clip(tr["med"] / tr["natr"], 0.5, 2.0).to_numpy(),
                 "REGIME": np.array([regime_w[t] for t in tr["terc"]])}
            h = (tr.entry_time >= cut).to_numpy()
            row = {"source": src, "combo": c["combo"], "primary": c["primary"],
                   "hold_trades": int(h.sum())}
            for s, wv in w.items():
                r = (wv * tr["R"].to_numpy())[h]
                row[f"{s}_mean"] = float(r.mean()) if len(r) else None
                row[f"{s}_unit_1pct"], row[f"{s}_dd"] = growth(r)
                hold_all[s].setdefault(key, []).append(r)
                if c["primary"]:
                    hold[s][key] = r
            rows.append(row)
        res["assets"][key] = {"tercile_shrunk_mean_r": shrunk, "regime_weights": regime_w,
                              "rules": rows}
        print(f"[A] {key}: {len(rows)} rules, regime weights {regime_w}", flush=True)
    res["verdict_primary"] = {s: verdict(v) for s, v in hold.items()}
    res["verdict_all_candidates"] = {
        s: verdict({k: np.concatenate(v) for k, v in d.items()}) for s, d in hold_all.items()}
    # The stage succeeds only if a *dynamic* sizing rule passes (CONST is the baseline).
    res["positive"] = bool(res["verdict_primary"]["INVVOL"]["positive"]
                           or res["verdict_primary"]["REGIME"]["positive"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage_a.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    r = run()
    for scope in ("verdict_primary", "verdict_all_candidates"):
        print(scope)
        for s, v in r[scope].items():
            print(f"  {s:7s} trades={v['trades']:5d} mean={v['mean_r']:+.3f} t={v['t']:+.2f} "
                  f"assets+={v['assets_positive']}/{v['assets']} positive={v['positive']}")
    print("STAGE A POSITIVE:", r["positive"])
