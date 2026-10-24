"""Build XAU 15m holdout bars from Binance PAXGUSDT (gold-backed token), scaled to the XAU 1h series.

PAXG trades 24/7 and carries a small premium, so every 15m bar is multiplied by
XAU_1h_close / PAXG_1h_close of its hour (hour-level ratio, known only after the hour is
used for the previous hour to avoid lookahead). Output: data/cache/XAU_15m_paxg.parquet
"""
import io, zipfile
import pandas as pd, requests
from ictlab.data import CACHE

B = "https://data.binance.vision/data/spot"
cols = ["ot", "open", "high", "low", "close", "volume", "ct", "qv", "n", "tb", "tq", "ig"]


def read(url):
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return pd.read_csv(z.open(z.namelist()[0]), header=None, names=cols)


def main():
    parts = []
    for p in pd.period_range("2024-08", "2026-10", freq="M"):
        d = read(f"{B}/monthly/klines/PAXGUSDT/15m/PAXGUSDT-15m-{p}.zip")
        if d is None:  # current month: daily files
            for day in pd.date_range(p.start_time, p.end_time.normalize()):
                x = read(f"{B}/daily/klines/PAXGUSDT/15m/PAXGUSDT-15m-{day:%Y-%m-%d}.zip")
                if x is not None:
                    parts.append(x)
        else:
            parts.append(d)
    d = pd.concat(parts)
    unit = "us" if d.ot.iloc[-1] > 1e14 else "ms"
    d["ot"] = d.ot.where(d.ot < 1e14, d.ot // 1000)
    d.index = pd.to_datetime(d.ot, unit="ms", utc=True)
    q = d[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    q = q[~q.index.duplicated()]
    xau = pd.read_parquet(CACHE / "XAU_1h.parquet")["close"]
    pax_h = q["close"].resample("1h").last()
    ratio = (xau / pax_h).dropna()
    ratio = ratio[(ratio > 0.9) & (ratio < 1.1)].shift(1)  # previous completed hour
    r = ratio.reindex(q.index.floor("1h")).to_numpy()
    for c in ("open", "high", "low", "close"):
        q[c] = q[c] * r
    q = q.dropna()
    q = q[q.index >= pd.Timestamp("2024-09-01", tz="UTC")]
    q.index = q.index.as_unit("ns") if hasattr(q.index, "as_unit") else q.index
    q.to_parquet(CACHE / "XAU_15m_paxg.parquet")
    print(len(q), q.index[0], q.index[-1], "ratio mean", float(ratio.mean()))


if __name__ == "__main__":
    main()
