"""Data acquisition and multi-timeframe resampling.

All loaders return a DataFrame indexed by bar-open time (UTC, tz-aware) with
float columns open/high/low/close/volume at 1h resolution.

Sources:
    dukascopy  - NQ (USATECHIDXUSD), SPX (USA500IDXUSD), XAU, XAG; 1h back to ~2010+
    binance    - BTCUSDT / ETHUSDT spot klines from data.binance.vision; back to 2017-08
    yahoo      - any symbol via yfinance (1h only for the last 730 days)
    csv        - any local file (MT4/MT5/TradingView/Dukascopy exports)
    github_xau - XAUUSD h1 2012-2022 from github.com/ejtraderLabs/historical-data
"""

from __future__ import annotations

import io
import lzma
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ASSETS, AssetSpec

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
OHLCV = ["open", "high", "low", "close", "volume"]

# Dukascopy integer price divisor per instrument.
DUKA_DIVISOR = {
    "XAUUSD": 1000.0, "XAGUSD": 1000.0,
    "USATECHIDXUSD": 1000.0, "USA500IDXUSD": 1000.0,
}
# Plausible price range per asset; used to reject a wrong decoder scale.
PRICE_SANITY = {
    "NQ": (500, 100_000), "SPX": (300, 30_000), "XAU": (200, 20_000),
    "XAG": (3, 500), "BTC": (100, 10_000_000), "ETH": (5, 1_000_000),
}


def _http_get(url: str, timeout: int = 60) -> bytes | None:
    import requests

    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df = df[OHLCV].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[(df["high"] >= df["low"]) & (df["close"] > 0)]
    # Repair rare OHLC inconsistencies instead of dropping bars.
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


# --------------------------------------------------------------------------- dukascopy
def decode_dukascopy_candles(raw: bytes, period_start: datetime, divisor: float) -> pd.DataFrame:
    """Decode one LZMA-compressed Dukascopy candle file (24-byte big-endian records)."""
    if not raw:
        return pd.DataFrame(columns=OHLCV)
    data = lzma.decompress(raw)
    n = len(data) // 24
    rec = np.frombuffer(data[: n * 24], dtype=np.dtype(">i4, >i4, >i4, >i4, >i4, >f4"))
    t0 = pd.Timestamp(period_start).tz_convert("UTC") if pd.Timestamp(period_start).tzinfo \
        else pd.Timestamp(period_start, tz="UTC")
    idx = t0 + pd.to_timedelta(rec["f0"].astype(np.int64), unit="s")
    df = pd.DataFrame({
        "open": rec["f1"] / divisor, "close": rec["f2"] / divisor,
        "low": rec["f3"] / divisor, "high": rec["f4"] / divisor,
        "volume": rec["f5"].astype(float),
    }, index=idx)
    return df[df["volume"] > 0]


def _duka_get(url: str, tries: int = 6) -> bytes | None:
    """GET with backoff: the feed rate-limits with 429 / 503 / resets / timeouts."""
    for attempt in range(tries):
        try:
            raw = _http_get(url, timeout=30)
            time.sleep(0.5)
            return raw
        except Exception:
            time.sleep(2 * 2 ** attempt)
    return None


def _duka_month_from_minutes(base: str, store: Path, m: pd.Timestamp, end_ts: pd.Timestamp,
                             div: float) -> pd.DataFrame:
    """One month of 1h bars rebuilt from Dukascopy daily 1-minute candle files."""
    frames = []
    last = min(m + pd.offsets.MonthEnd(0), end_ts - pd.Timedelta(days=1))
    for d in pd.date_range(m, last, freq="D"):
        if d.dayofweek == 5:  # no trading on Saturday
            continue
        f = store / f"{d:%Y-%m-%d}.min.bi5"
        raw = f.read_bytes() if f.exists() else _duka_get(
            f"{base}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5")
        if raw is None:
            continue
        if not f.exists():
            f.write_bytes(raw)
        if raw:
            frames.append(decode_dukascopy_candles(raw, d.to_pydatetime(), div))
    if not frames:
        return pd.DataFrame(columns=OHLCV)
    return minute_to_hour(pd.concat(frames))


def load_dukascopy(symbol: str, start: str = "2012-01-01", end: str | None = None) -> pd.DataFrame:
    end_ts = pd.Timestamp(end or datetime.now(timezone.utc).date().isoformat(), tz="UTC")
    months = pd.date_range(pd.Timestamp(start, tz="UTC"), end_ts, freq="MS")
    frames = []
    div = DUKA_DIVISOR.get(symbol, 100000.0)
    store = CACHE.parent / "raw" / "dukascopy" / symbol
    store.mkdir(parents=True, exist_ok=True)
    this_month = pd.Timestamp(datetime.now(timezone.utc).date().isoformat(), tz="UTC").replace(day=1)
    base = f"https://datafeed.dukascopy.com/datafeed/{symbol}"
    for n, m in enumerate(months, 1):
        f = store / f"{m:%Y-%m}.bi5"
        raw = None
        if f.exists() and m < this_month:  # finished months never change: reuse
            raw = f.read_bytes()
        elif m < this_month:
            raw = _duka_get(f"{base}/{m.year}/{m.month - 1:02d}/BID_candles_hour_1.bi5")
            if raw:
                f.write_bytes(raw)
        if raw:
            frames.append(decode_dukascopy_candles(raw, m.to_pydatetime(), div))
            status = "ok"
        else:
            # Monthly hour file not published yet (current month) or refused after
            # retries: rebuild the month from daily minute files instead.
            part = _duka_month_from_minutes(base, store, m, end_ts, div)
            status = f"minutes:{len(part)}" if len(part) else "missing"
            if len(part):
                frames.append(part)
        print(f"{symbol} {m:%Y-%m} {n}/{len(months)} {status}", flush=True)
    if not frames:
        raise RuntimeError(f"dukascopy returned no data for {symbol}")
    return _finish(pd.concat(frames))


# --------------------------------------------------------------------------- binance
def parse_binance_klines(raw_zip: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        with z.open(z.namelist()[0]) as fh:
            df = pd.read_csv(fh, header=None)
    if not str(df.iloc[0, 0]).isdigit():  # some files carry a header row
        df = df.iloc[1:].astype(float)
    t = df[0].astype(np.int64)
    # Spot files switched from milliseconds to microseconds on 2025-01-01.
    t = np.where(t > 10**14, t // 1000, t)
    out = pd.DataFrame({
        "open": df[1].astype(float), "high": df[2].astype(float),
        "low": df[3].astype(float), "close": df[4].astype(float),
        "volume": df[5].astype(float),
    })
    out.index = pd.to_datetime(t, unit="ms", utc=True)
    return out


def load_binance(symbol: str, start: str = "2017-08-01", end: str | None = None) -> pd.DataFrame:
    base = "https://data.binance.vision/data/spot"
    today = pd.Timestamp(end or datetime.now(timezone.utc).date().isoformat(), tz="UTC")
    frames = []
    for m in pd.date_range(pd.Timestamp(start, tz="UTC"), today, freq="MS"):
        if m.year == today.year and m.month == today.month:
            for d in pd.date_range(m, today - pd.Timedelta(days=1), freq="D"):
                raw = _http_get(f"{base}/daily/klines/{symbol}/1h/{symbol}-1h-{d:%Y-%m-%d}.zip")
                if raw:
                    frames.append(parse_binance_klines(raw))
            continue
        raw = _http_get(f"{base}/monthly/klines/{symbol}/1h/{symbol}-1h-{m:%Y-%m}.zip")
        if raw:
            frames.append(parse_binance_klines(raw))
    if not frames:
        raise RuntimeError(f"binance returned no data for {symbol}")
    return _finish(pd.concat(frames))


# --------------------------------------------------------------------------- yahoo
def load_yahoo(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbol, period="730d", interval="1h", auto_adjust=False,
                     progress=False, multi_level_index=False)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index, utc=True)
    return _finish(df)


# --------------------------------------------------------------------------- csv
def load_csv(path: str | Path, tz: str = "UTC", divisor: float = 1.0) -> pd.DataFrame:
    """Generic loader; detects common column names and MT4/MT5 split date/time columns."""
    df = pd.read_csv(path, sep=None, engine="python")
    cols = {c.lower().strip("<>").strip(): c for c in df.columns}
    tcol = next((cols[k] for k in ("timestamp", "datetime", "date", "time", "open_time",
                                   "gmt time", "local time") if k in cols), df.columns[0])
    ts = df[tcol].astype(str)
    if "time" in cols and cols["time"] != tcol:
        ts = ts + " " + df[cols["time"]].astype(str)
    if np.issubdtype(df[tcol].dtype, np.number):
        unit = "ms" if df[tcol].iloc[0] > 10**11 else "s"
        idx = pd.to_datetime(df[tcol], unit=unit, utc=True)
    else:
        idx = pd.to_datetime(ts.str.replace(".", "-", n=2, regex=False), utc=False)
        idx = idx.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward") \
            if idx.dt.tz is None else idx
        idx = idx.dt.tz_convert("UTC")
    pick = {}
    for k in OHLCV:
        cand = [c for lc, c in cols.items() if lc == k or lc.startswith(k)]
        if k == "volume" and not cand:
            cand = [c for lc, c in cols.items() if "vol" in lc]
        pick[k] = df[cand[0]].astype(float) if cand else 0.0
    out = pd.DataFrame(pick)
    out.index = pd.DatetimeIndex(idx)
    out = out[out.index.notna()]
    for k in ("open", "high", "low", "close"):
        out[k] = out[k] / divisor
    return _finish(out)


def load_github_xau() -> pd.DataFrame:
    url = "https://raw.githubusercontent.com/ejtraderLabs/historical-data/main/XAUUSD/XAUUSDh1.csv"
    raw = _http_get(url, timeout=120)
    df = pd.read_csv(io.BytesIO(raw))
    idx = pd.to_datetime(df["Date"]).dt.tz_localize(
        "Europe/Helsinki", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
    out = pd.DataFrame({
        "open": df["open"] / 100, "high": df["high"] / 100, "low": df["low"] / 100,
        "close": df["close"] / 100, "volume": df["tick_volume"].astype(float),
    })
    out.index = pd.DatetimeIndex(idx)
    return _finish(out[out.index.notna()])


# --------------------------------------------------------------------------- github mirrors
# Public GitHub-hosted copies used when the primary feeds are unreachable.
OANDA_GH = ("https://raw.githubusercontent.com/FutureSharks/financial-data/master/"
            "pyfinancialdata/data/currencies/oanda")
OANDA_INST = {"NQ": "NAS100_USD", "SPX": "SPX500_USD", "XAU": "XAU_USD"}
EPSOFT_XAG = ("https://raw.githubusercontent.com/EPSOFT/Database-Currency-Pair/main/XAGUSD/"
              "XAGUSD%20(2007-2023)%20Timeframe%20(5M-H-D-W-M).zip")
CRYPTO_GH = ("https://media.githubusercontent.com/media/Speirsy11/crypto-dataset/main/data/"
             "interval_id={iv}/symbol_id={sym}/year={y}/month={m:02d}/{sym}-{iv}-{y}-{m:02d}.parquet")


def minute_to_hour(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    g = df.resample(freq, label="left", closed="left")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    return out.dropna(subset=["open"])


def _parallel_get(urls: list[str], workers: int = 8) -> list[bytes | None]:
    from concurrent.futures import ThreadPoolExecutor

    def get(u):
        for attempt in range(4):
            try:
                return _http_get(u, timeout=120)
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(get, urls))


def load_oanda_github(key: str, start_year: int = 2005, end_year: int = 2020,
                      freq: str = "1h") -> pd.DataFrame:
    """Oanda 1-minute bars (UTC) from the FutureSharks/financial-data repository."""
    inst = OANDA_INST[key]
    months = [(y, m) for y in range(start_year, end_year + 1) for m in range(1, 13)]
    urls = [f"{OANDA_GH}/{inst}/{y}/oanda-{inst}-{y}-{m}.csv" for y, m in months]
    frames = []
    for raw in _parallel_get(urls):
        if not raw:
            continue
        df = pd.read_csv(io.BytesIO(raw))
        df.index = pd.to_datetime(df["time"], utc=True)
        frames.append(minute_to_hour(df[OHLCV].astype(float), freq))
    if not frames:
        raise RuntimeError(f"no oanda data for {inst}")
    return _finish(pd.concat(frames))


def load_epsoft_xag() -> pd.DataFrame:
    """Dukascopy XAGUSD 1h export (2007-2023, fixed GMT-5 stamps) from EPSOFT."""
    raw = _http_get(EPSOFT_XAG, timeout=300)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist()
                    if "1_Hour" in n and n.endswith(".csv") and not n.startswith("__MACOSX"))
        df = pd.read_csv(z.open(name))
    ts = pd.to_datetime(df["Local time"].str.replace(r"\.000 GMT", "", regex=True),
                        format="%d.%m.%Y %H:%M:%S%z", utc=True)
    out = pd.DataFrame({"open": df["Open"].values, "high": df["High"].values,
                        "low": df["Low"].values, "close": df["Close"].values,
                        "volume": df["Volume"].values}, index=pd.DatetimeIndex(ts))
    # Dukascopy exports carry flat zero-volume bars over weekends and holidays.
    return _finish(out[out["volume"] > 0])


def load_crypto_github(symbol: str, start: str = "2017-08-01", interval: str = "1h") -> pd.DataFrame:
    """Binance spot candles (UTC; 1h, 15m, 5m ...) from the Speirsy11/crypto-dataset mirror."""
    now = datetime.now(timezone.utc)
    months = pd.date_range(start, f"{now:%Y-%m}-01", freq="MS")
    urls = [CRYPTO_GH.format(iv=interval, sym=symbol, y=m.year, m=m.month) for m in months]
    frames = []
    for raw in _parallel_get(urls):
        if not raw or raw[:4] != b"PAR1":
            continue
        df = pd.read_parquet(io.BytesIO(raw))
        df.index = pd.to_datetime(df["timestamp"], utc=True)
        frames.append(df[OHLCV].astype(float))
    if not frames:
        raise RuntimeError(f"no crypto data for {symbol}")
    return _finish(pd.concat(frames))


def load_github(key: str) -> pd.DataFrame:
    if key in OANDA_INST:
        return load_oanda_github(key)
    if key == "XAG":
        return load_epsoft_xag()
    spec = ASSETS[key]
    if spec.binance:
        return load_crypto_github(spec.binance)
    raise ValueError(f"no github mirror for {key}")


# --------------------------------------------------------------------------- facade
def load_asset(key: str, source: str = "auto", refresh: bool = False,
               csv_path: str | None = None, start: str = "2012-01-01") -> pd.DataFrame:
    spec = ASSETS[key]
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{key}_1h.parquet"
    if cache.exists() and not refresh and source in ("auto", "cache"):
        return pd.read_parquet(cache)
    if source == "cache":
        raise FileNotFoundError(cache)
    if source == "csv":
        df = load_csv(csv_path, tz="UTC")
    elif source == "github_xau":
        df = load_github_xau()
    elif source == "github":
        df = load_github(key)
    elif source == "yahoo":
        df = load_yahoo(spec.yahoo)
    elif source == "dukascopy" or (source == "auto" and spec.dukascopy):
        df = load_dukascopy(spec.dukascopy, start=start)
    elif source == "binance" or (source == "auto" and spec.binance):
        df = load_binance(spec.binance, start=max(start, "2017-08-01"))
    else:
        raise ValueError(f"no source for {key}: {source}")
    validate(df, key)
    df.to_parquet(cache)
    return df


def validate(df: pd.DataFrame, key: str) -> None:
    if len(df) < 2000:
        raise ValueError(f"{key}: only {len(df)} bars")
    lo, hi = PRICE_SANITY[key]
    med = float(df["close"].median())
    if not lo <= med <= hi:
        raise ValueError(f"{key}: median price {med} outside sanity range {lo}-{hi}; "
                         "check the price divisor of the source")


# --------------------------------------------------------------------------- resample
TF_ORDER = ("H1", "H4", "D", "W", "M")


def bucket_keys(index: pd.DatetimeIndex, spec: AssetSpec) -> dict[str, np.ndarray]:
    """Integer bucket id per 1h bar for each higher timeframe.

    The trading day starts at `rollover_hour` local time (18:00 New York for CME
    style markets, 00:00 UTC for crypto). Weeks start on the trading Monday.
    """
    local = index.tz_convert(spec.tz)
    shifted = local + pd.Timedelta(hours=24 - spec.rollover_hour) if spec.rollover_hour else local
    day = shifted.normalize().tz_localize(None)
    # Explicit second resolution: pandas >= 3 may store non-ns units.
    sec = shifted.tz_localize(None).values.astype("datetime64[s]").astype(np.int64)
    day_sec = day.values.astype("datetime64[s]").astype(np.int64)
    day_ns = day_sec // 86400
    hours_into_day = (sec - day_sec) // 3600
    week = day_ns - ((day.dayofweek.values) % 7)
    month = day.year.values * 12 + day.month.values - 1
    return {
        "H4": day_ns * 6 + hours_into_day // 4,
        "D": day_ns.astype(np.int64),
        "W": week.astype(np.int64),
        "M": month.astype(np.int64),
    }


def resample_all(h1: pd.DataFrame, spec: AssetSpec) -> dict[str, dict]:
    """Return {tf: {"df": ohlc, "close_idx": 1h index of the bar's last hour}}.

    A higher-timeframe bar becomes visible to the 1h stream at `close_idx`
    (after that 1h bar closes), which removes lookahead by construction.
    """
    keys = bucket_keys(h1.index, spec)
    out = {"H1": {"df": h1, "close_idx": np.arange(len(h1), dtype=np.int64)}}
    pos = np.arange(len(h1), dtype=np.int64)
    for tf, k in keys.items():
        g = pd.DataFrame({
            "open": h1["open"].values, "high": h1["high"].values, "low": h1["low"].values,
            "close": h1["close"].values, "volume": h1["volume"].values,
            "pos": pos, "key": k, "t": h1.index,
        }).groupby("key", sort=True)
        df = pd.DataFrame({
            "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
            "close": g["close"].last(), "volume": g["volume"].sum(),
        })
        close_idx = g["pos"].max().values.astype(np.int64)
        df.index = pd.DatetimeIndex(g["t"].first().values)
        # The last bucket may still be forming at the data end (live use): drop it so
        # a partial candle is never treated as closed.
        out[tf] = {"df": df.iloc[:-1], "close_idx": close_idx[:-1]}
    return out
