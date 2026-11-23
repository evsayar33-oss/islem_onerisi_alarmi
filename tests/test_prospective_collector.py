import copy
import io
import json
import lzma
import struct
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ictlab.prospective_collector import (
    append, binance_rows, collect, dukascopy_rows, read, valid_candle, previous_market_candidate_days, futures_proxy_rows,
)


def zip_klines(day, microseconds=True):
    opened=datetime(day.year,day.month,day.day,tzinfo=timezone.utc)
    ts=int(opened.timestamp()*(1000000 if microseconds else 1000))
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as archive:
        archive.writestr("test.csv",
            f"{ts},100,111,99,105,10,{ts},0,0,0,0,0\n")
    return buf.getvalue()


def duka_bytes():
    # Real Dukascopy file layout: 24 bytes per candle, big endian.
    return lzma.compress(struct.pack(">iiiiif",3600,100000,104000,98000,106000,25.0))


class ProspectiveICT(unittest.TestCase):
    def test_inconsistent_ohlc_is_rejected_never_repaired(self):
        self.assertFalse(valid_candle(
            {"open":101,"high":100,"low":99,"close":100,"volume":1}))
        self.assertFalse(valid_candle(
            {"open":101,"high":110,"low":99,"close":103,"volume":-1}))

    def test_binance_us_vs_ms_timestamps(self):
        d=date(2026,11,23)
        now=datetime(2026,11,24,10,tzinfo=timezone.utc)
        for micro in (False,True):
            a=binance_rows(zip_klines(d,micro),d,now)
            self.assertEqual(len(a),1)
            self.assertEqual(a[0]["open_utc"],
                             "2026-11-23T00:00:00+00:00")

    def test_no_future_or_wrong_date_reused(self):
        d=date(2026,11,23)
        current=datetime(2026,11,23,0,30,tzinfo=timezone.utc)
        self.assertEqual(binance_rows(zip_klines(d),d,current),[])
        self.assertEqual(binance_rows(zip_klines(d),date(2026,11,22),
                                      datetime(2026,11,24,tzinfo=timezone.utc)),[])

    def test_real_dukascopy_lzma_scale_and_1hour_candle(self):
        d=date(2026,11,23)
        rows=dukascopy_rows(duka_bytes(),d,datetime(2026,11,24,tzinfo=timezone.utc),
                            "XAUUSD")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["open_utc"],"2026-11-23T01:00:00+00:00")
        self.assertEqual(rows[0]["open"],100.0)
        self.assertEqual(rows[0]["high"],106.0)

    def test_fake_provider_missing_is_explicit_not_imputed(self):
        now=datetime(2026,11,24,10,tzinfo=timezone.utc)
        def fetch(url):
            if "BTCUSDT-1h-2026-11-23" in url:
                return zip_klines(date(2026,11,23))
            return None
        a=collect(now,fetch)
        self.assertEqual(list(a["datasets"]),["BTC"])
        self.assertGreater(len(a["failed_sources"]),0)
        self.assertFalse(a["datasets"]["BTC"]["is_prospective_trade_confirmation"])
        self.assertFalse(a["paper_approved"])

    def test_monday_scan_includes_previous_friday_not_only_weekend(self):
        monday=datetime(2026,11,23,8,tzinfo=timezone.utc)
        days=previous_market_candidate_days(monday)
        self.assertEqual([str(d) for d in days],
                         ["2026-11-18","2026-11-19","2026-11-20"])
        seen=[]
        def provider(url):
            seen.append(url)
            if "BTCUSDT-1h-2026-11-22" in url:
                return zip_klines(date(2026,11,22))
            return None
        scan=collect(monday,provider)
        self.assertTrue(any("/2026/10/20/" in url for url in seen))
        self.assertFalse(any("/2026/10/21/" in url for url in seen))
        self.assertFalse(any("/2026/10/22/" in url for url in seen))
        self.assertEqual(scan["datasets"]["BTC"]["latest_complete_bar"],
                         "2026-11-22T00:00:00+00:00")
        self.assertEqual(list(scan["datasets"]),["BTC"])
        self.assertFalse(scan["live_allowed"])

    def test_independent_futures_proxy_strict_instrument_and_closed_time(self):
        now=datetime(2026,11,23,16,tzinfo=timezone.utc)
        valid=datetime(2026,11,23,12,tzinfo=timezone.utc)
        future=datetime(2026,11,23,16,tzinfo=timezone.utc)
        ts=[int(valid.timestamp()),int(future.timestamp())]
        data={"chart":{"result":[{
            "meta":{"symbol":"GC=F"},
            "timestamp":ts,
            "indicators":{"quote":[{
                "open":[4000,4005],"high":[4010,4012],
                "low":[3990,3991],"close":[4001,4002],
                "volume":[123,222]}]}}]}}
        raw=json.dumps(data).encode()
        x=futures_proxy_rows(raw,"GC=F",now)
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]["close"],4001)
        with self.assertRaisesRegex(ValueError,"WRONG_INSTRUMENT"):
            futures_proxy_rows(raw,"XAUUSD",now)

    def test_futures_proxy_never_fills_missing_original_cfd_series(self):
        now=datetime(2026,11,23,16,tzinfo=timezone.utc)
        stamp=int(datetime(2026,11,20,12,tzinfo=timezone.utc).timestamp())
        chart={"chart":{"result":[{
            "meta":{"symbol":"NQ=F"},"timestamp":[stamp],
            "indicators":{"quote":[{
                "open":[24000],"high":[24100],"low":[23900],
                "close":[24050],"volume":[240]}]}}]}}
        def get(url):
            if "NQ%3DF" in url:
                return json.dumps(chart).encode()
            return None
        result=collect(now,get)
        self.assertNotIn("NQ",result["datasets"])
        self.assertIn("NQ_FUTURES_PROXY",result["proxy_datasets"])
        self.assertFalse(result["proxy_datasets"]["NQ_FUTURES_PROXY"]
                         ["execution_substitute_permitted"])
        self.assertFalse(result["paper_approved"])
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"future_context.jsonl"
            self.assertEqual(append(f,result)["records"],1)
            self.assertIn("IDENTICAL_SOURCE",append(f,result)["status"])

    def test_sha_append_idempotence_and_tamper_detection(self):
        now=datetime(2026,11,24,10,tzinfo=timezone.utc)
        f=lambda url: zip_klines(date(2026,11,23)) if "BTCUSDT-1h-2026-11-23" in url else None
        scan=collect(now,f)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ledger.jsonl"
            self.assertEqual(append(path,scan)["records"],1)
            self.assertEqual(len(read(path)),1)
            self.assertIn("IDENTICAL_SOURCE",append(path,scan)["status"])
            forged=json.loads(path.read_text())
            forged["datasets"]["BTC"]["bars"][0]["close"]=999
            path.write_text(json.dumps(forged)+"\n")
            with self.assertRaisesRegex(ValueError,"ICT_EVIDENCE_SHA_CHAIN_INVALID"):
                read(path)


if __name__=="__main__":
    unittest.main()
