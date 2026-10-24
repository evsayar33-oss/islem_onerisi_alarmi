"""Rule search with a locked holdout.

For each asset:
  1. lock the last HOLDOUT_YEARS of data; nothing below may look at it;
  2. run the full combo x config search (zones, blocks, rule filters, exits) with
     anchored walk-forward on the pre-holdout data only;
  3. pick candidates with two selection rules (both use pre-holdout data only):
       - "best_t":  highest whole-period t-statistic (the naive choice);
       - "robust":  positive in-sample AND out-of-sample, neighbouring RR settings
                    positive, at least 30 OOS trades; ranked by the weaker of the
                    in-sample and out-of-sample t-statistics;
  4. open the holdout once and replay the selected rules on it unchanged.

Usage: PYTHONPATH=. python3 scripts/rule_search.py NQ SPX XAU XAG BTC ETH
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ictlab.combos import parse_slots, replay_trades
from ictlab.config import ASSETS, ENTRY_FILTERS, ResearchParams
from ictlab.data import load_asset
from ictlab.research import detail, prepare, run_asset

HOLDOUT_YEARS = 2
OUT = Path(__file__).resolve().parent.parent / "results" / "rule_search"
ENTRY_NAME = {v: k for k, v in ENTRY_FILTERS.items()}


def robust_pick(g: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    c = g[(g["exp_is"] > 0) & (g["exp_oos"] > 0) & (g["n_oos"] >= 30) & (g["n_is"] >= 60)
          & (g["stab_raw"] > 0)].copy()
    c["t_oos"] = c["exp_oos"] / c["sd_oos"] * np.sqrt(c["n_oos"])
    c["t_min"] = np.minimum(c["t_is"], c["t_oos"])
    return c.sort_values("t_min", ascending=False).drop_duplicates("combo_id").head(k)


def best_t_pick(g: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    c = g[(g["n_all"] >= 100) & (g["n_oos"] >= 20)]
    return c.sort_values("t_all", ascending=False).drop_duplicates("combo_id").head(k)


def growth(r: np.ndarray, risk: float) -> tuple[float, float]:
    if r.size == 0:
        return 1.0, 0.0
    eq = np.cumprod(1 + risk * r)
    peak = np.maximum.accumulate(eq)
    return float(eq[-1]), float(((peak - eq) / peak).max() * 100)


def describe(row: pd.Series) -> dict:
    s = parse_slots(int(row["mask"]))
    return {
        "combo": row["combo"], "monthly": s["M"], "weekly": s["W"], "daily": s["D"],
        "h4": s["H4"], "monthly_liquidity_sweep": s["LIQ"], "h4_msb": s["MSB"],
        "rule_filter": s["FILTER"], "h1_entry": ENTRY_NAME.get(int(row["kmask"]), "?"),
        "entry_mode": row["entry"], "stop": row["stop"], "rr": float(row["rr"]),
        "management": row["mgmt"],
    }


def evaluate_candidate(key, row, prep_full, cut, method, rank):
    tr = replay_trades(prep_full["ctx"], prep_full["R"], prep_full["XB"], prep_full["FB"],
                       int(row["mask"]), int(row["kmask"]), int(row["cfg"]), int(row["e"]))
    pre, hold = tr[tr.entry_time < cut], tr[tr.entry_time >= cut]
    out = {"asset": key, "method": method, "rank": rank, **describe(row),
           "search_n": int(row["n_all"]), "search_exp": float(row["exp_all"]),
           "search_t": float(row["t_all"]), "search_is_exp": float(row["exp_is"]),
           "search_oos_exp": float(row["exp_oos"]) if pd.notna(row["exp_oos"]) else None,
           "pre_trades": int(len(pre)), "pre_exp": float(pre.R.mean()) if len(pre) else None,
           "hold_trades": int(len(hold)),
           "hold_win_pct": float((hold.R > 0).mean() * 100) if len(hold) else None,
           "hold_exp": float(hold.R.mean()) if len(hold) else None,
           "hold_total_r": float(hold.R.sum()), "full_trades": int(len(tr)),
           "full_total_r": float(tr.R.sum())}
    for risk in (0.01, 0.02):
        g, dd = growth(hold.R.to_numpy(), risk)
        out[f"hold_unit_{int(risk * 100)}pct"], out[f"hold_maxdd_{int(risk * 100)}pct"] = g, dd
        g, dd = growth(tr.R.to_numpy(), risk)
        out[f"full_unit_{int(risk * 100)}pct"], out[f"full_maxdd_{int(risk * 100)}pct"] = g, dd
    return out, tr


def run(key: str, p: ResearchParams) -> list[dict]:
    t0 = time.time()
    h1 = load_asset(key, source="cache")
    cut = h1.index[-1] - pd.DateOffset(years=HOLDOUT_YEARS)
    train = h1[h1.index < cut]
    res = run_asset(key, train, p, out_dir=OUT, folds=5)
    g = res["grid"]
    prep_full = prepare(key, h1, p)
    rows, trades = [], {}
    for method, pick in (("robust", robust_pick(g)), ("best_t", best_t_pick(g))):
        for rank, (_, row) in enumerate(pick.iterrows(), 1):
            out, tr = evaluate_candidate(key, row, prep_full, cut, method, rank)
            rows.append(out)
            if rank == 1:
                d = detail(prep_full, row)
                trades[method] = {
                    "yearly": d["yearly"].reset_index().to_dict("records"),
                    "session": d["session"].reset_index().to_dict("records"),
                    "pd": d["pd"].reset_index().to_dict("records"),
                    "regime": d["regime"].reset_index().to_dict("records"),
                    "long_exp": d["long_exp"], "short_exp": d["short_exp"],
                    "longest_losing_streak": d["longest_losing_streak"],
                    "equity": [(str(t), float(r)) for t, r in zip(tr.exit_time, tr.R)],
                }
    meta = {"asset": key, "data_start": str(h1.index[0]), "data_end": str(h1.index[-1]),
            "holdout_start": str(cut), "bars": len(h1), "search": res["meta"],
            "cost_bps_round_trip": ASSETS[key].cost_bps, "details": trades,
            "seconds": round(time.time() - t0, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}_selection.json").write_text(json.dumps({"meta": meta, "candidates": rows},
                                                          indent=1, default=str))
    print(f"[{key}] done in {meta['seconds']}s", flush=True)
    return rows


if __name__ == "__main__":
    p = ResearchParams()
    for k in sys.argv[1:]:
        run(k, p)
