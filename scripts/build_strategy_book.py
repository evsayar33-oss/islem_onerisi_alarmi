"""Build STRATEGY_BOOK.md: one self-contained file that explains every result.

Reads results/rule_search/<ASSET>_selection.json (written by scripts/rule_search.py).
Usage: PYTHONPATH=. python3 scripts/build_strategy_book.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "results" / "rule_search"
OUT = ROOT / "STRATEGY_BOOK.md"
ASSETS = ["NQ", "SPX", "XAU", "XAG", "BTC", "ETH"]
NAMES = {"NQ": "Nasdaq 100 (CFD)", "SPX": "S&P 500 (CFD)", "XAU": "Gold spot",
         "XAG": "Silver spot", "BTC": "Bitcoin / USDT", "ETH": "Ether / USDT"}
SOURCES = {"NQ": "Dukascopy USATECHIDXUSD 1h", "SPX": "Dukascopy USA500IDXUSD 1h",
           "XAU": "Dukascopy XAUUSD 1h", "XAG": "Dukascopy XAGUSD 1h",
           "BTC": "Binance spot BTCUSDT 1h", "ETH": "Binance spot ETHUSDT 1h"}

ZONE_TEXT = {
    "FVG": "fair value gap (FVG)", "OB": "order block (OB)", "BB": "breaker block (BB)",
    "MB": "mitigation block (MB)", "RB": "rejection block (RB)",
    "PB": "propulsion block (PB)", "VB": "vacuum block (VB)", "ANYB": "block of any type",
}
TF_TEXT = {"monthly": "monthly", "weekly": "weekly", "daily": "daily", "h4": "4-hour"}
STOP_TEXT = {
    "zone": "at the far edge of the 1h entry zone",
    "atr": "{v} x ATR(14, 1h) away from the entry price",
    "swing": "beyond the last confirmed 1h swing point plus 0.1 x ATR",
    "pattern": "beyond the extreme of the pattern that formed the zone plus 0.1 x ATR",
}
ENTRY_TEXT = {
    "market": "enter at the close of the 1h candle that completes the zone",
    "limit_edge": "place a limit order at the near edge of the zone (valid 24 hours; "
                  "cancelled if a candle closes beyond the far edge)",
    "limit_ce": "place a limit order at the 50 % level of the zone, the consequent "
                "encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge)",
}
MGMT_TEXT = {
    "none": "no management: the trade ends at the stop, the target, or after 120 hours",
    "be1r": "move the stop to the entry price once price reaches +1R",
    "trail2atr": "once price reaches +1R, trail the stop 2 x ATR behind the best price "
                 "(never below entry)",
}
FILTER_TEXT = {
    "BIAS_D": "the last closed daily candle closed on the trade side of its 50-day EMA",
    "BIAS_W": "the most recent weekly market structure break points in the trade direction",
    "KZ": "the entry hour is inside a killzone (02:00-05:00 or 07:00-11:00 New York time)",
    "PD": "the zone sits in discount (long) or premium (short) of the previous week's range",
}


def stop_text(name: str) -> str:
    if name.startswith("atr"):
        return STOP_TEXT["atr"].format(v=name[3:])
    if name.startswith("zone"):
        buf = name[4:].replace("+", "").replace("atr", "")
        return STOP_TEXT["zone"] + (f" plus {buf} x ATR" if buf else "")
    return STOP_TEXT[name.split("+")[0]]


def slot_text(choice: str) -> str:
    if choice.startswith("FVG+"):
        return f"FVG that overlaps a {ZONE_TEXT[choice[4:]]} (FVG inside the block area)"
    return ZONE_TEXT.get(choice, choice)


def rules_text(c: dict) -> list[str]:
    side = []
    for key in ("monthly", "weekly", "daily", "h4"):
        if c[key] not in ("-", "?"):
            side.append(f"the 1h entry zone overlaps an active {TF_TEXT[key]} "
                        f"{slot_text(c[key])} of the same direction")
    if c["monthly_liquidity_sweep"]:
        side.append("price swept the previous month's low (long) / high (short) within the "
                    "last ~22 trading days and the 1h close is back on the other side")
    if c["h4_msb"]:
        side.append("the latest 4-hour market structure break (close beyond the last swing) "
                    "points in the trade direction and is at most 42 4h candles old")
    if c["rule_filter"] not in ("-", "?"):
        for f in c["rule_filter"].split("+"):
            side.append(FILTER_TEXT[f])
    steps = [f"Wait for a new 1h {slot_text(c['h1_entry'])} to complete. Its direction "
             "(bullish/bearish) is the trade direction."]
    if side:
        steps.append("Take it only if all of these are true at that candle's close: "
                     + "; ".join(side) + ".")
    else:
        steps.append("No higher-timeframe condition is required.")
    steps += [f"Entry: {ENTRY_TEXT[c['entry_mode']]}.",
              f"Stop: {stop_text(c['stop'])}. 1R = distance from entry to stop.",
              f"Target: {c['rr']:g}R from the entry.",
              f"Management: {MGMT_TEXT[c['management']]}.",
              "One position at a time; a new setup is ignored while a trade is open."]
    return steps


def md(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_none_\n"
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = ["| " + " | ".join(str(v).replace("|", "\\|") for v in r) + " |"
            for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *body]) + "\n"


def fmt(v, nd=3):
    return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{nd}f}"


def verdict(c: dict) -> str:
    n, e = c["hold_trades"], c["hold_exp"]
    if not n:
        return "NO HOLDOUT TRADES - cannot be judged."
    if e is not None and e > 0 and c["search_oos_exp"] and c["search_oos_exp"] > 0:
        return ("POSITIVE in the locked holdout and in the search out-of-sample period. "
                "Still a single candidate among many tested: treat as a watch-list rule, "
                "confirm with live paper trading before risking capital.")
    if e is not None and e > 0:
        return "POSITIVE in the locked holdout only. Weak evidence."
    return "NEGATIVE in the locked holdout. The historical edge did not persist."


def main() -> None:
    data = {}
    for a in ASSETS:
        f = SRC / f"{a}_selection.json"
        if f.exists():
            data[a] = json.loads(f.read_text())
    L = []
    L.append("# STRATEGY BOOK - ICT multi-timeframe confluence research\n\n")
    L.append("This single file is written so that a person or another AI can understand the "
             "whole study without reading code. It states what was tested, how each rule is "
             "defined, which rule was selected for each asset, and how that rule performed "
             "on data that was locked away during the search.\n\n")

    # ------------------------------------------------------------------ summary
    L.append("## 1. Summary\n\n")
    rows = []
    for a, d in data.items():
        c = [x for x in d["candidates"] if x["method"] == "robust" and x["rank"] == 1]
        c = c[0] if c else next((x for x in d["candidates"] if x["rank"] == 1), None)
        if not c:
            continue
        rows.append({"asset": a, "selected rule (robust #1)": c["combo"],
                     "entry": c["entry_mode"], "stop": c["stop"], "RR": c["rr"],
                     "mgmt": c["management"], "search trades": c["search_n"],
                     "search R/trade": c["search_exp"],
                     "holdout trades": c["hold_trades"],
                     "holdout R/trade": c["hold_exp"],
                     "holdout 1 unit @1%": c["hold_unit_1pct"],
                     "holdout 1 unit @2%": c["hold_unit_2pct"]})
    L.append(md(pd.DataFrame(rows)))
    L.append("\nHoldout = the last 2 years of each asset's data. It was not used for the "
             "search, the walk-forward or the selection. '1 unit @1%' = what 1 unit of "
             "capital became over the holdout when each trade risks 1 % of current equity "
             "(compounded, costs included).\n\n")
    allc = pd.DataFrame([x for d in data.values() for x in d["candidates"]])
    sel = pd.DataFrame(rows)
    if len(allc) and len(sel):
        rob = allc[allc["method"] == "robust"]
        pos_sel = int((sel["holdout R/trade"] > 0).sum())
        L.append(
            "**Bottom line.** The selected rule (robust #1) was positive in the locked holdout "
            f"on {pos_sel} of {len(sel)} assets. Across all {len(rob)} robust candidates, "
            f"{int((rob['hold_exp'] > 0).sum())} were positive and the average holdout result "
            f"was {rob['hold_exp'].mean():+.3f} R/trade. Search-period results were "
            "much better than holdout results, which means most of the search-period edge was "
            "selection luck (overfitting). No rule in this book is a proven edge; the "
            "candidates that stayed positive in the holdout are a watch list for paper "
            "trading.\n\n"
            "**Türkçe özet.** Seçilen kural (robust #1) kilitli son 2 yılda pozitif kalan "
            f"varlık sayısı: {pos_sel}/{len(sel)}. Pozitif kalan robust aday sayısı: "
            f"{int((rob['hold_exp'] > 0).sum())}/{len(rob)}; ortalama sonuç "
            f"{rob['hold_exp'].mean():+.3f} R/işlem. Arama dönemindeki güçlü sonuçlar ileriye "
            "taşınmadı. Bu kitaptaki hiçbir kural kanıtlanmış bir avantaj değildir; kilitli "
            "dönemde pozitif kalanlar yalnızca kâğıt üzerinde izlenecek adaylardır.\n\n")

    # ------------------------------------------------------------------ method
    L.append("## 2. How to read the numbers\n\n")
    L.append(
        "- **R**: profit or loss in units of the initial risk. +2R = won twice the risked "
        "amount; -1R = stopped out. Every R value already subtracts round-trip costs.\n"
        "- **R/trade**: average R per trade (expectancy). Above 0 = profitable before sizing.\n"
        "- **Search period**: data before the holdout. Inside it, the first 70 % is in-sample "
        "(IS) and the last 30 % is out-of-sample (OOS).\n"
        "- **t**: t-statistic of the mean R. With tens of thousands of combinations tested, "
        "luck alone produces t of about 4; values below that are not significant on their own.\n"
        "- **1 unit @x%**: compounded growth of 1 unit when each trade risks x % of equity.\n\n")

    L.append("## 3. Data\n\n")
    drows = []
    for a, d in data.items():
        m = d["meta"]
        drows.append({"asset": a, "instrument": NAMES[a], "source": SOURCES[a],
                      "first bar": m["data_start"][:10], "last bar": m["data_end"][:10],
                      "holdout from": m["holdout_start"][:10], "1h bars": m["bars"],
                      "round-trip cost (bps)": m["cost_bps_round_trip"]})
    L.append(md(pd.DataFrame(drows)))
    L.append("\nHigher timeframes are built from the 1h bars. Trading day starts 18:00 New York "
             "time for NQ, SPX, XAU and XAG (CME-style session) and 00:00 UTC for crypto. Weeks "
             "start on the trading Monday. A higher-timeframe candle is used only after it has "
             "closed; the forming candle is never used.\n\n")

    # ------------------------------------------------------------------ definitions
    L.append("## 4. Definitions of every building block\n\n")
    L.append(
        "All patterns are detected on every timeframe (1M, 1W, 1D, 4H, 1H) with the same code. "
        "A zone is *active* from the close of the candle that confirms it until a candle closes "
        "beyond its far edge, or until it is too old (36 months, 104 weeks, 250 days, 360 4h "
        "candles).\n\n"
        "| Code | Name | Exact rule (bullish; bearish is the mirror) |\n|---|---|---|\n"
        "| FVG | Fair value gap | low[i] > high[i-2] and the gap is at least 0.1 x ATR(14). "
        "Zone = [high[i-2], low[i]]. |\n"
        "| OB | Order block | A candle closes above the last confirmed swing high (swing = "
        "fractal with 2 candles on each side). The last down-close candle of the up-leg is the "
        "OB; zone = its high-low range. |\n"
        "| BB | Breaker block | At such a break: the last up-close candle at the swing high that "
        "was broken, when the decline after that high swept below the previous swing low. |\n"
        "| MB | Mitigation block | Same as BB, but the decline did not take the previous swing "
        "low (higher low, failure swing). |\n"
        "| RB | Rejection block | A confirmed swing low whose lower wick is at least 50 % of the "
        "candle range. Zone = from the low to the lower end of the body. |\n"
        "| PB | Propulsion block | An order block whose candle trades into an older, still "
        "active order block of the same direction. |\n"
        "| VB | Vacuum block | The open is at least 0.25 x ATR above the previous close (gap). "
        "Zone = [previous close, open]. |\n"
        "| ANYB | Any block | Any of OB, BB, MB, RB, PB, VB. |\n"
        "| FVG+X | FVG inside block | On that timeframe an FVG and a block X both overlap the 1h "
        "entry zone. |\n"
        "| M:LIQ | Monthly liquidity sweep | Price traded below the previous month's low "
        "(long) within the last 22 trading days and the current 1h close is back above it. |\n"
        "| H4:MSB | 4H market structure break | Latest 4h close beyond the last swing points in "
        "the trade direction and is at most 42 4h candles old. |\n"
        "| BIAS_D | Daily trend filter | " + FILTER_TEXT["BIAS_D"] + ". |\n"
        "| BIAS_W | Weekly structure filter | " + FILTER_TEXT["BIAS_W"] + ". |\n"
        "| KZ | Killzone filter | " + FILTER_TEXT["KZ"] + ". |\n"
        "| PD | Premium / discount filter | " + FILTER_TEXT["PD"] + ". |\n\n"
        "**Execution grid tested for every combination** (3 x 10 x 9 x 3 = 810 settings):\n\n"
        "- Entry: market at the zone's completion, limit at the near edge, limit at 50 % (CE).\n"
        "- Stop: zone edge (+0 / 0.1 / 0.25 / 0.5 ATR), 1 / 1.5 / 2 / 3 ATR from entry, last "
        "swing + 0.1 ATR, pattern extreme + 0.1 ATR.\n"
        "- Target: 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6 R.\n"
        "- Management: none, break-even at +1R, 2-ATR trailing stop after +1R.\n"
        "- Conservative simulation: if stop and target are both touched in one candle the stop "
        "counts; no target on the candle that fills a limit order; gaps fill at the open; "
        "trades close after 120 hours at the latest.\n\n")

    L.append("## 5. How the rules were searched and selected\n\n")
    L.append(
        "1. Each higher timeframe (M, W, D, H4) gets one choice: nothing, one zone type, any "
        "block, or FVG inside a block. Add the M:LIQ and H4:MSB flags, one rule filter (none, "
        "BIAS_D, BIAS_W, KZ, PD, BIAS_D+KZ) and a 1h entry type. Every combination with at "
        "least 30 trades was tested (about 60 000-90 000 per asset), each with all 810 "
        "execution settings.\n"
        "2. An anchored 5-fold walk-forward tested whether picking the best combination on past "
        "data works on the next period.\n"
        "3. Two selection rules were applied to the search period only:\n"
        "   - **robust**: positive in-sample *and* out-of-sample, neighbouring RR settings also "
        "positive, at least 30 OOS trades; ranked by the weaker of the IS and OOS t-statistics.\n"
        "   - **best_t**: the highest whole-period t-statistic (the naive choice, shown for "
        "comparison).\n"
        "4. The last 2 years (holdout) were opened once, and the selected rules were replayed on "
        "them unchanged.\n\n")

    # ------------------------------------------------------------------ per asset
    L.append("## 6. Asset by asset\n")
    for a, d in data.items():
        m = d["meta"]
        L.append(f"\n### 6.{ASSETS.index(a) + 1} {a} - {NAMES[a]}\n\n")
        wf = (m["search"] or {}).get("walk_forward") or {}
        cal = (m["search"] or {}).get("calibration") or {}
        L.append(f"Search: {m['search']['combos']:,} distinct combinations x 810 settings. "
                 f"Walk-forward of the selection process: {wf.get('oos_trades', 0)} trades, "
                 f"{fmt(wf.get('oos_exp'))} R/trade, {wf.get('folds_positive', 0)}/"
                 f"{wf.get('folds', 0)} folds positive. In-sample vs out-of-sample correlation "
                 f"of all combinations: {fmt(cal.get('is_oos_corr'))}.\n\n")
        for method in ("robust", "best_t"):
            cands = [x for x in d["candidates"] if x["method"] == method]
            if not cands:
                continue
            c = cands[0]
            label = "Selected rule (robust #1)" if method == "robust" else \
                "For comparison: naive best-t rule"
            L.append(f"**{label}: `{c['combo']}` | {c['entry_mode']} | {c['stop']} | "
                     f"RR {c['rr']:g} | {c['management']}**\n\n")
            for i, s in enumerate(rules_text(c), 1):
                L.append(f"{i}. {s}\n")
            L.append("\n")
            L.append(md(pd.DataFrame([{
                "period": "search (pre-holdout)", "trades": c["search_n"],
                "R/trade": c["search_exp"], "IS R/trade": c["search_is_exp"],
                "OOS R/trade": c["search_oos_exp"], "t": c["search_t"]}])))
            L.append("\n")
            L.append(md(pd.DataFrame([{
                "period": "locked holdout", "trades": c["hold_trades"],
                "win %": c["hold_win_pct"], "R/trade": c["hold_exp"],
                "total R": c["hold_total_r"], "1 unit @1%": c["hold_unit_1pct"],
                "max DD @1% (%)": c["hold_maxdd_1pct"], "1 unit @2%": c["hold_unit_2pct"],
                "max DD @2% (%)": c["hold_maxdd_2pct"]}, {
                "period": "whole data", "trades": c["full_trades"], "win %": None,
                "R/trade": c["full_total_r"] / c["full_trades"] if c["full_trades"] else None,
                "total R": c["full_total_r"], "1 unit @1%": c["full_unit_1pct"],
                "max DD @1% (%)": c["full_maxdd_1pct"], "1 unit @2%": c["full_unit_2pct"],
                "max DD @2% (%)": c["full_maxdd_2pct"]}])))
            L.append(f"\nVerdict: **{verdict(c)}**\n\n")
            det = m["details"].get(method)
            if det and method == "robust":
                L.append(f"Long trades {fmt(det['long_exp'])} R/trade, short trades "
                         f"{fmt(det['short_exp'])} R/trade, longest losing streak "
                         f"{det['longest_losing_streak']}.\n\n")
                L.append("By year (whole data):\n\n" + md(pd.DataFrame(det["yearly"])) + "\n")
                L.append("By killzone of entry:\n\n" + md(pd.DataFrame(det["session"])) + "\n")
            if method == "robust" and len(cands) > 1:
                L.append("Other robust candidates (ranks 2-5):\n\n")
                L.append(md(pd.DataFrame([{
                    "rank": x["rank"], "combo": x["combo"], "entry": x["entry_mode"],
                    "stop": x["stop"], "RR": x["rr"], "mgmt": x["management"],
                    "search R/trade": x["search_exp"], "holdout trades": x["hold_trades"],
                    "holdout R/trade": x["hold_exp"], "holdout 1 unit @1%": x["hold_unit_1pct"]}
                    for x in cands[1:]])))
                L.append("\n")

    # ------------------------------------------------------------------ win-rate study
    wr = {a: json.loads((ROOT / "results" / "winrate" / f"{a}_winrate.json").read_text())
          for a in ASSETS if (ROOT / "results" / "winrate" / f"{a}_winrate.json").exists()}
    if wr:
        L.append("## 7. High win-rate study (scripts/winrate_search.py)\n\n")
        L.append(
            "Question: which combinations have the highest win rate, and can the right stop and "
            "RR turn them into profit? Method, using pre-holdout data only:\n\n"
            "1. Score every combination by its win rate on a symmetric reference trade (market "
            "entry, stop 1 x ATR, target 1 x ATR). A symmetric bracket measures directional "
            "skill independent of RR. Rank by the lower 5 % bound of the in-sample win rate "
            "(Beta posterior), minimum 60 trades.\n"
            "2. For the top 20, test every entry x stop x RR (0.5-6) x management setting and "
            "keep the one with the best in-sample expectancy lower bound.\n"
            "3. Open the locked 2-year holdout once.\n\n"
            "**Is win rate a real, persistent property of a combination?**\n\n")
        rows = []
        for a, d in wr.items():
            n = d["noise_test"]
            c = pd.DataFrame(d["selected"])
            rows.append({"asset": a, "combos scored": d["combos_scored"],
                         "base win rate": d["pooled_reference_wr_is"],
                         "observed sd": n["observed_sd"], "pure-noise sd": n["noise_sd"],
                         "implied true-skill sd": n["implied_skill_sd"],
                         "top-20 WR in-sample": c["ref_wr_is"].mean(),
                         "top-20 WR out-of-sample": c["ref_wr_oos"].mean(),
                         "top-20 WR holdout": c["ref_hold_wr"].mean()})
        L.append(md(pd.DataFrame(rows)))
        L.append(
            "\nReading: the spread of win rates across combinations is almost exactly what pure "
            "chance produces (observed sd ~ noise sd). True differences in win rate between "
            "combinations are at most about 2 percentage points. The combinations that showed "
            "60-65 % in-sample fall back to roughly the base rate (about 40-53 % out-of-sample, "
            "45-61 % in the holdout).\n\n"
            "**Did the best stop/RR make the top-20 profitable in the holdout?**\n\n")
        rows = []
        for a, d in wr.items():
            c = pd.DataFrame(d["selected"])
            big = c[c["hold_n"] >= 10]
            rows.append({"asset": a,
                         "holdout price change": None,
                         "rules positive / tested": f"{int((c['hold_exp'] > 0).sum())}/{len(c)}",
                         "rules with >=10 holdout trades": len(big),
                         "of those positive": int((big["hold_exp"] > 0).sum()),
                         "mean R/trade (>=10 trades)": big["hold_exp"].mean() if len(big) else None})
        L.append(md(pd.DataFrame(rows).drop(columns=["holdout price change"])))
        L.append(
            "\nPositive results in the holdout come mostly from rules with very few trades "
            "(1-5) and large RR, so they are not evidence. XAU and XAG rose 47 % and 60 % in "
            "the holdout, which favours long trades.\n\n"
            "**Single conditions: which ones move the win rate?** (all triggers, reference "
            "trade, average over the six assets; lift = win rate with the condition minus the "
            "base rate)\n\n")
        F = pd.concat([pd.DataFrame(d["factors"]).assign(asset=a) for a, d in wr.items()])
        g = F.groupby("factor").agg(lift_is=("lift_is", "mean"), lift_oos=("lift_oos", "mean"),
                                    lift_holdout=("lift_hold", "mean"),
                                    holdout_trades=("n_hold", "sum")).reset_index()
        g = g[g["holdout_trades"] >= 1000].sort_values("lift_holdout", ascending=False)
        L.append(md(pd.concat([g.head(6), g.tail(6)])))
        L.append(
            "\nNo single condition changes the win rate by more than about 1-2 percentage "
            "points in a way that holds in-sample, out-of-sample and in the holdout. 1h order "
            "blocks as entries are slightly worse than average in all three periods.\n\n"
            "**Conclusion of the win-rate study:** none of the tested ICT conditions or their "
            "combinations produces a persistently high win rate on these six markets at 1h "
            "entry resolution. High in-sample win rates are selection luck. Choosing stop and "
            "RR afterwards cannot create an edge that the entry does not have.\n\n"
            "**Türkçe özet:** Test edilen ICT koşulları ve kombinasyonları, bu altı piyasada "
            "1 saatlik girişle kalıcı olarak yüksek bir kazanma oranı üretmiyor. Örneklem "
            "içinde %60-65 görünen oranlar şans eseri seçilmiş. Sonradan doğru stop ve RR "
            "seçmek, girişte olmayan bir avantajı yaratamaz.\n\n")

    # ------------------------------------------------------------------ verdict
    L.append("## 8. Overall conclusion and limits\n\n")
    hold = pd.DataFrame([x for d in data.values() for x in d["candidates"]])
    if len(hold):
        agg = hold.groupby("method").agg(rules=("combo", "count"),
                                         positive_in_holdout=("hold_exp", lambda s: int((s > 0).sum())),
                                         mean_holdout_R=("hold_exp", "mean"))
        L.append("All candidates (5 per method per asset) in the locked holdout:\n\n")
        L.append(md(agg.reset_index()))
    L.append(
        "\n- These are historical simulations. Fills, spreads and slippage in live trading can "
        "be worse.\n"
        "- Thousands of combinations were tested; some will look good by chance. The holdout "
        "test is the main protection; a rule that is positive in the holdout still needs live "
        "paper trading before real money.\n"
        "- Index and metal data are CFD prices (Dukascopy), not exchange futures.\n"
        "- Reproduce: `python -m ictlab fetch --assets all --source dukascopy` (NQ/SPX/XAU/XAG) "
        "and `--source github` (BTC/ETH), then `PYTHONPATH=. python3 scripts/rule_search.py NQ SPX "
        "XAU XAG BTC ETH` and `PYTHONPATH=. python3 scripts/build_strategy_book.py`.\n"
        "- Code map: `ictlab/features.py` (pattern detection), `ictlab/context.py` "
        "(multi-timeframe conditions and filters), `ictlab/simulate.py` (trade simulation), "
        "`ictlab/combos.py` (search), `scripts/rule_search.py` (holdout test). Raw results: "
        "`results/rule_search/<ASSET>_selection.json`.\n")
    OUT.write_text("".join(L))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
