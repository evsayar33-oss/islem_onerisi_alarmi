# RESEARCH LOG - every method tried and its result

This file records every method that was tested in this repository, the data, the
fixed success test and the result. It is written for a person or another AI that
did not see the work. Rule definitions are in [`STRATEGY_BOOK.md`](STRATEGY_BOOK.md).
Raw numbers are in `results/`.

**Short answer.** No tested method passed the success test. No method produced a
persistent, statistically reliable profit on the six markets (NQ, SPX, XAU, XAG,
BTC, ETH) in the locked 2-year holdout.

**Türkçe kısa cevap.** Denenen hiçbir yöntem başarı testini geçmedi. Hiçbir yöntem
altı piyasada (NQ, SPX, XAU, XAG, BTC, ETH) kilitli son 2 yılda kalıcı ve
istatistiksel olarak güvenilir bir kâr üretmedi.

## 1. Data and test protocol

- 1h bars: NQ 2012-2026, SPX 2017-2026, XAU 2012-2026, XAG 2007-2026 (Dukascopy CFD);
  BTC and ETH 2017-2026 (Binance spot). Last bar: 2026-10-22/23.
- Higher timeframes (4H, 1D, 1W, 1M) are built from 1h bars. An HTF candle is used
  only after it closes (no lookahead; a truncation test checks this).
- Costs per round trip: NQ 2, SPX 2, XAU 3, XAG 8, BTC 10, ETH 10 bps.
- **Locked holdout**: the last 2 years of each asset (from about 2024-10-23).
  All choices (rule, stop, RR, filter, sizing) use only data before the holdout.
  The holdout is opened once per method.
- **Pre-registered success test** (fixed before stages A-D ran,
  `scripts/stages_common.py`): a method is POSITIVE when the pooled holdout trades
  of the six assets have mean R > 0 with t >= 2, AND at least 4 of 6 assets have a
  positive mean.
- R = result in units of the initial risk, after costs.

## 2. Summary table

| # | method | holdout trades | mean R/trade | t | assets positive | result |
|---|---|---|---|---|---|---|
| 0a | Full ICT combo search, robust #1 per asset (1h entry) | 244 | -0.057 | -0.53 | 2/6 | negative |
| 0b | Same, all 30 robust candidates | - | -0.002 | - | 18/30 rules | negative |
| 0c | High win-rate search (top 20 per asset) | - | -0.04 to -0.21 on 5 assets, +0.01 on XAG | - | 1/6 | negative |
| A1 | Volatility sizing: inverse ATR (INVVOL) | 244 | -0.060 | -0.45 | 2/6 | negative |
| A2 | Volatility sizing: regime weights (REGIME) | 244 | -0.074 | -0.61 | 1/6 | negative |
| B | 15m confirmation entry, all six assets (XAU, NQ, SPX, XAG on proxy data) | 256 | +0.033 | +0.28 | 4/6 | not significant (fails t >= 2) |
| B' | 15m entry, all candidate rules (crypto) | 587 | +0.052 | +0.61 | 1/2 | not significant |
| C1 | Macro filter chosen per asset (AVOID / POST / NONE) | 99 | -0.063 | -0.39 | 3/6 | negative |
| C2 | News candle strategy (CPI, NFP, FOMC) | 176 | +0.028 | +0.24 | 4/6 | not significant |
| D1 | JUDAS swing (Asian range sweep in London) | 739 | -0.153 | -2.98 | 0/6 | negative (significant) |
| D2 | PO3 (midnight open reclaim) | 1408 | -0.074 | -2.05 | 0/6 | negative (significant) |
| D3 | Turtle soup (previous-day high/low in killzone) | 1007 | -0.155 | -3.67 | 0/6 | negative (significant) |
| D4 | Silver bullet (10-11 NY, first 15m FVG; crypto) | 688 | -0.086 | -1.47 | 1/2 | negative |

Order of work, as asked: A (sizing) -> B (5-15 min entry) -> C (news and macro) ->
D (new combos). Each stage was run because the stage before it did not pass.

## 3. Earlier studies (before stages A-D)

### 0a/0b. Multi-timeframe ICT combo search (`scripts/rule_search.py`)
- Conditions: 1M liquidity sweep (M:LIQ), FVG and all block types on 1M, 1W, 1D,
  4H; 4H MSB; 1h entry zone. Block types: OB, BB (breaker), MB (mitigation),
  RB (rejection), PB (propulsion), VB (vacuum); also ANYB and FVG-inside-block.
- Filters: none, BIAS_D, BIAS_W, KZ (killzone), PD (premium/discount), BIAS_D+KZ.
- Execution grid: 3 entries x 10 stops x 11 RR (0.5-6) x 3 management = 990 settings.
- About 60 000-90 000 combos per asset. Selection: shrinkage prior, t hurdle,
  walk-forward, placebo test.
- Result: walk-forward verdicts "NO EDGE" or "WEAK SIGNAL" on all assets. Holdout:
  robust #1 positive on 2/6 assets; all robust candidates average -0.002 R.

### 0c. High win-rate study (`scripts/winrate_search.py`)
- Rank combos by the lower bound of the win rate on a 1:1 ATR bracket, then pick
  stop/RR on pre-holdout data.
- Result: the spread of win rates between combos equals pure chance. True skill
  spread is at most about 2 percentage points. In-sample win rates of 60-65 % fell
  to about 40-53 % out-of-sample. Stop/RR choice did not create profit.

## 4. Stage A - volatility-regime dynamic position size (`scripts/stage_a_vol_sizing.py`)
- Trades are the same as in 0a; only the size changes.
- CONST: 1 unit per trade. INVVOL: size = median ATR / current ATR (clipped).
  REGIME: ATR tercile (low/mid/high) weights from shrunk pre-holdout mean R.
- Result: sizing does not change the sign. Mean R stays negative (-0.06 to -0.07).
  Sizing can only scale an edge; it cannot make one.

## 5. Stage B - 5-15 minute entry resolution (`scripts/stage_b_ltf_entry.py`)
- Setup = 1h zone from the candidate combos. Inside 24 h, wait for a 15m FVG in the
  trade direction inside the 1h zone. Entries: 15m market, 15m limit at FVG middle.
  Stops: 15m pattern, 1h zone, 2 x 15m ATR. 198 settings.
- Data: BTC and ETH have full 15m history (Binance). For NQ, SPX, XAU, XAG the
  free 15m sources end in 2020 (OANDA) and 2023 (XAG). The holdout needs 15m data
  from 2024-09. Dukascopy 1-minute files are downloaded one day per request
  (`scripts/fetch_minutes.py`); the server rate limit allowed about 50-75 of 672
  days per asset in this session. **Thus Stage B for NQ, SPX, XAU, XAG is not
  complete.** When `data/cache/<ASSET>_15m_duka.parquet` exists, run
  `PYTHONPATH=.:scripts python3 scripts/stage_b_ltf_entry.py BTC ETH NQ SPX XAU XAG`.
- Result (crypto): BTC best rule D:RB | H1:MB, 15m limit at FVG middle, stop at
  1h zone, RR 2: 40 holdout trades, +0.167 R. Pooled crypto +0.086 R, t 0.52.
  Positive sign, but far from t >= 2. Not a proven edge.

- **Run of all six assets (2026-10-24).** `stage_b_ltf_entry.py BTC ETH NQ SPX XAU XAG`
  ran to the end. The 15m series of NQ, SPX, XAU end on 2020-05-14 and XAG on
  2023-04-03, so these four assets have **0 holdout bars and 0 holdout trades**.
  The verdict (88 trades, +0.086 R, t 0.52, 2/6 assets listed, positive=False)
  comes from BTC and ETH only. It is not a test of the four missing assets.
  The minute download covers only about 50-75 of 672 days per asset (rate limit),
  so the result for these four assets stays open.

- **XAU added with a gold-token proxy (2026-10-24).** Dukascopy answered mostly
  HTTP 429 even with one paced request stream (`scripts/fetch_minutes_paced.py`), so
  the minute download did not progress. Yahoo is blocked (429); TextToQuant and FMP
  need a paid plan for metals, indices and intraday data; Binance futures XAU/XAG/QQQ/SPY
  start only in 2025-12 to 2026-04. For gold, Binance spot PAXGUSDT 15m (full holdout) was
  scaled to the XAU 1h close with an hourly ratio (`scripts/build_xau_paxg.py`).
  This is a proxy, not the same price feed; PAXG also trades on weekends.
  XAU holdout (47 300 bars) result: pooled six-asset primary 115 trades, -0.013 R,
  t -0.08, 2/6; all candidates 773 trades, -0.033 R, t -0.45. XAU rules: 27-51
  holdout trades each, mostly negative (-0.33 to -0.48 R; one +0.06 R).
  **NQ, SPX and XAG still have no holdout 15m data and remain untested.**
  No free source with full history was found for them.
- **API keys tried (2026-10-24).** Twelve Data: free daily credit limit already used up
  (HTTP 429, limit 800 per day). Alpha Vantage: `FX_INTRADAY` and
  `TIME_SERIES_INTRADAY` with `month=` are premium endpoints on the free key (and the
  free key allows 25 requests per day). Result: **NQ, SPX, XAG: Stage B closed as
  "not testable with free data".** Needed: 15m bars from 2024-09 to now
  (NQ/SPX futures or CFD, XAG spot). The minute downloader was stopped.
- **Second Twelve Data key worked (2026-10-24), all six assets now tested.** Its free
  plan has no XAG/USD, NDX or SPX, so ETF proxies were used: QQQ for NQ, SPY for SPX,
  SLV for XAG (`scripts/fetch_twelvedata_etf.py`, key read from an environment
  variable). Bars exist only in US regular hours (09:30-16:00 NY); each bar is scaled
  to the CFD price by the previous day's 15:00-16:00 NY close ratio. Holdout: about
  12 900 bars each. Entries outside US hours are not possible for these three assets.
  Final Stage B (primary rules, six assets): 256 trades, +0.033 R, t +0.28, 4/6 assets
  positive -> **not positive** (needs t >= 2). Per asset: BTC +0.167, ETH +0.019,
  NQ +0.004, SPX +0.151, XAU -0.335, XAG -0.290. All candidates: 1450 trades, -0.018 R,
  t -0.33, 2/6. Proxy data (XAU, NQ, SPX, XAG) limits how far these numbers can be trusted.

## 6. Stage C - news and macro calendar (`scripts/stage_c_macro.py`)
- Events: 511 CPI and NFP (08:30 NY) and FOMC (14:00 NY) dates,
  `data/macro/release_dates.json`.
- C1 filters on the candidate rules: AVOID (no trade 12 h before to 4 h after an
  event), POST (only 48 h after an event), NONE. Choice per asset on pre-holdout data.
- C2 news candle: at the close of the event candle, if the body >= k x ATR, follow
  or fade it; 48 settings of k, mode, stop, RR.
- Result: C1 -0.063 R (t -0.39). C2 +0.028 R (t 0.24, 4/6 assets positive). The
  pre-holdout C2 means (+0.09 to +0.31 R) fell close to zero in the holdout.

## 7. Stage D - new ICT combos (`scripts/stage_d_new_models.py`)
- JUDAS: Asian range (19:00-24:00 NY) swept in London killzone, close back inside.
- PO3: price trades below/above the midnight open, then closes back across it.
- SOUP: previous-day high/low swept inside a killzone, close back inside.
- SB: 10:00-11:00 NY first 15m FVG (crypto, full 15m data).
- Grid: stop (sweep extreme + 0.1 ATR, or 1 ATR) x RR {1, 1.5, 2, 3} x filter
  {none, BIAS_D}; best pre-holdout setting per asset.
- Result: JUDAS, PO3 and SOUP lose on all six assets; the losses are statistically
  significant (t -2.0 to -3.7). These session reversal patterns did not work in the
  last 2 years, and most were already negative before the holdout.

## 8. What the results show

1. ICT zone confluence at 1h, 4H and higher timeframes does not predict direction
   better than chance on these markets after costs.
2. Changing RR, stop, management, size, entry timeframe or news timing does not
   change this. These tools scale or filter an edge; they cannot create one.
3. In-sample winners regress to zero. The locked holdout and the walk-forward test
   show this clearly; without them, many rules would look profitable.
4. The only results with a positive sign (Stage B crypto, Stage C news candle) are
   small and not significant. They are candidates for paper trading only.

## 9. Ideas not yet tested

- Finish Stage B for NQ, SPX, XAU, XAG (data download, see section 5).
- Order-flow data (futures volume, footprint, order book), which ICT concepts try
  to approximate from price only.
- Cross-asset and macro regime state (rates, USD, volatility index) as a condition,
  not as a timing filter.
- Live paper trading of Stage B crypto and Stage C2 for at least 100 trades.

## 10. Synthesis with quant_lab (2026-10-24)

The owner asked for both labs to be used as one, with the S&P 500 index (not cash) as the benchmark.
The study is in quant_lab: `lab/synthesis.py`, rules in `config/synthesis.yaml` (pre-registered),
report `SENTEZ_RAPORU.md`. Input from this repo: all ICT methods above are negative or not significant in the
locked holdout, so no ICT rule enters the synthesis. Result (rules fixed before the run):
- No published timing rule passed all 7 checks against the US index over 1928-2026 (68 grid points, 4 time-machine cuts: 0/4).
- Index + trend-following overlay (AQR TSMOM, 1988-2026) passed 6 of 7 checks and the time machine 2/2;
  it failed only the luck test (DSR 0.56 < 0.90), and the trend premium fell after 2012 (Sharpe 1.5 -> 0.4).
- S&P 500 + 10-20% of the H054 crypto trend book passed its own rule in 2018-2026 (CAGR 15.1% -> 17.6-20.0%,
  drawdown not deeper). Short history; tracked forward in quant_lab `decisions/synthesis/forward.json`.
Conclusion for this repo: more ICT combination search is not recommended. Order-flow data (section 9) is the only
open idea with different information.

## 10b. Per-asset book (2026-10-24)

quant_lab H073 tested every rule, Fibonacci premium/discount entries and ICT combos per asset (29,912 trials): nothing passed. The fixed H054 core rule passed on BTC, ETH and SOL. See quant_lab `VARLIK_STRATEJI_KITABI.md`.

## 11. Files

| file | content |
|---|---|
| `results/rule_search/*_selection.json` | study 0a/0b candidates and holdout |
| `results/winrate/*_winrate.json` | study 0c |
| `results/stages/stage_a.json` | Stage A |
| `results/stages/stage_b.json`, `stage_b_crypto.json` | Stage B (crypto) |
| `results/stages/stage_c.json` | Stage C |
| `results/stages/stage_d.json` | Stage D |
| `scripts/stages_common.py` | success test, holdout cut, candidate loading |
