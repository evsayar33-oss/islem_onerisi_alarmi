"""Markdown research report."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .combos import parse_slots
from .config import BLOCK_TYPES, ENTRY_FILTERS, HTF, RR_GRID, STOPS, ResearchParams
from .features import BLOCK_NAMES
from .research import RESULTS, detail, slot_strength

REPORTS = Path(__file__).resolve().parent.parent / "reports"

RANK_COLS = ["combo", "entry", "stop", "rr", "mgmt", "n_all", "exp_all", "wr_all", "pf_all",
             "t_all", "dsr_all", "exp_is", "n_oos", "exp_oos", "exp_recent", "dd_all"]


def _md(df: pd.DataFrame | None, floatfmt: str = ".3f") -> str:
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
    rows = ["| " + " | ".join(str(v).replace("|", "\\|") for v in r) + " |"
            for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows]) + "\n"


def rank_full(g: pd.DataFrame, k: int = 15, min_n: int = 100) -> pd.DataFrame:
    """Best config per combo, ranked by the deflated whole-period t-statistic."""
    c = g[(g["n_all"] >= min_n) & (g["n_oos"] >= 20)]
    return c.sort_values("t_all", ascending=False).drop_duplicates("combo_id").head(k)


def best_by_entry(g: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    rows = []
    name = {v: k for k, v in ENTRY_FILTERS.items()}
    c = g[(g["n_all"] >= min_n) & (g["n_oos"] >= 20)]
    for km, sub in c.groupby("kmask"):
        r = sub.sort_values("t_all", ascending=False).iloc[0]
        rows.append({"h1_entry": name.get(int(km), str(km)), "best_combo": r["combo"],
                     "entry": r["entry"], "stop": r["stop"], "rr": r["rr"], "mgmt": r["mgmt"],
                     "n_all": r["n_all"], "exp_all": r["exp_all"], "t_all": r["t_all"],
                     "exp_oos": r["exp_oos"]})
    return pd.DataFrame(rows).sort_values("t_all", ascending=False) if rows else pd.DataFrame()


def block_usage(g: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    """For every block type: best combo that uses it on any HTF slot or as entry."""
    c = g[(g["n_all"] >= min_n) & (g["n_oos"] >= 20)].copy()
    slots = pd.DataFrame([parse_slots(int(m)) for m in c["mask"]], index=c.index)
    name = {v: k for k, v in ENTRY_FILTERS.items()}
    c["h1"] = [name.get(int(k), "") for k in c["kmask"]]
    rows = []
    for b in ("FVG", *BLOCK_TYPES):
        has = np.zeros(len(c), bool)
        for tf in HTF:
            col = slots[tf].astype(str)
            has |= (col == b) | col.str.endswith("+" + b) | ((b == "FVG") & col.str.startswith("FVG"))
        has |= (c["h1"] == b).to_numpy()
        sub = c[has]
        if sub.empty:
            rows.append({"zone": b, "name": BLOCK_NAMES[b], "combos": 0})
            continue
        r = sub.sort_values("t_all", ascending=False).iloc[0]
        rows.append({"zone": b, "name": BLOCK_NAMES[b], "combos": int(sub["combo_id"].nunique()),
                     "median_exp_all": float(sub.drop_duplicates("combo_id")["exp_all"].median()),
                     "best_combo": r["combo"], "best_t": r["t_all"], "best_exp": r["exp_all"],
                     "best_exp_oos": r["exp_oos"]})
    return pd.DataFrame(rows)


def verdict(meta: dict, top: pd.DataFrame, placebo: pd.DataFrame | None = None,
            grid: pd.DataFrame | None = None) -> str:
    """Three levels: validated / weak signal / no edge."""
    cal = meta.get("calibration") or {}
    wf = meta.get("walk_forward") or {}
    t0 = meta.get("t_hurdle") or 0.0
    passed = top[top["dsr_all"] >= 0.95] if len(top) else top
    n_wf = float(wf.get("oos_trades") or 0)
    e_wf = float(wf.get("oos_exp") or 0.0) if n_wf else 0.0
    sd = float(grid["sd_all"].median()) if grid is not None and len(grid) else 1.5
    t_wf = e_wf / sd * np.sqrt(n_wf) if n_wf else 0.0
    plac = None
    if placebo is not None and len(placebo) > 1:
        plac = float(placebo.loc[placebo["series"] != "real", "oos_exp"].max())
    gain = 1 - cal.get("mse", 1) / cal.get("mse_no_skill", 1) if cal.get("mse_no_skill") else 0.0
    lines = [
        f"- IS -> OOS persistence: corr {cal.get('is_oos_corr', np.nan):+.3f}, slope "
        f"{cal.get('persistence_slope', np.nan):+.2f}, learned tau^2 {cal.get('tau2', np.nan):.2g}, "
        f"prediction-error reduction vs no skill {gain:+.1%}.",
        f"- Walk-forward selection (top 10 per fold, chosen on past data only): "
        f"{int(n_wf)} trades, {e_wf:+.3f} R/trade (t = {t_wf:+.2f}), "
        f"{wf.get('folds_positive', 0)}/{wf.get('folds', 0)} folds positive"
        + (f"; best placebo {plac:+.3f} R/trade." if plac is not None else "."),
        f"- Multiple-testing hurdle: t > {t0:.2f} ({meta.get('combos', 0):,} distinct combos, "
        f"{meta.get('trials', 0):,} combo x config trials). Combos passing: **{len(passed)}**.",
    ]
    beats_placebo = plac is None or e_wf > plac
    if t_wf >= 2 and beats_placebo and len(passed):
        v = "**VALIDATED** - the selection process works forward and the top rows survive " \
            "multiple-testing correction."
    elif e_wf > 0 and beats_placebo:
        v = "**WEAK SIGNAL** - some forward information, but not statistically reliable " \
            "(walk-forward t < 2 or no combo clears the hurdle). Rows below are candidates to " \
            "monitor, not to trade."
    else:
        v = "**NO EDGE** - in-sample ranking does not predict out-of-sample results. Rows " \
            "below are the strongest *historical* records only."
    lines.append(f"- Verdict: {v}")
    return "\n".join(lines) + "\n"


def build_report(results: dict, wf: dict, placebo: dict, cross: pd.DataFrame | None,
                 kb, missing: dict, p: ResearchParams, path: Path | None = None) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = path or REPORTS / "RESEARCH_REPORT.md"
    L = ["# ICT Multi-Timeframe Confluence Research Report\n\n"]
    L.append("## 1. Method\n\n")
    L.append(
        "- Base data: 1h OHLC. 4H / D / W / M bars are built from it with a session-aware "
        "calendar (18:00 New York rollover for CME-type markets, 00:00 UTC for crypto). A "
        "higher-timeframe bar is visible only after its last 1h bar closes; the forming bar is "
        "dropped.\n"
        "- Zone types on every timeframe: " + ", ".join(f"{k} ({v})" for k, v in
                                                     BLOCK_NAMES.items()) + ".\n"
        "- Slots: each of M / W / D / H4 takes one choice: none, one zone type, ANYB (any "
        "block), or FVG+<block> (an FVG and a block of that timeframe both overlap the 1h "
        "entry zone = FVG inside the block area). Flags: M:LIQ (previous-month high/low swept "
        "and reclaimed), H4:MSB (fresh 4H structure break in the trade direction). Entry: 1h "
        "FVG, any single block type, ANYB, or ANY.\n"
        "- Exhaustive enumeration with pruning (a branch stops below the minimum trade count); "
        "combos that select identical triggers are evaluated once.\n"
        "- Entry modes: market, limit at zone edge, limit at 50 % (CE). "
        f"Stops ({len(STOPS)}): " + ", ".join(s.name for s in STOPS) + ". "
        f"RR: {', '.join(str(r) for r in RR_GRID)}. Management: none or break-even at +1R.\n"
        "- Conservative fills: stop wins same-bar ties, no target on a limit fill bar, gaps fill "
        "at the open, round-trip costs per asset; one position at a time, accepted in fill "
        "order.\n"
        "- Validation: anchored 5-fold walk-forward of the selection process; shrinkage strength "
        "learned from walk-forward prediction error; t-stat hurdle for the number of distinct "
        "combos; placebo runs on block-permuted series.\n\n")

    L.append("## 2. Data coverage\n\n")
    cov = [{"asset": k, "bars": r["meta"]["bars"], "start": r["meta"]["start"][:10],
            "end": r["meta"]["end"][:10], "triggers": r["meta"]["triggers"],
            "combos": r["meta"]["combos"], "trials": r["meta"]["trials"]}
           for k, r in results.items()]
    L.append(_md(pd.DataFrame(cov)))
    for k, why in missing.items():
        L.append(f"- **{k}** not tested: {why}\n")

    summary = []
    for n, (k, r) in enumerate(results.items(), 1):
        g, meta = r["grid"], r["meta"]
        top = rank_full(g)
        L.append(f"\n## 3.{n} {k}\n\n**Validation**\n\n")
        L.append(verdict(meta, top, placebo.get(k), g))
        if k in placebo:
            L.append("\n**Real vs placebo (same pipeline on structure-free copies)**\n\n")
            L.append(_md(placebo[k]))
        L.append("\n**Strongest combos (whole period, best config per combo, ranked by t)**\n\n")
        L.append(_md(top[RANK_COLS]))
        L.append("\n**Best combo for each 1h entry type**\n\n")
        L.append(_md(best_by_entry(g)))
        L.append("\n**Every zone / block type: where it helps most**\n\n")
        L.append(_md(block_usage(g)))
        L.append("\n**Marginal value of each slot choice (median over combos)**\n\n")
        ss = slot_strength(g).drop(columns=["median_is_score", "best_is_score"], errors="ignore")
        L.append(_md(ss))
        for _, row in top.head(3).iterrows():
            d = detail(r, row)
            L.append(f"\n**Detail: {row['combo']} | {row['entry']} | {row['stop']} | RR "
                     f"{row['rr']} | {row['mgmt']}** - max DD {d['max_dd']:.1f} R, longest "
                     f"losing streak {d['longest_losing_streak']}, long/short "
                     f"{d['long_exp']:+.3f} / {d['short_exp']:+.3f} R\n\n")
            L.append(_md(d["yearly"].reset_index().rename(columns={"entry_time": "year"})))
            L.append("\n")
            L.append(_md(d["regime"].reset_index()))
            L.append("\n")
            L.append(_md(d["session"].reset_index()))
            L.append("\n")
            L.append(_md(d["pd"].reset_index()))
        if len(top):
            t = top.iloc[0]
            summary.append({"asset": k, "best_combo": t["combo"], "entry": t["entry"],
                            "stop": t["stop"], "rr": t["rr"], "mgmt": t["mgmt"],
                            "n_all": t["n_all"], "exp_all": t["exp_all"], "t_all": t["t_all"],
                            "dsr_all": t["dsr_all"], "exp_oos": t["exp_oos"],
                            "wf_oos_exp": (meta.get("walk_forward") or {}).get("oos_exp"),
                            "is_oos_corr": (meta.get("calibration") or {}).get("is_oos_corr")})

    L.append("\n## 4. Summary across assets\n\n")
    L.append(_md(pd.DataFrame(summary)))
    if cross is not None and not cross.empty:
        L.append("\n## 5. Cross-asset robustness (same combo + config on several assets)\n\n"
                 "Selected on in-sample data only (positive IS on every listed asset, ranked by "
                 "combined IS t). `pos_oos` / `pooled_oos_exp` are the untouched check.\n\n")
        L.append(_md(cross.head(25)))

    if kb is not None:
        L.append("\n## 6. Knowledge base (self-improvement state)\n\n")
        cal = pd.DataFrame(kb.cal).T.reset_index().rename(columns={"index": "asset"})
        L.append(_md(cal) if len(cal) else "_first run: no forward evidence yet_\n")
    replay = RESULTS / "replay_log.csv"
    if replay.exists():
        L.append("\n## 7. Learning curve (`replay`)\n\n")
        L.append(_md(pd.read_csv(replay)))
    path.write_text("".join(L))
    return path
