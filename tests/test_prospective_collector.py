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
    append, binance_rows, collect, dukascopy_rows, read, valid_candle,
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
