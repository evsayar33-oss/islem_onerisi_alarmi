"""Research runner: assets x combos x (entry, stop, RR, management)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .combos import (combo_name, config_table, enumerate_combos, eval_all, fill_order,
                     replay_trades, to_frame)
from .config import ASSETS, CONDITIONS, ResearchParams
from .context import build_context
from .metrics import enrich, neighbour_stability
from .simulate import run_simulation

RESULTS = Path(__file__).resolve().parent.parent / "results"


HALFLIFE_BARS = 24 * 365 * 2.0  # 2-year half-life for the regime-aware (recent) stat


def prepare(key: str, h1: pd.DataFrame, p: ResearchParams) -> dict:
    """Context + outcome tensor + combo list; reused by every evaluation window."""
    spec = ASSETS[key]
    ctx = build_context(h1, spec, p)
    R, XB, FB = run_simulation(ctx, p, spec.cost_bps)
    nt = R.shape[0]
    cfgs = config_table()
    masks, etypes = enumerate_combos(ctx.trig.bits, ctx.trig.kind, p.min_trades,
                                     p.max_combo_size)
    return {"key": key, "ctx": ctx, "R": R.reshape(nt, -1), "XB": XB.reshape(nt, -1), "FB": FB,
            "order": fill_order(FB), "cfgs": cfgs, "cfg_e": cfgs["e"].to_numpy(np.int64),
            "masks": masks, "etypes": etypes, "p": p}


def evaluate(prep: dict, split_bar: int, end_cut: int | None = None,
             min_trades: int | None = None) -> pd.DataFrame:
    """Grid statistics with IS = [0, split_bar) and OOS = [split_bar, end_cut)."""
    ctx, p, cfgs = prep["ctx"], prep["p"], prep["cfgs"]
    h1 = ctx.h1
    n1 = len(h1)
    end_cut = n1 if end_cut is None else end_cut
    stats = eval_all(prep["masks"], prep["etypes"], ctx.trig.bits, ctx.trig.kind, prep["R"],
                     prep["XB"], prep["FB"], prep["cfg_e"], prep["order"], split_bar,
                     end_cut - 1, HALFLIFE_BARS, end_cut)
    df = to_frame(stats, prep["masks"], prep["etypes"], min_trades or p.min_trades)
    span = (h1.index[min(end_cut, n1) - 1] - h1.index[0]).days / 365.25
    frac_is = split_bar / max(end_cut, 1)
    df = enrich(df, span * frac_is, span * (1 - frac_is),
                n_trials=int(len(prep["masks"]) * len(cfgs)))
    attrs = dict(df.attrs)
    df = df.join(cfgs, on="cfg")
    df["stab"] = neighbour_stability(df, cfgs)
    df["asset"] = prep["key"]
    df["combo"] = [combo_name(int(m), int(e)) for m, e in zip(df["mask"], df["etype"])]
    df["n_conds"] = [bin(int(m)).count("1") for m in df["mask"]]
    df.attrs.update(attrs)
    return df


def run_asset(key: str, h1: pd.DataFrame, p: ResearchParams, out_dir: Path = RESULTS,
              verbose: bool = True, save: bool = True) -> dict:
    t0 = time.time()
    prep = prepare(key, h1, p)
    ctx = prep["ctx"]
    n1 = len(h1)
    split_bar = int(n1 * (1 - p.oos_fraction))
    df = evaluate(prep, split_bar)
    meta = {
        "asset": key, "bars": n1, "start": str(h1.index[0]), "end": str(h1.index[-1]),
        "split_time": str(h1.index[split_bar]), "triggers": int(prep["R"].shape[0]),
        "combos": int(len(prep["masks"])), "configs": int(len(prep["cfgs"])),
        "trials": int(len(prep["masks"]) * len(prep["cfgs"])), "rows_kept": int(len(df)),
        "eb_mu0": df.attrs.get("eb_mu0"), "eb_tau2": df.attrs.get("eb_tau2"),
        "sr0": df.attrs.get("sr0"),
        "condition_rates": {c: float(((ctx.trig.bits >> i) & 1).mean())
                            for i, c in enumerate(CONDITIONS)},
        "seconds": round(time.time() - t0, 1),
    }
    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_dir / f"{key}_grid.parquet")
        (out_dir / f"{key}_meta.json").write_text(json.dumps(meta, indent=2))
    if verbose:
        print(f"[{key}] bars={n1} triggers={meta['triggers']} combos={meta['combos']} "
              f"rows={len(df)} in {meta['seconds']}s")
    return {**prep, "grid": df, "meta": meta}


def walk_forward(prep: dict, folds: int = 5, first_train: float = 0.4, top_k: int = 10,
                 min_is: int = 30) -> pd.DataFrame:
    """Anchored walk-forward test of the *selection process itself*.

    For each fold: rank every (combo, config) on data before the fold, keep the
    top_k (one config per combo), then measure them only inside the fold. The
    pooled fold result answers: "does picking the best combo work out of sample?"
    """
    n1 = len(prep["ctx"].h1)
    edges = np.linspace(int(n1 * first_train), n1, folds + 1).astype(int)
    rows = []
    for k in range(folds):
        s, e = int(edges[k]), int(edges[k + 1])
        df = evaluate(prep, s, end_cut=e, min_trades=1)
        cand = df[(df["n_is"] >= min_is) & (df["stab"] > 0) & (df["exp_shrunk"] > 0)]
        top = cand.sort_values("score", ascending=False).drop_duplicates("combo_id").head(top_k)
        idx = prep["ctx"].h1.index
        if top.empty:  # no combo has positive shrunk edge: the process abstains
            rows.append({"fold": k + 1, "test_start": idx[s], "test_end": idx[e - 1],
                         "rank": 0, "combo": None, "oos_n": 0.0, "oos_sum": 0.0})
        for rank, (_, r) in enumerate(top.iterrows(), 1):
            rows.append({
                "fold": k + 1, "test_start": idx[s], "test_end": idx[e - 1], "rank": rank,
                "combo": r["combo"], "entry": r["entry"], "stop": r["stop"], "rr": r["rr"],
                "mgmt": r["mgmt"], "is_score": r["score"], "is_exp": r["exp_is"],
                "oos_n": r["n_oos"], "oos_sum": r["sum_oos"],
                "oos_exp": r["exp_oos"] if r["n_oos"] > 0 else np.nan,
            })
    return pd.DataFrame(rows)


def walk_forward_summary(wf: pd.DataFrame) -> dict:
    if wf.empty:
        return {"oos_trades": 0}
    n = float(wf["oos_n"].sum())
    total = float(wf["oos_sum"].sum())
    per_fold = wf.groupby("fold").apply(
        lambda g: g["oos_sum"].sum() / max(g["oos_n"].sum(), 1), include_groups=False)
    traded = wf.groupby("fold")["oos_n"].sum() > 0
    return {"oos_trades": int(n), "oos_exp": total / n if n else np.nan,
            "oos_total_r": total, "folds_positive": int((per_fold > 0).sum()),
            "folds_traded": int(traded.sum()), "folds": int(per_fold.size)}


def placebo_series(h1: pd.DataFrame, seed: int = 0, block: int = 24) -> pd.DataFrame:
    """Block-permuted copy of the asset: same candles and volatility, no structure.

    Whole days (24 bars) are shuffled and the price path is rebuilt from each
    bar's own return and wick sizes, so any multi-day / multi-timeframe edge is
    destroyed while intraday behaviour and the cost-to-volatility ratio remain.
    """
    rng = np.random.default_rng(seed)
    o, h, l, c = (h1[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    ret = np.log(c / o)
    up = np.log(h / o)
    dn = np.log(l / o)
    gap = np.log(o[1:] / c[:-1])
    gap = np.r_[0.0, gap]
    n = len(h1)
    nb = n // block
    perm = (rng.permutation(nb)[:, None] * block + np.arange(block)[None, :]).ravel()
    perm = np.r_[perm, np.arange(nb * block, n)]
    lo_ = np.empty(n)
    po = np.empty(n)
    pc = np.empty(n)
    ph = np.empty(n)
    level = np.log(c[0])
    for i, j in enumerate(perm):
        oo = level + (gap[j] if i else 0.0)
        po[i] = oo
        pc[i] = oo + ret[j]
        ph[i] = oo + up[j]
        lo_[i] = oo + dn[j]
        level = pc[i]
    return pd.DataFrame({"open": np.exp(po), "high": np.exp(ph), "low": np.exp(lo_),
                         "close": np.exp(pc), "volume": h1["volume"].to_numpy()},
                        index=h1.index)


def placebo_test(key: str, h1: pd.DataFrame, p: ResearchParams, runs: int = 3,
                 folds: int = 5) -> pd.DataFrame:
    """Walk-forward selection result on real data vs on block-permuted placebos."""
    rows = []
    for r in range(runs + 1):
        series = h1 if r == 0 else placebo_series(h1, seed=p.pt_seed + r)
        prep = prepare(key, series, p)
        wf = walk_forward_summary(walk_forward(prep, folds=folds))
        grid = evaluate(prep, int(len(series) * (1 - p.oos_fraction)))
        top = select_top(grid, 1)
        rows.append({"series": "real" if r == 0 else f"placebo_{r}", **wf,
                     "best_is_score": float(top["score"].iloc[0]) if len(top) else np.nan,
                     "grid_mean_exp": float(grid["exp_all"].mean())})
    return pd.DataFrame(rows)


def select_top(df: pd.DataFrame, k: int = 25, min_oos: int = 10) -> pd.DataFrame:
    """Rank on IS evidence only; OOS columns are the honest check."""
    cand = df[(df["n_is"] >= 30) & (df["n_oos"] >= min_oos) & (df["stab"] > 0)]
    cand = cand.sort_values("score", ascending=False)
    # One row per combo: its best execution config.
    return cand.drop_duplicates("combo_id").head(k)


def summarize_combo_strength(df: pd.DataFrame) -> pd.DataFrame:
    """Marginal value of each condition: best-config shrunk edge with vs without it."""
    best = df.sort_values("score", ascending=False).drop_duplicates("combo_id")
    rows = []
    for i, c in enumerate(CONDITIONS):
        has = (best["mask"].astype(np.int64).to_numpy() >> i) & 1 == 1
        rows.append({
            "condition": c,
            "combos_with": int(has.sum()),
            "median_score_with": float(best.loc[has, "score"].median()) if has.any() else np.nan,
            "median_score_without": float(best.loc[~has, "score"].median()),
            "median_oos_with": float(best.loc[has, "exp_oos"].median()) if has.any() else np.nan,
            "median_oos_without": float(best.loc[~has, "exp_oos"].median()),
        })
    return pd.DataFrame(rows)


def cross_asset(grids: list[pd.DataFrame], min_assets: int = 2) -> pd.DataFrame:
    """Robustness across assets for the same (combo, config)."""
    all_ = pd.concat([g[["asset", "combo", "entry", "stop", "rr", "mgmt", "n_all", "exp_shrunk",
                         "exp_oos", "n_oos", "score"]] for g in grids], ignore_index=True)
    key = ["combo", "entry", "stop", "rr", "mgmt"]
    agg = all_.groupby(key).agg(
        assets=("asset", "nunique"), trades=("n_all", "sum"),
        mean_shrunk=("exp_shrunk", "mean"), min_shrunk=("exp_shrunk", "min"),
        mean_oos=("exp_oos", "mean"), min_oos=("exp_oos", "min"),
        pos_oos=("exp_oos", lambda s: int((s > 0).sum())), mean_score=("score", "mean"),
    ).reset_index()
    agg = agg[agg["assets"] >= min_assets]
    agg["robust_score"] = agg["mean_score"] * agg["pos_oos"] / agg["assets"]
    return agg.sort_values(["robust_score"], ascending=False)


def yearly_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    g = trades.groupby(trades["entry_time"].dt.year)["R"]
    return pd.DataFrame({"n": g.size(), "exp": g.mean(), "sum": g.sum(),
                         "wr": g.apply(lambda s: (s > 0).mean())})


def regime_breakdown(ctx, trades: pd.DataFrame) -> pd.DataFrame:
    """Expectancy by volatility regime (1h ATR / price percentile, terciles)."""
    if trades.empty:
        return pd.DataFrame()
    c = ctx.h1["close"].to_numpy()
    natr = ctx.atr1 / c
    pct = pd.Series(natr).rank(pct=True).to_numpy()
    lab = np.digitize(pct[trades["fill_bar"].to_numpy()], [1 / 3, 2 / 3])
    names = np.array(["low_vol", "mid_vol", "high_vol"])[lab]
    g = trades.assign(regime=names).groupby("regime")["R"]
    return pd.DataFrame({"n": g.size(), "exp": g.mean(), "wr": g.apply(lambda s: (s > 0).mean())})


def detail(res: dict, row: pd.Series) -> dict:
    tr = replay_trades(res["ctx"], res["R"], res["XB"], res["FB"], int(row["mask"]),
                       int(row["etype"]), int(row["cfg"]), int(row["e"]))
    eq = tr["R"].cumsum()
    return {
        "trades": tr,
        "yearly": yearly_breakdown(tr),
        "regime": regime_breakdown(res["ctx"], tr),
        "max_dd": float((eq.cummax() - eq).max()) if len(eq) else 0.0,
        "longest_losing_streak": _streak(tr["R"].to_numpy() <= 0),
    }


def _streak(flags: np.ndarray) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best
