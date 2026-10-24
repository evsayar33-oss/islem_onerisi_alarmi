"""Markdown research report."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import RR_GRID, STOPS, ResearchParams
from .research import RESULTS, detail, select_top, summarize_combo_strength

REPORTS = Path(__file__).resolve().parent.parent / "reports"

TOP_COLS = ["combo", "entry", "stop", "rr", "mgmt", "n_is", "exp_is", "wr_is", "exp_shrunk",
            "score", "n_oos", "exp_oos", "wr_oos", "pf_oos", "exp_recent", "dd_all"]


def _md(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    if df is None or df.empty:
        return "_none_\n"
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            whole = d[c].dropna().map(float.is_integer).all() and c not in ("rr", "kappa")
            fmt = "d" if whole else floatfmt
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else format(int(v) if whole else v, fmt))
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    rows = ["| " + " | ".join(map(str, r)) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows]) + "\n"


def build_report(results: dict, wf: dict, placebo: dict, cross: pd.DataFrame | None,
                 kb, missing: dict, p: ResearchParams, path: Path | None = None) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = path or REPORTS / "RESEARCH_REPORT.md"
    L = ["# ICT Multi-Timeframe Confluence Research Report\n"]
    L.append("## 1. Method\n")
    L.append(
        "- Base data: 1h OHLC. 4H / D / W / M bars are built from it with a session-aware "
        "calendar (18:00 New York rollover for CME-type markets, 00:00 UTC for crypto).\n"
        "- A higher-timeframe bar is visible only after its last 1h bar closes (no lookahead).\n"
        "- Conditions: M_LIQ (previous-month high/low swept and reclaimed), M/W/D/H4 FVG and "
        "order block zones that overlap the 1h entry zone in the trade direction, H4_MSB "
        "(latest 4H structure break in the trade direction, fresh).\n"
        "- Entry: every 1h FVG and 1h order block is a trigger. Entry modes: market (trigger "
        "close), limit at zone edge, limit at consequent encroachment (50 %).\n"
        f"- Stops ({len(STOPS)}): " + ", ".join(s.name for s in STOPS) + ".\n"
        f"- RR grid: {', '.join(str(r) for r in RR_GRID)}; management: none or break-even at +1R.\n"
        "- Conservative fills: stop wins a same-bar stop/target tie, no target on a limit fill "
        "bar, gaps fill at the open, round-trip costs per asset.\n"
        "- One position at a time per strategy, accepted in fill order.\n"
        f"- Validation: IS = first {int((1 - p.oos_fraction) * 100)} %, OOS = last "
        f"{int(p.oos_fraction * 100)} %. Ranking uses IS only. Score = empirical-Bayes shrunk "
        "expectancy minus 1.645 posterior SD. Deflated Sharpe uses the full trial count. "
        "Anchored walk-forward re-selects the top 10 combos per fold. Placebo = the same "
        "pipeline on block-permuted copies of the asset (structure destroyed).\n")

    L.append("## 2. Data coverage\n")
    cov = [{"asset": k, "bars": r["meta"]["bars"], "start": r["meta"]["start"][:10],
            "end": r["meta"]["end"][:10], "triggers": r["meta"]["triggers"],
            "combos": r["meta"]["combos"], "trials": r["meta"]["trials"]}
           for k, r in results.items()]
    L.append(_md(pd.DataFrame(cov)))
    if missing:
        L.append("\nNot tested in this run (no data reachable):\n")
        for k, why in missing.items():
            L.append(f"- **{k}**: {why}\n")

    for k, r in results.items():
        g = r["grid"]
        L.append(f"\n## 3.{list(results).index(k) + 1} {k}\n")
        L.append(f"Trials: {r['meta']['trials']:,}. Deflated-Sharpe hurdle (per-trade SR0): "
                 f"{g.attrs.get('sr0', np.nan):.3f}. Grid mean expectancy: "
                 f"{g['exp_all'].mean():.3f} R.\n\n")
        top = select_top(g, 15)
        L.append("**Top 15 combos (ranked on IS score, best config per combo)**\n\n")
        L.append(_md(top[TOP_COLS]))
        L.append("\n**Marginal value of each condition (best config per combo)**\n\n")
        L.append(_md(summarize_combo_strength(g)))
        if k in wf:
            L.append(f"\n**Walk-forward selection test**: {wf[k]}\n")
        if k in placebo:
            L.append("\n**Real vs placebo**\n\n")
            L.append(_md(placebo[k]))
        for _, row in top.head(3).iterrows():
            d = detail(r, row)
            L.append(f"\n**Detail: {row['combo']} | {row['entry']} | {row['stop']} | "
                     f"RR {row['rr']} | {row['mgmt']}** - max DD {d['max_dd']:.1f} R, "
                     f"longest losing streak {d['longest_losing_streak']}\n\n")
            L.append(_md(d["yearly"].reset_index().rename(columns={"entry_time": "year"})))
            L.append("\n")
            L.append(_md(d["regime"].reset_index()))

    if cross is not None and not cross.empty:
        L.append("\n## 4. Cross-asset robustness (same combo + config)\n\n")
        L.append(_md(cross.head(20)))

    if kb is not None:
        L.append("\n## 5. Knowledge base (self-improvement state)\n\n")
        cal = pd.DataFrame(kb.cal).T.reset_index().rename(columns={"index": "asset"})
        L.append(_md(cal) if len(cal) else "_first run: no forward evidence yet_\n")
    replay = RESULTS / "replay_log.csv"
    if replay.exists():
        L.append("\n## 6. Learning curve (`replay`: the system learns from its own forward "
                 "results)\n\n")
        L.append("Each row: the system only saw data up to `as_of`, then its earlier "
                 "recommendations were scored on bars it had not seen. `kappa` = share of the "
                 "back-tested edge that survived forward; `pred_exp` = fused forecast, "
                 "`fwd_exp` = realised forward expectancy (decayed).\n\n")
        L.append(_md(pd.read_csv(replay)))
    path.write_text("".join(L))
    return path
