# ICT Multi-Timeframe Confluence Research Report
## 1. Method
- Base data: 1h OHLC. 4H / D / W / M bars are built from it with a session-aware calendar (18:00 New York rollover for CME-type markets, 00:00 UTC for crypto).
- A higher-timeframe bar is visible only after its last 1h bar closes (no lookahead).
- Conditions: M_LIQ (previous-month high/low swept and reclaimed), M/W/D/H4 FVG and order block zones that overlap the 1h entry zone in the trade direction, H4_MSB (latest 4H structure break in the trade direction, fresh).
- Entry: every 1h FVG and 1h order block is a trigger. Entry modes: market (trigger close), limit at zone edge, limit at consequent encroachment (50 %).
- Stops (10): zone, zone+0.1atr, zone+0.25atr, zone+0.5atr, atr1.0, atr1.5, atr2.0, atr3.0, swing+0.1atr, pattern+0.1atr.
- RR grid: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0; management: none or break-even at +1R.
- Conservative fills: stop wins a same-bar stop/target tie, no target on a limit fill bar, gaps fill at the open, round-trip costs per asset.
- One position at a time per strategy, accepted in fill order.
- Validation: IS = first 70 %, OOS = last 30 %. Ranking uses IS only. Score = empirical-Bayes shrunk expectancy minus 1.645 posterior SD. Deflated Sharpe uses the full trial count. Anchored walk-forward re-selects the top 10 combos per fold. Placebo = the same pipeline on block-permuted copies of the asset (structure destroyed).
## 2. Data coverage
| asset | bars | start | end | triggers | combos | trials |
|---|---|---|---|---|---|---|
| XAU | 57600 | 2012-05-17 | 2022-03-04 | 13801 | 477 | 257580 |

Not tested in this run (no data reachable):
- **NQ**: no cached data; run `python -m ictlab fetch` first
- **SPX**: no cached data; run `python -m ictlab fetch` first
- **XAG**: no cached data; run `python -m ictlab fetch` first
- **BTC**: no cached data; run `python -m ictlab fetch` first
- **ETH**: no cached data; run `python -m ictlab fetch` first

## 3.1 XAU
Trials: 257,580. Deflated-Sharpe hurdle (per-trade SR0): 2.141. Grid mean expectancy: -0.065 R.

**Top 15 combos (ranked on IS score, best config per combo)**

| combo | entry | stop | rr | mgmt | n_is | exp_is | wr_is | exp_shrunk | score | n_oos | exp_oos | wr_oos | pf_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D_OB+H4_MSB+H1_OB | market | atr3.0 | 1.000 | be1r | 101 | 0.319 | 0.673 | 0.128 | 0.013 | 41 | -0.053 | 0.488 | 0.899 | 0.128 | 4.777 |
| H4_FVG+H1_ANY | limit_ce | atr1.5 | 3.000 | none | 651 | 0.214 | 0.327 | 0.107 | 0.008 | 272 | 0.019 | 0.272 | 1.024 | 0.108 | 19.464 |
| H1_OB | market | atr3.0 | 2.500 | none | 703 | 0.150 | 0.373 | 0.087 | 0.002 | 296 | -0.042 | 0.331 | 0.938 | 0.054 | 28.290 |
| H4_MSB+H1_FVG | limit_edge | pattern+0.1atr | 3.500 | none | 974 | 0.152 | 0.301 | 0.084 | -0.003 | 410 | 0.049 | 0.266 | 1.063 | 0.083 | 32.491 |
| H4_MSB+H1_ANY | limit_ce | zone+0.5atr | 4.000 | be1r | 2278 | 0.077 | 0.171 | 0.055 | -0.004 | 995 | 0.044 | 0.162 | 1.074 | 0.050 | 63.414 |
| H1_ANY | limit_edge | atr3.0 | 3.500 | none | 630 | 0.175 | 0.359 | 0.088 | -0.006 | 284 | -0.067 | 0.285 | 0.904 | 0.047 | 29.634 |
| H4_FVG+H1_FVG | limit_edge | atr3.0 | 1.500 | none | 354 | 0.159 | 0.483 | 0.081 | -0.011 | 139 | -0.018 | 0.410 | 0.969 | 0.059 | 22.709 |
| H4_MSB+H1_OB | limit_ce | atr2.0 | 2.500 | be1r | 865 | 0.099 | 0.251 | 0.061 | -0.011 | 363 | -0.049 | 0.201 | 0.910 | 0.002 | 32.942 |
| D_OB+H4_MSB+H1_ANY | limit_ce | atr1.5 | 1.000 | none | 164 | 0.215 | 0.622 | 0.093 | -0.013 | 86 | -0.136 | 0.453 | 0.765 | 0.000 | 18.132 |
| H1_FVG | limit_edge | atr3.0 | 3.000 | none | 630 | 0.150 | 0.365 | 0.078 | -0.013 | 276 | 0.086 | 0.351 | 1.133 | 0.126 | 17.075 |
| H4_FVG+H1_OB | limit_ce | atr2.0 | 1.500 | be1r | 543 | 0.099 | 0.401 | 0.059 | -0.016 | 216 | -0.005 | 0.356 | 0.990 | 0.033 | 18.866 |
| H4_FVG+H4_OB+H1_FVG | market | atr2.0 | 1.000 | none | 100 | 0.275 | 0.660 | 0.099 | -0.017 | 44 | -0.090 | 0.477 | 0.836 | 0.069 | 7.764 |
| W_OB+H4_MSB+H1_ANY | limit_ce | atr3.0 | 1.000 | none | 111 | 0.249 | 0.640 | 0.092 | -0.022 | 47 | 0.034 | 0.532 | 1.069 | 0.127 | 6.489 |
| H4_MSB+H4_FVG+H1_ANY | limit_edge | swing+0.1atr | 1.500 | be1r | 484 | 0.104 | 0.411 | 0.056 | -0.024 | 173 | -0.129 | 0.324 | 0.774 | 0.007 | 30.127 |
| D_FVG+H1_OB | limit_ce | atr2.0 | 2.500 | be1r | 353 | 0.183 | 0.272 | 0.078 | -0.025 | 113 | 0.094 | 0.239 | 1.191 | 0.113 | 15.849 |

**Marginal value of each condition (best config per combo)**

| condition | combos_with | median_score_with | median_score_without | median_oos_with | median_oos_without |
|---|---|---|---|---|---|
| M_LIQ | 149 | -0.175 | -0.164 | -0.009 | -0.069 |
| M_FVG | 47 | -0.200 | -0.163 | 0.014 | -0.051 |
| M_OB | 91 | -0.202 | -0.163 | -0.093 | -0.033 |
| W_FVG | 120 | -0.201 | -0.152 | -0.028 | -0.055 |
| W_OB | 109 | -0.174 | -0.164 | -0.072 | -0.035 |
| D_FVG | 125 | -0.182 | -0.163 | 0.051 | -0.064 |
| D_OB | 125 | -0.172 | -0.166 | -0.136 | -0.009 |
| H4_MSB | 141 | -0.166 | -0.171 | -0.058 | -0.036 |
| H4_FVG | 139 | -0.167 | -0.167 | -0.015 | -0.058 |
| H4_OB | 127 | -0.167 | -0.167 | -0.078 | -0.031 |

**Walk-forward selection test**: {'oos_trades': 4788, 'oos_exp': 0.019912718880047076, 'oos_total_r': 95.3420979976654, 'folds_positive': 1, 'folds_traded': 3, 'folds': 5}

**Real vs placebo**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|
| real | 4788 | 0.020 | 95.342 | 1 | 3 | 5 | 0.013 | -0.065 |
| placebo_1 | 2111 | 0.016 | 33.836 | 1 | 2 | 5 | 0.059 | -0.028 |
| placebo_2 | 1841 | 0.035 | 64.283 | 3 | 5 | 5 | 0.012 | -0.056 |
| placebo_3 | 62 | -0.059 | -3.657 | 0 | 1 | 5 | -0.029 | -0.095 |

**Detail: D_OB+H4_MSB+H1_OB | market | atr3.0 | RR 1.0 | be1r** - max DD 4.8 R, longest losing streak 4

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2012 | 8 | 0.220 | 1.762 | 0.625 |
| 2013 | 16 | 0.222 | 3.556 | 0.625 |
| 2014 | 13 | 0.047 | 0.614 | 0.538 |
| 2015 | 12 | 0.668 | 8.011 | 0.833 |
| 2016 | 12 | 0.639 | 7.670 | 0.833 |
| 2017 | 21 | 0.106 | 2.232 | 0.571 |
| 2018 | 14 | 0.544 | 7.612 | 0.786 |
| 2019 | 11 | -0.124 | -1.369 | 0.455 |
| 2020 | 12 | -0.026 | -0.316 | 0.500 |
| 2021 | 20 | -0.030 | -0.609 | 0.500 |
| 2022 | 3 | 0.298 | 0.893 | 0.667 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 37 | 0.231 | 0.622 |
| low_vol | 50 | 0.363 | 0.700 |
| mid_vol | 55 | 0.061 | 0.545 |

**Detail: H4_FVG+H1_ANY | limit_ce | atr1.5 | RR 3.0 | none** - max DD 19.5 R, longest losing streak 13

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2012 | 66 | 0.047 | 3.093 | 0.273 |
| 2013 | 102 | 0.254 | 25.877 | 0.333 |
| 2014 | 100 | 0.204 | 20.380 | 0.330 |
| 2015 | 98 | 0.252 | 24.696 | 0.337 |
| 2016 | 91 | 0.450 | 40.943 | 0.385 |
| 2017 | 99 | -0.075 | -7.443 | 0.253 |
| 2018 | 75 | 0.429 | 32.175 | 0.387 |
| 2019 | 88 | 0.085 | 7.495 | 0.295 |
| 2020 | 81 | -0.059 | -4.766 | 0.247 |
| 2021 | 104 | -0.013 | -1.372 | 0.269 |
| 2022 | 19 | 0.183 | 3.483 | 0.316 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 346 | 0.163 | 0.309 |
| low_vol | 282 | 0.306 | 0.351 |
| mid_vol | 295 | 0.006 | 0.275 |

**Detail: H1_OB | market | atr3.0 | RR 2.5 | none** - max DD 28.3 R, longest losing streak 18

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2012 | 63 | 0.175 | 11.003 | 0.381 |
| 2013 | 107 | -0.015 | -1.651 | 0.327 |
| 2014 | 101 | 0.334 | 33.709 | 0.416 |
| 2015 | 95 | 0.074 | 7.063 | 0.368 |
| 2016 | 101 | 0.050 | 5.041 | 0.356 |
| 2017 | 111 | 0.336 | 37.340 | 0.396 |
| 2018 | 99 | 0.074 | 7.277 | 0.364 |
| 2019 | 107 | -0.092 | -9.864 | 0.308 |
| 2020 | 96 | 0.202 | 19.361 | 0.385 |
| 2021 | 102 | -0.187 | -19.118 | 0.304 |
| 2022 | 17 | 0.176 | 2.984 | 0.412 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 365 | -0.039 | 0.353 |
| low_vol | 286 | 0.180 | 0.360 |
| mid_vol | 348 | 0.160 | 0.368 |

## 5. Knowledge base (self-improvement state)

| asset | kappa | forward_trades | realized_r | predicted_r | updated |
|---|---|---|---|---|---|
| XAU | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 07:40 |

## 6. Learning curve (`replay`: the system learns from its own forward results)

Each row: the system only saw data up to `as_of`, then its earlier recommendations were scored on bars it had not seen. `kappa` = share of the back-tested edge that survived forward; `pred_exp` = fused forecast, `fwd_exp` = realised forward expectancy (decayed).

| asset | as_of | new_fwd_trades | kappa | fwd_trades | fwd_exp | pred_exp | best |
|---|---|---|---|---|---|---|---|
| XAU | 2016-05-01 | 0 | 1.000 | 0.000 | 0.000 | 0.000 | H1_ANY |
| XAU | 2016-11-01 | 945 | 0.000 | 945.000 | -0.055 | 0.026 | H4_MSB+H1_ANY |
| XAU | 2017-05-01 | 977 | 0.000 | 1647.122 | -0.042 | 0.028 | H4_MSB+H1_ANY |
| XAU | 2017-11-01 | 947 | 0.000 | 2108.378 | -0.007 | 0.029 | H4_MSB+H1_ANY |
| XAU | 2018-05-01 | 858 | 0.068 | 2353.101 | -0.000 | 0.025 | H4_MSB+H1_ANY |
| XAU | 2018-11-01 | 1493 | 0.000 | 3152.161 | -0.059 | 0.020 | H1_ANY |
| XAU | 2019-05-01 | 1590 | 0.000 | 3825.273 | -0.047 | 0.017 | W_OB+D_FVG+D_OB+H1_OB |
| XAU | 2019-11-01 | 1368 | 0.000 | 4065.182 | -0.039 | 0.015 | W_OB+D_FVG+D_OB+H1_OB |
| XAU | 2020-05-01 | 1361 | 0.000 | 4238.249 | -0.017 | 0.013 | W_OB+D_FVG+D_OB+H1_OB |
| XAU | 2020-11-01 | 1300 | 0.000 | 4299.741 | -0.013 | 0.012 | W_OB+D_FVG+D_OB+H1_OB |
| XAU | 2021-05-01 | 1400 | 0.334 | 4443.264 | 0.003 | 0.011 | H4_MSB+H1_ANY |
| XAU | 2021-11-01 | 2212 | 0.721 | 5344.925 | 0.007 | 0.010 | H1_ANY |
