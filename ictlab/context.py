"""Builds 1h entry triggers and their higher-timeframe confluence bits."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

from . import features as F
from .config import CONDITIONS, AssetSpec, ResearchParams
from .data import resample_all

TF_OF = {"M": "M", "W": "W", "D": "D", "H4": "H4"}


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
    kind: np.ndarray  # 0 = FVG, 1 = OB
    bits: np.ndarray  # condition bitmask, bit i -> CONDITIONS[i]


def _project(bar, inv, close_idx, max_age, n1):
    """Map HTF zone lifetimes onto the 1h stream."""
    nh = close_idx.size
    vis_from = close_idx[bar]
    end = np.minimum(inv, bar + max_age if max_age > 0 else nh)
    vis_to = np.where(end >= nh, n1, close_idx[np.minimum(end, nh - 1)])
    return vis_from.astype(np.int64), vis_to.astype(np.int64)


def build_zones(tf_df: pd.DataFrame, close_idx: np.ndarray, n1: int, p: ResearchParams,
                tf: str) -> tuple[Zones, Zones, tuple[np.ndarray, np.ndarray]]:
    o, h, l, c = (tf_df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    a = F.atr(h, l, c, p.atr_len)
    fb, fd, flo, fhi, _, finv = F.detect_fvg(h, l, c, a, p.fvg_min_atr)
    mb, md, ob, od, olo, ohi, _, oinv = F.detect_structure(o, h, l, c, p.swing_k, 20)
    age = p.zone_max_age[tf]
    fv0, fv1 = _project(fb, finv, close_idx, age, n1)
    ov0, ov1 = _project(ob, oinv, close_idx, age, n1)
    return (Zones(fv0, fv1, fd, flo, fhi), Zones(ov0, ov1, od, olo, ohi),
            (close_idx[mb] if mb.size else mb, md))


@njit(cache=True)
def match_zones(tt, td, tlo, thi, zf, zt, zd, zlo, zhi, inside):
    out = np.zeros(tt.size, np.bool_)
    for i in range(tt.size):
        for z in range(zf.size):
            if zd[z] != td[i] or zf[z] > tt[i] or zt[z] <= tt[i]:
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
        # age in 4H bars between the MSB bar and the last closed 4H bar
        b_msb = np.searchsorted(h4_close_idx, msb_vis[j])
        b_now = np.searchsorted(h4_close_idx, tt[i], side="right") - 1
        out[i] = (b_now - b_msb) <= max_age
    return out


def prev_month_levels(mtf: dict, n1: int) -> tuple[np.ndarray, np.ndarray]:
    """Previous completed month high/low for every 1h bar."""
    close_idx = mtf["close_idx"]
    mh = mtf["df"]["high"].to_numpy()
    ml = mtf["df"]["low"].to_numpy()
    month_of = np.searchsorted(close_idx, np.arange(n1), side="left")  # bucket of bar
    prev = month_of - 1
    plo = np.where(prev >= 0, ml[np.clip(prev, 0, None)], np.nan)
    phi = np.where(prev >= 0, mh[np.clip(prev, 0, None)], np.nan)
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
    zones: dict  # (tf, "FVG"/"OB") -> Zones
    liq: tuple[np.ndarray, np.ndarray]
    msb4: tuple[np.ndarray, np.ndarray]


def build_context(h1: pd.DataFrame, spec: AssetSpec, p: ResearchParams) -> AssetContext:
    tfs = resample_all(h1, spec)
    n1 = len(h1)
    o, h, l, c = (h1[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    a1 = F.atr(h, l, c, p.atr_len)
    sh_p, _, sl_p, _ = F.swings_asof(h, l, p.swing_k)

    # 1h entry triggers
    fb, fd, flo, fhi, fext, finv = F.detect_fvg(h, l, c, a1, p.fvg_min_atr)
    _, _, ob, od, olo, ohi, oext, oinv = F.detect_structure(o, h, l, c, p.swing_k, 20)
    t = np.concatenate([fb, ob])
    order = np.argsort(t, kind="stable")
    trig = Triggers(
        t=t[order], dir=np.concatenate([fd, od])[order],
        lo=np.concatenate([flo, olo])[order], hi=np.concatenate([fhi, ohi])[order],
        ext=np.concatenate([fext, oext])[order], inv=np.concatenate([finv, oinv])[order],
        kind=np.concatenate([np.zeros(fb.size, np.int64), np.ones(ob.size, np.int64)])[order],
        bits=np.zeros(t.size, np.int64),
    )

    zones = {}
    msb4 = (np.empty(0, np.int64), np.empty(0, np.int64))
    for tf in ("M", "W", "D", "H4"):
        fz, oz, msb = build_zones(tfs[tf]["df"], tfs[tf]["close_idx"], n1, p, tf)
        zones[(tf, "FVG")] = fz
        zones[(tf, "OB")] = oz
        if tf == "H4":
            msb4 = msb

    plo, phi = prev_month_levels(tfs["M"], n1)
    la, sa = F.liquidity_sweeps(l, h, c, plo, phi, p.liq_lookback_h1)

    inside = p.overlap_mode == "inside"
    bits = np.zeros(trig.t.size, np.int64)
    for bi, name in enumerate(CONDITIONS):
        if name == "M_LIQ":
            ok = np.where(trig.dir == 1, la[trig.t], sa[trig.t])
        elif name == "H4_MSB":
            ok = msb_state(trig.t, trig.dir, msb4[0], msb4[1], tfs["H4"]["close_idx"],
                           p.msb_max_age_h4)
        else:
            tf, kind = name.split("_")
            z = zones[(tf, kind)]
            ok = match_zones(trig.t, trig.dir, trig.lo, trig.hi, z.vis_from, z.vis_to,
                             z.dir, z.lo, z.hi, inside)
        bits |= ok.astype(np.int64) << bi
    trig.bits = bits
    return AssetContext(spec.key, h1, tfs, a1, sl_p, sh_p, trig, zones, (la, sa), msb4)
