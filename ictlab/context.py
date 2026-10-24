"""Builds 1h entry triggers and their higher-timeframe confluence bits."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

from . import features as F
from .config import BIT, BLOCK_TYPES, CONDITIONS, HTF, ZONE_TYPES, AssetSpec, ResearchParams
from .data import resample_all


@dataclass
class Zones:
    vis_from: np.ndarray  # first 1h index at which the zone is known
    vis_to: np.ndarray  # first 1h index at which the zone is no longer valid
    dir: np.ndarray
    lo: np.ndarray
    hi: np.ndarray


@dataclass
class Triggers:
    t: np.ndarray  # 1h bar index at which the entry zone is known
    dir: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    ext: np.ndarray  # pattern extreme (stop reference)
    inv: np.ndarray  # 1h bar at which the entry zone is invalidated
    kind: np.ndarray  # index into ZONE_TYPES
    bits: np.ndarray  # condition bitmask, bit i -> CONDITIONS[i]


def _project(bar, inv, close_idx, max_age, n1):
    """Map HTF zone lifetimes onto the 1h stream."""
    nh = close_idx.size
    if bar.size == 0:
        e = np.empty(0, np.int64)
        return e, e
    vis_from = close_idx[np.minimum(bar, nh - 1)]
    end = np.minimum(inv, bar + max_age if max_age > 0 else nh)
    vis_to = np.where(end >= nh, n1, close_idx[np.minimum(end, nh - 1)])
    return vis_from.astype(np.int64), vis_to.astype(np.int64)


def _ohlc(df: pd.DataFrame):
    return tuple(df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))


def build_zones(tf_df: pd.DataFrame, close_idx: np.ndarray, n1: int, p: ResearchParams,
                tf: str) -> tuple[dict, tuple[np.ndarray, np.ndarray]]:
    o, h, l, c = _ohlc(tf_df)
    a = F.atr(h, l, c, p.atr_len)
    det = F.detect_all(o, h, l, c, a, p)
    age = p.zone_max_age[tf]
    zones = {}
    for z, (bar, dr, lo, hi, _, inv) in det.items():
        v0, v1 = _project(bar, inv, close_idx, age, n1)
        zones[z] = Zones(v0, v1, dr, lo, hi)
    mb, md, *_ = F.detect_structure(o, h, l, c, p.swing_k, 20)
    msb = (close_idx[mb] if mb.size else mb, md)
    return zones, msb


@njit(cache=True)
def match_zones(tt, td, tlo, thi, zf, zt, zd, zlo, zhi, inside):
    out = np.zeros(tt.size, np.bool_)
    if zf.size == 0:
        return out
    # zones sorted by vis_from: only those already visible are scanned
    for i in range(tt.size):
        hi_z = np.searchsorted(zf, tt[i], side="right")
        for z in range(hi_z - 1, -1, -1):
            if zd[z] != td[i] or zt[z] <= tt[i]:
                continue
            if inside:
                tol = 0.05 * (zhi[z] - zlo[z])
                ok = tlo[i] >= zlo[z] - tol and thi[i] <= zhi[z] + tol
            else:
                ok = tlo[i] <= zhi[z] and thi[i] >= zlo[z]
            if ok:
                out[i] = True
                break
    return out


@njit(cache=True)
def msb_state(tt, td, msb_vis, msb_dir, h4_close_idx, max_age):
    """Most recent visible 4H MSB direction equals trade direction and is fresh."""
    out = np.zeros(tt.size, np.bool_)
    j = -1
    for i in range(tt.size):  # triggers are sorted by tt
        while j + 1 < msb_vis.size and msb_vis[j + 1] <= tt[i]:
            j += 1
        if j < 0 or msb_dir[j] != td[i]:
            continue
        b_msb = np.searchsorted(h4_close_idx, msb_vis[j])
        b_now = np.searchsorted(h4_close_idx, tt[i], side="right") - 1
        out[i] = (b_now - b_msb) <= max_age
    return out


def prev_month_levels(mtf: dict, n1: int) -> tuple[np.ndarray, np.ndarray]:
    """Previous completed month high/low for every 1h bar."""
    close_idx = mtf["close_idx"]
    mh = mtf["df"]["high"].to_numpy()
    ml = mtf["df"]["low"].to_numpy()
    month_of = np.searchsorted(close_idx, np.arange(n1), side="left")
    prev = month_of - 1
    ok = (prev >= 0) & (prev < mh.size)
    pc = np.clip(prev, 0, max(mh.size - 1, 0))
    plo = np.where(ok, ml[pc], np.nan)
    phi = np.where(ok, mh[pc], np.nan)
    return plo, phi


@dataclass
class AssetContext:
    key: str
    h1: pd.DataFrame
    tfs: dict
    atr1: np.ndarray
    swing_lo: np.ndarray
    swing_hi: np.ndarray
    trig: Triggers
    zones: dict  # (tf, type) -> Zones
    liq: tuple[np.ndarray, np.ndarray]
    msb4: tuple[np.ndarray, np.ndarray]


def build_triggers(h1: pd.DataFrame, a1: np.ndarray, p: ResearchParams) -> Triggers:
    o, h, l, c = _ohlc(h1)
    det = F.detect_all(o, h, l, c, a1, p)
    parts = [(ZONE_TYPES.index(z), det[z]) for z in ZONE_TYPES]
    t = np.concatenate([d[0] for _, d in parts])
    order = np.argsort(t, kind="stable")
    cat = lambda i: np.concatenate([d[i] for _, d in parts])[order]  # noqa: E731
    kind = np.concatenate([np.full(d[0].size, k, np.int64) for k, d in parts])[order]
    return Triggers(t=t[order], dir=cat(1), lo=cat(2), hi=cat(3), ext=cat(4), inv=cat(5),
                    kind=kind, bits=np.zeros(t.size, np.int64))


def build_context(h1: pd.DataFrame, spec: AssetSpec, p: ResearchParams) -> AssetContext:
    tfs = resample_all(h1, spec)
    n1 = len(h1)
    o, h, l, c = _ohlc(h1)
    a1 = F.atr(h, l, c, p.atr_len)
    sh_p, _, sl_p, _ = F.swings_asof(h, l, p.swing_k)
    trig = build_triggers(h1, a1, p)

    zones = {}
    msb4 = (np.empty(0, np.int64), np.empty(0, np.int64))
    msbw = msb4
    for tf in HTF:
        zs, msb = build_zones(tfs[tf]["df"], tfs[tf]["close_idx"], n1, p, tf)
        for z, v in zs.items():
            srt = np.argsort(v.vis_from, kind="stable")
            zones[(tf, z)] = Zones(v.vis_from[srt], v.vis_to[srt], v.dir[srt], v.lo[srt],
                                   v.hi[srt])
        if tf == "H4":
            msb4 = msb
        if tf == "W":
            msbw = msb

    plo, phi = prev_month_levels(tfs["M"], n1)
    la, sa = F.liquidity_sweeps(l, h, c, plo, phi, p.liq_lookback_h1)

    inside = p.overlap_mode == "inside"
    bits = np.zeros(trig.t.size, np.int64)
    for tf in HTF:
        anyb = np.zeros(trig.t.size, np.bool_)
        for z in ZONE_TYPES:
            zz = zones[(tf, z)]
            ok = match_zones(trig.t, trig.dir, trig.lo, trig.hi, zz.vis_from, zz.vis_to,
                             zz.dir, zz.lo, zz.hi, inside)
            bits |= ok.astype(np.int64) << BIT[f"{tf}_{z}"]
            if z in BLOCK_TYPES:
                anyb |= ok
        bits |= anyb.astype(np.int64) << BIT[f"{tf}_ANYB"]
    liq = np.where(trig.dir == 1, la[trig.t], sa[trig.t])
    bits |= liq.astype(np.int64) << BIT["M_LIQ"]
    msb = msb_state(trig.t, trig.dir, msb4[0], msb4[1], tfs["H4"]["close_idx"], p.msb_max_age_h4)
    bits |= msb.astype(np.int64) << BIT["H4_MSB"]
    for name, ok in rule_filters(h1, tfs, trig, msbw).items():
        bits |= ok.astype(np.int64) << BIT[name]
    trig.bits = bits
    return AssetContext(spec.key, h1, tfs, a1, sl_p, sh_p, trig, zones, (la, sa), msb4)


KILLZONES_NY = ((2, 5), (7, 11))  # London open, New York morning (NY local hours)


def rule_filters(h1: pd.DataFrame, tfs: dict, trig: Triggers,
                 msbw: tuple[np.ndarray, np.ndarray]) -> dict[str, np.ndarray]:
    """Trend, killzone and premium/discount filters, known at the trigger bar close."""
    t, d = trig.t, trig.dir
    out = {}
    # BIAS_D: last closed daily bar's close vs EMA50 of daily closes
    dd = tfs["D"]
    dc = dd["df"]["close"]
    side = np.sign((dc - dc.ewm(span=50, adjust=False).mean()).to_numpy())
    k = np.searchsorted(dd["close_idx"], t, side="right") - 1
    out["BIAS_D"] = (k >= 50) & (side[np.clip(k, 0, None)] == d)
    # BIAS_W: latest visible weekly MSB in the trade direction (no freshness limit)
    out["BIAS_W"] = msb_state(t, d, msbw[0], msbw[1], tfs["W"]["close_idx"], 10**9)
    # KZ: the entry bar (the hour after the trigger closes) opens inside a killzone
    hrs = (h1.index[t] + pd.Timedelta(hours=1)).tz_convert("America/New_York").hour.to_numpy()
    kz = np.zeros(t.size, bool)
    for a, b in KILLZONES_NY:
        kz |= (hrs >= a) & (hrs < b)
    out["KZ"] = kz
    # PD: entry-zone midpoint vs 50 % of the previous completed week's range
    w = tfs["W"]
    wk = np.searchsorted(w["close_idx"], t, side="right") - 1
    wh = w["df"]["high"].to_numpy()
    wl = w["df"]["low"].to_numpy()
    wc = np.clip(wk, 0, None)
    eq = 0.5 * (wh[wc] + wl[wc])
    mid = 0.5 * (trig.lo + trig.hi)
    out["PD"] = (wk >= 0) & np.where(d == 1, mid < eq, mid > eq)
    return out


def condition_rates(trig: Triggers) -> dict[str, float]:
    return {c: float(((trig.bits >> i) & 1).mean()) for i, c in enumerate(CONDITIONS)}
