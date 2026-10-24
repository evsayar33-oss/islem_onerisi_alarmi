import io
import lzma
import struct
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from ictlab import config, features as F
from ictlab.config import ASSETS, ResearchParams
from ictlab.context import build_context
from ictlab.data import decode_dukascopy_candles, parse_binance_klines, resample_all
from ictlab.research import evaluate, prepare
from ictlab.simulate import _path


def random_walk(n=20000, sub=60, seed=1, start="2015-01-01"):
    rng = np.random.default_rng(seed)
    steps = rng.standard_normal((n, sub)) * 0.002 / np.sqrt(sub)
    path = 1000 * np.exp(np.cumsum(steps.ravel())).reshape(n, sub)
    o = np.r_[1000, path[:-1, -1]]
    c = path[:, -1]
    h = np.maximum(path.max(1), o)
    l = np.minimum(path.min(1), o)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1.0}, index=idx)


@pytest.fixture(scope="module", autouse=True)
def rw_asset():
    config.ASSETS["RW"] = config.AssetSpec("RW", "random walk", "UTC", 0, 0.0)
    yield


def test_fvg_detection_and_invalidation():
    h = np.array([10, 11, 15, 16, 14, 9.0])
    l = np.array([9, 10, 12, 14, 12, 8.0])
    c = np.array([10, 11, 14, 15, 13, 8.5])
    a = np.ones(6)
    bar, d, lo, hi, ext, inv = F.detect_fvg(h, l, c, a, 0.1)
    # bar 2: low 12 > high[0] 10 -> bullish zone [10, 12]
    assert bar[0] == 2 and d[0] == 1 and lo[0] == 10 and hi[0] == 12
    assert ext[0] == 9
    assert inv[0] == 5  # close 8.5 < 10


def test_structure_break_and_order_block():
    # swing high at bar 2 (k=1), down-close candle at bar 4, break at bar 5
    o = np.array([10, 11, 12, 11.5, 11.2, 10.8, 13.0])
    c = np.array([11, 12, 11.5, 11.2, 10.8, 13.5, 13.2])
    h = np.array([11.2, 12.2, 13.0, 11.8, 11.3, 13.6, 13.4])
    l = np.array([9.8, 10.9, 11.4, 11.0, 10.6, 10.7, 12.9])
    mb, md, ob, od, olo, ohi, oext, oinv = F.detect_structure(o, h, l, c, 1, 20)
    assert 5 in mb[md == 1]
    k = np.nonzero((ob == 5) & (od == 1))[0][0]
    assert olo[k] == 10.6 and ohi[k] == 11.3


def test_resample_buckets_and_partial_bar_dropped():
    df = random_walk(24 * 40)
    tfs = resample_all(df, config.ASSETS["RW"])
    d = tfs["D"]["df"]
    assert len(d) == 39  # 40 days, the last (possibly forming) one dropped
    assert d["high"].iloc[0] == df["high"].iloc[:24].max()
    assert (np.diff(tfs["D"]["close_idx"]) == 24).all()


def test_no_lookahead_truncation_invariance():
    """Condition bits of a trigger must not change when future bars are removed."""
    df = random_walk(24 * 300, seed=3)
    p = ResearchParams()
    full = build_context(df, config.ASSETS["RW"], p)
    cut = len(df) - 24 * 60
    part = build_context(df.iloc[:cut], config.ASSETS["RW"], p)
    lim = cut - 24 * 35  # beyond the last (dropped) monthly bucket of the truncated run
    a = {(t, k, d): b for t, k, d, b in zip(full.trig.t, full.trig.kind, full.trig.dir,
                                             full.trig.bits) if t < lim}
    b = {(t, k, d): b for t, k, d, b in zip(part.trig.t, part.trig.kind, part.trig.dir,
                                             part.trig.bits) if t < lim}
    assert a.keys() == b.keys()
    diff = [k for k in a if a[k] != b[k]]
    assert not diff, f"{len(diff)} triggers changed"


def test_path_rules():
    o = np.array([100, 100, 101, 103.0])
    h = np.array([100, 101, 104, 104.0])
    l = np.array([100, 99.5, 100.5, 102.0])
    c = np.array([100, 100.5, 103, 103.0])
    # long from 100, stop 99, target 103 -> target hit on bar 2
    xp, xb = _path(1, 0, 100.0, 99.0, 103.0, 0, o, h, l, c, 10, False, 2.0)
    assert xp == 103 and xb == 2
    # same-bar tie -> stop
    l2 = l.copy()
    l2[2] = 98.0
    xp, xb = _path(1, 0, 100.0, 99.0, 103.0, 0, o, h, l2, c, 10, False, 2.0)
    assert xp == 99 and xb == 2


def test_random_walk_has_no_edge():
    """Null calibration: on a martingale the whole grid must average ~0 R (zero cost)."""
    df = random_walk(30000, seed=11)
    p = ResearchParams()
    prep = prepare("RW", df, p)
    g = evaluate(prep, int(len(df) * 0.7))
    # grand mean over *all* trials (not only the kept top configs)
    assert abs(g.attrs["prior"]["mu0"]) < 0.05
    # the kept rows were selected in-sample: their out-of-sample mean must still be ~0
    oos = g[g["n_oos"] > 0]
    assert abs(oos["sum_oos"].sum() / oos["n_oos"].sum()) < 0.05
    raw = prep["R"][np.isfinite(prep["R"])]
    assert abs(raw.mean()) < 0.05


def test_dukascopy_decoder():
    recs = b"".join(struct.pack(">iiiiif", 3600 * i, 1500000 + i, 1500500, 1499000, 1501000,
                                10.0) for i in range(3))
    raw = lzma.compress(recs, format=lzma.FORMAT_ALONE)
    df = decode_dukascopy_candles(raw, datetime(2024, 1, 1, tzinfo=timezone.utc), 1000.0)
    assert len(df) == 3
    assert df["open"].iloc[1] == pytest.approx(1500.001)
    assert df["high"].iloc[0] == pytest.approx(1501.0)
    assert df.index[2] == pd.Timestamp("2024-01-01 02:00", tz="UTC")


def test_binance_parser_handles_microseconds():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "1735689600000000,1,2,0.5,1.5,10,0,0,0,0,0,0\n"
                            "1735693200000000,1.5,2,1,1.8,10,0,0,0,0,0,0\n")
    df = parse_binance_klines(buf.getvalue())
    assert df.index[0] == pd.Timestamp("2025-01-01", tz="UTC")
    assert df["close"].iloc[1] == 1.8


def test_knowledge_base_loop(tmp_path):
    from ictlab.learner import KnowledgeBase

    df = random_walk(24 * 500, seed=5)
    p = ResearchParams()
    kb = KnowledgeBase(tmp_path)
    cut = len(df) - 24 * 60
    prep0 = prepare("RW", df.iloc[:cut], p)
    g0 = kb.rank(evaluate(prep0, int(cut * 0.7)), "RW")
    g0 = g0.assign(final_mean=g0["final_mean"].abs() + 0.01, stab=1.0)  # force recommendations
    kb.record(g0, "RW", df.index[cut - 1], "run0")
    assert len(kb.recs) > 0
    prep1 = prepare("RW", df, p)
    added = kb.ingest(prep1)
    kappa = kb.calibrate("RW")
    kb.save()
    assert added >= 0
    assert 0.0 <= kappa <= 1.5
    assert (pd.to_datetime(kb.recs["counted_until"], utc=True) == df.index[-1]).all()


# --------------------------------------------------------------------------- block family
def _bars(rows):
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]  # o, h, l, c


def test_breaker_vs_mitigation():
    # k=1 swings. Up-candle at bar 2 makes swing high 12; prior swing low 9 (bar 0..1).
    # Breaker: the leg after the high sweeps below 9, then a close breaks 12.
    o, h, l, c = _bars([
        [10, 10.5, 9.5, 10.2], [10.2, 10.4, 9.0, 9.8], [9.8, 12.0, 9.7, 11.5],
        [11.5, 11.6, 10.0, 10.2], [10.2, 10.3, 8.5, 9.0], [9.0, 10.0, 8.8, 9.9],
        [9.9, 12.6, 9.8, 12.5], [12.5, 12.8, 12.2, 12.6]])
    b, d, lo, hi, ext, brk = F.detect_breaker_mitigation(o, h, l, c, 1, 20)
    k = np.nonzero(d == 1)[0]
    assert k.size and brk[k[0]] and lo[k[0]] == 9.7 and hi[k[0]] == 12.0 and ext[k[0]] == 8.5
    # Mitigation: same shape but the leg low (9.4) holds above the prior swing low (9.0).
    l2 = l.copy()
    l2[4], l2[5] = 9.4, 9.45
    b, d, lo, hi, ext, brk = F.detect_breaker_mitigation(o, h, l2, c, 1, 20)
    k = np.nonzero(d == 1)[0]
    assert k.size and not brk[k[0]]


def test_rejection_block():
    o, h, l, c = _bars([[10, 10.2, 9.8, 10], [10, 10.1, 9.7, 9.9], [9.9, 10.0, 8.0, 9.8],
                        [9.8, 10.3, 9.6, 10.2], [10.2, 10.5, 10.0, 10.4]])
    b, d, lo, hi, ext = F.detect_rejection(o, h, l, c, 1, 0.5)
    k = np.nonzero(d == 1)[0][0]
    assert b[k] == 3 and lo[k] == 8.0 and hi[k] == 9.8  # zone = wick, known at p + k


def test_vacuum_and_propulsion():
    h = np.array([10.2, 10.3, 11.5, 11.6])
    l = np.array([9.8, 9.9, 11.0, 11.1])
    c = np.array([10.0, 10.1, 11.4, 11.5])
    o = np.array([10.0, 10.0, 11.1, 11.4])
    b, d, lo, hi, ext = F.detect_vacuum(h, l, c, o, np.full(4, 0.5), 0.25)
    assert b[0] == 2 and d[0] == 1 and lo[0] == 10.1 and hi[0] == 11.1
    ob_bar = np.array([5, 9])
    flags = F.propulsion_flags(ob_bar, np.array([1, 1]), np.array([10.0, 10.5]),
                               np.array([11.0, 11.5]), np.array([100, 100]))
    assert not flags[0] and flags[1]


def test_all_zone_types_present_and_bits_consistent():
    df = random_walk(24 * 400, seed=8)
    ctx = build_context(df, config.ASSETS["RW"], ResearchParams())
    kinds = set(np.unique(ctx.trig.kind))
    assert {0, 1, 2, 3, 4, 5} <= kinds  # FVG, OB, BB, MB, RB, PB (no gaps in a 24/7 walk)
    for tf in config.HTF:
        anyb = (ctx.trig.bits >> config.BIT[f"{tf}_ANYB"]) & 1
        blocks = np.zeros_like(anyb)
        for bname in config.BLOCK_TYPES:
            blocks |= (ctx.trig.bits >> config.BIT[f"{tf}_{bname}"]) & 1
        assert (anyb == blocks).all()


def test_enumeration_prunes_and_names():
    from ictlab.combos import combo_name, enumerate_combos

    df = random_walk(24 * 300, seed=9)
    ctx = build_context(df, config.ASSETS["RW"], ResearchParams())
    masks, kmasks, raw = enumerate_combos(ctx.trig.bits, ctx.trig.kind, 30)
    assert raw >= len(masks) > 10
    sel = [((ctx.trig.bits & m) == m) & ((np.left_shift(1, ctx.trig.kind) & k) != 0)
           for m, k in zip(masks[:200], kmasks[:200])]
    assert min(int(s.sum()) for s in sel) >= 30
    assert combo_name(int(masks[0]), int(kmasks[0])).startswith("H1:")
