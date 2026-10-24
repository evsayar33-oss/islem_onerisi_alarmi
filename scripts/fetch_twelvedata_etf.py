"""15m holdout bars for NQ, SPX, XAG from Twelve Data ETF proxies (QQQ, SPY, SLV).

Key is read from the TWELVE_KEY environment variable (never stored). ETF bars exist
only in regular US hours (09:30-16:00 New York). Each bar is scaled to the CFD price by
the ratio of the previous day's 15:00-16:00 NY hourly close (CFD / ETF), so no lookahead.
Output: data/cache/<ASSET>_15m_etf.parquet (from 2024-09-01).
"""
import os, sys, time
import pandas as pd, requests
from ictlab.data import CACHE

MAP = {"NQ": "QQQ", "SPX": "SPY", "XAG": "SLV"}
KEY = os.environ["TWELVE_KEY"]


def pull(sym, a, b):
    for _ in range(12):
        r = requests.get("https://api.twelvedata.com/time_series", timeout=60, params={
            "symbol": sym, "interval": "15min", "start_date": a, "end_date": b,
            "outputsize": 5000, "timezone": "UTC", "apikey": KEY}).json()
        if r.get("status") == "error":
            if r.get("code") == 429:
                time.sleep(65); continue
            raise SystemExit(f"{sym}: {r}")
        return pd.DataFrame(r["values"])
    raise SystemExit(f"{sym}: rate limit")


def one(asset, sym):
    chunks, cur = [], pd.Timestamp("2024-09-01")
    end = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=150), end)
        d = pull(sym, f"{cur:%Y-%m-%d}", f"{nxt:%Y-%m-%d}")
        chunks.append(d); print(asset, sym, cur.date(), nxt.date(), len(d), flush=True)
        cur = nxt; time.sleep(8)
    d = pd.concat(chunks)
    d.index = pd.to_datetime(d["datetime"], utc=True)
    q = d[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    q = q[~q.index.duplicated()]
    h1 = pd.read_parquet(CACHE / f"{asset}_1h.parquet")["close"]
    ny = q.index.tz_convert("America/New_York")
    last = q[(ny.hour == 15) & (ny.minute == 45)]["close"]  # closes at 16:00 NY
    cfd = h1.reindex(last.index.floor("h"))  # 1h bar 15:00-16:00 NY
    ratio = pd.Series(cfd.to_numpy() / last.to_numpy(), index=last.index.tz_convert("America/New_York").date)
    ratio = ratio.dropna().shift(1)
    r = pd.Series(ny.date, index=q.index).map(ratio)
    for c in ("open", "high", "low", "close"):
        q[c] = q[c] * r
    q = q.dropna()
    q.to_parquet(CACHE / f"{asset}_15m_etf.parquet")
    print(asset, len(q), q.index[0], q.index[-1], "ratio", float(ratio.mean()), flush=True)


if __name__ == "__main__":
    for a in (sys.argv[1:] or MAP):
        one(a, MAP[a])
