"""Research runner: assets x combos x (entry, stop, RR, management)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .combos import (combo_name, config_table, enumerate_combos, eval_topk, parse_slots,
                     prior_from_moments, replay_trades, rr_neighbours, to_frame)
from .config import ASSETS, ENTRY_FILTERS, ENTRY_MODES, HTF, ResearchParams
from .context import build_context, condition_rates
from .metrics import enrich, full_sample
from .simulate import run_simulation

RESULTS = Path(__file__).resolve().parent.parent / "results"


HALFLIFE_BARS = 24 * 365 * 2.0  # 2-year half-life for the regime-aware (recent) stat


def prepare(key: str, h1: pd.DataFrame, p: ResearchParams, verbose: bool = False) -> dict:
    """Context + outcome tensor + combo list; reused by every evaluation window."""
    t0 = time.time()
    spec = ASSETS[key]
    ctx = build_context(h1, spec, p)
    t1 = time.time()
    R, XB, FB = run_simulation(ctx, p, spec.cost_bps)
    t2 = time.time()
    nt = R.shape[0]
    cfgs = config_table()
    masks, kmasks, raw = enumerate_combos(ctx.trig.bits, ctx.trig.kind, p.min_trades,
                                          p.max_combo_size)
    if verbose:
        print(f"[{key}] context {t1 - t0:.1f}s, simulate {t2 - t1:.1f}s, "
              f"{nt} triggers, {raw} combos -> {len(masks)} distinct "
              f"({time.time() - t2:.1f}s)")
    return {"key": key, "ctx": ctx, "R": R.reshape(nt, -1), "XB": XB.reshape(nt, -1), "FB": FB,
            "cfgs": cfgs, "cfg_e": cfgs["e"].to_numpy(np.int64), "nbr": rr_neighbours(cfgs),
            "masks": masks, "kmasks": kmasks, "raw_combos": raw, "p": p}


def evaluate(prep: dict, split_bar: int, end_cut: int | None = None,
             min_trades: int | None = None, topk: int = 12,
             prior_override: dict | None = None) -> pd.DataFrame:
    """Grid statistics with IS = [0, split_bar) and OOS = [split_bar, end_cut)."""
    ctx, p, cfgs = prep["ctx"], prep["p"], prep["cfgs"]
    h1 = ctx.h1
    n1 = len(h1)
    end_cut = n1 if end_cut is None else end_cut
    stats, cfg_ids, stab, mom = eval_topk(
        prep["masks"], prep["kmasks"], ctx.trig.bits, ctx.trig.kind, prep["R"], prep["XB"],
        prep["FB"], prep["cfg_e"], len(ENTRY_MODES), prep["nbr"], split_bar, end_cut - 1,
        HALFLIFE_BARS, end_cut, topk, p.min_trades)
    prior = prior_from_moments(mom)
    if prior_override:
        prior.update({k: prior_override[k] for k in ("mu0", "tau2") if k in prior_override})
        prior["source"] = prior_override.get("source", "override")
    df = to_frame(stats, cfg_ids, stab, prep["masks"], prep["kmasks"],
                  min_trades or p.min_trades)
    span = (h1.index[min(end_cut, n1) - 1] - h1.index[0]).days / 365.25
    frac_is = split_bar / max(end_cut, 1)
    df = enrich(df, span * frac_is, span * (1 - frac_is),
                n_trials=int(len(prep["masks"]) * len(cfgs)), prior=prior,
                n_eff=int(len(prep["masks"])))
    df = full_sample(df, n_eff=int(len(prep["masks"])))
    attrs = dict(df.attrs)
    df = df.join(cfgs, on="cfg")
    # RR-neighbour stability on the same shrinkage scale as the score
    w = prior["tau2"] / (prior["tau2"] + (df["sd_is"].clip(lower=0.5) ** 2)
                         / df["n_is"].clip(lower=1))
    df["stab"] = w * df["stab_raw"] + (1 - w) * prior["mu0"]
    df["asset"] = prep["key"]
    names = {(int(m), int(k)): combo_name(int(m), int(k))
             for m, k in set(zip(df["mask"], df["kmask"]))}
    df["combo"] = [names[(int(m), int(k))] for m, k in zip(df["mask"], df["kmask"])]
    df["n_conds"] = [bin(int(m)).count("1") for m in df["mask"]]
    df.attrs.update(attrs)
    df.attrs["prior"] = prior
    return df


def run_asset(key: str, h1: pd.DataFrame, p: ResearchParams, out_dir: Path = RESULTS,
              verbose: bool = True, save: bool = True, folds: int = 5) -> dict:
    t0 = time.time()
    prep = prepare(key, h1, p, verbose=verbose)
    ctx = prep["ctx"]
    n1 = len(h1)
    split_bar = int(n1 * (1 - p.oos_fraction))
    wf = pairs = None
    calib = {}
    if folds:
        wf, pairs = walk_forward(prep, folds=folds)
        calib = calibrate_prior(pairs)
    df = evaluate(prep, split_bar, prior_override=calib or None)
    meta = {
        "asset": key, "bars": n1, "start": str(h1.index[0]), "end": str(h1.index[-1]),
        "split_time": str(h1.index[split_bar]), "triggers": int(prep["R"].shape[0]),
        "trigger_kinds": {k: int((ctx.trig.kind == i).sum())
                          for i, k in enumerate(ENTRY_FILTERS) if i < 7},
        "raw_combos": int(prep["raw_combos"]), "combos": int(len(prep["masks"])),
        "configs": int(len(prep["cfgs"])),
        "trials": int(len(prep["masks"]) * len(prep["cfgs"])), "rows_kept": int(len(df)),
        "prior": df.attrs.get("prior"), "t_hurdle": df.attrs.get("t_hurdle"),
        "condition_rates": condition_rates(ctx.trig),
        "calibration": calib,
        "walk_forward": walk_forward_summary(wf) if wf is not None else None,
        "seconds": round(time.time() - t0, 1),
    }
    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_dir / f"{key}_grid.parquet")
        (out_dir / f"{key}_meta.json").write_text(json.dumps(meta, indent=2, default=str))
        if wf is not None:
            wf.to_csv(out_dir / f"{key}_walkforward.csv", index=False)
    if verbose:
        print(f"[{key}] bars={n1} triggers={meta['triggers']} combos={meta['combos']} "
              f"rows={len(df)} in {meta['seconds']}s")
    return {**prep, "grid": df, "meta": meta, "wf": wf}


def walk_forward(prep: dict, folds: int = 5, first_train: float = 0.4, top_k: int = 10,
                 min_is: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Anchored walk-forward test of the *selection process itself*.

    For each fold: rank every (combo, config) on data before the fold only (prior
    estimated on that data too), keep the top_k combos, then measure them only
    inside the fold. The pooled result answers: "does picking the best combo work
    out of sample?". Also returns IS/OOS pairs of every evaluated row, which
    `calibrate_prior` uses to learn how much in-sample edge survives.
    """
    n1 = len(prep["ctx"].h1)
    edges = np.linspace(int(n1 * first_train), n1, folds + 1).astype(int)
    rows, pairs = [], []
    idx = prep["ctx"].h1.index
    for k in range(folds):
        s, e = int(edges[k]), int(edges[k + 1])
        df = evaluate(prep, s, end_cut=e, min_trades=1)
        pr = df.attrs["prior"]
        ok = (df["n_is"] >= min_is) & (df["n_oos"] >= 5)
        pairs.append(pd.DataFrame({
            "fold": k + 1, "mu0": pr["mu0"], "m_is": df.loc[ok, "exp_is"],
            "se2_is": df.loc[ok, "sd_is"].clip(lower=0.5) ** 2 / df.loc[ok, "n_is"],
            "m_oos": df.loc[ok, "exp_oos"],
            "se2_oos": df.loc[ok, "sd_oos"].fillna(df.loc[ok, "sd_is"]).clip(lower=0.5) ** 2
            / df.loc[ok, "n_oos"]}))
        cand = df[(df["n_is"] >= min_is) & (df["stab"] > 0) & (df["exp_shrunk"] > 0)]
        top = cand.sort_values("score", ascending=False).drop_duplicates("combo_id").head(top_k)
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
    return pd.DataFrame(rows), pd.concat(pairs, ignore_index=True)


def calibrate_prior(pairs: pd.DataFrame) -> dict:
    """Learn the shrinkage strength from out-of-sample predictions.

    Prediction: OOS mean = mu0 + w (IS mean - mu0), w = tau2 / (tau2 + se_is^2).
    tau2 minimises the precision-weighted squared OOS prediction error over all
    walk-forward folds. Small tau2 = in-sample differences do not persist.
    Also reports the persistence slope (weighted regression of OOS on IS excess).
    """
    if pairs.empty:
        return {}
    p = pairs.dropna()
    p = p[(p["se2_oos"] > 0) & (p["se2_is"] > 0)]
    wt = 1.0 / p["se2_oos"]
    x = p["m_is"] - p["mu0"]
    y = p["m_oos"] - p["mu0"]
    grid = np.logspace(-6, 0, 61)
    err = []
    for t2 in grid:
        w = t2 / (t2 + p["se2_is"])
        err.append(float((wt * (y - w * x) ** 2).sum() / wt.sum()))
    best = int(np.argmin(err))
    slope = float((wt * x * y).sum() / (wt * x * x).sum())
    corr = float(np.corrcoef(p["m_is"], p["m_oos"])[0, 1]) if len(p) > 2 else np.nan
    return {"tau2": float(grid[best]), "mse": err[best], "mse_no_skill": float(
        (wt * y ** 2).sum() / wt.sum()), "pairs": int(len(p)), "persistence_slope": slope,
            "is_oos_corr": corr, "source": "walk-forward calibrated"}


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
        wf_rows, pairs = walk_forward(prep, folds=folds)
        wf = walk_forward_summary(wf_rows)
        calib = calibrate_prior(pairs)
        wf["learned_tau2"] = calib.get("tau2")
        wf["is_oos_corr"] = calib.get("is_oos_corr")
        grid = evaluate(prep, int(len(series) * (1 - p.oos_fraction)), prior_override=calib)
        top = select_top(grid, 1)
        rows.append({"series": "real" if r == 0 else f"placebo_{r}", **wf,
                     "best_is_score": float(top["score"].iloc[0]) if len(top) else np.nan,
                     "grid_mean_exp": float(grid["exp_all"].mean())})
    return pd.DataFrame(rows)


def select_top(df: pd.DataFrame, k: int = 25, min_oos: int = 10) -> pd.DataFrame:
    """Rank on IS evidence only; OOS columns are the honest check."""
    cand = df[(df["n_is"] >= 30) & (df["n_oos"] >= min_oos)]
    cand = cand.sort_values("score", ascending=False)
    # One row per combo: its best execution config.
    return cand.drop_duplicates("combo_id").head(k)


def _best_per_combo(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("score", ascending=False).drop_duplicates("combo_id")


def slot_strength(df: pd.DataFrame) -> pd.DataFrame:
    """Marginal value of every slot choice (best config per combo).

    For each TF slot option (and flag, and entry filter) it compares combos that
    contain it with otherwise-identical combos where that slot is empty.
    """
    best = _best_per_combo(df).copy()
    slots = pd.DataFrame([parse_slots(int(m)) for m in best["mask"]], index=best.index)
    entry_name = {v: k for k, v in ENTRY_FILTERS.items()}
    slots["H1"] = [entry_name.get(int(k), "?") for k in best["kmask"]]
    best = best.join(slots)
    rows = []
    for col in [*HTF, "LIQ", "MSB", "FILTER", "H1"]:
        for val, g in best.groupby(col):
            if col in (*HTF, "FILTER") and val == "-":
                continue
            if col in ("LIQ", "MSB") and not val:
                continue
            rows.append({
                "slot": col, "choice": str(val), "combos": len(g),
                "median_is_score": g["score"].median(), "best_is_score": g["score"].max(),
                "median_oos_exp": g["exp_oos"].median(),
                "share_oos_positive": float((g["exp_oos"] > 0).mean()),
                "oos_trades": float(g["n_oos"].sum()),
            })
    return pd.DataFrame(rows).sort_values(["slot", "median_oos_exp"], ascending=[True, False])


def cross_asset(grids: list[pd.DataFrame], min_assets: int = 3, min_n: int = 50) -> pd.DataFrame:
    """Robustness across assets for the same (combo, config).

    Selection uses in-sample columns only (exp_is, t_is); the OOS columns are the
    untouched check. Ranking on whole-period numbers would leak the OOS period.
    """
    cols = ["asset", "combo", "entry", "stop", "rr", "mgmt", "n_is", "exp_is", "t_is",
            "n_oos", "sum_oos", "exp_oos"]
    all_ = pd.concat([g.loc[g["n_is"] >= min_n, cols] for g in grids], ignore_index=True)
    key = ["combo", "entry", "stop", "rr", "mgmt"]
    agg = all_.groupby(key).agg(
        assets=("asset", "nunique"), is_trades=("n_is", "sum"),
        mean_exp_is=("exp_is", "mean"), min_exp_is=("exp_is", "min"),
        mean_t_is=("t_is", "mean"), min_t_is=("t_is", "min"),
        pos_is=("exp_is", lambda s: int((s > 0).sum())),
        oos_trades=("n_oos", "sum"), oos_sum=("sum_oos", "sum"),
        pos_oos=("exp_oos", lambda s: int((s > 0).sum())),
        names=("asset", lambda s: ",".join(sorted(s))),
    ).reset_index()
    agg = agg[agg["assets"] >= min_assets]
    agg["pooled_oos_exp"] = agg["oos_sum"] / agg["oos_trades"].where(agg["oos_trades"] > 0)
    agg["combined_t_is"] = agg["mean_t_is"] * np.sqrt(agg["assets"])
    agg = agg[agg["pos_is"] == agg["assets"]]  # positive in-sample on every asset
    return agg.sort_values("combined_t_is", ascending=False).drop(columns=["oos_sum"])


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


SESSIONS_NY = (  # ICT killzones, New York local time
    ("asia", 20, 24), ("london", 2, 5), ("ny_am", 7, 10), ("ny_pm", 13, 16),
)


def session_breakdown(ctx, trades: pd.DataFrame) -> pd.DataFrame:
    """Expectancy by ICT killzone of the fill bar (New York time)."""
    if trades.empty:
        return pd.DataFrame()
    hrs = trades["entry_time"].dt.tz_convert("America/New_York").dt.hour.to_numpy()
    lab = np.full(len(trades), "other", object)
    for name, a, b in SESSIONS_NY:
        lab[(hrs >= a) & (hrs < b)] = name
    g = trades.assign(session=lab).groupby("session")["R"]
    return pd.DataFrame({"n": g.size(), "exp": g.mean(), "wr": g.apply(lambda s: (s > 0).mean())})


def premium_discount(ctx, trades: pd.DataFrame) -> pd.DataFrame:
    """Expectancy by entry location inside the previous week's range.

    ICT: buy in discount (< 50 % of the dealing range), sell in premium (> 50 %).
    """
    if trades.empty:
        return pd.DataFrame()
    w = ctx.tfs["W"]
    close_idx = w["close_idx"]
    wh, wl = w["df"]["high"].to_numpy(), w["df"]["low"].to_numpy()
    fb = trades["fill_bar"].to_numpy()
    prev = np.searchsorted(close_idx, fb, side="left") - 1
    ok = prev >= 0
    px = ctx.h1["close"].to_numpy()[fb]
    pos = np.full(len(fb), np.nan)
    rng = wh[np.clip(prev, 0, None)] - wl[np.clip(prev, 0, None)]
    pos[ok] = (px[ok] - wl[prev[ok]]) / np.where(rng[ok] > 0, rng[ok], np.nan)
    d = trades["dir"].to_numpy()
    aligned = np.where(d == 1, pos < 0.5, pos > 0.5)
    lab = np.where(np.isnan(pos), "n/a", np.where(aligned, "aligned (long in discount / "
                                                           "short in premium)", "against"))
    g = trades.assign(pd_zone=lab).groupby("pd_zone")["R"]
    return pd.DataFrame({"n": g.size(), "exp": g.mean(), "wr": g.apply(lambda s: (s > 0).mean())})


def detail(res: dict, row: pd.Series) -> dict:
    tr = replay_trades(res["ctx"], res["R"], res["XB"], res["FB"], int(row["mask"]),
                       int(row["kmask"]), int(row["cfg"]), int(row["e"]))
    eq = tr["R"].cumsum()
    return {
        "trades": tr,
        "yearly": yearly_breakdown(tr),
        "regime": regime_breakdown(res["ctx"], tr),
        "session": session_breakdown(res["ctx"], tr),
        "pd": premium_discount(res["ctx"], tr),
        "max_dd": float((eq.cummax() - eq).max()) if len(eq) else 0.0,
        "long_exp": float(tr.loc[tr["dir"] == 1, "R"].mean()) if (tr["dir"] == 1).any() else np.nan,
        "short_exp": float(tr.loc[tr["dir"] == -1, "R"].mean()) if (tr["dir"] == -1).any()
        else np.nan,
        "longest_losing_streak": _streak(tr["R"].to_numpy() <= 0),
    }


def _streak(flags: np.ndarray) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best
