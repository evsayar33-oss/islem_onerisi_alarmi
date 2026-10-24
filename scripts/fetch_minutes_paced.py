"""Paced Dukascopy minute-file downloader (one request stream, honours 429).

Usage: PYTHONPATH=. python3 scripts/fetch_minutes_paced.py 2024-09-01 [delay_s]
Fills data/raw/dukascopy/<SYMBOL>/<day>.min.bi5 for the four CFD assets, round robin.
"""
import sys, time
from datetime import datetime, timezone
import pandas as pd
import requests
from ictlab.data import CACHE

SYMS = ["USATECHIDXUSD", "USA500IDXUSD", "XAUUSD", "XAGUSD"]


def main(start, delay=1.5):
    end = pd.Timestamp(datetime.now(timezone.utc).date())
    days = [d for d in pd.date_range(start, end - pd.Timedelta(days=1)) if d.dayofweek != 5]
    root = CACHE.parent / "raw" / "dukascopy"
    todo = []
    for d in days:
        for s in SYMS:
            f = root / s / f"{d:%Y-%m-%d}.min.bi5"
            if not f.exists():
                todo.append((s, d, f))
    ses, wait, done = requests.Session(), delay, 0
    for s, d, f in todo:
        f.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://datafeed.dukascopy.com/datafeed/{s}/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
        while True:
            try:
                r = ses.get(url, timeout=60)
            except requests.RequestException:
                time.sleep(10); continue
            if r.status_code == 200 or r.status_code == 404:
                f.write_bytes(r.content if r.status_code == 200 else b"")
                wait = max(delay, wait * 0.9); break
            wait = min(60, wait * 1.7 + 1); time.sleep(wait)
        done += 1
        if done % 50 == 0:
            print(f"{done}/{len(todo)} wait={wait:.1f}s last={s} {d:%Y-%m-%d}", flush=True)
        time.sleep(wait)
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.5)
