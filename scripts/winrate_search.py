"""High win-rate study with a locked holdout.

Stage 1 - entry quality. Every combination is scored by its win rate on a fixed,
symmetric reference trade (market entry, stop 1 x ATR, target 1 x ATR, no
management). With a symmetric bracket the win rate measures directional skill
only, independent of any RR choice. Ranking uses the lower 5 % bound of the
in-sample (IS) win rate under a Beta posterior, so small samples cannot win.

Stage 2 - profit. For the TOP_N highest win-rate combinations every execution
setting (entry x stop x RR x management) is evaluated on the search period, and
the setting with the best IS expectancy lower bound is kept (RR neighbours must
also be positive).

Stage 3 - locked holdout. The last HOLDOUT_YEARS are opened once. For every
selected combination: does its win rate persist, and does the chosen setting make
money?

Usage: PYTHONPATH=. python3 scripts/winrate_search.py NQ SPX XAU XAG BTC ETH
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

from ictlab.combos import (NSTAT, STAT_COLS, combo_name, eval_topk, parse_slots,
                           replay_trades)
from ictlab.config import ENTRY_FILTERS, ENTRY_MODES, ResearchParams
from ictlab.data import load_asset
from ictlab.research import HALFLIFE_BARS, prepare

HOLDOUT_YEARS = 2
TOP_N = 20
MIN_IS = 60
OUT = Path(__file__).resolve().parent.parent / "results" / "winrate"
ENTRY_NAME = {v: k for k, v in ENTRY_FILTERS.items()}


def cfg_index(cfgs: pd.DataFrame, entry: str, stop: str, rr: float, mgmt: str) -> int:
    m = cfgs[(cfgs.entry == entry) & (cfgs.stop == stop) & (cfgs.rr == rr) & (cfgs.mgmt == mgmt)]
    return int(m.index[0])


def kernel(prep: dict, masks, kmasks, cols: np.ndarray, split: int, topk: int) -> tuple:
    """Stats for the given config columns of the given combos."""
    ctx = prep["ctx"]
    R = np.ascontiguousarray(prep["R"][:, cols])
    XB = np.ascontiguousarray(prep["XB"][:, cols])
    cfg_e = prep["cfg_e"][cols]
    nbr = np.full((cols.size, 2), -1, np.int64)
    if topk == cols.size:  # full grid: keep the RR neighbours for stability
        nbr = prep["nbr"][cols]
    n1 = len(ctx.h1)
    return eval_topk(np.asarray(masks, np.int64), np.asarray(kmasks, np.int64), ctx.trig.bits,
                     ctx.trig.kind, R, XB, prep["FB"], cfg_e, len(ENTRY_MODES), nbr, split,
                     n1 - 1, HALFLIFE_BARS, n1, topk, 2)


def frame(stats, cfg_ids, stab, masks, kmasks, cols) -> pd.DataFrame:
    nk, tk, _ = stats.shape
    flat = stats.reshape(nk * tk, NSTAT).astype(float)
    df = pd.DataFrame(flat, columns=STAT_COLS)
    df["combo_id"] = np.repeat(np.arange(nk), tk)
    local = cfg_ids.reshape(-1)
    df = df[local >= 0].copy()
    df["cfg"] = cols[local[local >= 0]]
    df["stab_raw"] = stab.reshape(-1)[local >= 0]
    df["mask"] = np.asarray(masks)[df["combo_id"]]
    df["kmask"] = np.asarray(kmasks)[df["combo_id"]]
    return df


def wr_bounds(wins, n, a0, b0):
    """Posterior mean and lower 5 % bound of a win rate under a Beta(a0, b0) prior."""
    a, b = a0 + wins, b0 + n - wins
    return a / (a + b), beta.ppf(0.05, a, b)


def factor_table(full: dict, ref: int, cut, oos_start) -> list[dict]:
    """Win-rate lift of every single condition at the reference bracket.

    Uses every trigger (no one-position rule), so samples are large. Lift = win rate
    of triggers with the condition minus win rate of all triggers, per period.
    """
    from ictlab.config import CONDITIONS, ZONE_TYPES

    tr = full["ctx"].trig
    r = full["R"][:, ref]
    ok = np.isfinite(r)
    t_idx = full["ctx"].h1.index[tr.t]
    period = np.where(t_idx >= cut, "hold", np.where(t_idx >= oos_start, "oos", "is"))
    win = r > 0
    feats = {c: ((tr.bits >> i) & 1).astype(bool) for i, c in enumerate(CONDITIONS)}
    feats.update({f"H1_{z}": tr.kind == i for i, z in enumerate(ZONE_TYPES)})
    feats["LONG"] = tr.dir == 1
    rows = []
    for name, f in feats.items():
        row = {"factor": name}
        for per in ("is", "oos", "hold"):
            m = ok & (period == per)
            base = win[m].mean() if m.any() else np.nan
            sel = m & f
            n = int(sel.sum())
            wr = win[sel].mean() if n else np.nan
            se = np.sqrt(base * (1 - base) / n) if n else np.nan
            row.update({f"n_{per}": n, f"wr_{per}": wr, f"lift_{per}": wr - base,
                        f"z_{per}": (wr - base) / se if n else np.nan})
        rows.append(row)
    return rows


def run(key: str, p: ResearchParams) -> dict:
    t0 = time.time()
    h1 = load_asset(key, source="cache")
    cut = h1.index[-1] - pd.DateOffset(years=HOLDOUT_YEARS)
    train = h1[h1.index < cut]
    prep = prepare(key, train, p, verbose=True)
    cfgs = prep["cfgs"]
    split = int(len(train) * (1 - p.oos_fraction))
    masks, kmasks = prep["masks"], prep["kmasks"]

    # ---------------------------------------------------------------- stage 1
    ref = cfg_index(cfgs, "market", "atr1.0", 1.0, "none")
    st, ids, sb, _ = kernel(prep, masks, kmasks, np.array([ref]), split, 1)
    s1 = frame(st, ids, sb, masks, kmasks, np.array([ref]))
    s1 = s1[s1["n_is"] >= MIN_IS].copy()
    base = (s1["win_is"].sum() / s1["n_is"].sum())  # pooled reference win rate
    k = 50.0  # prior strength in trades
    a0, b0 = base * k, (1 - base) * k
    s1["wr_is"] = s1["win_is"] / s1["n_is"]
    s1["wr_oos"] = s1["win_oos"] / s1["n_oos"].where(s1["n_oos"] > 0)
    s1["wr_post"], s1["wr_lcb"] = wr_bounds(s1["win_is"], s1["n_is"], a0, b0)
    s1["combo"] = [combo_name(int(m), int(km)) for m, km in zip(s1["mask"], s1["kmask"])]
    top = s1.sort_values("wr_lcb", ascending=False).drop_duplicates("combo").head(TOP_N)
    # How much of the spread in win rates is real skill and how much binomial noise?
    one = s1.drop_duplicates("combo")
    var_obs = float(one["wr_is"].var())
    var_noise = float((one["wr_is"] * (1 - one["wr_is"]) / one["n_is"]).mean())
    noise = {"observed_sd": var_obs ** 0.5, "noise_sd": var_noise ** 0.5,
             "implied_skill_sd": max(var_obs - var_noise, 0.0) ** 0.5,
             "is_oos_wr_corr": float(one[["wr_is", "wr_oos"]].corr().iloc[0, 1])}

    # ---------------------------------------------------------------- stage 2
    allc = np.arange(len(cfgs))
    st2, ids2, sb2, _ = kernel(prep, top["mask"].values, top["kmask"].values, allc, split,
                               len(allc))
    s2 = frame(st2, ids2, sb2, top["mask"].values, top["kmask"].values, allc)
    s2 = s2[s2["n_is"] >= MIN_IS].copy()
    s2["exp_is"] = s2["sum_is"] / s2["n_is"]
    sd = np.sqrt(((s2["sum2_is"] - s2["n_is"] * s2["exp_is"] ** 2) / (s2["n_is"] - 1)).clip(0.25))
    s2["lcb_is"] = s2["exp_is"] - 1.645 * sd / np.sqrt(s2["n_is"])
    s2["exp_oos"] = s2["sum_oos"] / s2["n_oos"].where(s2["n_oos"] > 0)
    s2["wr_is_cfg"] = s2["win_is"] / s2["n_is"]
    best = (s2[s2["stab_raw"] > 0].sort_values("lcb_is", ascending=False)
            .drop_duplicates("combo_id"))

    # ---------------------------------------------------------------- stage 3
    full = prepare(key, h1, p)
    factors = factor_table(full, ref, cut, train.index[split])
    rows = []
    for _, t in top.iterrows():
        tr_ref = replay_trades(full["ctx"], full["R"], full["XB"], full["FB"], int(t["mask"]),
                               int(t["kmask"]), ref, int(cfgs.loc[ref, "e"]))
        h_ref = tr_ref[tr_ref.entry_time >= cut]
        row = {"combo": t["combo"], **{f"slot_{k2}": v for k2, v in
                                        parse_slots(int(t["mask"])).items()},
               "h1_entry": ENTRY_NAME.get(int(t["kmask"]), "?"),
               "ref_n_is": int(t["n_is"]), "ref_wr_is": float(t["wr_is"]),
               "ref_wr_lcb": float(t["wr_lcb"]),
               "ref_n_oos": int(t["n_oos"]),
               "ref_wr_oos": float(t["wr_oos"]) if pd.notna(t["wr_oos"]) else None,
               "ref_hold_n": int(len(h_ref)),
               "ref_hold_wr": float((h_ref.R > 0).mean()) if len(h_ref) else None,
               "ref_hold_exp": float(h_ref.R.mean()) if len(h_ref) else None}
        b = best[(best["mask"] == t["mask"]) & (best["kmask"] == t["kmask"])]
        if len(b):
            b = b.iloc[0]
            c = cfgs.loc[int(b["cfg"])]
            tr = replay_trades(full["ctx"], full["R"], full["XB"], full["FB"], int(t["mask"]),
                               int(t["kmask"]), int(b["cfg"]), int(c["e"]))
            pre, hold = tr[tr.entry_time < cut], tr[tr.entry_time >= cut]
            eq1 = np.cumprod(1 + 0.01 * hold.R.values) if len(hold) else np.array([1.0])
            eq2 = np.cumprod(1 + 0.02 * hold.R.values) if len(hold) else np.array([1.0])
            pk = np.maximum.accumulate(eq1)
            row.update({
                "entry": c["entry"], "stop": c["stop"], "rr": float(c["rr"]), "mgmt": c["mgmt"],
                "be_wr": 1 / (1 + float(c["rr"])),
                "cfg_n_is": int(b["n_is"]), "cfg_wr_is": float(b["wr_is_cfg"]),
                "cfg_exp_is": float(b["exp_is"]), "cfg_lcb_is": float(b["lcb_is"]),
                "cfg_n_oos": int(b["n_oos"]),
                "cfg_exp_oos": float(b["exp_oos"]) if pd.notna(b["exp_oos"]) else None,
                "pre_n": int(len(pre)), "pre_exp": float(pre.R.mean()) if len(pre) else None,
                "hold_n": int(len(hold)),
                "hold_wr": float((hold.R > 0).mean()) if len(hold) else None,
                "hold_exp": float(hold.R.mean()) if len(hold) else None,
                "hold_total_r": float(hold.R.sum()),
                "hold_unit_1pct": float(eq1[-1]), "hold_unit_2pct": float(eq2[-1]),
                "hold_maxdd_1pct": float(((pk - eq1) / pk).max() * 100)})
        rows.append(row)
    out = {"asset": key, "data_start": str(h1.index[0]), "data_end": str(h1.index[-1]),
           "holdout_start": str(cut), "combos_scored": int(len(s1)),
           "reference": "market entry, stop 1 x ATR(14,1h), target 1 x ATR, no management",
           "pooled_reference_wr_is": float(base),
           "wr_distribution_is": s1["wr_is"].describe().to_dict(),
           "noise_test": noise, "factors": factors,
           "selected": rows, "seconds": round(time.time() - t0, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}_winrate.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"[{key}] done in {out['seconds']}s", flush=True)
    return out


if __name__ == "__main__":
    params = ResearchParams()
    for a in sys.argv[1:]:
        run(a, params)
