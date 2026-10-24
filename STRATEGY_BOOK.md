# STRATEGY BOOK - ICT multi-timeframe confluence research

This single file is written so that a person or another AI can understand the whole study without reading code. It states what was tested, how each rule is defined, which rule was selected for each asset, and how that rule performed on data that was locked away during the search.

## 1. Summary

| asset | selected rule (robust #1) | entry | stop | RR | mgmt | search trades | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% | holdout 1 unit @2% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ | M:ANYB \| H4:ANYB \| H1:FVG | market | atr1.5 | 4.000 | trail2atr | 262 | 0.334 | 31 | -0.147 | 0.953 | 0.904 |
| SPX | D:MB \| F:BIAS_D \| H1:OB | market | zone+0.25atr | 3.500 | none | 136 | 0.600 | 25 | -0.265 | 0.932 | 0.861 |
| XAU | D:MB \| F:BIAS_W \| H1:OB | limit_ce | atr2.0 | 4.000 | trail2atr | 393 | 0.218 | 48 | 0.006 | 1.000 | 0.994 |
| XAG | W:BB \| H4:MB \| H1:ANYB | limit_ce | atr1.0 | 1.000 | none | 227 | 0.294 | 20 | 0.188 | 1.037 | 1.072 |
| BTC | H4:MB \| H4:MSB \| F:BIAS_W \| H1:MB | market | zone+0.5atr | 6.000 | be1r | 231 | 0.451 | 60 | -0.047 | 0.962 | 0.907 |
| ETH | H4:OB \| H4:MSB \| H1:BB | market | atr1.5 | 6.000 | be1r | 183 | 0.604 | 60 | -0.065 | 0.952 | 0.887 |

Holdout = the last 2 years of each asset's data. It was not used for the search, the walk-forward or the selection. '1 unit @1%' = what 1 unit of capital became over the holdout when each trade risks 1 % of current equity (compounded, costs included).

**Bottom line.** The selected rule (robust #1) was positive in the locked holdout on 2 of 6 assets. Across all 30 robust candidates, 18 were positive and the average holdout result was -0.002 R/trade. Search-period results were much better than holdout results, which means most of the search-period edge was selection luck (overfitting). No rule in this book is a proven edge; the candidates that stayed positive in the holdout are a watch list for paper trading.

**Türkçe özet.** Seçilen kural (robust #1) kilitli son 2 yılda pozitif kalan varlık sayısı: 2/6. Pozitif kalan robust aday sayısı: 18/30; ortalama sonuç -0.002 R/işlem. Arama dönemindeki güçlü sonuçlar ileriye taşınmadı. Bu kitaptaki hiçbir kural kanıtlanmış bir avantaj değildir; kilitli dönemde pozitif kalanlar yalnızca kâğıt üzerinde izlenecek adaylardır.

## 2. How to read the numbers

- **R**: profit or loss in units of the initial risk. +2R = won twice the risked amount; -1R = stopped out. Every R value already subtracts round-trip costs.
- **R/trade**: average R per trade (expectancy). Above 0 = profitable before sizing.
- **Search period**: data before the holdout. Inside it, the first 70 % is in-sample (IS) and the last 30 % is out-of-sample (OOS).
- **t**: t-statistic of the mean R. With tens of thousands of combinations tested, luck alone produces t of about 4; values below that are not significant on their own.
- **1 unit @x%**: compounded growth of 1 unit when each trade risks x % of equity.

## 3. Data

| asset | instrument | source | first bar | last bar | holdout from | 1h bars | round-trip cost (bps) |
|---|---|---|---|---|---|---|---|
| NQ | Nasdaq 100 (CFD) | Dukascopy USATECHIDXUSD 1h | 2012-01-19 | 2026-10-23 | 2024-10-23 | 74842 | 2.000 |
| SPX | S&P 500 (CFD) | Dukascopy USA500IDXUSD 1h | 2017-01-03 | 2026-10-23 | 2024-10-23 | 55064 | 2.000 |
| XAU | Gold spot | Dukascopy XAUUSD 1h | 2012-01-01 | 2026-10-23 | 2024-10-23 | 88288 | 3.000 |
| XAG | Silver spot | Dukascopy XAGUSD 1h | 2007-01-01 | 2026-10-23 | 2024-10-23 | 93373 | 8.000 |
| BTC | Bitcoin / USDT | Binance spot BTCUSDT 1h | 2017-08-17 | 2026-10-22 | 2024-10-22 | 80241 | 10.000 |
| ETH | Ether / USDT | Binance spot ETHUSDT 1h | 2017-08-17 | 2026-10-22 | 2024-10-22 | 80241 | 10.000 |

Higher timeframes are built from the 1h bars. Trading day starts 18:00 New York time for NQ, SPX, XAU and XAG (CME-style session) and 00:00 UTC for crypto. Weeks start on the trading Monday. A higher-timeframe candle is used only after it has closed; the forming candle is never used.

## 4. Definitions of every building block

All patterns are detected on every timeframe (1M, 1W, 1D, 4H, 1H) with the same code. A zone is *active* from the close of the candle that confirms it until a candle closes beyond its far edge, or until it is too old (36 months, 104 weeks, 250 days, 360 4h candles).

| Code | Name | Exact rule (bullish; bearish is the mirror) |
|---|---|---|
| FVG | Fair value gap | low[i] > high[i-2] and the gap is at least 0.1 x ATR(14). Zone = [high[i-2], low[i]]. |
| OB | Order block | A candle closes above the last confirmed swing high (swing = fractal with 2 candles on each side). The last down-close candle of the up-leg is the OB; zone = its high-low range. |
| BB | Breaker block | At such a break: the last up-close candle at the swing high that was broken, when the decline after that high swept below the previous swing low. |
| MB | Mitigation block | Same as BB, but the decline did not take the previous swing low (higher low, failure swing). |
| RB | Rejection block | A confirmed swing low whose lower wick is at least 50 % of the candle range. Zone = from the low to the lower end of the body. |
| PB | Propulsion block | An order block whose candle trades into an older, still active order block of the same direction. |
| VB | Vacuum block | The open is at least 0.25 x ATR above the previous close (gap). Zone = [previous close, open]. |
| ANYB | Any block | Any of OB, BB, MB, RB, PB, VB. |
| FVG+X | FVG inside block | On that timeframe an FVG and a block X both overlap the 1h entry zone. |
| M:LIQ | Monthly liquidity sweep | Price traded below the previous month's low (long) within the last 22 trading days and the current 1h close is back above it. |
| H4:MSB | 4H market structure break | Latest 4h close beyond the last swing points in the trade direction and is at most 42 4h candles old. |
| BIAS_D | Daily trend filter | the last closed daily candle closed on the trade side of its 50-day EMA. |
| BIAS_W | Weekly structure filter | the most recent weekly market structure break points in the trade direction. |
| KZ | Killzone filter | the entry hour is inside a killzone (02:00-05:00 or 07:00-11:00 New York time). |
| PD | Premium / discount filter | the zone sits in discount (long) or premium (short) of the previous week's range. |

**Execution grid tested for every combination** (3 x 10 x 9 x 3 = 810 settings):

- Entry: market at the zone's completion, limit at the near edge, limit at 50 % (CE).
- Stop: zone edge (+0 / 0.1 / 0.25 / 0.5 ATR), 1 / 1.5 / 2 / 3 ATR from entry, last swing + 0.1 ATR, pattern extreme + 0.1 ATR.
- Target: 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6 R.
- Management: none, break-even at +1R, 2-ATR trailing stop after +1R.
- Conservative simulation: if stop and target are both touched in one candle the stop counts; no target on the candle that fills a limit order; gaps fill at the open; trades close after 120 hours at the latest.

## 5. How the rules were searched and selected

1. Each higher timeframe (M, W, D, H4) gets one choice: nothing, one zone type, any block, or FVG inside a block. Add the M:LIQ and H4:MSB flags, one rule filter (none, BIAS_D, BIAS_W, KZ, PD, BIAS_D+KZ) and a 1h entry type. Every combination with at least 30 trades was tested (about 60 000-90 000 per asset), each with all 810 execution settings.
2. An anchored 5-fold walk-forward tested whether picking the best combination on past data works on the next period.
3. Two selection rules were applied to the search period only:
   - **robust**: positive in-sample *and* out-of-sample, neighbouring RR settings also positive, at least 30 OOS trades; ranked by the weaker of the IS and OOS t-statistics.
   - **best_t**: the highest whole-period t-statistic (the naive choice, shown for comparison).
4. The last 2 years (holdout) were opened once, and the selected rules were replayed on them unchanged.

## 6. Asset by asset

### 6.1 NQ - Nasdaq 100 (CFD)

Search: 57,178 distinct combinations x 810 settings. Walk-forward of the selection process: 2225 trades, 0.002 R/trade, 3/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.007.

**Selected rule (robust #1): `M:ANYB | H4:ANYB | H1:FVG` | market | atr1.5 | RR 4 | trail2atr**

1. Wait for a new 1h fair value gap (FVG) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active monthly block of any type of the same direction; the 1h entry zone overlaps an active 4-hour block of any type of the same direction.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: 1.5 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 4R from the entry.
6. Management: once price reaches +1R, trail the stop 2 x ATR behind the best price (never below entry).
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 262 | 0.334 | 0.362 | 0.307 | 3.392 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 31 | 29.032 | -0.147 | -4.571 | 0.953 | 7.406 | 0.904 | 14.362 |
| whole data | 293 |  | 0.283 | 82.816 | 2.207 | 11.904 | 4.540 | 22.515 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**

Long trades 0.330 R/trade, short trades 0.188 R/trade, longest losing streak 10.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2013 | 22 | 0.718 | 15.793 | 0.500 |
| 2015 | 18 | 0.350 | 6.295 | 0.444 |
| 2016 | 26 | 0.384 | 9.986 | 0.462 |
| 2018 | 24 | 0.358 | 8.594 | 0.417 |
| 2019 | 28 | 0.176 | 4.921 | 0.321 |
| 2020 | 7 | -0.046 | -0.325 | 0.286 |
| 2022 | 67 | 0.453 | 30.348 | 0.507 |
| 2023 | 70 | 0.168 | 11.775 | 0.457 |
| 2025 | 31 | -0.147 | -4.571 | 0.290 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 44 | 0.329 | 0.523 |
| london | 43 | -0.034 | 0.349 |
| ny_am | 34 | 0.294 | 0.500 |
| ny_pm | 45 | 0.112 | 0.333 |
| other | 127 | 0.431 | 0.449 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | H1:ANY | limit_ce | atr3.0 | 3.500 | trail2atr | 0.090 | 409 | 0.006 | 0.995 |
| 3 | H4:MB \| F:BIAS_W \| H1:ANYB | market | atr1.0 | 6.000 | trail2atr | 0.198 | 245 | -0.017 | 0.935 |
| 4 | W:BB \| F:BIAS_W \| H1:FVG | market | atr1.5 | 1.500 | none | 0.437 | 52 | 0.081 | 1.039 |
| 5 | H4:OB \| F:BIAS_W \| H1:RB | market | atr2.0 | 6.000 | trail2atr | 0.202 | 116 | 0.156 | 1.187 |

**For comparison: naive best-t rule: `D:OB | M:LIQ | H1:MB` | market | atr1.0 | RR 2.5 | trail2atr**

1. Wait for a new 1h mitigation block (MB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active daily order block (OB) of the same direction; price swept the previous month's low (long) / high (short) within the last ~22 trading days and the 1h close is back on the other side.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: 1.0 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 2.5R from the entry.
6. Management: once price reaches +1R, trail the stop 2 x ATR behind the best price (never below entry).
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 136 | 0.497 | 0.623 | 0.122 | 3.735 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 22 | 22.727 | -0.142 | -3.120 | 0.967 | 6.405 | 0.933 | 12.461 |
| whole data | 158 |  | 0.408 | 64.535 | 1.870 | 8.484 | 3.364 | 16.325 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**


### 6.2 SPX - S&P 500 (CFD)

Search: 43,458 distinct combinations x 810 settings. Walk-forward of the selection process: 5526 trades, -0.014 R/trade, 2/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.055.

**Selected rule (robust #1): `D:MB | F:BIAS_D | H1:OB` | market | zone+0.25atr | RR 3.5 | none**

1. Wait for a new 1h order block (OB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active daily mitigation block (MB) of the same direction; the last closed daily candle closed on the trade side of its 50-day EMA.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: at the far edge of the 1h entry zone plus 0.25 x ATR. 1R = distance from entry to stop.
5. Target: 3.5R from the entry.
6. Management: no management: the trade ends at the stop, the target, or after 120 hours.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 136 | 0.600 | 0.485 | 0.907 | 3.361 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 25 | 20.000 | -0.265 | -6.624 | 0.932 | 13.275 | 0.861 | 25.052 |
| whole data | 161 |  | 0.465 | 74.914 | 2.041 | 13.275 | 3.891 | 25.052 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**

Long trades 0.654 R/trade, short trades 0.020 R/trade, longest losing streak 11.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 12 | -0.749 | -8.990 | 0.083 |
| 2018 | 12 | 0.630 | 7.557 | 0.417 |
| 2019 | 18 | 0.441 | 7.939 | 0.389 |
| 2020 | 21 | 0.443 | 9.296 | 0.381 |
| 2021 | 16 | 0.750 | 12.003 | 0.438 |
| 2022 | 20 | 1.009 | 20.172 | 0.500 |
| 2023 | 23 | 0.477 | 10.965 | 0.348 |
| 2024 | 17 | 1.668 | 28.361 | 0.647 |
| 2025 | 7 | -0.432 | -3.024 | 0.143 |
| 2026 | 15 | -0.624 | -9.364 | 0.133 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 24 | 0.206 | 0.292 |
| london | 27 | 0.668 | 0.407 |
| ny_am | 31 | 0.552 | 0.387 |
| ny_pm | 25 | 0.492 | 0.360 |
| other | 54 | 0.417 | 0.389 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | D:MB \| F:BIAS_D \| H1:FVG | market | pattern+0.1atr | 3.000 | none | 0.574 | 32 | 0.075 | 1.019 |
| 3 | H4:FVG+MB \| H4:MSB \| F:BIAS_W \| H1:RB | market | atr2.0 | 3.500 | trail2atr | 0.434 | 46 | -0.074 | 0.964 |
| 4 | H4:MSB \| F:KZ \| H1:PB | market | atr1.5 | 5.000 | be1r | 0.525 | 50 | 0.034 | 1.008 |
| 5 | H4:FVG+ANYB \| H1:RB | market | atr3.0 | 3.500 | trail2atr | 0.156 | 163 | 0.015 | 1.016 |

**For comparison: naive best-t rule: `H4:MB | F:BIAS_D | H1:MB` | market | zone+0.1atr | RR 6 | none**

1. Wait for a new 1h mitigation block (MB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active 4-hour mitigation block (MB) of the same direction; the last closed daily candle closed on the trade side of its 50-day EMA.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: at the far edge of the 1h entry zone plus 0.1 x ATR. 1R = distance from entry to stop.
5. Target: 6R from the entry.
6. Management: no management: the trade ends at the stop, the target, or after 120 hours.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 205 | 0.912 | 1.114 | 0.435 | 4.503 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 67 | 20.896 | -0.137 | -9.211 | 0.898 | 17.632 | 0.782 | 33.482 |
| whole data | 272 |  | 0.653 | 177.713 | 5.313 | 17.632 | 23.084 | 33.482 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**


### 6.3 XAU - Gold spot

Search: 83,390 distinct combinations x 810 settings. Walk-forward of the selection process: 1735 trades, 0.019 R/trade, 3/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.032.

**Selected rule (robust #1): `D:MB | F:BIAS_W | H1:OB` | limit_ce | atr2.0 | RR 4 | trail2atr**

1. Wait for a new 1h order block (OB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active daily mitigation block (MB) of the same direction; the most recent weekly market structure break points in the trade direction.
3. Entry: place a limit order at the 50 % level of the zone, the consequent encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge).
4. Stop: 2.0 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 4R from the entry.
6. Management: once price reaches +1R, trail the stop 2 x ATR behind the best price (never below entry).
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 393 | 0.218 | 0.179 | 0.320 | 2.976 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 48 | 54.167 | 0.006 | 0.304 | 1.000 | 5.066 | 0.994 | 9.942 |
| whole data | 441 |  | 0.195 | 86.098 | 2.262 | 10.181 | 4.687 | 19.648 |

Verdict: **POSITIVE in the locked holdout and in the search out-of-sample period. Still a single candidate among many tested: treat as a watch-list rule, confirm with live paper trading before risking capital.**

Long trades 0.259 R/trade, short trades 0.109 R/trade, longest losing streak 5.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2012 | 36 | -0.022 | -0.805 | 0.583 |
| 2013 | 24 | 0.156 | 3.745 | 0.458 |
| 2014 | 42 | 0.212 | 8.909 | 0.548 |
| 2015 | 32 | 0.623 | 19.940 | 0.625 |
| 2016 | 40 | 0.012 | 0.473 | 0.500 |
| 2017 | 37 | 0.125 | 4.625 | 0.514 |
| 2018 | 28 | -0.037 | -1.039 | 0.500 |
| 2019 | 19 | 0.173 | 3.281 | 0.474 |
| 2020 | 25 | 0.459 | 11.484 | 0.600 |
| 2021 | 25 | 0.239 | 5.986 | 0.480 |
| 2022 | 31 | 0.180 | 5.576 | 0.613 |
| 2023 | 28 | 0.332 | 9.298 | 0.464 |
| 2024 | 29 | 0.428 | 12.404 | 0.621 |
| 2025 | 14 | 0.057 | 0.796 | 0.571 |
| 2026 | 31 | 0.046 | 1.426 | 0.548 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 61 | 0.192 | 0.607 |
| london | 74 | 0.211 | 0.554 |
| ny_am | 136 | 0.287 | 0.529 |
| ny_pm | 26 | -0.148 | 0.385 |
| other | 144 | 0.164 | 0.549 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | D:FVG+ANYB \| H4:FVG \| H1:ANYB | limit_ce | atr2.0 | 6.000 | none | 0.479 | 20 | -0.721 | 0.865 |
| 3 | D:FVG+ANYB \| F:BIAS_W \| H1:OB | limit_ce | atr3.0 | 2.500 | be1r | 0.366 | 13 | -0.223 | 0.971 |
| 4 | W:ANYB \| D:ANYB \| M:LIQ \| F:PD \| H1:MB | market | atr3.0 | 1.000 | be1r | 0.301 | 14 | 0.117 | 1.016 |
| 5 | D:MB \| F:BIAS_W \| H1:ANY | limit_ce | atr1.5 | 3.000 | none | 0.197 | 96 | -0.050 | 0.940 |

**For comparison: naive best-t rule: `D:FVG+ANYB | H4:FVG+MB | H1:ANY` | limit_ce | atr3.0 | RR 3 | be1r**

1. Wait for a new 1h ANY to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active daily FVG that overlaps a block of any type (FVG inside the block area) of the same direction; the 1h entry zone overlaps an active 4-hour FVG that overlaps a mitigation block (MB) (FVG inside the block area) of the same direction.
3. Entry: place a limit order at the 50 % level of the zone, the consequent encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge).
4. Stop: 3.0 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 3R from the entry.
6. Management: move the stop to the entry price once price reaches +1R.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 125 | 0.622 | 0.599 | 0.697 | 4.086 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 9 | 22.222 | -0.242 | -2.182 | 0.978 | 3.069 | 0.954 | 6.093 |
| whole data | 134 |  | 0.564 | 75.582 | 2.085 | 5.192 | 4.176 | 10.166 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**


### 6.4 XAG - Silver spot

Search: 195,949 distinct combinations x 810 settings. Walk-forward of the selection process: 58 trades, -0.661 R/trade, 1/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.009.

**Selected rule (robust #1): `W:BB | H4:MB | H1:ANYB` | limit_ce | atr1.0 | RR 1 | none**

1. Wait for a new 1h block of any type to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active weekly breaker block (BB) of the same direction; the 1h entry zone overlaps an active 4-hour mitigation block (MB) of the same direction.
3. Entry: place a limit order at the 50 % level of the zone, the consequent encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge).
4. Stop: 1.0 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 1R from the entry.
6. Management: no management: the trade ends at the stop, the target, or after 120 hours.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 227 | 0.294 | 0.270 | 0.371 | 3.647 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 20 | 60.000 | 0.188 | 3.757 | 1.037 | 2.419 | 1.072 | 4.885 |
| whole data | 247 |  | 0.285 | 70.515 | 1.986 | 10.129 | 3.800 | 19.643 |

Verdict: **POSITIVE in the locked holdout and in the search out-of-sample period. Still a single candidate among many tested: treat as a watch-list rule, confirm with live paper trading before risking capital.**

Long trades 0.304 R/trade, short trades 0.233 R/trade, longest losing streak 3.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2007 | 11 | 0.413 | 4.538 | 0.727 |
| 2009 | 20 | 0.445 | 8.900 | 0.700 |
| 2010 | 68 | 0.310 | 21.061 | 0.676 |
| 2014 | 12 | 0.195 | 2.344 | 0.750 |
| 2015 | 9 | 0.375 | 3.373 | 0.778 |
| 2016 | 2 | -1.725 | -3.451 | 0.000 |
| 2017 | 13 | 0.027 | 0.353 | 0.615 |
| 2018 | 13 | -0.475 | -6.174 | 0.385 |
| 2019 | 24 | 0.643 | 15.431 | 0.750 |
| 2020 | 10 | -0.015 | -0.150 | 0.600 |
| 2021 | 43 | 0.437 | 18.809 | 0.744 |
| 2024 | 14 | 0.190 | 2.657 | 0.571 |
| 2025 | 8 | 0.353 | 2.823 | 0.750 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 35 | 0.091 | 0.657 |
| london | 37 | -0.034 | 0.568 |
| ny_am | 37 | 0.049 | 0.568 |
| ny_pm | 30 | 0.796 | 0.767 |
| other | 108 | 0.397 | 0.731 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | W:ANYB \| H4:MB \| H4:MSB \| F:PD \| H1:ANY | limit_ce | atr1.5 | 1.000 | trail2atr | 0.238 | 26 | 0.226 | 1.059 |
| 3 | D:ANYB \| H4:VB \| H4:MSB \| H1:RB | limit_ce | atr1.0 | 1.000 | none | 0.225 | 10 | 0.127 | 1.012 |
| 4 | W:BB \| H4:MB \| H1:ANY | limit_ce | atr1.0 | 1.000 | be1r | 0.265 | 23 | 0.103 | 1.022 |
| 5 | W:BB \| H4:MB \| F:BIAS_W \| H1:ANYB | limit_ce | zone+0.5atr | 1.000 | be1r | 0.277 | 13 | -0.010 | 0.998 |

**For comparison: naive best-t rule: `D:OB | H4:VB | H1:RB` | limit_ce | zone+0.5atr | RR 1 | none**

1. Wait for a new 1h rejection block (RB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active daily order block (OB) of the same direction; the 1h entry zone overlaps an active 4-hour vacuum block (VB) of the same direction.
3. Entry: place a limit order at the 50 % level of the zone, the consequent encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge).
4. Stop: at the far edge of the 1h entry zone plus 0.5 x ATR. 1R = distance from entry to stop.
5. Target: 1R from the entry.
6. Management: no management: the trade ends at the stop, the target, or after 120 hours.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 378 | 0.321 | 0.345 | 0.070 | 5.673 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 9 | 55.556 | 0.005 | 0.048 | 1.000 | 1.761 | 0.999 | 3.559 |
| whole data | 387 |  | 0.313 | 121.260 | 3.279 | 21.269 | 10.240 | 38.789 |

Verdict: **POSITIVE in the locked holdout and in the search out-of-sample period. Still a single candidate among many tested: treat as a watch-list rule, confirm with live paper trading before risking capital.**


### 6.5 BTC - Bitcoin / USDT

Search: 69,890 distinct combinations x 810 settings. Walk-forward of the selection process: 4812 trades, 0.021 R/trade, 3/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.042.

**Selected rule (robust #1): `H4:MB | H4:MSB | F:BIAS_W | H1:MB` | market | zone+0.5atr | RR 6 | be1r**

1. Wait for a new 1h mitigation block (MB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active 4-hour mitigation block (MB) of the same direction; the latest 4-hour market structure break (close beyond the last swing) points in the trade direction and is at most 42 4h candles old; the most recent weekly market structure break points in the trade direction.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: at the far edge of the 1h entry zone plus 0.5 x ATR. 1R = distance from entry to stop.
5. Target: 6R from the entry.
6. Management: move the stop to the entry price once price reaches +1R.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 231 | 0.451 | 0.381 | 0.680 | 2.934 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 60 | 11.667 | -0.047 | -2.791 | 0.962 | 22.118 | 0.907 | 39.545 |
| whole data | 291 |  | 0.349 | 101.421 | 2.561 | 22.118 | 5.705 | 39.545 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**

Long trades 0.426 R/trade, short trades 0.236 R/trade, longest losing streak 23.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 9 | 0.746 | 6.716 | 0.222 |
| 2018 | 42 | 0.254 | 10.685 | 0.214 |
| 2019 | 31 | 0.547 | 16.967 | 0.226 |
| 2020 | 44 | 0.127 | 5.574 | 0.182 |
| 2021 | 28 | 0.911 | 25.499 | 0.286 |
| 2022 | 32 | -0.007 | -0.229 | 0.094 |
| 2023 | 31 | 0.063 | 1.963 | 0.129 |
| 2024 | 23 | 2.053 | 47.222 | 0.478 |
| 2025 | 30 | -0.104 | -3.112 | 0.100 |
| 2026 | 21 | -0.470 | -9.864 | 0.048 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 53 | 0.309 | 0.189 |
| london | 47 | 0.439 | 0.191 |
| ny_am | 41 | 0.094 | 0.195 |
| ny_pm | 32 | 0.456 | 0.219 |
| other | 118 | 0.390 | 0.186 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | H4:FVG+OB \| H4:MSB \| H1:OB | market | zone | 3.500 | none | 0.491 | 43 | 0.099 | 1.036 |
| 3 | D:ANYB \| H4:MB \| H4:MSB \| H1:MB | market | atr2.0 | 6.000 | be1r | 0.550 | 37 | 0.222 | 1.077 |
| 4 | H4:ANYB \| H1:FVG | market | atr3.0 | 6.000 | none | 0.217 | 203 | -0.018 | 0.933 |
| 5 | H4:ANYB \| H4:MSB \| F:BIAS_W \| H1:MB | market | zone+0.5atr | 6.000 | be1r | 0.331 | 93 | -0.167 | 0.844 |

**For comparison: naive best-t rule: `F:BIAS_D | H1:ANY` | limit_ce | atr2.0 | RR 4 | none**

1. Wait for a new 1h ANY to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the last closed daily candle closed on the trade side of its 50-day EMA.
3. Entry: place a limit order at the 50 % level of the zone, the consequent encroachment (valid 24 hours; cancelled if a candle closes beyond the far edge).
4. Stop: 2.0 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 4R from the entry.
6. Management: no management: the trade ends at the stop, the target, or after 120 hours.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 1162 | 0.201 | 0.277 | 0.037 | 3.391 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 375 | 26.133 | 0.019 | 7.310 | 1.002 | 41.495 | 0.873 | 67.360 |
| whole data | 1537 |  | 0.155 | 238.493 | 8.000 | 41.495 | 35.487 | 67.360 |

Verdict: **POSITIVE in the locked holdout and in the search out-of-sample period. Still a single candidate among many tested: treat as a watch-list rule, confirm with live paper trading before risking capital.**


### 6.6 ETH - Ether / USDT

Search: 38,236 distinct combinations x 810 settings. Walk-forward of the selection process: 7740 trades, 0.030 R/trade, 3/5 folds positive. In-sample vs out-of-sample correlation of all combinations: 0.063.

**Selected rule (robust #1): `H4:OB | H4:MSB | H1:BB` | market | atr1.5 | RR 6 | be1r**

1. Wait for a new 1h breaker block (BB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the 1h entry zone overlaps an active 4-hour order block (OB) of the same direction; the latest 4-hour market structure break (close beyond the last swing) points in the trade direction and is at most 42 4h candles old.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: 1.5 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 6R from the entry.
6. Management: move the stop to the entry price once price reaches +1R.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 183 | 0.604 | 0.533 | 0.717 | 3.257 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 60 | 11.667 | -0.065 | -3.885 | 0.952 | 14.057 | 0.887 | 26.256 |
| whole data | 243 |  | 0.439 | 106.582 | 2.709 | 14.057 | 6.445 | 26.256 |

Verdict: **NEGATIVE in the locked holdout. The historical edge did not persist.**

Long trades 0.323 R/trade, short trades 0.548 R/trade, longest losing streak 25.

By year (whole data):

| entry_time | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 6 | 1.078 | 6.469 | 0.333 |
| 2018 | 20 | 0.893 | 17.867 | 0.250 |
| 2019 | 12 | 0.253 | 3.039 | 0.167 |
| 2020 | 23 | -0.225 | -5.172 | 0.087 |
| 2021 | 29 | 0.366 | 10.602 | 0.172 |
| 2022 | 36 | 0.599 | 21.570 | 0.167 |
| 2023 | 26 | 1.417 | 36.851 | 0.308 |
| 2024 | 35 | 0.626 | 21.898 | 0.200 |
| 2025 | 37 | -0.063 | -2.335 | 0.108 |
| 2026 | 19 | -0.222 | -4.209 | 0.105 |

By killzone of entry:

| session | n | exp | wr |
|---|---|---|---|
| asia | 37 | -0.078 | 0.108 |
| london | 24 | 0.040 | 0.083 |
| ny_am | 26 | 1.012 | 0.308 |
| ny_pm | 32 | -0.036 | 0.125 |
| other | 124 | 0.672 | 0.202 |

Other robust candidates (ranks 2-5):

| rank | combo | entry | stop | RR | mgmt | search R/trade | holdout trades | holdout R/trade | holdout 1 unit @1% |
|---|---|---|---|---|---|---|---|---|---|
| 2 | H1:OB | market | atr3.0 | 5.000 | be1r | 0.203 | 304 | 0.060 | 1.152 |
| 3 | F:KZ \| H1:MB | market | atr3.0 | 6.000 | none | 0.318 | 178 | 0.076 | 1.107 |
| 4 | H4:ANYB \| H4:MSB \| F:BIAS_D \| H1:BB | market | atr1.5 | 6.000 | be1r | 0.582 | 59 | 0.058 | 1.022 |
| 5 | H4:ANYB \| F:KZ \| H1:ANY | market | atr3.0 | 5.000 | none | 0.269 | 190 | 0.107 | 1.188 |

**For comparison: naive best-t rule: `H4:MSB | F:BIAS_D | H1:BB` | market | atr1.5 | RR 6 | be1r**

1. Wait for a new 1h breaker block (BB) to complete. Its direction (bullish/bearish) is the trade direction.
2. Take it only if all of these are true at that candle's close: the latest 4-hour market structure break (close beyond the last swing) points in the trade direction and is at most 42 4h candles old; the last closed daily candle closed on the trade side of its 50-day EMA.
3. Entry: enter at the close of the 1h candle that completes the zone.
4. Stop: 1.5 x ATR(14, 1h) away from the entry price. 1R = distance from entry to stop.
5. Target: 6R from the entry.
6. Management: move the stop to the entry price once price reaches +1R.
7. One position at a time; a new setup is ignored while a trade is open.

| period | trades | R/trade | IS R/trade | OOS R/trade | t |
|---|---|---|---|---|---|
| search (pre-holdout) | 389 | 0.572 | 0.625 | 0.463 | 4.438 |

| period | trades | win % | R/trade | total R | 1 unit @1% | max DD @1% (%) | 1 unit @2% | max DD @2% (%) |
|---|---|---|---|---|---|---|---|---|
| locked holdout | 126 | 12.698 | 0.064 | 8.088 | 1.057 | 14.219 | 1.066 | 26.838 |
| whole data | 515 |  | 0.448 | 230.725 | 8.624 | 14.219 | 55.865 | 26.838 |

Verdict: **POSITIVE in the locked holdout and in the search out-of-sample period. Still a single candidate among many tested: treat as a watch-list rule, confirm with live paper trading before risking capital.**

## 7. High win-rate study (scripts/winrate_search.py)

Question: which combinations have the highest win rate, and can the right stop and RR turn them into profit? Method, using pre-holdout data only:

1. Score every combination by its win rate on a symmetric reference trade (market entry, stop 1 x ATR, target 1 x ATR). A symmetric bracket measures directional skill independent of RR. Rank by the lower 5 % bound of the in-sample win rate (Beta posterior), minimum 60 trades.
2. For the top 20, test every entry x stop x RR (0.5-6) x management setting and keep the one with the best in-sample expectancy lower bound.
3. Open the locked 2-year holdout once.

**Is win rate a real, persistent property of a combination?**

| asset | combos scored | base win rate | observed sd | pure-noise sd | implied true-skill sd | top-20 WR in-sample | top-20 WR out-of-sample | top-20 WR holdout |
|---|---|---|---|---|---|---|---|---|
| NQ | 11867 | 0.501 | 0.053 | 0.049 | 0.021 | 0.628 | 0.410 | 0.452 |
| SPX | 5353 | 0.498 | 0.055 | 0.049 | 0.024 | 0.628 | 0.462 | 0.518 |
| XAU | 17136 | 0.494 | 0.050 | 0.049 | 0.011 | 0.635 | 0.532 | 0.609 |
| XAG | 45667 | 0.476 | 0.050 | 0.049 | 0.008 | 0.651 | 0.508 | 0.492 |
| BTC | 14578 | 0.472 | 0.047 | 0.049 | 0.000 | 0.608 | 0.396 | 0.483 |
| ETH | 7174 | 0.491 | 0.049 | 0.047 | 0.012 | 0.629 | 0.462 | 0.489 |

Reading: the spread of win rates across combinations is almost exactly what pure chance produces (observed sd ~ noise sd). True differences in win rate between combinations are at most about 2 percentage points. The combinations that showed 60-65 % in-sample fall back to roughly the base rate (about 40-53 % out-of-sample, 45-61 % in the holdout).

**Did the best stop/RR make the top-20 profitable in the holdout?**

| asset | rules positive / tested | rules with >=10 holdout trades | of those positive | mean R/trade (>=10 trades) |
|---|---|---|---|---|
| NQ | 5/20 | 16 | 4 | -0.139 |
| SPX | 7/20 | 20 | 7 | -0.036 |
| XAU | 12/20 | 10 | 4 | -0.091 |
| XAG | 12/20 | 11 | 5 | 0.011 |
| BTC | 7/20 | 20 | 7 | -0.037 |
| ETH | 2/20 | 20 | 2 | -0.206 |

Positive results in the holdout come mostly from rules with very few trades (1-5) and large RR, so they are not evidence. XAU and XAG rose 47 % and 60 % in the holdout, which favours long trades.

**Single conditions: which ones move the win rate?** (all triggers, reference trade, average over the six assets; lift = win rate with the condition minus the base rate)

| factor | lift_is | lift_oos | lift_holdout | holdout_trades |
|---|---|---|---|---|
| BIAS_D | 0.012 | -0.001 | 0.014 | 20295 |
| W_MB | -0.012 | -0.003 | 0.014 | 3539 |
| H4_PB | -0.001 | 0.015 | 0.013 | 1925 |
| H4_MSB | 0.007 | -0.002 | 0.009 | 20457 |
| H1_BB | -0.006 | -0.011 | 0.009 | 2466 |
| H4_OB | 0.005 | -0.000 | 0.007 | 7170 |
| W_FVG | 0.001 | -0.004 | -0.019 | 4582 |
| M_BB | -0.014 | 0.011 | -0.022 | 1376 |
| D_RB | -0.005 | 0.001 | -0.023 | 3650 |
| M_FVG | -0.008 | -0.004 | -0.027 | 3167 |
| D_PB | -0.015 | -0.005 | -0.042 | 1567 |
| W_BB | 0.025 | -0.016 | -0.106 | 1513 |

No single condition changes the win rate by more than about 1-2 percentage points in a way that holds in-sample, out-of-sample and in the holdout. 1h order blocks as entries are slightly worse than average in all three periods.

**Conclusion of the win-rate study:** none of the tested ICT conditions or their combinations produces a persistently high win rate on these six markets at 1h entry resolution. High in-sample win rates are selection luck. Choosing stop and RR afterwards cannot create an edge that the entry does not have.

**Türkçe özet:** Test edilen ICT koşulları ve kombinasyonları, bu altı piyasada 1 saatlik girişle kalıcı olarak yüksek bir kazanma oranı üretmiyor. Örneklem içinde %60-65 görünen oranlar şans eseri seçilmiş. Sonradan doğru stop ve RR seçmek, girişte olmayan bir avantajı yaratamaz.

## 8. Overall conclusion and limits

All candidates (5 per method per asset) in the locked holdout:

| method | rules | positive_in_holdout | mean_holdout_R |
|---|---|---|---|
| best_t | 30 | 14 | -0.023 |
| robust | 30 | 18 | -0.002 |

- These are historical simulations. Fills, spreads and slippage in live trading can be worse.
- Thousands of combinations were tested; some will look good by chance. The holdout test is the main protection; a rule that is positive in the holdout still needs live paper trading before real money.
- Index and metal data are CFD prices (Dukascopy), not exchange futures.
- Reproduce: `python -m ictlab fetch --assets all --source dukascopy` (NQ/SPX/XAU/XAG) and `--source github` (BTC/ETH), then `PYTHONPATH=. python3 scripts/rule_search.py NQ SPX XAU XAG BTC ETH` and `PYTHONPATH=. python3 scripts/build_strategy_book.py`.
- Code map: `ictlab/features.py` (pattern detection), `ictlab/context.py` (multi-timeframe conditions and filters), `ictlab/simulate.py` (trade simulation), `ictlab/combos.py` (search), `scripts/rule_search.py` (holdout test). Raw results: `results/rule_search/<ASSET>_selection.json`.
