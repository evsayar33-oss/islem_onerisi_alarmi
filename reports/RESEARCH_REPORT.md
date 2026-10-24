# ICT Multi-Timeframe Confluence Research Report

## 1. Method

- Base data: 1h OHLC. 4H / D / W / M bars are built from it with a session-aware calendar (18:00 New York rollover for CME-type markets, 00:00 UTC for crypto). A higher-timeframe bar is visible only after its last 1h bar closes; the forming bar is dropped.
- Zone types on every timeframe: FVG (Fair value gap), OB (Order block), BB (Breaker block), MB (Mitigation block), RB (Rejection block), PB (Propulsion block), VB (Vacuum block).
- Slots: each of M / W / D / H4 takes one choice: none, one zone type, ANYB (any block), or FVG+<block> (an FVG and a block of that timeframe both overlap the 1h entry zone = FVG inside the block area). Flags: M:LIQ (previous-month high/low swept and reclaimed), H4:MSB (fresh 4H structure break in the trade direction). Entry: 1h FVG, any single block type, ANYB, or ANY.
- Exhaustive enumeration with pruning (a branch stops below the minimum trade count); combos that select identical triggers are evaluated once.
- Entry modes: market, limit at zone edge, limit at 50 % (CE). Stops (10): zone, zone+0.1atr, zone+0.25atr, zone+0.5atr, atr1.0, atr1.5, atr2.0, atr3.0, swing+0.1atr, pattern+0.1atr. RR: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0. Management: none or break-even at +1R.
- Conservative fills: stop wins same-bar ties, no target on a limit fill bar, gaps fill at the open, round-trip costs per asset; one position at a time, accepted in fill order.
- Validation: anchored 5-fold walk-forward of the selection process; shrinkage strength learned from walk-forward prediction error; t-stat hurdle for the number of distinct combos; placebo runs on block-permuted series.

## 2. Data coverage

| asset | bars | start | end | triggers | combos | trials |
|---|---|---|---|---|---|---|
| NQ | 92506 | 2005-01-02 | 2020-05-14 | 46595 | 18029 | 9735660 |
| SPX | 92537 | 2005-01-02 | 2020-05-14 | 45533 | 21709 | 11722860 |
| XAU | 87214 | 2006-03-19 | 2020-05-14 | 40712 | 30258 | 16339320 |
| XAG | 71973 | 2007-01-01 | 2023-03-31 | 39240 | 67564 | 36484560 |
| BTC | 80241 | 2017-08-17 | 2026-10-22 | 35336 | 35020 | 18910800 |
| ETH | 80241 | 2017-08-17 | 2026-10-22 | 36587 | 20252 | 10936080 |

## 3.1 NQ

**Validation**

- IS -> OOS persistence: corr +0.027, slope -0.01, learned tau^2 0.004, prediction-error reduction vs no skill +5.0%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 3764 trades, +0.002 R/trade (t = +0.08), 3/5 folds positive; best placebo -0.025 R/trade.
- Multiple-testing hurdle: t > 4.00 (18,029 distinct combos, 9,735,660 combo x config trials). Combos passing: **0**.
- Verdict: **WEAK SIGNAL** - some forward information, but not statistically reliable (walk-forward t < 2 or no combo clears the hurdle). Rows below are candidates to monitor, not to trade.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 3764 | 0.002 | 6.470 | 3 | 5 | 5 | 0.004 | 0.027 | -0.003 | 0.112 |
| placebo_1 | 2033 | -0.025 | -50.319 | 1 | 5 | 5 | 0.003 | 0.013 | -0.011 | 0.094 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M:MB \| H4:RB \| H1:ANYB | market | atr1.5 | 1.000 | be1r | 170 | 0.273 | 0.653 | 1.756 | 3.662 | 0.367 | 0.258 | 32 | 0.339 | 0.350 | 5.461 |
| H4:MB \| M:LIQ \| H1:BB | market | atr3.0 | 1.500 | be1r | 268 | 0.264 | 0.474 | 1.609 | 3.646 | 0.361 | 0.249 | 60 | 0.315 | 0.284 | 6.935 |
| H4:ANYB \| M:LIQ \| H1:BB | market | atr3.0 | 1.500 | be1r | 414 | 0.211 | 0.452 | 1.465 | 3.622 | 0.352 | 0.200 | 103 | 0.243 | 0.210 | 12.292 |
| M:MB \| D:FVG \| H4:ANYB \| H1:ANY | market | atr1.5 | 3.500 | be1r | 108 | 0.631 | 0.296 | 2.612 | 3.478 | 0.300 | 0.634 | 20 | 0.613 | 0.719 | 8.372 |
| D:FVG \| H4:ANYB \| M:LIQ \| H1:FVG | market | atr3.0 | 1.500 | none | 136 | 0.369 | 0.566 | 1.825 | 3.464 | 0.295 | 0.419 | 42 | 0.258 | 0.326 | 6.338 |
| M:ANYB \| D:FVG \| H4:ANYB \| H1:ANY | market | atr1.5 | 3.500 | be1r | 181 | 0.464 | 0.260 | 2.075 | 3.423 | 0.281 | 0.387 | 33 | 0.811 | 0.698 | 9.136 |
| H4:FVG+MB \| H4:MSB \| H1:MB | limit_edge | atr3.0 | 2.000 | none | 165 | 0.372 | 0.467 | 1.692 | 3.176 | 0.204 | 0.512 | 46 | 0.013 | 0.203 | 8.414 |
| M:ANYB \| D:FVG \| H4:FVG+ANYB \| H1:ANY | market | atr1.5 | 3.500 | be1r | 106 | 0.594 | 0.302 | 2.329 | 3.169 | 0.202 | 0.512 | 23 | 0.894 | 0.800 | 6.956 |
| D:ANYB \| H4:RB \| H4:MSB \| H1:FVG | market | atr2.0 | 1.500 | be1r | 106 | 0.363 | 0.519 | 1.916 | 3.158 | 0.199 | 0.404 | 30 | 0.259 | 0.281 | 4.111 |
| H4:FVG+OB \| H1:BB | market | pattern+0.1atr | 3.000 | none | 119 | 0.516 | 0.462 | 1.932 | 3.141 | 0.195 | 0.506 | 34 | 0.541 | 0.647 | 6.543 |
| M:ANYB \| D:FVG \| H4:FVG+ANYB \| H1:ANYB | market | atr1.0 | 5.000 | none | 101 | 0.857 | 0.327 | 2.183 | 3.074 | 0.176 | 0.745 | 20 | 1.312 | 1.189 | 9.377 |
| M:MB \| H4:RB \| H1:ANY | market | atr1.5 | 1.000 | none | 190 | 0.219 | 0.626 | 1.564 | 3.065 | 0.174 | 0.209 | 37 | 0.261 | 0.255 | 5.433 |
| H4:FVG+ANYB \| H1:BB | market | atr3.0 | 3.000 | none | 307 | 0.311 | 0.375 | 1.486 | 3.034 | 0.167 | 0.417 | 83 | 0.025 | 0.261 | 23.108 |
| M:ANYB \| D:FVG \| H4:ANYB \| H1:ANYB | market | atr1.5 | 3.500 | be1r | 172 | 0.412 | 0.244 | 1.955 | 3.024 | 0.164 | 0.315 | 28 | 0.909 | 0.719 | 9.870 |
| H4:OB \| M:LIQ \| H4:MSB \| H1:ANYB | limit_edge | atr3.0 | 4.000 | be1r | 318 | 0.297 | 0.242 | 1.630 | 2.987 | 0.155 | 0.277 | 83 | 0.351 | 0.403 | 13.982 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| ANYB | M:MB \| H4:RB \| H1:ANYB | market | atr1.5 | 1.000 | be1r | 170 | 0.273 | 3.662 | 0.339 |
| BB | H4:MB \| M:LIQ \| H1:BB | market | atr3.0 | 1.500 | be1r | 268 | 0.264 | 3.646 | 0.315 |
| ANY | M:MB \| D:FVG \| H4:ANYB \| H1:ANY | market | atr1.5 | 3.500 | be1r | 108 | 0.631 | 3.478 | 0.613 |
| FVG | D:FVG \| H4:ANYB \| M:LIQ \| H1:FVG | market | atr3.0 | 1.500 | none | 136 | 0.369 | 3.464 | 0.258 |
| MB | H4:FVG+MB \| H4:MSB \| H1:MB | limit_edge | atr3.0 | 2.000 | none | 165 | 0.372 | 3.176 | 0.013 |
| RB | D:FVG+BB \| H1:RB | market | zone+0.25atr | 2.500 | none | 161 | 0.363 | 2.708 | 0.264 |
| VB | M:LIQ \| H4:MSB \| H1:VB | market | atr3.0 | 2.000 | none | 173 | 0.292 | 2.619 | 0.098 |
| OB | D:FVG+ANYB \| M:LIQ \| H1:OB | market | atr3.0 | 2.500 | be1r | 134 | 0.344 | 2.613 | 0.210 |
| PB | M:LIQ \| H1:PB | market | atr3.0 | 2.500 | be1r | 523 | 0.148 | 2.446 | 0.068 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 1513 | 0.046 | M:MB \| D:FVG \| H4:ANYB \| H1:ANY | 3.478 | 0.631 | 0.613 |
| OB | Order block | 1071 | 0.036 | H4:FVG+OB \| H1:BB | 3.141 | 0.516 | 0.541 |
| BB | Breaker block | 382 | 0.062 | H4:MB \| M:LIQ \| H1:BB | 3.646 | 0.264 | 0.315 |
| MB | Mitigation block | 921 | 0.035 | M:MB \| H4:RB \| H1:ANYB | 3.662 | 0.273 | 0.339 |
| RB | Rejection block | 844 | 0.027 | M:MB \| H4:RB \| H1:ANYB | 3.662 | 0.273 | 0.339 |
| PB | Propulsion block | 171 | 0.033 | M:LIQ \| H1:PB | 2.446 | 0.148 | 0.068 |
| VB | Vacuum block | 43 | 0.050 | M:LIQ \| H4:MSB \| H1:VB | 2.619 | 0.292 | 0.098 |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+OB | 177 | 0.117 | 0.672 | 2643 |
| D | FVG+VB | 2 | 0.079 | 1.000 | 75 |
| D | OB | 837 | -0.007 | 0.491 | 22349 |
| D | ANYB | 1702 | -0.013 | 0.471 | 52697 |
| D | FVG+BB | 80 | -0.019 | 0.487 | 1710 |
| D | FVG+ANYB | 448 | -0.023 | 0.460 | 9850 |
| D | RB | 592 | -0.029 | 0.412 | 11115 |
| D | FVG+PB | 40 | -0.029 | 0.425 | 149 |
| D | FVG | 973 | -0.045 | 0.414 | 22922 |
| D | MB | 718 | -0.047 | 0.390 | 16684 |
| D | VB | 26 | -0.052 | 0.423 | 1198 |
| D | BB | 385 | -0.089 | 0.371 | 9534 |
| D | FVG+MB | 163 | -0.092 | 0.368 | 2735 |
| D | FVG+RB | 118 | -0.133 | 0.280 | 2273 |
| D | PB | 223 | -0.191 | 0.238 | 991 |
| H1 | VB | 105 | 0.074 | 0.619 | 2169 |
| H1 | FVG | 1040 | -0.019 | 0.459 | 30737 |
| H1 | ANY | 2786 | -0.025 | 0.435 | 97833 |
| H1 | MB | 543 | -0.027 | 0.444 | 16678 |
| H1 | OB | 1128 | -0.028 | 0.441 | 30655 |
| H1 | ANYB | 2352 | -0.030 | 0.424 | 77226 |
| H1 | PB | 450 | -0.045 | 0.389 | 9790 |
| H1 | BB | 332 | -0.055 | 0.437 | 8581 |
| H1 | RB | 1326 | -0.071 | 0.361 | 43021 |
| H4 | FVG+ANYB | 598 | 0.015 | 0.517 | 18239 |
| H4 | FVG+OB | 264 | 0.004 | 0.511 | 6943 |
| H4 | ANYB | 1685 | -0.017 | 0.456 | 54302 |
| H4 | FVG+RB | 251 | -0.021 | 0.442 | 5395 |
| H4 | FVG+VB | 16 | -0.026 | 0.438 | 605 |
| H4 | OB | 776 | -0.035 | 0.428 | 22703 |
| H4 | FVG+PB | 46 | -0.040 | 0.413 | 723 |
| H4 | BB | 452 | -0.041 | 0.409 | 12701 |
| H4 | RB | 731 | -0.044 | 0.406 | 18051 |
| H4 | FVG | 892 | -0.045 | 0.405 | 29916 |
| H4 | MB | 888 | -0.047 | 0.417 | 21159 |
| H4 | FVG+MB | 360 | -0.054 | 0.389 | 7944 |
| H4 | PB | 230 | -0.062 | 0.357 | 3719 |
| H4 | VB | 35 | -0.068 | 0.429 | 1753 |
| H4 | FVG+BB | 169 | -0.078 | 0.343 | 4307 |
| LIQ | True | 2245 | -0.023 | 0.454 | 59199 |
| M | OB | 398 | 0.051 | 0.578 | 10544 |
| M | MB | 660 | 0.045 | 0.548 | 13614 |
| M | ANYB | 1273 | 0.021 | 0.522 | 28265 |
| M | FVG+ANYB | 99 | 0.018 | 0.505 | 825 |
| M | RB | 319 | 0.008 | 0.498 | 4753 |
| M | FVG+MB | 60 | -0.013 | 0.450 | 285 |
| M | FVG+OB | 8 | -0.136 | 0.250 | 90 |
| M | FVG+RB | 6 | -0.159 | 0.167 | 57 |
| M | FVG | 677 | -0.190 | 0.287 | 3896 |
| M | BB | 130 | -0.389 | 0.138 | 971 |
| MSB | True | 2085 | -0.039 | 0.427 | 69395 |
| W | FVG+RB | 17 | 0.326 | 0.882 | 341 |
| W | VB | 12 | 0.161 | 0.917 | 351 |
| W | FVG+BB | 49 | -0.010 | 0.469 | 322 |
| W | ANYB | 1738 | -0.019 | 0.459 | 39804 |
| W | FVG+ANYB | 260 | -0.035 | 0.419 | 5150 |
| W | OB | 984 | -0.044 | 0.391 | 19889 |
| W | FVG | 791 | -0.078 | 0.338 | 16995 |
| W | RB | 442 | -0.078 | 0.351 | 9656 |
| W | MB | 528 | -0.084 | 0.335 | 14978 |
| W | FVG+OB | 89 | -0.111 | 0.382 | 1682 |
| W | BB | 175 | -0.127 | 0.337 | 2349 |
| W | FVG+MB | 72 | -0.138 | 0.264 | 1689 |
| W | PB | 35 | -0.173 | 0.229 | 461 |

**Detail: M:MB | H4:RB | H1:ANYB | market | atr1.5 | RR 1.0 | be1r** - max DD 5.5 R, longest losing streak 4, long/short +0.272 / +0.285 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2006 | 29 | 0.261 | 7.582 | 0.655 |
| 2008 | 29 | -0.067 | -1.930 | 0.483 |
| 2009 | 21 | 0.285 | 5.975 | 0.667 |
| 2012 | 30 | 0.292 | 8.765 | 0.667 |
| 2013 | 25 | 0.454 | 11.361 | 0.760 |
| 2015 | 13 | 0.503 | 6.544 | 0.769 |
| 2016 | 13 | 0.348 | 4.527 | 0.692 |
| 2018 | 10 | 0.361 | 3.611 | 0.600 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 85 | 0.119 | 0.565 |
| low_vol | 21 | 0.442 | 0.762 |
| mid_vol | 64 | 0.422 | 0.734 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 17 | 0.360 | 0.706 |
| london | 23 | -0.264 | 0.391 |
| ny_am | 19 | 0.418 | 0.737 |
| ny_pm | 33 | 0.351 | 0.667 |
| other | 78 | 0.345 | 0.692 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 56 | 0.273 | 0.643 |
| aligned (long in discount / short in premium) | 114 | 0.273 | 0.658 |

**Detail: H4:MB | M:LIQ | H1:BB | market | atr3.0 | RR 1.5 | be1r** - max DD 6.9 R, longest losing streak 8, long/short +0.358 / +0.186 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2005 | 21 | 0.300 | 6.290 | 0.476 |
| 2006 | 26 | 0.390 | 10.150 | 0.538 |
| 2007 | 26 | -0.069 | -1.800 | 0.308 |
| 2008 | 14 | 0.305 | 4.274 | 0.500 |
| 2009 | 16 | -0.172 | -2.750 | 0.312 |
| 2010 | 16 | 0.509 | 8.148 | 0.562 |
| 2011 | 16 | 0.509 | 8.146 | 0.562 |
| 2012 | 18 | 0.669 | 12.049 | 0.611 |
| 2013 | 16 | -0.222 | -3.552 | 0.250 |
| 2014 | 18 | 0.308 | 5.549 | 0.500 |
| 2015 | 27 | 0.246 | 6.633 | 0.481 |
| 2016 | 24 | 0.364 | 8.747 | 0.542 |
| 2017 | 11 | 0.104 | 1.140 | 0.455 |
| 2018 | 13 | 0.480 | 6.242 | 0.538 |
| 2019 | 4 | 0.855 | 3.421 | 0.750 |
| 2020 | 2 | -1.006 | -2.013 | 0.000 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 91 | 0.219 | 0.451 |
| low_vol | 70 | 0.087 | 0.400 |
| mid_vol | 107 | 0.417 | 0.542 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 7 | 0.400 | 0.571 |
| london | 32 | 0.313 | 0.438 |
| ny_am | 82 | 0.256 | 0.476 |
| ny_pm | 52 | 0.197 | 0.442 |
| other | 95 | 0.280 | 0.495 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 172 | 0.267 | 0.465 |
| aligned (long in discount / short in premium) | 96 | 0.257 | 0.490 |

**Detail: H4:ANYB | M:LIQ | H1:BB | market | atr3.0 | RR 1.5 | be1r** - max DD 12.3 R, longest losing streak 11, long/short +0.359 / +0.098 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2005 | 29 | 0.311 | 9.027 | 0.483 |
| 2006 | 35 | 0.168 | 5.874 | 0.457 |
| 2007 | 34 | 0.220 | 7.480 | 0.441 |
| 2008 | 25 | 0.064 | 1.604 | 0.400 |
| 2009 | 33 | 0.029 | 0.950 | 0.394 |
| 2010 | 20 | 0.253 | 5.064 | 0.450 |
| 2011 | 25 | 0.400 | 9.991 | 0.520 |
| 2012 | 27 | 0.420 | 11.330 | 0.519 |
| 2013 | 22 | -0.398 | -8.766 | 0.182 |
| 2014 | 32 | 0.379 | 12.142 | 0.531 |
| 2015 | 36 | 0.286 | 10.279 | 0.472 |
| 2016 | 34 | 0.397 | 13.498 | 0.559 |
| 2017 | 23 | -0.081 | -1.867 | 0.348 |
| 2018 | 20 | 0.665 | 13.293 | 0.650 |
| 2019 | 14 | -0.200 | -2.795 | 0.214 |
| 2020 | 5 | 0.011 | 0.055 | 0.400 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 155 | 0.208 | 0.445 |
| low_vol | 102 | 0.114 | 0.412 |
| mid_vol | 157 | 0.276 | 0.484 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 16 | 0.444 | 0.562 |
| london | 41 | 0.188 | 0.390 |
| ny_am | 119 | 0.234 | 0.479 |
| ny_pm | 85 | 0.094 | 0.388 |
| other | 153 | 0.238 | 0.471 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 238 | 0.250 | 0.458 |
| aligned (long in discount / short in premium) | 176 | 0.157 | 0.443 |

## 3.2 SPX

**Validation**

- IS -> OOS persistence: corr +0.013, slope -0.22, learned tau^2 0.0013, prediction-error reduction vs no skill +2.3%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 6004 trades, -0.062 R/trade (t = -3.91), 1/5 folds positive; best placebo -0.013 R/trade.
- Multiple-testing hurdle: t > 4.05 (21,709 distinct combos, 11,722,860 combo x config trials). Combos passing: **0**.
- Verdict: **NO EDGE** - in-sample ranking does not predict out-of-sample results. Rows below are the strongest *historical* records only.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 6004 | -0.062 | -374.088 | 1 | 5 | 5 | 0.001 | 0.013 | -0.029 | 0.072 |
| placebo_1 | 3860 | -0.013 | -49.604 | 1 | 5 | 5 | 0.001 | -0.032 | -0.059 | 0.091 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D:OB \| H4:ANYB \| H4:MSB \| H1:MB | limit_edge | pattern+0.1atr | 3.000 | none | 111 | 0.619 | 0.441 | 2.035 | 3.280 | 0.222 | 0.652 | 31 | 0.533 | 0.664 | 6.408 |
| W:BB \| H1:RB | limit_edge | atr1.5 | 4.000 | be1r | 174 | 0.454 | 0.241 | 1.956 | 3.021 | 0.153 | 0.435 | 42 | 0.512 | 0.397 | 9.201 |
| W:BB \| H1:ANY | limit_ce | atr3.0 | 3.000 | none | 148 | 0.439 | 0.419 | 1.742 | 2.930 | 0.132 | 0.463 | 38 | 0.373 | 0.273 | 8.980 |
| M:ANYB \| W:ANYB \| D:RB \| H1:FVG | limit_edge | atr1.0 | 1.500 | none | 108 | 0.370 | 0.556 | 1.785 | 2.921 | 0.130 | 0.332 | 27 | 0.485 | 0.466 | 5.447 |
| W:BB \| D:OB \| H1:ANYB | limit_ce | atr1.0 | 1.500 | none | 113 | 0.348 | 0.566 | 1.738 | 2.917 | 0.129 | 0.258 | 41 | 0.506 | 0.338 | 6.081 |
| D:ANYB \| H4:FVG+MB \| M:LIQ \| H1:ANY | limit_edge | atr3.0 | 6.000 | be1r | 105 | 0.612 | 0.295 | 2.381 | 2.907 | 0.127 | 0.531 | 32 | 0.796 | 0.828 | 18.798 |
| W:ANYB \| H4:ANYB \| M:LIQ \| H1:MB | market | atr1.5 | 5.000 | be1r | 143 | 0.569 | 0.224 | 2.101 | 2.884 | 0.123 | 0.525 | 36 | 0.700 | 0.643 | 8.517 |
| W:BB \| H4:ANYB \| H1:RB | market | atr1.5 | 5.000 | be1r | 148 | 0.549 | 0.209 | 2.125 | 2.884 | 0.123 | 0.530 | 33 | 0.615 | 0.607 | 10.176 |
| D:ANYB \| H4:FVG \| H4:MSB \| H1:OB | limit_edge | atr2.0 | 3.000 | none | 179 | 0.415 | 0.363 | 1.623 | 2.851 | 0.116 | 0.541 | 52 | 0.107 | 0.412 | 15.058 |
| W:BB \| H1:ANYB | limit_ce | atr3.0 | 3.000 | none | 132 | 0.454 | 0.424 | 1.780 | 2.850 | 0.116 | 0.527 | 35 | 0.253 | 0.280 | 7.292 |
| W:RB \| M:LIQ \| H1:FVG | limit_edge | atr1.0 | 2.000 | be1r | 177 | 0.290 | 0.390 | 1.632 | 2.836 | 0.113 | 0.276 | 51 | 0.326 | 0.264 | 8.625 |
| H4:MB \| M:LIQ \| H1:MB | market | atr2.0 | 5.000 | none | 309 | 0.394 | 0.278 | 1.520 | 2.835 | 0.113 | 0.441 | 89 | 0.281 | 0.564 | 27.902 |
| D:ANYB \| H4:FVG+MB \| H1:OB | limit_edge | atr1.5 | 4.000 | none | 220 | 0.436 | 0.300 | 1.585 | 2.814 | 0.109 | 0.545 | 58 | 0.132 | 0.370 | 16.980 |
| W:BB \| H4:ANYB \| H1:FVG | limit_ce | atr1.0 | 6.000 | be1r | 106 | 0.728 | 0.208 | 2.538 | 2.810 | 0.108 | 0.917 | 23 | 0.046 | 0.377 | 10.180 |
| W:BB \| D:OB \| H1:ANY | limit_ce | atr1.0 | 1.500 | none | 149 | 0.292 | 0.544 | 1.590 | 2.801 | 0.107 | 0.215 | 57 | 0.417 | 0.305 | 7.167 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| MB | D:OB \| H4:ANYB \| H4:MSB \| H1:MB | limit_edge | pattern+0.1atr | 3.000 | none | 111 | 0.619 | 3.280 | 0.533 |
| RB | W:BB \| H1:RB | limit_edge | atr1.5 | 4.000 | be1r | 174 | 0.454 | 3.021 | 0.512 |
| ANY | W:BB \| H1:ANY | limit_ce | atr3.0 | 3.000 | none | 148 | 0.439 | 2.930 | 0.373 |
| FVG | M:ANYB \| W:ANYB \| D:RB \| H1:FVG | limit_edge | atr1.0 | 1.500 | none | 108 | 0.370 | 2.921 | 0.485 |
| ANYB | W:BB \| D:OB \| H1:ANYB | limit_ce | atr1.0 | 1.500 | none | 113 | 0.348 | 2.917 | 0.506 |
| OB | D:ANYB \| H4:FVG \| H4:MSB \| H1:OB | limit_edge | atr2.0 | 3.000 | none | 179 | 0.415 | 2.851 | 0.107 |
| PB | H4:FVG \| M:LIQ \| H1:PB | limit_ce | atr1.0 | 6.000 | be1r | 107 | 0.727 | 2.738 | 0.334 |
| VB | M:LIQ \| H4:MSB \| H1:VB | limit_ce | atr2.0 | 1.500 | be1r | 151 | 0.249 | 2.567 | 0.096 |
| BB | H4:MB \| H1:BB | limit_ce | atr3.0 | 2.500 | none | 378 | 0.196 | 2.343 | 0.145 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 1658 | 0.035 | M:ANYB \| W:ANYB \| D:RB \| H1:FVG | 2.921 | 0.370 | 0.485 |
| OB | Order block | 1252 | 0.014 | D:OB \| H4:ANYB \| H4:MSB \| H1:MB | 3.280 | 0.619 | 0.533 |
| BB | Breaker block | 466 | 0.001 | W:BB \| H1:RB | 3.021 | 0.454 | 0.512 |
| MB | Mitigation block | 986 | 0.022 | D:OB \| H4:ANYB \| H4:MSB \| H1:MB | 3.280 | 0.619 | 0.533 |
| RB | Rejection block | 1011 | -0.007 | W:BB \| H1:RB | 3.021 | 0.454 | 0.512 |
| PB | Propulsion block | 235 | 0.024 | H4:FVG \| M:LIQ \| H1:PB | 2.738 | 0.727 | 0.334 |
| VB | Vacuum block | 74 | 0.045 | H4:VB \| H1:MB | 2.584 | 0.339 | 0.266 |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+BB | 95 | 0.008 | 0.505 | 1156 |
| D | FVG+RB | 80 | -0.006 | 0.487 | 2055 |
| D | FVG+PB | 33 | -0.024 | 0.424 | 454 |
| D | FVG+OB | 251 | -0.041 | 0.410 | 3625 |
| D | FVG+ANYB | 613 | -0.058 | 0.411 | 11260 |
| D | OB | 1039 | -0.105 | 0.307 | 29124 |
| D | MB | 1378 | -0.105 | 0.269 | 24496 |
| D | ANYB | 2255 | -0.126 | 0.258 | 63994 |
| D | FVG | 1012 | -0.135 | 0.277 | 28807 |
| D | RB | 660 | -0.140 | 0.283 | 13634 |
| D | VB | 112 | -0.141 | 0.286 | 2537 |
| D | FVG+MB | 355 | -0.143 | 0.279 | 4427 |
| D | BB | 539 | -0.160 | 0.282 | 8826 |
| D | PB | 277 | -0.181 | 0.227 | 4956 |
| D | FVG+VB | 12 | -0.292 | 0.333 | 184 |
| H1 | MB | 739 | -0.038 | 0.403 | 20611 |
| H1 | FVG | 1232 | -0.073 | 0.334 | 41530 |
| H1 | VB | 79 | -0.089 | 0.392 | 2559 |
| H1 | ANY | 3588 | -0.102 | 0.283 | 117841 |
| H1 | BB | 406 | -0.110 | 0.296 | 8085 |
| H1 | ANYB | 3044 | -0.114 | 0.279 | 90843 |
| H1 | OB | 1455 | -0.146 | 0.253 | 34923 |
| H1 | RB | 1790 | -0.159 | 0.245 | 49984 |
| H1 | PB | 564 | -0.190 | 0.261 | 10464 |
| H4 | FVG+PB | 37 | -0.037 | 0.378 | 802 |
| H4 | MB | 1207 | -0.060 | 0.340 | 27225 |
| H4 | FVG+VB | 41 | -0.079 | 0.390 | 918 |
| H4 | FVG+ANYB | 759 | -0.092 | 0.325 | 20613 |
| H4 | VB | 84 | -0.103 | 0.333 | 3215 |
| H4 | FVG | 1145 | -0.107 | 0.287 | 34242 |
| H4 | ANYB | 2229 | -0.111 | 0.276 | 64854 |
| H4 | FVG+MB | 415 | -0.112 | 0.292 | 8961 |
| H4 | OB | 1070 | -0.124 | 0.268 | 25034 |
| H4 | BB | 637 | -0.136 | 0.297 | 16239 |
| H4 | FVG+BB | 161 | -0.158 | 0.236 | 4192 |
| H4 | RB | 876 | -0.180 | 0.224 | 20276 |
| H4 | FVG+OB | 289 | -0.187 | 0.277 | 7503 |
| H4 | PB | 243 | -0.207 | 0.255 | 3640 |
| H4 | FVG+RB | 298 | -0.235 | 0.238 | 5713 |
| LIQ | True | 2838 | -0.092 | 0.321 | 60912 |
| M | FVG+RB | 74 | 0.090 | 0.473 | 447 |
| M | RB | 463 | -0.062 | 0.350 | 12189 |
| M | ANYB | 2132 | -0.062 | 0.382 | 42978 |
| M | OB | 77 | -0.091 | 0.273 | 4711 |
| M | BB | 97 | -0.127 | 0.186 | 3209 |
| M | PB | 9 | -0.167 | 0.222 | 83 |
| M | FVG | 865 | -0.230 | 0.234 | 7868 |
| M | MB | 1221 | -0.230 | 0.143 | 3463 |
| M | FVG+ANYB | 310 | -0.247 | 0.213 | 2171 |
| M | FVG+OB | 19 | -0.310 | 0.211 | 220 |
| M | FVG+MB | 155 |  | 0.000 | 0 |
| M | FVG+PB | 2 |  | 0.000 | 0 |
| MSB | True | 2874 | -0.140 | 0.251 | 87101 |
| W | FVG+PB | 2 | 0.133 | 1.000 | 52 |
| W | FVG+BB | 21 | 0.086 | 0.429 | 48 |
| W | BB | 324 | 0.085 | 0.509 | 3904 |
| W | PB | 95 | -0.005 | 0.432 | 2340 |
| W | OB | 1437 | -0.072 | 0.324 | 36736 |
| W | FVG+OB | 95 | -0.091 | 0.242 | 1068 |
| W | FVG | 532 | -0.096 | 0.336 | 14944 |
| W | VB | 61 | -0.107 | 0.426 | 739 |
| W | RB | 476 | -0.125 | 0.269 | 14486 |
| W | MB | 1444 | -0.126 | 0.292 | 15299 |
| W | ANYB | 2466 | -0.133 | 0.269 | 63254 |
| W | FVG+RB | 19 | -0.163 | 0.211 | 471 |
| W | FVG+ANYB | 316 | -0.238 | 0.199 | 3880 |
| W | FVG+MB | 119 | -0.289 | 0.160 | 849 |
| W | FVG+VB | 1 | -0.336 | 0.000 | 3 |

**Detail: D:OB | H4:ANYB | H4:MSB | H1:MB | limit_edge | pattern+0.1atr | RR 3.0 | none** - max DD 6.4 R, longest losing streak 5, long/short +0.628 / +0.606 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2005 | 6 | 0.850 | 5.098 | 0.500 |
| 2006 | 8 | 0.770 | 6.161 | 0.500 |
| 2007 | 4 | 1.888 | 7.552 | 0.750 |
| 2008 | 6 | -0.380 | -2.282 | 0.167 |
| 2009 | 8 | 0.610 | 4.881 | 0.500 |
| 2010 | 5 | 0.534 | 2.671 | 0.400 |
| 2011 | 4 | 0.947 | 3.786 | 0.500 |
| 2012 | 20 | 0.046 | 0.929 | 0.300 |
| 2013 | 4 | 0.774 | 3.098 | 0.500 |
| 2014 | 8 | 0.673 | 5.382 | 0.500 |
| 2015 | 8 | 1.731 | 13.846 | 0.625 |
| 2016 | 7 | 0.035 | 0.246 | 0.286 |
| 2017 | 6 | 0.659 | 3.955 | 0.500 |
| 2018 | 8 | 0.945 | 7.560 | 0.500 |
| 2019 | 7 | 0.652 | 4.564 | 0.429 |
| 2020 | 2 | 0.623 | 1.247 | 0.500 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 30 | 0.839 | 0.500 |
| low_vol | 38 | 0.734 | 0.474 |
| mid_vol | 43 | 0.364 | 0.372 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 17 | -0.133 | 0.235 |
| london | 25 | 1.255 | 0.600 |
| ny_am | 20 | 1.459 | 0.650 |
| ny_pm | 12 | 0.605 | 0.417 |
| other | 37 | 0.085 | 0.324 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 54 | 0.823 | 0.500 |
| aligned (long in discount / short in premium) | 57 | 0.426 | 0.386 |

**Detail: W:BB | H1:RB | limit_edge | atr1.5 | RR 4.0 | be1r** - max DD 9.2 R, longest losing streak 13, long/short +0.509 / +0.396 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2005 | 12 | 0.661 | 7.937 | 0.250 |
| 2006 | 11 | 0.577 | 6.348 | 0.273 |
| 2007 | 27 | 0.381 | 10.277 | 0.222 |
| 2008 | 14 | 1.024 | 14.339 | 0.357 |
| 2011 | 13 | 0.578 | 7.519 | 0.308 |
| 2012 | 15 | -0.261 | -3.909 | 0.067 |
| 2013 | 2 | -0.591 | -1.181 | 0.000 |
| 2014 | 27 | 0.269 | 7.272 | 0.222 |
| 2015 | 18 | 0.801 | 14.412 | 0.333 |
| 2016 | 28 | 0.585 | 16.375 | 0.250 |
| 2018 | 4 | 0.460 | 1.839 | 0.250 |
| 2019 | 1 | -1.284 | -1.284 | 0.000 |
| 2020 | 2 | -0.509 | -1.019 | 0.000 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 85 | 0.535 | 0.259 |
| low_vol | 23 | 0.387 | 0.217 |
| mid_vol | 66 | 0.372 | 0.227 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 23 | 0.270 | 0.217 |
| london | 16 | 0.250 | 0.188 |
| ny_am | 29 | 0.283 | 0.207 |
| ny_pm | 27 | 0.471 | 0.222 |
| other | 79 | 0.605 | 0.278 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 24 | 1.007 | 0.375 |
| aligned (long in discount / short in premium) | 150 | 0.365 | 0.220 |

**Detail: W:BB | H1:ANY | limit_ce | atr3.0 | RR 3.0 | none** - max DD 9.0 R, longest losing streak 5, long/short +0.596 / +0.283 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2005 | 8 | 0.809 | 6.476 | 0.500 |
| 2006 | 12 | 0.584 | 7.014 | 0.500 |
| 2007 | 26 | 0.269 | 6.993 | 0.385 |
| 2008 | 9 | 1.412 | 12.712 | 0.667 |
| 2011 | 10 | 0.982 | 9.816 | 0.500 |
| 2012 | 10 | -0.421 | -4.208 | 0.200 |
| 2013 | 2 | 0.954 | 1.907 | 0.500 |
| 2014 | 24 | 0.266 | 6.372 | 0.333 |
| 2015 | 17 | 0.739 | 12.569 | 0.529 |
| 2016 | 22 | 0.443 | 9.751 | 0.455 |
| 2018 | 4 | -1.017 | -4.069 | 0.000 |
| 2019 | 2 | 0.974 | 1.948 | 0.500 |
| 2020 | 2 | -1.119 | -2.238 | 0.000 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 65 | 0.362 | 0.415 |
| low_vol | 24 | 0.338 | 0.375 |
| mid_vol | 59 | 0.566 | 0.441 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 26 | 0.044 | 0.346 |
| london | 25 | 0.699 | 0.440 |
| ny_am | 25 | 0.372 | 0.400 |
| ny_pm | 12 | 0.569 | 0.417 |
| other | 60 | 0.505 | 0.450 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 17 | 0.634 | 0.471 |
| aligned (long in discount / short in premium) | 131 | 0.414 | 0.412 |

## 3.3 XAU

**Validation**

- IS -> OOS persistence: corr -0.004, slope -0.38, learned tau^2 1e-06, prediction-error reduction vs no skill -0.0%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 7654 trades, +0.013 R/trade (t = +0.86), 4/5 folds positive; best placebo -0.072 R/trade.
- Multiple-testing hurdle: t > 4.12 (30,258 distinct combos, 16,339,320 combo x config trials). Combos passing: **0**.
- Verdict: **WEAK SIGNAL** - some forward information, but not statistically reliable (walk-forward t < 2 or no combo clears the hurdle). Rows below are candidates to monitor, not to trade.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 7654 | 0.013 | 102.172 | 4 | 5 | 5 | 0.000 | -0.004 | -0.089 | 0.127 |
| placebo_1 | 1015 | -0.072 | -72.636 | 0 | 5 | 5 | 0.000 | 0.004 | -0.103 | 0.162 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D:FVG+ANYB \| H4:FVG+ANYB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | none | 110 | 0.324 | 0.682 | 1.979 | 3.630 | 0.311 | 0.313 | 33 | 0.349 | 0.355 | 4.117 |
| D:FVG+ANYB \| H4:MB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | be1r | 114 | 0.316 | 0.675 | 1.947 | 3.602 | 0.301 | 0.330 | 23 | 0.257 | 0.340 | 4.195 |
| H1:ANY | limit_ce | atr1.5 | 4.000 | be1r | 4224 | 0.094 | 0.161 | 1.179 | 3.554 | 0.285 | 0.123 | 1245 | 0.026 | 0.053 | 62.447 |
| M:ANYB \| H4:MB \| H1:MB | limit_ce | atr3.0 | 2.000 | none | 136 | 0.448 | 0.500 | 1.859 | 3.485 | 0.262 | 0.634 | 56 | 0.182 | 0.299 | 12.996 |
| D:FVG+ANYB \| H4:ANYB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | be1r | 184 | 0.245 | 0.641 | 1.661 | 3.465 | 0.255 | 0.202 | 53 | 0.351 | 0.322 | 6.066 |
| W:ANYB \| M:LIQ \| H1:BB | limit_edge | swing+0.1atr | 4.000 | none | 120 | 0.677 | 0.433 | 2.173 | 3.447 | 0.250 | 0.518 | 43 | 0.963 | 0.819 | 6.654 |
| M:ANYB \| H4:MB \| M:LIQ \| H1:ANYB | limit_edge | zone+0.25atr | 2.500 | none | 189 | 0.438 | 0.450 | 1.706 | 3.423 | 0.242 | 0.506 | 85 | 0.355 | 0.382 | 15.294 |
| D:FVG+ANYB \| H4:FVG+ANYB \| H4:MSB \| H1:ANYB | market | atr3.0 | 1.000 | none | 104 | 0.313 | 0.673 | 1.943 | 3.420 | 0.241 | 0.315 | 31 | 0.309 | 0.319 | 4.117 |
| D:FVG \| H4:FVG \| H1:BB | market | atr3.0 | 4.000 | none | 164 | 0.547 | 0.409 | 1.913 | 3.402 | 0.235 | 0.589 | 43 | 0.429 | 0.519 | 12.089 |
| D:FVG+ANYB \| H4:OB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | be1r | 131 | 0.277 | 0.656 | 1.785 | 3.344 | 0.218 | 0.236 | 41 | 0.368 | 0.371 | 4.434 |
| D:PB \| H4:FVG+ANYB \| H1:ANYB | market | atr3.0 | 1.500 | be1r | 129 | 0.330 | 0.488 | 1.877 | 3.267 | 0.196 | 0.298 | 46 | 0.387 | 0.431 | 4.086 |
| H4:MB \| M:LIQ \| H1:BB | limit_edge | atr3.0 | 2.000 | be1r | 167 | 0.334 | 0.389 | 1.814 | 3.255 | 0.193 | 0.403 | 43 | 0.133 | 0.228 | 6.766 |
| M:ANYB \| M:LIQ \| H4:MSB \| H1:ANY | limit_ce | atr2.0 | 1.500 | none | 261 | 0.252 | 0.525 | 1.499 | 3.246 | 0.190 | 0.293 | 131 | 0.210 | 0.228 | 7.849 |
| M:ANYB \| H4:MB \| M:LIQ \| H1:ANY | limit_edge | swing+0.1atr | 3.000 | none | 160 | 0.490 | 0.419 | 1.771 | 3.206 | 0.179 | 0.685 | 66 | 0.212 | 0.352 | 14.315 |
| D:ANYB \| H4:MB \| M:LIQ \| H1:RB | market | atr3.0 | 1.500 | none | 212 | 0.273 | 0.528 | 1.565 | 3.205 | 0.179 | 0.307 | 56 | 0.180 | 0.264 | 11.818 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| ANY | D:FVG+ANYB \| H4:FVG+ANYB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | be1r | 110 | 0.324 | 3.630 | 0.349 |
| MB | M:ANYB \| H4:MB \| H1:MB | limit_ce | atr3.0 | 2.000 | none | 136 | 0.448 | 3.485 | 0.182 |
| BB | W:ANYB \| M:LIQ \| H1:BB | limit_edge | swing+0.1atr | 4.000 | none | 120 | 0.677 | 3.447 | 0.963 |
| ANYB | M:ANYB \| H4:MB \| M:LIQ \| H1:ANYB | limit_edge | zone+0.25atr | 2.500 | none | 189 | 0.438 | 3.423 | 0.355 |
| RB | D:ANYB \| H4:MB \| M:LIQ \| H1:RB | market | atr3.0 | 1.500 | none | 212 | 0.273 | 3.205 | 0.180 |
| PB | H4:MB \| M:LIQ \| H1:PB | market | swing+0.1atr | 5.000 | none | 176 | 0.571 | 3.152 | 0.667 |
| OB | H4:ANYB \| M:LIQ \| H1:OB | market | swing+0.1atr | 5.000 | none | 506 | 0.298 | 3.082 | 0.258 |
| FVG | H1:FVG | limit_edge | atr3.0 | 4.000 | be1r | 1589 | 0.120 | 3.038 | 0.113 |
| VB | H4:ANYB \| H4:MSB \| H1:VB | market | atr1.0 | 6.000 | none | 142 | 0.719 | 2.752 | 1.570 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 2464 | 0.065 | D:FVG+ANYB \| H4:FVG+ANYB \| H4:MSB \| H1:ANY | 3.630 | 0.324 | 0.349 |
| OB | Order block | 1561 | 0.059 | D:FVG+ANYB \| H4:OB \| H4:MSB \| H1:ANY | 3.344 | 0.277 | 0.368 |
| BB | Breaker block | 609 | 0.039 | W:ANYB \| M:LIQ \| H1:BB | 3.447 | 0.677 | 0.963 |
| MB | Mitigation block | 1394 | 0.073 | D:FVG+ANYB \| H4:MB \| H4:MSB \| H1:ANY | 3.602 | 0.316 | 0.257 |
| RB | Rejection block | 1403 | 0.044 | D:ANYB \| H4:MB \| M:LIQ \| H1:RB | 3.205 | 0.273 | 0.180 |
| PB | Propulsion block | 326 | 0.071 | D:PB \| H4:FVG+ANYB \| H1:ANYB | 3.267 | 0.330 | 0.387 |
| VB | Vacuum block | 32 | 0.032 | H4:ANYB \| H4:MSB \| H1:VB | 2.752 | 0.719 | 1.570 |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+BB | 135 | 0.013 | 0.504 | 2064 |
| D | OB | 1350 | -0.026 | 0.454 | 38408 |
| D | PB | 393 | -0.055 | 0.402 | 11330 |
| D | RB | 912 | -0.058 | 0.406 | 23042 |
| D | FVG+ANYB | 825 | -0.071 | 0.366 | 22182 |
| D | ANYB | 2439 | -0.084 | 0.339 | 85788 |
| D | FVG+MB | 452 | -0.085 | 0.356 | 7746 |
| D | BB | 620 | -0.085 | 0.342 | 10270 |
| D | FVG+OB | 369 | -0.103 | 0.304 | 9906 |
| D | FVG | 1282 | -0.107 | 0.292 | 42066 |
| D | VB | 5 | -0.111 | 0.400 | 210 |
| D | FVG+RB | 260 | -0.118 | 0.354 | 5109 |
| D | MB | 1208 | -0.123 | 0.315 | 31746 |
| D | FVG+PB | 79 | -0.184 | 0.190 | 2426 |
| H1 | VB | 76 | -0.020 | 0.447 | 2370 |
| H1 | FVG | 1323 | -0.029 | 0.449 | 42671 |
| H1 | BB | 349 | -0.056 | 0.387 | 10943 |
| H1 | MB | 833 | -0.067 | 0.376 | 25930 |
| H1 | ANYB | 3396 | -0.073 | 0.351 | 125214 |
| H1 | ANY | 3996 | -0.074 | 0.362 | 158499 |
| H1 | PB | 490 | -0.080 | 0.367 | 12985 |
| H1 | RB | 2010 | -0.089 | 0.331 | 76296 |
| H1 | OB | 1431 | -0.101 | 0.327 | 45734 |
| H4 | FVG+PB | 70 | 0.109 | 0.729 | 1655 |
| H4 | FVG+RB | 340 | 0.030 | 0.524 | 8527 |
| H4 | PB | 377 | 0.005 | 0.493 | 8713 |
| H4 | FVG+BB | 181 | -0.025 | 0.464 | 4540 |
| H4 | FVG+OB | 373 | -0.027 | 0.440 | 11977 |
| H4 | FVG | 1238 | -0.029 | 0.426 | 43240 |
| H4 | FVG+ANYB | 859 | -0.038 | 0.432 | 28451 |
| H4 | VB | 34 | -0.048 | 0.441 | 912 |
| H4 | RB | 978 | -0.059 | 0.364 | 28819 |
| H4 | FVG+MB | 553 | -0.072 | 0.378 | 12749 |
| H4 | BB | 502 | -0.078 | 0.365 | 16650 |
| H4 | OB | 1201 | -0.084 | 0.351 | 40828 |
| H4 | ANYB | 2285 | -0.104 | 0.311 | 90704 |
| H4 | MB | 1480 | -0.116 | 0.324 | 38186 |
| H4 | FVG+VB | 9 | -0.307 | 0.222 | 192 |
| LIQ | True | 2836 | -0.039 | 0.422 | 79759 |
| M | FVG+RB | 9 | 0.066 | 0.556 | 31 |
| M | RB | 676 | -0.051 | 0.411 | 7163 |
| M | FVG+ANYB | 16 | -0.060 | 0.188 | 879 |
| M | FVG | 1182 | -0.081 | 0.368 | 17866 |
| M | OB | 488 | -0.118 | 0.289 | 19089 |
| M | ANYB | 1899 | -0.129 | 0.244 | 83941 |
| M | BB | 74 | -0.133 | 0.135 | 7209 |
| M | MB | 836 | -0.152 | 0.273 | 8502 |
| MSB | True | 2995 | -0.026 | 0.447 | 104749 |
| W | BB | 350 | -0.033 | 0.400 | 12653 |
| W | ANYB | 2469 | -0.036 | 0.431 | 89597 |
| W | FVG+BB | 48 | -0.057 | 0.292 | 1849 |
| W | RB | 822 | -0.098 | 0.331 | 22742 |
| W | OB | 1087 | -0.102 | 0.293 | 38189 |
| W | FVG | 1109 | -0.105 | 0.316 | 32365 |
| W | FVG+ANYB | 609 | -0.128 | 0.289 | 18060 |
| W | MB | 1140 | -0.157 | 0.275 | 27540 |
| W | PB | 3 | -0.182 | 0.000 | 269 |
| W | FVG+RB | 307 | -0.201 | 0.244 | 2822 |
| W | FVG+MB | 170 | -0.238 | 0.212 | 4500 |
| W | FVG+OB | 101 | -0.271 | 0.109 | 2489 |

**Detail: D:FVG+ANYB | H4:FVG+ANYB | H4:MSB | H1:ANY | market | atr3.0 | RR 1.0 | none** - max DD 4.1 R, longest losing streak 4, long/short +0.256 / +0.383 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2006 | 4 | -0.029 | -0.115 | 0.500 |
| 2007 | 2 | -0.037 | -0.073 | 0.500 |
| 2008 | 3 | 0.311 | 0.932 | 0.667 |
| 2009 | 10 | 0.173 | 1.733 | 0.600 |
| 2010 | 6 | 0.622 | 3.734 | 0.833 |
| 2011 | 14 | 0.242 | 3.388 | 0.643 |
| 2012 | 20 | 0.457 | 9.149 | 0.750 |
| 2013 | 12 | 0.300 | 3.601 | 0.667 |
| 2014 | 3 | -0.359 | -1.077 | 0.333 |
| 2015 | 3 | 0.950 | 2.850 | 1.000 |
| 2016 | 9 | 0.520 | 4.679 | 0.778 |
| 2017 | 10 | 0.151 | 1.506 | 0.600 |
| 2018 | 6 | 0.281 | 1.688 | 0.667 |
| 2019 | 4 | 0.442 | 1.767 | 0.750 |
| 2020 | 4 | 0.470 | 1.879 | 0.750 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 42 | 0.211 | 0.619 |
| low_vol | 28 | 0.154 | 0.607 |
| mid_vol | 40 | 0.561 | 0.800 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 13 | 0.660 | 0.846 |
| london | 9 | 0.286 | 0.667 |
| ny_am | 24 | 0.212 | 0.625 |
| ny_pm | 19 | 0.331 | 0.684 |
| other | 45 | 0.291 | 0.667 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 59 | 0.383 | 0.712 |
| aligned (long in discount / short in premium) | 51 | 0.255 | 0.647 |

**Detail: D:FVG+ANYB | H4:MB | H4:MSB | H1:ANY | market | atr3.0 | RR 1.0 | be1r** - max DD 4.2 R, longest losing streak 4, long/short +0.344 / +0.283 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2006 | 5 | -0.223 | -1.114 | 0.400 |
| 2007 | 1 | 0.953 | 0.953 | 1.000 |
| 2008 | 8 | -0.024 | -0.194 | 0.500 |
| 2009 | 12 | 0.803 | 9.636 | 0.917 |
| 2010 | 4 | 0.457 | 1.829 | 0.750 |
| 2011 | 15 | 0.155 | 2.320 | 0.600 |
| 2012 | 21 | 0.406 | 8.533 | 0.714 |
| 2013 | 14 | 0.111 | 1.559 | 0.571 |
| 2014 | 6 | 0.292 | 1.754 | 0.667 |
| 2015 | 5 | 0.960 | 4.800 | 1.000 |
| 2016 | 5 | -0.234 | -1.171 | 0.400 |
| 2017 | 7 | 0.385 | 2.692 | 0.714 |
| 2018 | 7 | 0.372 | 2.607 | 0.714 |
| 2019 | 3 | 0.271 | 0.813 | 0.667 |
| 2020 | 1 | 0.960 | 0.960 | 1.000 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 49 | 0.166 | 0.592 |
| low_vol | 28 | 0.154 | 0.607 |
| mid_vol | 37 | 0.636 | 0.838 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 15 | 0.829 | 0.933 |
| london | 10 | -0.053 | 0.500 |
| ny_am | 25 | 0.262 | 0.640 |
| ny_pm | 14 | 0.676 | 0.857 |
| other | 50 | 0.161 | 0.600 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 51 | 0.340 | 0.686 |
| aligned (long in discount / short in premium) | 63 | 0.296 | 0.667 |

**Detail: H1:ANY | limit_ce | atr1.5 | RR 4.0 | be1r** - max DD 62.4 R, longest losing streak 39, long/short +0.136 / +0.052 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2006 | 280 | 0.109 | 30.602 | 0.157 |
| 2007 | 296 | 0.112 | 33.142 | 0.159 |
| 2008 | 305 | 0.147 | 44.887 | 0.161 |
| 2009 | 293 | 0.075 | 21.926 | 0.143 |
| 2010 | 320 | 0.136 | 43.510 | 0.166 |
| 2011 | 368 | 0.129 | 47.633 | 0.163 |
| 2012 | 297 | 0.059 | 17.642 | 0.155 |
| 2013 | 264 | 0.295 | 77.829 | 0.205 |
| 2014 | 291 | 0.051 | 14.700 | 0.162 |
| 2015 | 284 | 0.140 | 39.747 | 0.169 |
| 2016 | 287 | 0.029 | 8.367 | 0.146 |
| 2017 | 257 | 0.161 | 41.415 | 0.183 |
| 2018 | 286 | -0.044 | -12.700 | 0.150 |
| 2019 | 301 | -0.055 | -16.598 | 0.143 |
| 2020 | 95 | 0.055 | 5.257 | 0.137 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 1693 | 0.044 | 0.143 |
| low_vol | 1081 | 0.183 | 0.188 |
| mid_vol | 1450 | 0.086 | 0.161 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 520 | 0.029 | 0.146 |
| london | 416 | -0.030 | 0.144 |
| ny_am | 775 | 0.200 | 0.186 |
| ny_pm | 595 | 0.100 | 0.160 |
| other | 1918 | 0.094 | 0.158 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 2291 | 0.170 | 0.172 |
| aligned (long in discount / short in premium) | 1933 | 0.005 | 0.147 |

## 3.4 XAG

**Validation**

- IS -> OOS persistence: corr -0.003, slope -0.08, learned tau^2 0.00063, prediction-error reduction vs no skill +1.0%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 82 trades, +0.084 R/trade (t = +0.60), 3/5 folds positive; best placebo +0.106 R/trade.
- Multiple-testing hurdle: t > 4.30 (67,564 distinct combos, 36,484,560 combo x config trials). Combos passing: **0**.
- Verdict: **NO EDGE** - in-sample ranking does not predict out-of-sample results. Rows below are the strongest *historical* records only.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 82 | 0.084 | 6.848 | 3 | 5 | 5 | 0.001 | -0.003 | -0.052 | 0.035 |
| placebo_1 | 569 | 0.106 | 60.546 | 5 | 5 | 5 | 0.020 | 0.080 | 0.420 | 0.019 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D:OB \| H4:VB \| H1:RB | limit_ce | zone+0.25atr | 1.000 | none | 404 | 0.326 | 0.710 | 1.855 | 5.333 | 0.848 | 0.402 | 63 | -0.081 | 0.011 | 39.611 |
| M:MB \| W:ANYB \| H4:ANYB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | none | 138 | 0.421 | 0.732 | 2.364 | 4.816 | 0.696 | 0.503 | 25 | 0.048 | 0.279 | 6.531 |
| M:MB \| D:ANYB \| H4:ANYB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | be1r | 134 | 0.388 | 0.739 | 2.299 | 4.808 | 0.693 | 0.456 | 23 | 0.057 | 0.214 | 5.097 |
| D:OB \| H4:VB \| H1:ANYB | limit_ce | zone+0.5atr | 1.000 | be1r | 862 | 0.192 | 0.646 | 1.424 | 4.662 | 0.640 | 0.258 | 173 | -0.068 | 0.010 | 56.023 |
| D:OB \| H4:VB \| H1:ANY | limit_ce | zone+0.5atr | 1.000 | none | 936 | 0.181 | 0.636 | 1.393 | 4.571 | 0.605 | 0.236 | 197 | -0.026 | 0.035 | 54.311 |
| D:MB \| H4:VB \| H1:RB | limit_ce | zone+0.25atr | 1.000 | be1r | 464 | 0.227 | 0.670 | 1.524 | 4.253 | 0.479 | 0.359 | 76 | -0.448 | -0.201 | 84.337 |
| H4:VB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | be1r | 1451 | 0.130 | 0.625 | 1.274 | 4.101 | 0.419 | 0.198 | 307 | -0.123 | -0.076 | 139.001 |
| M:MB \| D:ANYB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | none | 157 | 0.324 | 0.713 | 1.943 | 4.064 | 0.405 | 0.399 | 31 | 0.019 | 0.132 | 6.593 |
| D:ANYB \| H4:VB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | none | 927 | 0.162 | 0.632 | 1.354 | 4.042 | 0.396 | 0.232 | 204 | -0.085 | -0.033 | 83.882 |
| W:RB \| H4:VB \| H1:RB | limit_ce | zone+0.5atr | 1.000 | be1r | 206 | 0.316 | 0.704 | 1.875 | 3.999 | 0.380 | 0.365 | 32 | 0.048 | 0.146 | 7.686 |
| W:RB \| D:FVG+ANYB \| H4:RB \| H1:ANYB | limit_ce | atr1.0 | 1.000 | none | 100 | 0.393 | 0.730 | 2.286 | 3.994 | 0.378 | 0.386 | 26 | 0.413 | 0.368 | 5.611 |
| M:MB \| W:ANYB \| H4:ANYB \| H1:ANY | limit_ce | zone+0.5atr | 1.000 | none | 390 | 0.207 | 0.633 | 1.499 | 3.886 | 0.338 | 0.239 | 68 | 0.055 | 0.119 | 8.143 |
| W:RB \| H4:MB \| M:LIQ \| H4:MSB \| H1:ANY | limit_ce | zone+0.5atr | 1.000 | none | 186 | 0.350 | 0.715 | 2.019 | 3.870 | 0.332 | 0.241 | 30 | 0.915 | 0.452 | 3.965 |
| D:MB \| H4:PB \| H1:RB | limit_ce | zone+0.25atr | 1.000 | none | 204 | 0.280 | 0.691 | 1.742 | 3.855 | 0.327 | 0.319 | 27 | 0.026 | 0.055 | 26.089 |
| H4:PB \| M:LIQ \| H1:RB | limit_ce | zone+0.25atr | 1.500 | none | 185 | 0.370 | 0.616 | 1.766 | 3.854 | 0.326 | 0.419 | 24 | 0.044 | 0.052 | 24.300 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| RB | D:OB \| H4:VB \| H1:RB | limit_ce | zone+0.25atr | 1.000 | be1r | 404 | 0.326 | 5.333 | -0.081 |
| ANYB | D:OB \| H4:VB \| H1:ANYB | limit_ce | zone+0.5atr | 1.000 | be1r | 862 | 0.192 | 4.662 | -0.068 |
| ANY | D:OB \| H4:VB \| H1:ANY | limit_ce | zone+0.5atr | 1.000 | none | 936 | 0.181 | 4.571 | -0.026 |
| MB | M:ANYB \| H4:MB \| H1:MB | limit_ce | atr1.5 | 1.000 | be1r | 128 | 0.328 | 3.505 | 0.366 |
| OB | W:RB \| H4:VB \| H1:OB | limit_ce | zone+0.5atr | 1.000 | none | 108 | 0.432 | 3.358 | 0.297 |
| PB | W:ANYB \| D:OB \| H1:PB | limit_ce | atr2.0 | 1.000 | none | 117 | 0.314 | 3.316 | 0.245 |
| BB | W:RB \| H4:ANYB \| H1:BB | limit_ce | atr1.0 | 1.000 | none | 142 | 0.291 | 3.186 | 0.079 |
| VB | D:RB \| H4:RB \| H1:VB | limit_edge | atr2.0 | 2.000 | be1r | 157 | 0.355 | 3.149 | 0.001 |
| FVG | D:VB \| H4:MSB \| H1:FVG | limit_edge | atr3.0 | 5.000 | none | 122 | 0.564 | 2.605 | 0.990 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 4943 | -0.005 | W:RB \| D:FVG+ANYB \| H4:RB \| H1:ANYB | 3.994 | 0.393 | 0.413 |
| OB | Order block | 2345 | 0.009 | D:OB \| H4:VB \| H1:RB | 5.333 | 0.326 | -0.081 |
| BB | Breaker block | 777 | 0.041 | D:OB \| H4:BB \| M:LIQ \| H1:ANYB | 3.708 | 0.292 | 0.174 |
| MB | Mitigation block | 2106 | 0.039 | M:MB \| W:ANYB \| H4:ANYB \| H1:RB | 4.816 | 0.421 | 0.048 |
| RB | Rejection block | 2372 | 0.024 | D:OB \| H4:VB \| H1:RB | 5.333 | 0.326 | -0.081 |
| PB | Propulsion block | 296 | 0.027 | D:MB \| H4:PB \| H1:RB | 3.855 | 0.280 | 0.026 |
| VB | Vacuum block | 2319 | -0.016 | D:OB \| H4:VB \| H1:RB | 5.333 | 0.326 | -0.081 |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+MB | 578 | 0.093 | 0.597 | 9215 |
| D | MB | 1930 | -0.132 | 0.333 | 40259 |
| D | FVG+ANYB | 2594 | -0.132 | 0.315 | 53489 |
| D | FVG+PB | 135 | -0.136 | 0.237 | 603 |
| D | FVG | 3553 | -0.146 | 0.314 | 78671 |
| D | ANYB | 7076 | -0.149 | 0.288 | 175973 |
| D | FVG+VB | 1160 | -0.165 | 0.280 | 26268 |
| D | FVG+BB | 384 | -0.170 | 0.232 | 4755 |
| D | RB | 3585 | -0.192 | 0.261 | 53209 |
| D | OB | 1895 | -0.200 | 0.226 | 42399 |
| D | VB | 1956 | -0.207 | 0.237 | 52681 |
| D | BB | 2336 | -0.214 | 0.250 | 23526 |
| D | FVG+OB | 735 | -0.230 | 0.210 | 8526 |
| D | FVG+RB | 533 | -0.326 | 0.186 | 6678 |
| D | PB | 475 | -0.411 | 0.105 | 4849 |
| H1 | MB | 1702 | -0.110 | 0.336 | 42549 |
| H1 | BB | 822 | -0.122 | 0.307 | 18982 |
| H1 | FVG | 2799 | -0.142 | 0.301 | 82336 |
| H1 | ANY | 11245 | -0.146 | 0.284 | 302126 |
| H1 | RB | 4396 | -0.162 | 0.292 | 95913 |
| H1 | ANYB | 10284 | -0.178 | 0.255 | 254078 |
| H1 | PB | 998 | -0.192 | 0.271 | 15455 |
| H1 | OB | 3024 | -0.215 | 0.237 | 73846 |
| H1 | VB | 3310 | -0.217 | 0.266 | 53108 |
| H4 | FVG+MB | 1065 | 0.017 | 0.500 | 18169 |
| H4 | MB | 3500 | -0.059 | 0.375 | 52976 |
| H4 | FVG | 3531 | -0.130 | 0.316 | 95728 |
| H4 | FVG+ANYB | 2883 | -0.135 | 0.308 | 74551 |
| H4 | ANYB | 6356 | -0.172 | 0.249 | 165562 |
| H4 | FVG+OB | 922 | -0.174 | 0.271 | 21489 |
| H4 | FVG+VB | 1453 | -0.176 | 0.258 | 44324 |
| H4 | VB | 2852 | -0.187 | 0.258 | 69324 |
| H4 | FVG+BB | 446 | -0.198 | 0.220 | 8168 |
| H4 | OB | 2687 | -0.211 | 0.221 | 56372 |
| H4 | BB | 1047 | -0.224 | 0.222 | 20503 |
| H4 | FVG+RB | 713 | -0.239 | 0.165 | 14325 |
| H4 | RB | 2136 | -0.248 | 0.195 | 41731 |
| H4 | PB | 632 | -0.321 | 0.180 | 7127 |
| H4 | FVG+PB | 91 | -0.401 | 0.121 | 1066 |
| LIQ | True | 9627 | -0.162 | 0.281 | 241191 |
| M | OB | 2144 | -0.080 | 0.366 | 19849 |
| M | BB | 468 | -0.110 | 0.335 | 5385 |
| M | MB | 1889 | -0.122 | 0.302 | 21280 |
| M | VB | 2511 | -0.142 | 0.333 | 26312 |
| M | PB | 14 | -0.161 | 0.000 | 1144 |
| M | ANYB | 6404 | -0.165 | 0.294 | 110457 |
| M | FVG | 2781 | -0.241 | 0.180 | 61701 |
| M | FVG+MB | 29 | -0.254 | 0.069 | 541 |
| M | RB | 1119 | -0.350 | 0.093 | 23469 |
| M | FVG+ANYB | 1299 | -0.370 | 0.159 | 10503 |
| M | FVG+VB | 906 | -0.405 | 0.057 | 987 |
| M | FVG+OB | 13 | -0.460 | 0.077 | 78 |
| M | FVG+RB | 54 | -0.793 | 0.000 | 816 |
| MSB | True | 9609 | -0.137 | 0.324 | 218912 |
| W | FVG | 3866 | -0.039 | 0.437 | 73027 |
| W | FVG+MB | 577 | -0.053 | 0.428 | 4988 |
| W | BB | 695 | -0.070 | 0.367 | 17914 |
| W | FVG+BB | 108 | -0.075 | 0.426 | 851 |
| W | FVG+ANYB | 2362 | -0.075 | 0.408 | 33825 |
| W | FVG+VB | 585 | -0.141 | 0.256 | 6606 |
| W | ANYB | 6902 | -0.155 | 0.273 | 178446 |
| W | VB | 1741 | -0.178 | 0.262 | 35548 |
| W | MB | 2463 | -0.194 | 0.274 | 40271 |
| W | PB | 93 | -0.201 | 0.280 | 1395 |
| W | FVG+RB | 1068 | -0.210 | 0.240 | 8192 |
| W | RB | 3522 | -0.222 | 0.254 | 47957 |
| W | OB | 3273 | -0.311 | 0.128 | 48818 |
| W | FVG+OB | 853 | -0.686 | 0.070 | 2606 |
| W | FVG+PB | 3 | -1.163 | 0.000 | 2 |

**Detail: D:OB | H4:VB | H1:RB | limit_ce | zone+0.25atr | RR 1.0 | none** - max DD 39.6 R, longest losing streak 8, long/short +0.365 / +0.249 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2007 | 118 | 0.749 | 88.360 | 0.881 |
| 2008 | 35 | 0.231 | 8.092 | 0.686 |
| 2009 | 63 | 0.725 | 45.664 | 0.889 |
| 2010 | 41 | 0.646 | 26.466 | 0.854 |
| 2011 | 4 | -0.662 | -2.648 | 0.250 |
| 2012 | 12 | -0.244 | -2.931 | 0.583 |
| 2013 | 13 | -0.097 | -1.255 | 0.462 |
| 2014 | 17 | -0.511 | -8.679 | 0.412 |
| 2015 | 16 | -0.729 | -11.664 | 0.312 |
| 2016 | 10 | 0.319 | 3.186 | 0.800 |
| 2017 | 12 | -0.639 | -7.673 | 0.333 |
| 2018 | 10 | 1.148 | 11.479 | 0.700 |
| 2019 | 24 | -0.576 | -13.824 | 0.375 |
| 2020 | 3 | -0.538 | -1.613 | 0.333 |
| 2021 | 8 | 0.041 | 0.324 | 0.625 |
| 2022 | 14 | 0.105 | 1.466 | 0.500 |
| 2023 | 4 | -0.741 | -2.964 | 0.250 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 255 | 0.645 | 0.839 |
| low_vol | 72 | -0.335 | 0.431 |
| mid_vol | 77 | -0.111 | 0.545 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 74 | 0.287 | 0.730 |
| london | 50 | 0.668 | 0.840 |
| ny_am | 71 | -0.021 | 0.465 |
| ny_pm | 34 | 0.531 | 0.824 |
| other | 175 | 0.346 | 0.743 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 106 | 0.707 | 0.830 |
| aligned (long in discount / short in premium) | 298 | 0.191 | 0.668 |

**Detail: M:MB | W:ANYB | H4:ANYB | H1:RB | limit_ce | zone+0.5atr | RR 1.0 | none** - max DD 6.5 R, longest losing streak 4, long/short +0.889 / +0.261 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2009 | 55 | 0.697 | 38.333 | 0.873 |
| 2010 | 53 | 0.238 | 12.592 | 0.642 |
| 2015 | 2 | 0.792 | 1.585 | 1.000 |
| 2016 | 3 | 1.442 | 4.327 | 0.667 |
| 2019 | 6 | -0.498 | -2.989 | 0.333 |
| 2021 | 1 | -1.281 | -1.281 | 0.000 |
| 2022 | 16 | 0.364 | 5.817 | 0.750 |
| 2023 | 2 | -0.172 | -0.344 | 0.500 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 90 | 0.529 | 0.789 |
| low_vol | 14 | -0.236 | 0.500 |
| mid_vol | 34 | 0.405 | 0.676 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 16 | 0.153 | 0.625 |
| london | 15 | 0.822 | 0.800 |
| ny_am | 26 | 0.327 | 0.692 |
| ny_pm | 18 | 0.241 | 0.667 |
| other | 63 | 0.483 | 0.778 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 24 | 0.541 | 0.792 |
| aligned (long in discount / short in premium) | 114 | 0.395 | 0.719 |

**Detail: M:MB | D:ANYB | H4:ANYB | H1:RB | limit_ce | zone+0.5atr | RR 1.0 | be1r** - max DD 5.1 R, longest losing streak 3, long/short +0.950 / +0.295 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2009 | 33 | 0.779 | 25.693 | 0.909 |
| 2010 | 67 | 0.297 | 19.904 | 0.687 |
| 2015 | 2 | 0.792 | 1.585 | 1.000 |
| 2016 | 9 | 0.384 | 3.458 | 0.778 |
| 2021 | 3 | -0.600 | -1.801 | 0.333 |
| 2022 | 16 | 0.364 | 5.825 | 0.750 |
| 2023 | 4 | -0.676 | -2.705 | 0.250 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 76 | 0.521 | 0.789 |
| low_vol | 19 | -0.032 | 0.579 |
| mid_vol | 39 | 0.334 | 0.718 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 18 | 0.351 | 0.722 |
| london | 13 | 0.352 | 0.692 |
| ny_am | 21 | 0.472 | 0.762 |
| ny_pm | 22 | 0.456 | 0.773 |
| other | 60 | 0.352 | 0.733 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 28 | 0.605 | 0.857 |
| aligned (long in discount / short in premium) | 106 | 0.330 | 0.708 |

## 3.5 BTC

**Validation**

- IS -> OOS persistence: corr +0.107, slope -0.13, learned tau^2 0.002, prediction-error reduction vs no skill +1.2%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 5359 trades, -0.040 R/trade (t = -2.42), 1/5 folds positive; best placebo +0.012 R/trade.
- Multiple-testing hurdle: t > 4.16 (35,020 distinct combos, 18,910,800 combo x config trials). Combos passing: **0**.
- Verdict: **NO EDGE** - in-sample ranking does not predict out-of-sample results. Rows below are the strongest *historical* records only.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 5359 | -0.040 | -213.547 | 1 | 5 | 5 | 0.002 | 0.107 | -0.083 | 0.008 |
| placebo_1 | 4460 | 0.012 | 51.966 | 2 | 5 | 5 | 0.005 | 0.045 | 0.005 | 0.067 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H4:FVG+OB \| H4:MSB \| H1:OB | market | atr1.0 | 6.000 | none | 190 | 0.784 | 0.279 | 1.948 | 3.454 | 0.241 | 0.842 | 58 | 0.654 | 0.603 | 12.152 |
| H4:FVG+OB \| H1:ANYB | market | atr3.0 | 6.000 | be1r | 599 | 0.244 | 0.267 | 1.503 | 3.240 | 0.180 | 0.332 | 175 | 0.033 | 0.100 | 20.092 |
| H4:MSB \| H1:ANY | limit_ce | atr3.0 | 2.500 | be1r | 1483 | 0.114 | 0.294 | 1.237 | 3.236 | 0.178 | 0.142 | 486 | 0.056 | 0.065 | 21.996 |
| H4:FVG+OB \| H1:ANY | market | atr3.0 | 6.000 | be1r | 611 | 0.231 | 0.267 | 1.472 | 3.111 | 0.148 | 0.323 | 180 | 0.013 | 0.083 | 20.566 |
| M:OB \| W:ANYB \| D:RB \| H1:ANYB | market | atr1.5 | 1.000 | be1r | 107 | 0.272 | 0.692 | 1.807 | 3.067 | 0.138 | 0.138 | 37 | 0.524 | 0.439 | 6.912 |
| H1:FVG | limit_ce | atr3.0 | 3.000 | be1r | 1427 | 0.116 | 0.266 | 1.241 | 3.043 | 0.133 | 0.122 | 460 | 0.105 | 0.069 | 22.914 |
| W:ANYB \| D:OB \| H4:MSB \| H1:ANY | limit_edge | atr2.0 | 2.000 | none | 146 | 0.371 | 0.493 | 1.681 | 3.024 | 0.129 | 0.380 | 53 | 0.356 | 0.404 | 8.560 |
| H4:FVG+OB \| M:LIQ \| H1:ANY | market | atr3.0 | 3.500 | be1r | 151 | 0.418 | 0.311 | 2.011 | 3.019 | 0.128 | 0.494 | 49 | 0.258 | 0.268 | 6.462 |
| M:OB \| D:RB \| H1:ANYB | market | atr1.5 | 1.000 | none | 109 | 0.266 | 0.688 | 1.781 | 3.019 | 0.128 | 0.150 | 38 | 0.482 | 0.409 | 6.912 |
| H4:FVG \| M:LIQ \| H1:FVG | limit_ce | atr3.0 | 1.000 | be1r | 140 | 0.240 | 0.650 | 1.652 | 2.972 | 0.118 | 0.218 | 37 | 0.300 | 0.242 | 5.269 |
| W:MB \| H4:FVG+OB \| H1:ANYB | market | atr2.0 | 6.000 | be1r | 144 | 0.592 | 0.236 | 2.259 | 2.967 | 0.117 | 0.627 | 40 | 0.502 | 0.444 | 8.642 |
| H1:ANY | market | atr3.0 | 3.500 | none | 1309 | 0.138 | 0.364 | 1.218 | 2.942 | 0.112 | 0.153 | 409 | 0.106 | 0.091 | 29.902 |
| H4:FVG+OB \| H4:MSB \| H1:ANYB | market | atr2.0 | 3.500 | none | 428 | 0.285 | 0.322 | 1.398 | 2.940 | 0.112 | 0.342 | 123 | 0.143 | 0.185 | 23.024 |
| H4:OB \| H1:FVG | market | swing+0.1atr | 6.000 | be1r | 694 | 0.226 | 0.220 | 1.433 | 2.929 | 0.110 | 0.207 | 221 | 0.268 | 0.295 | 24.773 |
| W:MB \| H4:FVG+OB \| H1:ANY | market | atr2.0 | 6.000 | be1r | 147 | 0.571 | 0.231 | 2.199 | 2.902 | 0.105 | 0.612 | 41 | 0.465 | 0.430 | 7.660 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| OB | H4:FVG+OB \| H4:MSB \| H1:OB | market | atr1.0 | 6.000 | none | 190 | 0.784 | 3.454 | 0.654 |
| ANYB | H4:FVG+OB \| H1:ANYB | market | atr3.0 | 6.000 | be1r | 599 | 0.244 | 3.240 | 0.033 |
| ANY | H4:MSB \| H1:ANY | limit_ce | atr3.0 | 2.500 | be1r | 1483 | 0.114 | 3.236 | 0.056 |
| FVG | H1:FVG | limit_ce | atr3.0 | 3.000 | be1r | 1427 | 0.116 | 3.043 | 0.105 |
| MB | D:ANYB \| H4:MB \| H4:MSB \| H1:MB | market | atr2.0 | 6.000 | be1r | 192 | 0.487 | 2.808 | 0.440 |
| RB | W:MB \| H4:FVG+OB \| H1:RB | market | atr1.5 | 5.000 | be1r | 133 | 0.517 | 2.673 | 0.650 |
| VB | H1:VB | market | atr1.5 | 2.500 | be1r | 114 | 0.381 | 2.624 | 0.485 |
| PB | H4:OB \| H1:PB | limit_ce | atr3.0 | 5.000 | be1r | 243 | 0.302 | 2.516 | 0.367 |
| BB | W:ANYB \| H4:FVG \| H1:BB | market | zone+0.1atr | 6.000 | none | 144 | 0.578 | 2.472 | 0.324 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 2375 | -0.032 | H4:FVG+OB \| H4:MSB \| H1:OB | 3.454 | 0.784 | 0.654 |
| OB | Order block | 1603 | -0.026 | H4:FVG+OB \| H4:MSB \| H1:OB | 3.454 | 0.784 | 0.654 |
| BB | Breaker block | 357 | 0.025 | D:BB \| H4:FVG \| H1:OB | 2.849 | 0.599 | 0.026 |
| MB | Mitigation block | 1712 | -0.049 | W:MB \| H4:FVG+OB \| H1:ANYB | 2.967 | 0.592 | 0.502 |
| RB | Rejection block | 1778 | -0.047 | M:OB \| W:ANYB \| D:RB \| H1:ANYB | 3.067 | 0.272 | 0.524 |
| PB | Propulsion block | 275 | -0.022 | H4:OB \| H1:PB | 2.516 | 0.302 | 0.367 |
| VB | Vacuum block | 1 | 0.381 | H1:VB | 2.624 | 0.381 | 0.485 |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+BB | 186 | 0.169 | 0.538 | 1412 |
| D | FVG+PB | 176 | 0.007 | 0.398 | 1311 |
| D | RB | 1695 | 0.000 | 0.461 | 34089 |
| D | ANYB | 3441 | -0.062 | 0.392 | 94765 |
| D | PB | 818 | -0.071 | 0.347 | 12272 |
| D | OB | 1679 | -0.074 | 0.368 | 43529 |
| D | BB | 794 | -0.093 | 0.321 | 8422 |
| D | FVG+ANYB | 1169 | -0.101 | 0.343 | 16027 |
| D | FVG+RB | 347 | -0.113 | 0.303 | 4014 |
| D | MB | 1607 | -0.133 | 0.307 | 36527 |
| D | FVG | 1842 | -0.138 | 0.301 | 28826 |
| D | FVG+OB | 558 | -0.148 | 0.244 | 5850 |
| D | FVG+MB | 484 | -0.286 | 0.217 | 4462 |
| H1 | BB | 442 | 0.042 | 0.552 | 10909 |
| H1 | PB | 499 | -0.040 | 0.425 | 11510 |
| H1 | VB | 12 | -0.045 | 0.500 | 91 |
| H1 | OB | 1917 | -0.050 | 0.404 | 40820 |
| H1 | FVG | 1719 | -0.052 | 0.386 | 43201 |
| H1 | MB | 1270 | -0.078 | 0.387 | 25235 |
| H1 | ANY | 5967 | -0.081 | 0.346 | 142202 |
| H1 | ANYB | 5127 | -0.086 | 0.346 | 121048 |
| H1 | RB | 3419 | -0.104 | 0.331 | 75358 |
| H4 | FVG+OB | 381 | 0.052 | 0.567 | 9416 |
| H4 | OB | 1555 | -0.037 | 0.426 | 40379 |
| H4 | ANYB | 3561 | -0.059 | 0.379 | 85916 |
| H4 | RB | 1972 | -0.084 | 0.353 | 37357 |
| H4 | FVG | 2003 | -0.091 | 0.344 | 38649 |
| H4 | FVG+PB | 62 | -0.099 | 0.290 | 1659 |
| H4 | FVG+ANYB | 1168 | -0.101 | 0.342 | 23831 |
| H4 | PB | 363 | -0.116 | 0.306 | 9059 |
| H4 | FVG+RB | 504 | -0.116 | 0.331 | 8967 |
| H4 | MB | 1982 | -0.120 | 0.317 | 40515 |
| H4 | FVG+MB | 541 | -0.122 | 0.290 | 10505 |
| H4 | BB | 762 | -0.188 | 0.255 | 12869 |
| H4 | FVG+BB | 283 | -0.321 | 0.138 | 3824 |
| LIQ | True | 3702 | -0.072 | 0.378 | 69655 |
| M | RB | 1481 | 0.080 | 0.320 | 4734 |
| M | FVG | 2283 | 0.012 | 0.449 | 33672 |
| M | OB | 901 | -0.016 | 0.425 | 21325 |
| M | FVG+MB | 109 | -0.079 | 0.330 | 593 |
| M | FVG+RB | 115 | -0.086 | 0.235 | 378 |
| M | ANYB | 3951 | -0.119 | 0.316 | 92589 |
| M | MB | 1468 | -0.128 | 0.302 | 34807 |
| M | FVG+ANYB | 301 | -0.340 | 0.150 | 4190 |
| MSB | True | 5439 | -0.056 | 0.402 | 107844 |
| W | FVG | 1786 | 0.026 | 0.521 | 31476 |
| W | FVG+OB | 264 | 0.020 | 0.470 | 3871 |
| W | BB | 181 | -0.008 | 0.398 | 1908 |
| W | FVG+ANYB | 1010 | -0.010 | 0.435 | 11390 |
| W | FVG+BB | 112 | -0.020 | 0.366 | 851 |
| W | OB | 1671 | -0.055 | 0.403 | 27685 |
| W | ANYB | 4045 | -0.066 | 0.391 | 92374 |
| W | MB | 1996 | -0.082 | 0.359 | 48377 |
| W | FVG+MB | 431 | -0.085 | 0.364 | 3554 |
| W | FVG+RB | 125 | -0.185 | 0.248 | 1003 |
| W | RB | 2362 | -0.199 | 0.203 | 33481 |
| W | PB | 568 | -1.089 | 0.002 | 362 |
| W | FVG+PB | 16 | -1.142 | 0.000 | 14 |

**Detail: H4:FVG+OB | H4:MSB | H1:OB | market | atr1.0 | RR 6.0 | none** - max DD 12.2 R, longest losing streak 11, long/short +0.917 / +0.644 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 5 | 0.328 | 1.638 | 0.200 |
| 2018 | 24 | 0.917 | 22.011 | 0.292 |
| 2019 | 9 | 0.770 | 6.926 | 0.333 |
| 2020 | 16 | 1.031 | 16.503 | 0.312 |
| 2021 | 27 | 0.730 | 19.718 | 0.259 |
| 2022 | 24 | 0.929 | 22.301 | 0.292 |
| 2023 | 25 | 0.415 | 10.369 | 0.240 |
| 2024 | 17 | 2.164 | 36.782 | 0.471 |
| 2025 | 28 | 0.337 | 9.433 | 0.214 |
| 2026 | 15 | 0.224 | 3.365 | 0.200 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 63 | 0.863 | 0.286 |
| low_vol | 57 | 0.834 | 0.298 |
| mid_vol | 70 | 0.673 | 0.257 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 31 | 0.876 | 0.290 |
| london | 19 | -0.052 | 0.158 |
| ny_am | 22 | 0.455 | 0.227 |
| ny_pm | 25 | 1.345 | 0.360 |
| other | 93 | 0.852 | 0.290 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 126 | 0.661 | 0.262 |
| aligned (long in discount / short in premium) | 64 | 1.027 | 0.312 |

**Detail: H4:FVG+OB | H1:ANYB | market | atr3.0 | RR 6.0 | be1r** - max DD 20.1 R, longest losing streak 14, long/short +0.238 / +0.252 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 23 | 1.243 | 28.592 | 0.565 |
| 2018 | 71 | 0.577 | 40.958 | 0.310 |
| 2019 | 64 | 0.294 | 18.816 | 0.328 |
| 2020 | 59 | -0.026 | -1.560 | 0.186 |
| 2021 | 77 | 0.158 | 12.182 | 0.260 |
| 2022 | 67 | 0.377 | 25.240 | 0.299 |
| 2023 | 60 | 0.270 | 16.187 | 0.250 |
| 2024 | 64 | 0.078 | 4.973 | 0.203 |
| 2025 | 64 | 0.070 | 4.472 | 0.250 |
| 2026 | 50 | -0.069 | -3.460 | 0.180 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 227 | 0.267 | 0.330 |
| low_vol | 178 | 0.190 | 0.208 |
| mid_vol | 194 | 0.268 | 0.247 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 100 | 0.334 | 0.260 |
| london | 54 | -0.308 | 0.185 |
| ny_am | 63 | 0.379 | 0.349 |
| ny_pm | 88 | 0.166 | 0.250 |
| other | 294 | 0.310 | 0.272 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 306 | 0.218 | 0.245 |
| aligned (long in discount / short in premium) | 293 | 0.272 | 0.290 |

**Detail: H4:MSB | H1:ANY | limit_ce | atr3.0 | RR 2.5 | be1r** - max DD 22.0 R, longest losing streak 15, long/short +0.160 / +0.060 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 68 | 0.393 | 26.724 | 0.368 |
| 2018 | 139 | 0.217 | 30.196 | 0.324 |
| 2019 | 148 | 0.167 | 24.687 | 0.297 |
| 2020 | 146 | 0.164 | 24.015 | 0.322 |
| 2021 | 163 | 0.080 | 13.029 | 0.282 |
| 2022 | 156 | 0.137 | 21.340 | 0.276 |
| 2023 | 169 | 0.001 | 0.103 | 0.302 |
| 2024 | 186 | 0.071 | 13.226 | 0.280 |
| 2025 | 161 | 0.061 | 9.763 | 0.292 |
| 2026 | 147 | 0.042 | 6.172 | 0.245 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 571 | 0.156 | 0.322 |
| low_vol | 385 | 0.071 | 0.275 |
| mid_vol | 527 | 0.100 | 0.277 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 244 | 0.043 | 0.275 |
| london | 197 | 0.167 | 0.315 |
| ny_am | 239 | 0.145 | 0.289 |
| ny_pm | 168 | 0.289 | 0.351 |
| other | 635 | 0.067 | 0.282 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 1046 | 0.153 | 0.301 |
| aligned (long in discount / short in premium) | 436 | 0.016 | 0.275 |
| n/a | 1 | 2.483 | 1.000 |

## 3.6 ETH

**Validation**

- IS -> OOS persistence: corr +0.015, slope -0.46, learned tau^2 1e-06, prediction-error reduction vs no skill -0.0%.
- Walk-forward selection (top 10 per fold, chosen on past data only): 8692 trades, -0.018 R/trade (t = -1.39), 2/5 folds positive; best placebo +0.032 R/trade.
- Multiple-testing hurdle: t > 4.03 (20,252 distinct combos, 10,936,080 combo x config trials). Combos passing: **0**.
- Verdict: **NO EDGE** - in-sample ranking does not predict out-of-sample results. Rows below are the strongest *historical* records only.

**Real vs placebo (same pipeline on structure-free copies)**

| series | oos_trades | oos_exp | oos_total_r | folds_positive | folds_traded | folds | learned_tau2 | is_oos_corr | best_is_score | grid_mean_exp |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 8692 | -0.018 | -153.700 | 2 | 5 | 5 | 0.000 | 0.015 | -0.143 | -0.000 |
| placebo_1 | 10897 | 0.032 | 352.338 | 3 | 5 | 5 | 0.003 | 0.069 | 0.008 | 0.043 |

**Strongest combos (whole period, best config per combo, ranked by t)**

| combo | entry | stop | rr | mgmt | n_all | exp_all | wr_all | pf_all | t_all | dsr_all | exp_is | n_oos | exp_oos | exp_recent | dd_all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H4:MSB \| H1:BB | market | atr1.5 | 6.000 | be1r | 816 | 0.311 | 0.158 | 1.565 | 3.817 | 0.416 | 0.403 | 261 | 0.115 | 0.164 | 25.780 |
| H1:ANY | market | atr2.0 | 6.000 | none | 1719 | 0.212 | 0.264 | 1.277 | 3.682 | 0.364 | 0.241 | 532 | 0.146 | 0.168 | 35.114 |
| H1:OB | market | atr3.0 | 5.000 | be1r | 1331 | 0.172 | 0.225 | 1.356 | 3.595 | 0.332 | 0.210 | 413 | 0.087 | 0.128 | 17.709 |
| H1:BB | market | atr3.0 | 6.000 | none | 763 | 0.273 | 0.350 | 1.417 | 3.573 | 0.324 | 0.293 | 232 | 0.227 | 0.245 | 22.057 |
| H1:FVG | market | atr2.0 | 5.000 | none | 1739 | 0.188 | 0.266 | 1.247 | 3.515 | 0.303 | 0.233 | 547 | 0.092 | 0.095 | 40.689 |
| H4:MSB \| H1:ANY | limit_ce | atr3.0 | 6.000 | be1r | 1292 | 0.177 | 0.217 | 1.366 | 3.475 | 0.289 | 0.176 | 389 | 0.178 | 0.127 | 20.843 |
| H4:MSB \| H1:OB | limit_ce | atr3.0 | 6.000 | be1r | 978 | 0.205 | 0.216 | 1.424 | 3.400 | 0.264 | 0.186 | 307 | 0.248 | 0.174 | 48.281 |
| H4:MSB \| H1:FVG | limit_edge | atr3.0 | 4.000 | be1r | 1286 | 0.145 | 0.222 | 1.296 | 3.165 | 0.194 | 0.130 | 394 | 0.178 | 0.144 | 30.867 |
| H4:MSB \| H1:ANYB | limit_ce | atr3.0 | 4.000 | none | 1062 | 0.173 | 0.354 | 1.270 | 3.108 | 0.178 | 0.209 | 330 | 0.094 | 0.093 | 18.573 |
| H1:MB | market | swing+0.1atr | 6.000 | none | 1166 | 0.192 | 0.306 | 1.276 | 3.008 | 0.153 | 0.206 | 349 | 0.159 | 0.144 | 19.440 |
| H4:OB \| H1:BB | limit_edge | atr3.0 | 6.000 | be1r | 273 | 0.367 | 0.267 | 1.777 | 2.980 | 0.147 | 0.493 | 95 | 0.130 | 0.225 | 15.230 |
| H4:PB \| H1:FVG | limit_ce | swing+0.1atr | 5.000 | none | 187 | 0.543 | 0.326 | 1.753 | 2.963 | 0.143 | 0.431 | 71 | 0.728 | 0.658 | 12.106 |
| D:FVG \| H4:FVG+ANYB \| H1:OB | limit_ce | atr1.5 | 6.000 | be1r | 131 | 0.674 | 0.229 | 2.269 | 2.931 | 0.136 | 0.783 | 33 | 0.348 | 0.455 | 11.052 |
| D:FVG \| H4:FVG+RB \| H1:ANY | market | swing+0.1atr | 6.000 | be1r | 319 | 0.350 | 0.235 | 1.715 | 2.930 | 0.136 | 0.477 | 76 | -0.056 | 0.155 | 17.019 |
| D:FVG \| H4:FVG+RB \| H1:ANYB | market | zone+0.5atr | 5.000 | be1r | 281 | 0.331 | 0.267 | 1.713 | 2.882 | 0.126 | 0.452 | 67 | -0.053 | 0.172 | 14.522 |

**Best combo for each 1h entry type**

| h1_entry | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | exp_oos |
|---|---|---|---|---|---|---|---|---|---|
| BB | H4:MSB \| H1:BB | market | atr1.5 | 6.000 | be1r | 816 | 0.311 | 3.817 | 0.115 |
| ANY | H1:ANY | market | atr2.0 | 6.000 | none | 1719 | 0.212 | 3.682 | 0.146 |
| OB | H1:OB | market | atr3.0 | 5.000 | be1r | 1331 | 0.172 | 3.595 | 0.087 |
| FVG | H1:FVG | market | atr2.0 | 5.000 | none | 1739 | 0.188 | 3.515 | 0.092 |
| ANYB | H4:MSB \| H1:ANYB | limit_ce | atr3.0 | 4.000 | none | 1062 | 0.173 | 3.108 | 0.094 |
| MB | H1:MB | market | swing+0.1atr | 6.000 | none | 1166 | 0.192 | 3.008 | 0.159 |
| PB | H4:RB \| H1:PB | market | atr3.0 | 6.000 | none | 357 | 0.317 | 2.758 | 0.534 |
| RB | D:FVG \| H4:FVG+RB \| H1:RB | market | zone+0.5atr | 5.000 | be1r | 247 | 0.312 | 2.578 | 0.063 |

**Every zone / block type: where it helps most**

| zone | name | combos | median_exp_all | best_combo | best_t | best_exp | best_exp_oos |
|---|---|---|---|---|---|---|---|
| FVG | Fair value gap | 2007 | -0.038 | H1:FVG | 3.515 | 0.188 | 0.092 |
| OB | Order block | 1033 | -0.032 | H1:OB | 3.595 | 0.172 | 0.087 |
| BB | Breaker block | 324 | -0.008 | H4:MSB \| H1:BB | 3.817 | 0.311 | 0.115 |
| MB | Mitigation block | 1267 | -0.043 | H1:MB | 3.008 | 0.192 | 0.159 |
| RB | Rejection block | 1288 | -0.047 | D:FVG \| H4:FVG+RB \| H1:ANY | 2.930 | 0.350 | -0.056 |
| PB | Propulsion block | 194 | -0.023 | H4:PB \| H1:FVG | 2.963 | 0.543 | 0.728 |
| VB | Vacuum block | 0 |  | nan |  |  |  |

**Marginal value of each slot choice (median over combos)**

| slot | choice | combos | median_oos_exp | share_oos_positive | oos_trades |
|---|---|---|---|---|---|
| D | FVG+PB | 18 | 0.043 | 0.556 | 157 |
| D | RB | 777 | -0.068 | 0.367 | 26524 |
| D | BB | 347 | -0.091 | 0.340 | 8318 |
| D | FVG+BB | 96 | -0.109 | 0.375 | 2178 |
| D | ANYB | 1502 | -0.124 | 0.260 | 73708 |
| D | OB | 725 | -0.129 | 0.221 | 24640 |
| D | FVG+OB | 131 | -0.131 | 0.298 | 2673 |
| D | FVG+RB | 256 | -0.143 | 0.270 | 4623 |
| D | FVG | 698 | -0.199 | 0.160 | 29294 |
| D | FVG+ANYB | 399 | -0.215 | 0.165 | 13374 |
| D | MB | 727 | -0.219 | 0.162 | 25879 |
| D | PB | 155 | -0.220 | 0.200 | 1496 |
| D | FVG+MB | 156 | -0.311 | 0.064 | 3655 |
| H1 | BB | 198 | -0.092 | 0.293 | 7783 |
| H1 | FVG | 828 | -0.111 | 0.277 | 38349 |
| H1 | MB | 612 | -0.123 | 0.283 | 24279 |
| H1 | OB | 820 | -0.145 | 0.232 | 35712 |
| H1 | RB | 1464 | -0.159 | 0.209 | 66163 |
| H1 | ANY | 2426 | -0.161 | 0.203 | 137035 |
| H1 | ANYB | 2082 | -0.162 | 0.196 | 111291 |
| H1 | PB | 269 | -0.219 | 0.175 | 9644 |
| H1 | VB | 20 | -1.127 | 0.150 | 64 |
| H4 | OB | 663 | -0.107 | 0.282 | 32371 |
| H4 | BB | 310 | -0.116 | 0.261 | 15098 |
| H4 | FVG+MB | 286 | -0.135 | 0.290 | 8872 |
| H4 | FVG | 710 | -0.139 | 0.220 | 34479 |
| H4 | PB | 190 | -0.144 | 0.268 | 6960 |
| H4 | FVG+BB | 96 | -0.147 | 0.156 | 3698 |
| H4 | FVG+PB | 38 | -0.152 | 0.289 | 1133 |
| H4 | ANYB | 1527 | -0.157 | 0.227 | 80006 |
| H4 | FVG+ANYB | 482 | -0.176 | 0.162 | 21534 |
| H4 | MB | 810 | -0.191 | 0.193 | 35222 |
| H4 | FVG+OB | 209 | -0.194 | 0.177 | 8078 |
| H4 | FVG+RB | 261 | -0.199 | 0.180 | 7435 |
| H4 | RB | 898 | -0.202 | 0.166 | 33516 |
| LIQ | True | 1695 | -0.158 | 0.248 | 42887 |
| M | RB | 409 | 0.107 | 0.374 | 1685 |
| M | OB | 348 | -0.063 | 0.402 | 8334 |
| M | FVG+RB | 8 | -0.105 | 0.125 | 58 |
| M | FVG+OB | 11 | -0.118 | 0.182 | 468 |
| M | FVG+MB | 63 | -0.123 | 0.302 | 2514 |
| M | ANYB | 960 | -0.154 | 0.197 | 61024 |
| M | MB | 242 | -0.188 | 0.058 | 25779 |
| M | FVG | 364 | -0.196 | 0.102 | 25446 |
| M | FVG+ANYB | 83 | -0.203 | 0.157 | 5364 |
| MSB | True | 2171 | -0.122 | 0.282 | 88034 |
| W | FVG+PB | 30 | 0.085 | 0.500 | 228 |
| W | FVG+BB | 7 | 0.025 | 0.571 | 276 |
| W | PB | 54 | -0.059 | 0.389 | 3145 |
| W | RB | 535 | -0.128 | 0.252 | 20058 |
| W | OB | 425 | -0.145 | 0.242 | 11801 |
| W | MB | 813 | -0.166 | 0.218 | 32282 |
| W | FVG+RB | 109 | -0.172 | 0.220 | 3335 |
| W | ANYB | 1355 | -0.179 | 0.201 | 61840 |
| W | FVG+MB | 173 | -0.190 | 0.168 | 6353 |
| W | FVG | 716 | -0.192 | 0.101 | 44905 |
| W | FVG+ANYB | 263 | -0.241 | 0.095 | 15304 |
| W | BB | 84 | -0.298 | 0.119 | 2299 |
| W | FVG+OB | 88 | -0.310 | 0.205 | 1086 |

**Detail: H4:MSB | H1:BB | market | atr1.5 | RR 6.0 | be1r** - max DD 25.8 R, longest losing streak 28, long/short +0.324 / +0.295 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 25 | 0.269 | 6.728 | 0.160 |
| 2018 | 70 | 1.302 | 91.155 | 0.300 |
| 2019 | 76 | 0.398 | 30.278 | 0.171 |
| 2020 | 86 | 0.320 | 27.555 | 0.151 |
| 2021 | 91 | 0.316 | 28.745 | 0.143 |
| 2022 | 104 | -0.018 | -1.906 | 0.106 |
| 2023 | 99 | 0.354 | 35.032 | 0.192 |
| 2024 | 92 | 0.329 | 30.227 | 0.163 |
| 2025 | 105 | 0.067 | 7.049 | 0.114 |
| 2026 | 68 | -0.021 | -1.407 | 0.118 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 233 | 0.125 | 0.129 |
| low_vol | 318 | 0.534 | 0.198 |
| mid_vol | 265 | 0.206 | 0.136 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 130 | 0.191 | 0.138 |
| london | 79 | 0.313 | 0.139 |
| ny_am | 127 | 0.398 | 0.181 |
| ny_pm | 102 | 0.417 | 0.196 |
| other | 378 | 0.293 | 0.151 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 617 | 0.365 | 0.167 |
| aligned (long in discount / short in premium) | 199 | 0.143 | 0.131 |

**Detail: H1:ANY | market | atr2.0 | RR 6.0 | none** - max DD 35.1 R, longest losing streak 26, long/short +0.240 / +0.182 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 68 | 0.086 | 5.855 | 0.235 |
| 2018 | 178 | 0.440 | 78.246 | 0.292 |
| 2019 | 179 | 0.279 | 49.924 | 0.296 |
| 2020 | 209 | 0.063 | 13.077 | 0.225 |
| 2021 | 189 | 0.097 | 18.424 | 0.228 |
| 2022 | 164 | 0.503 | 82.571 | 0.335 |
| 2023 | 190 | 0.165 | 31.418 | 0.258 |
| 2024 | 195 | 0.198 | 38.628 | 0.272 |
| 2025 | 196 | 0.112 | 21.884 | 0.240 |
| 2026 | 151 | 0.160 | 24.191 | 0.258 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 633 | 0.072 | 0.276 |
| low_vol | 485 | 0.250 | 0.241 |
| mid_vol | 601 | 0.329 | 0.270 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 290 | 0.065 | 0.221 |
| london | 175 | 0.252 | 0.291 |
| ny_am | 195 | 0.370 | 0.292 |
| ny_pm | 250 | 0.194 | 0.284 |
| other | 809 | 0.223 | 0.261 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 992 | 0.262 | 0.262 |
| aligned (long in discount / short in premium) | 724 | 0.148 | 0.268 |
| n/a | 3 | -1.033 | 0.000 |

**Detail: H1:OB | market | atr3.0 | RR 5.0 | be1r** - max DD 17.7 R, longest losing streak 20, long/short +0.241 / +0.099 R

| year | n | exp | sum | wr |
|---|---|---|---|---|
| 2017 | 56 | 0.070 | 3.914 | 0.232 |
| 2018 | 157 | 0.096 | 14.994 | 0.204 |
| 2019 | 141 | 0.171 | 24.114 | 0.213 |
| 2020 | 137 | 0.394 | 54.018 | 0.270 |
| 2021 | 140 | 0.135 | 18.866 | 0.236 |
| 2022 | 140 | 0.109 | 15.235 | 0.229 |
| 2023 | 139 | 0.395 | 54.895 | 0.259 |
| 2024 | 147 | 0.146 | 21.523 | 0.231 |
| 2025 | 155 | 0.108 | 16.781 | 0.200 |
| 2026 | 119 | 0.039 | 4.631 | 0.185 |

| regime | n | exp | wr |
|---|---|---|---|
| high_vol | 480 | 0.033 | 0.240 |
| low_vol | 404 | 0.348 | 0.223 |
| mid_vol | 447 | 0.162 | 0.213 |

| session | n | exp | wr |
|---|---|---|---|
| asia | 214 | 0.146 | 0.192 |
| london | 173 | 0.358 | 0.260 |
| ny_am | 201 | 0.290 | 0.249 |
| ny_pm | 134 | 0.055 | 0.194 |
| other | 609 | 0.115 | 0.227 |

| pd_zone | n | exp | wr |
|---|---|---|---|
| against | 794 | 0.232 | 0.223 |
| aligned (long in discount / short in premium) | 535 | 0.088 | 0.230 |
| n/a | 2 | -1.016 | 0.000 |

## 4. Summary across assets

| asset | best_combo | entry | stop | rr | mgmt | n_all | exp_all | t_all | dsr_all | exp_oos | wf_oos_exp | is_oos_corr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ | M:MB \| H4:RB \| H1:ANYB | market | atr1.5 | 1.000 | be1r | 170 | 0.273 | 3.662 | 0.367 | 0.339 | 0.002 | 0.027 |
| SPX | D:OB \| H4:ANYB \| H4:MSB \| H1:MB | limit_edge | pattern+0.1atr | 3.000 | none | 111 | 0.619 | 3.280 | 0.222 | 0.533 | -0.062 | 0.013 |
| XAU | D:FVG+ANYB \| H4:FVG+ANYB \| H4:MSB \| H1:ANY | market | atr3.0 | 1.000 | none | 110 | 0.324 | 3.630 | 0.311 | 0.349 | 0.013 | -0.004 |
| XAG | D:OB \| H4:VB \| H1:RB | limit_ce | zone+0.25atr | 1.000 | none | 404 | 0.326 | 5.333 | 0.848 | -0.081 | 0.084 | -0.003 |
| BTC | H4:FVG+OB \| H4:MSB \| H1:OB | market | atr1.0 | 6.000 | none | 190 | 0.784 | 3.454 | 0.241 | 0.654 | -0.040 | 0.107 |
| ETH | H4:MSB \| H1:BB | market | atr1.5 | 6.000 | be1r | 816 | 0.311 | 3.817 | 0.416 | 0.115 | -0.018 | 0.015 |

## 5. Cross-asset robustness (same combo + config on several assets)

Selected on in-sample data only (positive IS on every listed asset, ranked by combined IS t). `pos_oos` / `pooled_oos_exp` are the untouched check.

| combo | entry | stop | rr | mgmt | assets | is_trades | mean_exp_is | min_exp_is | mean_t_is | min_t_is | pos_is | oos_trades | pos_oos | names | pooled_oos_exp | combined_t_is |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H4:MSB \| H1:ANY | limit_ce | atr3.0 | 6.000 | be1r | 3 | 2788 | 0.163 | 0.117 | 2.722 | 2.183 | 3 | 1202 | 3 | BTC,ETH,XAU | 0.134 | 4.715 |
| H1:BB | market | atr3.0 | 6.000 | be1r | 4 | 2460 | 0.165 | 0.091 | 2.205 | 1.224 | 4 | 1139 | 1 | BTC,ETH,XAG,XAU | -0.043 | 4.409 |
| H1:OB | market | atr3.0 | 6.000 | none | 4 | 3024 | 0.151 | 0.121 | 2.040 | 1.618 | 4 | 1379 | 3 | BTC,ETH,XAG,XAU | 0.053 | 4.081 |
| H1:OB | market | atr3.0 | 5.000 | be1r | 3 | 2926 | 0.130 | 0.084 | 2.307 | 1.479 | 3 | 1263 | 3 | BTC,ETH,XAU | 0.074 | 3.996 |
| H1:OB | limit_ce | atr3.0 | 6.000 | none | 3 | 2204 | 0.174 | 0.128 | 2.306 | 1.699 | 3 | 965 | 1 | BTC,ETH,XAU | 0.014 | 3.995 |
| H4:FVG+RB \| H1:FVG | market | atr3.0 | 6.000 | be1r | 4 | 540 | 0.354 | 0.263 | 1.983 | 1.552 | 4 | 187 | 2 | BTC,ETH,NQ,XAU | 0.051 | 3.965 |
| H1:OB | market | atr3.0 | 6.000 | be1r | 3 | 2858 | 0.137 | 0.084 | 2.286 | 1.597 | 3 | 1259 | 3 | BTC,ETH,XAU | 0.057 | 3.959 |
| H1:BB | limit_edge | atr3.0 | 6.000 | be1r | 3 | 1832 | 0.170 | 0.125 | 2.252 | 1.923 | 3 | 834 | 1 | BTC,ETH,XAU | -0.047 | 3.900 |
| H4:MB \| M:LIQ \| H1:ANYB | limit_ce | atr3.0 | 2.000 | be1r | 3 | 1115 | 0.154 | 0.087 | 2.243 | 1.299 | 3 | 395 | 2 | NQ,SPX,XAU | -0.004 | 3.885 |
| D:ANYB \| H4:MB \| H1:MB | limit_edge | atr3.0 | 5.000 | none | 3 | 547 | 0.352 | 0.313 | 2.207 | 2.061 | 3 | 181 | 2 | ETH,NQ,SPX | -0.025 | 3.823 |
| H1:OB | limit_ce | atr3.0 | 6.000 | be1r | 3 | 2578 | 0.135 | 0.098 | 2.183 | 1.577 | 3 | 1127 | 2 | BTC,ETH,XAU | 0.008 | 3.781 |
| D:ANYB \| H4:MB \| H1:MB | limit_edge | atr3.0 | 4.000 | none | 4 | 738 | 0.275 | 0.184 | 1.875 | 1.333 | 4 | 257 | 3 | BTC,ETH,NQ,SPX | 0.019 | 3.751 |
| D:ANYB \| H4:MB \| H1:MB | limit_edge | atr3.0 | 6.000 | none | 4 | 727 | 0.306 | 0.209 | 1.874 | 1.366 | 4 | 257 | 3 | BTC,ETH,NQ,SPX | 0.066 | 3.748 |
| D:BB \| H1:FVG | limit_ce | atr3.0 | 5.000 | be1r | 3 | 429 | 0.371 | 0.219 | 2.153 | 1.749 | 3 | 162 | 1 | BTC,XAG,XAU | -0.098 | 3.729 |
| H1:OB | limit_ce | atr3.0 | 5.000 | none | 3 | 2421 | 0.149 | 0.111 | 2.119 | 1.553 | 3 | 1052 | 2 | BTC,ETH,NQ | 0.066 | 3.670 |
| H1:MB | market | atr3.0 | 6.000 | be1r | 3 | 2767 | 0.127 | 0.097 | 2.116 | 1.695 | 3 | 1223 | 3 | BTC,ETH,XAU | 0.019 | 3.664 |
| H4:FVG+ANYB \| H1:MB | limit_edge | atr3.0 | 4.000 | none | 3 | 848 | 0.253 | 0.186 | 2.100 | 1.605 | 3 | 388 | 1 | NQ,SPX,XAU | -0.010 | 3.637 |
| D:BB \| H1:FVG | limit_ce | atr3.0 | 6.000 | be1r | 3 | 426 | 0.374 | 0.201 | 2.077 | 1.575 | 3 | 162 | 1 | BTC,XAG,XAU | -0.081 | 3.597 |
| H1:BB | market | atr3.0 | 6.000 | none | 3 | 1540 | 0.188 | 0.115 | 2.074 | 1.345 | 3 | 718 | 1 | BTC,ETH,XAG | 0.049 | 3.592 |
| D:ANYB \| H4:FVG+MB \| H1:MB | limit_edge | atr3.0 | 6.000 | none | 3 | 223 | 0.557 | 0.503 | 2.053 | 2.011 | 3 | 79 | 2 | NQ,SPX,XAU | 0.204 | 3.555 |
| H4:FVG+MB \| H1:MB | limit_edge | atr3.0 | 5.000 | none | 3 | 524 | 0.333 | 0.291 | 2.044 | 1.824 | 3 | 207 | 1 | ETH,NQ,SPX | -0.044 | 3.540 |
| H4:FVG+MB \| H1:MB | market | atr3.0 | 6.000 | none | 3 | 593 | 0.331 | 0.246 | 2.037 | 1.629 | 3 | 224 | 0 | ETH,NQ,XAU | -0.114 | 3.528 |
| H4:MSB \| H1:FVG | market | atr3.0 | 6.000 | none | 3 | 1978 | 0.161 | 0.115 | 2.021 | 1.277 | 3 | 952 | 3 | BTC,ETH,XAG | 0.071 | 3.500 |
| H4:FVG+ANYB \| H1:MB | limit_edge | atr3.0 | 3.000 | none | 3 | 873 | 0.213 | 0.137 | 2.009 | 1.356 | 3 | 402 | 2 | NQ,SPX,XAU | -0.012 | 3.479 |
| D:ANYB \| H4:MB \| H1:MB | limit_edge | atr3.0 | 6.000 | be1r | 3 | 560 | 0.282 | 0.198 | 1.976 | 1.434 | 3 | 202 | 2 | BTC,ETH,NQ | -0.042 | 3.423 |

## 6. Knowledge base (self-improvement state)

| asset | kappa | forward_trades | realized_r | predicted_r | updated |
|---|---|---|---|---|---|
| NQ | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 08:35 |
| SPX | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 08:39 |
| XAU | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 08:43 |
| XAG | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 08:49 |
| BTC | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 08:57 |
| ETH | 1.0 | 0.0 | 0.0 | 0.0 | 2026-10-24 09:00 |
