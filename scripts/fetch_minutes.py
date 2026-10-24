"""Download Dukascopy 1-minute candles day by day and save a 15-minute series.

Usage: PYTHONPATH=. python3 scripts/fetch_minutes.py XAUUSD 2024-09-01 [end]
Day files are cached under data/raw/dukascopy/<SYMBOL>/ so the run can resume.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from ictlab.data import (CACHE, DUKA_DIVISOR, OHLCV, _duka_get, _finish,
                         decode_dukascopy_candles)

KEYS = {"USATECHIDXUSD": "NQ", "USA500IDXUSD": "SPX", "XAUUSD": "XAU", "XAGUSD": "XAG"}


def main(symbol: str, start: str, end: str | None = None) -> None:
    store = CACHE.parent / "raw" / "dukascopy" / symbol
    store.mkdir(parents=True, exist_ok=True)
    end_ts = pd.Timestamp(end or datetime.now(timezone.utc).date().isoformat())
    base = f"https://datafeed.dukascopy.com/datafeed/{symbol}"
    div = DUKA_DIVISOR.get(symbol, 100000.0)
    frames = []
    days = [d for d in pd.date_range(start, end_ts - pd.Timedelta(days=1), freq="D")
            if d.dayofweek != 5]
    for n, d in enumerate(days, 1):
        f = store / f"{d:%Y-%m-%d}.min.bi5"
        raw = f.read_bytes() if f.exists() else _duka_get(
            f"{base}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5")
        if raw is not None and not f.exists():
            f.write_bytes(raw)
        if raw:
            frames.append(decode_dukascopy_candles(raw, d.tz_localize("UTC").to_pydatetime(), div))
        if n % 25 == 0:
            print(f"{symbol} {d:%Y-%m-%d} {n}/{len(days)}", flush=True)
    m = pd.concat(frames)
    g = m.resample("15min", label="left", closed="left")
    q = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "volume": g["volume"].sum()}).dropna()
    q = _finish(q[OHLCV])
    out = CACHE / f"{KEYS[symbol]}_15m_duka.parquet"
    q.to_parquet(out)
    print(f"{symbol} 15m bars {len(q)} {q.index[0]} -> {q.index[-1]} saved {out.name}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
