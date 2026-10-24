"""ictlab - multi-timeframe ICT confluence research engine.

Pipeline:
    data  -> 1h OHLC per asset, resampled to 4H / D / W / M (session aware, no lookahead)
    features -> FVG, order blocks, market structure breaks, monthly liquidity sweeps
    triggers -> every 1h FVG / OB is a candidate entry
    simulate -> one outcome tensor per trigger for every entry / stop / RR / management config
    combos   -> every subset of HTF confluence conditions is a boolean mask over triggers
    validate -> IS/OOS split, deflated Sharpe, empirical-Bayes shrinkage, cross-asset robustness
    learn    -> persistent, decayed knowledge base that updates with each new run
"""

__version__ = "0.1.0"
