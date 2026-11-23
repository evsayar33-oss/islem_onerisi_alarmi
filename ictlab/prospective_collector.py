"""Prospective free 1h market-data collector for ICT research (NO TRADING).

Separate from historical locked ICT holdout. Never calls the trading
simulator, issues a signal, places an order, or retroactively marks a
yesterday candle as a contemporaneous strategy prediction.

Historical bars fetched *today* are labeled first-observed TODAY and are
only eligible as future research input from today's acquisition time onward.
No manufactured OHLC highs/lows or interpolated gaps.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from ictlab.config import ASSETS
from ictlab.data import DUKA_DIVISOR, decode_dukascopy_candles

SCHEMA = "ICT.prospective_real_market_data.v1"
ENDPOINT = "https://datafeed.dukascopy.com/datafeed"
BINANCE = "https://data.binance.vision/data/spot/daily/klines"
MAX_COMPRESSED_BYTES = 4000000
MAX_RAW_BYTES = 12000000


def canonical(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def sha(row):
    return hashlib.sha256(canonical(row).encode("utf-8")).hexdigest()


def fetch_public(url):
    response = requests.get(url, timeout=18,
                            headers={"User-Agent": "ICT-free-research-data/1"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    if len(response.content) > MAX_COMPRESSED_BYTES:
        raise ValueError("OVERSIZED_PROVIDER_RESPONSE")
    return response.content


def valid_candle(ohlc):
    try:
        o,h,l,c,v = [float(ohlc[k]) for k in ("open","high","low","close","volume")]
    except (ValueError, KeyError, TypeError, OverflowError):
        return False
    return (all(math.isfinite(z) for z in (o,h,l,c,v))
            and min(o,h,l,c)>0 and v>=0
            and h>=max(o,c,l) and l<=min(o,c,h))


def binance_rows(raw, day, observed):
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        files = [n for n in bundle.namelist() if n.endswith(".csv")]
        if len(files) != 1:
            raise ValueError("BINANCE_INVALID_ARCHIVE")
        with bundle.open(files[0]) as fh:
            payload = fh.read(MAX_RAW_BYTES + 1)
    if len(payload) > MAX_RAW_BYTES:
        raise ValueError("BINANCE_UNCOMPRESSED_OVERSIZE")
    rows = []
    for row in csv.reader(io.StringIO(payload.decode("utf-8-sig"))):
        if len(row) < 7:
            continue
        try:
            stamp = int(row[0])
            # Binance public archives switched 2025+ to microsecond UTC.
            seconds = stamp / (1000000 if stamp >= 10**15 else 1000)
            opened = datetime.fromtimestamp(seconds,timezone.utc)
            bar = {k:float(v) for k,v in zip(
                ("open","high","low","close","volume"),row[1:6])}
        except (OverflowError, ValueError, TypeError, OSError):
            continue
        if (opened.date()!=day or opened+timedelta(hours=1)>observed
                or opened.minute!=0 or opened.second!=0
                or not valid_candle(bar)):
            continue
        rows.append({"open_utc": opened.isoformat(),
                     **{k:round(float(v), 8) for k,v in bar.items()}})
    return sorted(rows,key=lambda x:x["open_utc"])


def dukascopy_rows(raw,day,observed,symbol):
    midnight = datetime(day.year,day.month,day.day,tzinfo=timezone.utc)
    frame=decode_dukascopy_candles(raw,midnight,DUKA_DIVISOR[symbol])
    if frame.empty:
        return []
    if not frame.index.is_monotonic_increasing:
        frame=frame.sort_index()
    candles=frame.resample("1h",label="left",closed="left").agg({
        "open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    out=[]
    for stamp,row in candles.dropna().iterrows():
        opened=stamp.to_pydatetime().astimezone(timezone.utc)
        values=row.to_dict()
        if (opened.date()!=day or opened+timedelta(hours=1)>observed
                or not valid_candle(values)):
            continue
        out.append({"open_utc":opened.isoformat(),
                    **{k:round(float(v),8) for k,v in values.items()}})
    return out


def previous_market_candidate_days(now, wanted=3):
    """Select previous weekday UTC dates, not assumed completed sessions.

    Holiday calendars and early closes are provider-specific. Missing source
    remains missing; this only ensures Monday scans include the last Friday.
    Do NOT manufacture the skipped weekend/holiday bars.
    """
    days = []
    cursor = now.date()
    while len(days) < wanted:
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            days.append(cursor)
    return sorted(days)


# These are distinct CME-style continuous futures proxies, NOT Dukascopy
# BID CFDs and NEVER substitutions in ICT strategy backtests/production.
YAHOO_FUTURES_PROXIES = {
    "NQ": "NQ=F", "SPX": "ES=F", "XAU": "GC=F", "XAG": "SI=F",
}


def futures_proxy_rows(raw, ticker, observed):
    """Read public Yahoo 60m OHLCV with strict instrument/time sanity.

    Yahoo continuous rolls, pricing and session hours differ materially from
    the original Dukascopy CFD market. Retain this dataset only as a parallel
    context-control series. It MUST NOT be selected as the same asset in the
    historical ICT regime/fill engine.
    """
    if not raw or len(raw) > MAX_COMPRESSED_BYTES:
        raise ValueError("YAHOO_PROXY_RESPONSE_INVALID")
    payload = json.loads(raw)
    result = payload.get("chart", {}).get("result", [])
    if not isinstance(result, list) or len(result) != 1:
        raise ValueError("YAHOO_PROXY_CHART_UNAVAILABLE")
    chart = result[0]
    meta = chart.get("meta", {})
    if meta.get("symbol") != ticker:
        raise ValueError("YAHOO_PROXY_WRONG_INSTRUMENT")
    indicators = chart.get("indicators", {}).get("quote", [])
    timestamps = chart.get("timestamp", [])
    if not isinstance(indicators, list) or len(indicators) != 1:
        raise ValueError("YAHOO_PROXY_QUOTES_UNAVAILABLE")
    quote = indicators[0]
    names = ("open", "high", "low", "close", "volume")
    if not all(isinstance(quote.get(k), list) for k in names):
        raise ValueError("YAHOO_PROXY_INCOMPLETE_FIELDS")
    seen = {}
    for i, ts in enumerate(timestamps):
        try:
            t = datetime.fromtimestamp(int(ts),timezone.utc)
            if (t + timedelta(hours=1) > observed
                    or t < observed - timedelta(days=7)):
                continue
            bar = {name: quote[name][i] for name in names}
            if not valid_candle(bar):
                continue
        except (TypeError,ValueError,OverflowError,OSError,IndexError):
            continue
        seen[t.isoformat()] = {
            "open_utc":t.isoformat(),
            **{k:round(float(v),8) for k,v in bar.items()}}
    return [seen[k] for k in sorted(seen)]


def collect_futures_context_proxies(now, get, failures):
    """Data are deliberately NOT merged into exact-venue CFD observations."""
    result={}
    for asset,ticker in YAHOO_FUTURES_PROXIES.items():
        url=("https://query1.finance.yahoo.com/v8/finance/chart/"
             +ticker.replace("=","%3D")+"?range=7d&interval=60m")
        try:
            blob=get(url)
            if blob is None:
                failures[asset+"/YAHOO_PROXY"]="NO_PUBLIC_CHART"
                continue
            bars=futures_proxy_rows(blob,ticker,now)
            if not bars:
                failures[asset+"/YAHOO_PROXY"]="NO_VERIFIED_CLOSED_PROXY_BARS"
                continue
            result[asset+"_FUTURES_PROXY"]={
                "symbol":ticker,
                "source":"YAHOO_CONTINUOUS_FUTURES_PROXY_60M",
                "distinct_from_primary_dukas_bid":True,
                "execution_substitute_permitted":False,
                "trade_signal_permitted":False,
                "source_recorded_utc":now.isoformat(),
                "provider_sha256":hashlib.sha256(blob).hexdigest(),
                "provider_url":url,
                "latest_complete_bar":bars[-1]["open_utc"],
                "bars":bars,
            }
        except (ValueError,TypeError,KeyError,OverflowError,
                requests.RequestException,OSError) as exc:
            status=(getattr(getattr(exc,"response",None),"status_code",None)
                    if isinstance(exc,requests.RequestException) else None)
            failures[asset+"/YAHOO_PROXY"]=(
                "HTTP_"+str(status) if status else type(exc).__name__)
    return result


def collect(now=None,get=fetch_public):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    datasets={}
    failures={}
    for asset,spec in ASSETS.items():
        rows={}
        provenance=[]
        # Crypto trades through weekends. US index/metal derivatives have
        # exchange sessions: use previous three weekdays (candidate dates)
        # and verify every requested day against actual published bars.
        days = ([(now-timedelta(days=lag)).date() for lag in (2,1)]
                if spec.binance else previous_market_candidate_days(now))
        for day in days:
            if spec.binance:
                url=f"{BINANCE}/{spec.binance}/1h/{spec.binance}-1h-{day}.zip"
            else:
                instrument=spec.dukascopy
                url=(f"{ENDPOINT}/{instrument}/{day.year}/{day.month-1:02d}/"
                     f"{day.day:02d}/BID_candles_min_1.bi5")
            try:
                blob=get(url)
                if blob is None:
                    failures[f"{asset}/{day}"]="NOT_PUBLISHED_OR_MARKET_CLOSED"
                    continue
                parsed=(binance_rows(blob,day,now) if spec.binance
                        else dukascopy_rows(blob,day,now,spec.dukascopy))
                if not parsed:
                    failures[f"{asset}/{day}"]="NO_VALID_COMPLETE_BARS"
                    continue
                provenance.append({"provider":"BINANCE_SPOT_ARCHIVE" if spec.binance
                                   else "DUKASCOPY_BID_CANDLES",
                                   "day":day.isoformat(),
                                   "raw_sha256":hashlib.sha256(blob).hexdigest(),
                                   "url":url})
                for row in parsed:
                    rows[row["open_utc"]]=row
            except (requests.RequestException, ValueError, TypeError,
                    KeyError, OSError, zipfile.BadZipFile, EOFError,
                    RuntimeError) as exc:
                code=getattr(getattr(exc,"response",None),"status_code",None)
                failures[f"{asset}/{day}"]=(
                    "HTTP_"+str(code) if code else type(exc).__name__)
                # A real 403 access denial or 429 throttling is not a
                # market holiday. Do not hammer every historical day and
                # misclassify blocked provider access as 'no session'.
                if not spec.binance and code in (403,429):
                    failures[asset+"/PRIMARY_PROVIDER_ACCESS"]=(
                        "DUKASCOPY_BLOCKED_HTTP_"+str(code))
                    break
        if rows:
            datasets[asset]={"instrument":spec.binance or spec.dukascopy,
                              "source_recorded_utc":now.isoformat(),
                              "latest_complete_bar":max(rows),
                              "bars": [rows[k] for k in sorted(rows)],
                              "provider_provenance":provenance,
                              "signals_first_observed_in_past":False,
                              "is_prospective_trade_confirmation":False}
    # Explicit 1h CME-style proxies for contextual analysis, never direct
    # replacement for missing Dukascopy BID CFD market observations.
    proxies=collect_futures_context_proxies(now,get,failures)
    return {"schema":SCHEMA,
            "captured_utc":now.isoformat(),
            "source_market":"SIX_ORIGINAL_ICT_ASSETS",
            "datasets":datasets,"proxy_datasets":proxies,
            "failed_sources":failures,
            "no_synthetic_intervals":True,
            "historical_fetched_later_not_retroactive_first_seen_signal":True,
            "research_only":True,"paper_approved":False,"live_allowed":False}


def read(path):
    path=Path(path)
    if not path.exists():return []
    prev="GENESIS";last=None;out=[]
    for text in path.read_text(encoding="utf-8").splitlines():
        rec=json.loads(text)
        signed={k:v for k,v in rec.items() if k!="sha256"}
        if rec.get("prev_sha256")!=prev or rec.get("sha256")!=sha(signed):
            raise ValueError("ICT_EVIDENCE_SHA_CHAIN_INVALID")
        stamp=datetime.fromisoformat(rec["captured_utc"])
        if stamp.tzinfo is None or (last is not None and stamp<=last):
            raise ValueError("ICT_EVIDENCE_CLOCK_REWIND")
        last=stamp;prev=rec["sha256"];out.append(rec)
    return out


def append(path,scan):
    old=read(path)
    if scan.get("schema")!=SCHEMA or (not scan["datasets"] and not scan.get("proxy_datasets")):
        return {"status":"NO_REAL_COMPLETE_BARS_NO_APPEND","records":len(old)}
    summary={asset: {"latest":v["latest_complete_bar"],
                     "raw_sha": [k["raw_sha256"] for k in v["provider_provenance"]]}
             for asset,v in scan["datasets"].items()}
    # Independent proxy source digests cannot silently mutate original
    # instrument truth; recording any new provider data never makes a trade.
    proxy_summary={asset: {"latest":v["latest_complete_bar"],
                           "raw_sha":v["provider_sha256"],
                           "instrument":v["symbol"]}
                   for asset,v in scan.get("proxy_datasets",{}).items()}
    key=sha({"primary_exact":summary,"independent_context_proxy":proxy_summary})
    if old and old[-1].get("input_digest")==key:
        return {"status":"IDENTICAL_SOURCE_NO_DUPLICATE_EVENT","records":len(old)}
    row=dict(scan)
    row["input_digest"]=key
    row["prev_sha256"]=old[-1]["sha256"] if old else "GENESIS"
    row["sha256"]=sha({k:v for k,v in row.items() if k!="sha256"})
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as fh:
        fh.write(canonical(row)+"\n")
    return {"status":"APPENDED_REAL_DATA_NOT_A_STRATEGY_SIGNAL",
            "records":len(old)+1,"sha256":row["sha256"]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",required=True)
    p.add_argument("--out",default="out/ict_real_data")
    args=p.parse_args()
    result=collect()
    report=append(args.ledger,result)
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    snapshot={"scan":result,"registry":report}
    (out/"source_report.json").write_text(
        json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# ICT real-data collection; six original assets",
           "Crypto: previous two UTC dates; US index/metals: previous three weekdays (calendar candidates only).",
           "Each candle requires real provider bytes. Earlier prices are NOT retroactive first-seen signals.",
           "Markets with valid bars: "+", ".join(result["datasets"]),
           "Independent CME futures CONTEXT PROXIES (not CFD replacements): "+
              ", ".join(result.get("proxy_datasets",{})),
           "Missing sources: "+str(len(result["failed_sources"])),
           "Evidence: "+report["status"],
           "No historical OOS re-selection, no synthetic candles, no PAPER/LIVE acceptance."]
    (out/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("ICT_COLLECT",len(result["datasets"]),"original markets;",
          len(result.get("proxy_datasets",{})),"independent proxy markets",
          len(result["failed_sources"]),"partial failures",report["status"])
    if not result["datasets"] and not result.get("proxy_datasets"):
        raise SystemExit("NO_VERIFIED_MARKET_BARS")


if __name__=="__main__":
    main()
