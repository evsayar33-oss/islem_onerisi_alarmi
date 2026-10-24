"""Command line interface.

    python -m ictlab fetch    --assets NQ SPX XAU XAG BTC ETH
    python -m ictlab research --assets all --placebo 3 --folds 5
    python -m ictlab replay   --assets XAU --step 6MS
    python -m ictlab scan     --assets all
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from .config import ASSETS, ResearchParams
from .data import load_asset
from .learner import KnowledgeBase
from .report import build_report
from .research import RESULTS, cross_asset, placebo_test
from .research import evaluate, prepare, run_asset
from .scanner import notify, pending_setups, save


def _assets(names: list[str]) -> list[str]:
    return list(ASSETS) if names == ["all"] else [n.upper() for n in names]


def _params(a) -> ResearchParams:
    p = ResearchParams()
    p.overlap_mode = a.overlap
    p.min_trades = a.min_trades
    p.oos_fraction = a.oos
    return p


def cmd_fetch(a) -> None:
    for k in _assets(a.assets):
        try:
            df = load_asset(k, source=a.source, refresh=True, csv_path=a.csv, start=a.start)
            print(f"{k}: {len(df)} bars {df.index[0]} -> {df.index[-1]}")
        except Exception as exc:  # report and continue with the other assets
            print(f"{k}: FAILED ({exc})")


def cmd_research(a) -> None:
    p = _params(a)
    kb = KnowledgeBase()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    results, wf, placebo, missing = {}, {}, {}, {}
    for k in _assets(a.assets):
        try:
            h1 = load_asset(k, source="cache")
        except FileNotFoundError:
            missing[k] = "no cached data; run `python -m ictlab fetch` first"
            continue
        res = run_asset(k, h1, p, folds=a.folds)
        kb.ingest(res)
        kb.calibrate(k)
        ranked = kb.rank(res["grid"], k)
        res["grid"] = ranked
        kb.record(ranked, k, h1.index[-1], run_id)
        if res["meta"]["walk_forward"]:
            wf[k] = res["meta"]["walk_forward"]
        if a.placebo:
            placebo[k] = placebo_test(k, h1, p, runs=a.placebo, folds=a.folds or 5)
            placebo[k].to_csv(RESULTS / f"{k}_placebo.csv", index=False)
        results[k] = res
    kb.save()
    cross = cross_asset([r["grid"] for r in results.values()]) if len(results) > 1 else None
    if cross is not None:
        cross.to_csv(RESULTS / "cross_asset.csv", index=False)
    path = build_report(results, wf, placebo, cross, kb, missing, p)
    print(f"report -> {path}")


def cmd_report(a) -> None:
    """Rebuild the report from saved grids (no re-run of the search)."""
    import json

    p = _params(a)
    kb = KnowledgeBase()
    results, wf, placebo, missing = {}, {}, {}, {}
    for k in _assets(a.assets):
        gp = RESULTS / f"{k}_grid.parquet"
        if not gp.exists():
            missing[k] = "no saved grid; run `python -m ictlab research` first"
            continue
        prep = prepare(k, load_asset(k, source="cache"), p)
        meta = json.loads((RESULTS / f"{k}_meta.json").read_text())
        grid = pd.read_parquet(gp)
        grid = kb.rank(grid, k) if "final_mean" not in grid else grid
        results[k] = {**prep, "grid": grid, "meta": meta}
        if meta.get("walk_forward"):
            wf[k] = meta["walk_forward"]
        pp = RESULTS / f"{k}_placebo.csv"
        if pp.exists():
            placebo[k] = pd.read_csv(pp)
    cross = cross_asset([r["grid"] for r in results.values()]) if len(results) > 1 else None
    if cross is not None:
        cross.to_csv(RESULTS / "cross_asset.csv", index=False)
    print(f"report -> {build_report(results, wf, placebo, cross, kb, missing, p)}")


def cmd_replay(a) -> None:
    """Walk through history, letting the knowledge base learn from real forward results.

    At each step the system sees only data up to that date, ranks every combo on it,
    records its recommendations, and at the next step scores them on the bars it
    had not seen. The printed log is the learning curve of the self-improving loop.
    """
    p = _params(a)
    kb = KnowledgeBase(RESULTS / "knowledge_replay")
    log = []
    for k in _assets(a.assets):
        try:
            h1 = load_asset(k, source="cache")
        except FileNotFoundError:
            print(f"{k}: no data")
            continue
        start = h1.index[int(len(h1) * a.warmup)]
        for cut in pd.date_range(start, h1.index[-1], freq=a.step):
            series = h1[h1.index <= cut]
            prep = prepare(k, series, p)
            added = kb.ingest(prep)
            kappa = kb.calibrate(k)
            ranked = kb.rank(evaluate(prep, len(series)), k)
            kb.record(ranked, k, series.index[-1], f"replay-{cut:%Y%m%d}", k=a.top)
            f = kb.fwd[kb.fwd["asset"] == k]
            row = {"asset": k, "as_of": f"{cut:%Y-%m-%d}", "new_fwd_trades": added,
                   "kappa": round(kappa, 3), "fwd_trades": float(f["n"].sum()),
                   "fwd_exp": float(f["sum"].sum() / max(f["n"].sum(), 1)),
                   "pred_exp": float(f["pred_sum"].sum() / max(f["n"].sum(), 1)),
                   "best": ranked.iloc[0]["combo"] if len(ranked) else None}
            log.append(row)
            print(row)
    kb.save()
    pd.DataFrame(log).to_csv(RESULTS / "replay_log.csv", index=False)


def cmd_scan(a) -> None:
    p = _params(a)
    kb = KnowledgeBase()
    setups = []
    for k in _assets(a.assets):
        try:
            h1 = load_asset(k, source="cache")
        except FileNotFoundError:
            print(f"{k}: no data")
            continue
        prep = prepare(k, h1, p)
        grid = evaluate(prep, int(len(h1) * (1 - p.oos_fraction)))
        setups += pending_setups(prep, kb.rank(grid, k), top_k=a.top, min_score=a.min_score)
    notify(setups)
    save(setups, RESULTS / "signals.json")


def main() -> None:
    ap = argparse.ArgumentParser(prog="ictlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "research", "scan", "replay", "report"):
        s = sub.add_parser(name)
        s.add_argument("--assets", nargs="+", default=["all"])
        s.add_argument("--overlap", choices=["overlap", "inside"], default="overlap")
        s.add_argument("--min-trades", type=int, default=30)
        s.add_argument("--oos", type=float, default=0.30)
        if name == "fetch":
            s.add_argument("--source", default="auto",
                           choices=["auto", "github", "dukascopy", "binance", "yahoo", "csv",
                                    "github_xau"])
            s.add_argument("--csv", default=None)
            s.add_argument("--start", default="2012-01-01")
        if name == "research":
            s.add_argument("--folds", type=int, default=5)
            s.add_argument("--placebo", type=int, default=0)
        if name in ("scan", "replay"):
            s.add_argument("--top", type=int, default=10)
        if name == "scan":
            s.add_argument("--min-score", type=float, default=0.0)
        if name == "replay":
            s.add_argument("--step", default="6MS")
            s.add_argument("--warmup", type=float, default=0.4)
    a = ap.parse_args()
    {"fetch": cmd_fetch, "research": cmd_research, "scan": cmd_scan,
     "replay": cmd_replay, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
