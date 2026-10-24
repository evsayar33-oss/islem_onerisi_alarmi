"""Trade simulation: one outcome tensor per trigger for every execution config.

Axes: [trigger, entry_mode, stop, rr, mgmt]. Conservative intrabar rules:
    - stop and target touched in the same bar -> stop
    - on a limit fill bar only the stop can be hit (target ignored)
    - gaps through stop / target fill at the bar open
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange

from .config import ENTRY_CODE, ENTRY_MODES, KIND_CODE, MGMT, RR_GRID, STOPS, ResearchParams


def grid_arrays():
    sk = np.array([KIND_CODE[s.kind] for s in STOPS], np.int64)
    sv = np.array([s.value for s in STOPS], np.float64)
    em = np.array([ENTRY_CODE[e] for e in ENTRY_MODES], np.int64)
    rr = np.array(RR_GRID, np.float64)
    mg = np.array([0 if m == "none" else 1 for m in MGMT], np.int64)
    return em, sk, sv, rr, mg


@njit(cache=True)
def _fill(tt, d, zlo, zhi, inv, mode, o, h, l, c, valid):
    """Return (fill_bar, entry_price) or (-1, nan)."""
    n = c.size
    if mode == 0:
        return tt, c[tt]
    px = (zhi if d == 1 else zlo) if mode == 1 else 0.5 * (zlo + zhi)
    last = min(n - 1, tt + valid)
    for b in range(tt + 1, last + 1):
        if d == 1:
            if l[b] <= px:
                return b, min(o[b], px)
            if c[b] < zlo:
                return -1, np.nan
        else:
            if h[b] >= px:
                return b, max(o[b], px)
            if c[b] > zhi:
                return -1, np.nan
    return -1, np.nan


@njit(cache=True)
def _path(d, fb, entry, stop, target, be, o, h, l, c, max_hold, is_limit):
    """Walk bars after the fill; return (exit_price, exit_bar)."""
    n = c.size
    risk = abs(entry - stop)
    s = stop
    if is_limit:
        if (d == 1 and l[fb] <= s) or (d == -1 and h[fb] >= s):
            return s, fb
    last = min(n - 1, fb + max_hold)
    for b in range(fb + 1, last + 1):
        if d == 1:
            if o[b] <= s:
                return o[b], b
            if l[b] <= s:
                return s, b
            if o[b] >= target:
                return o[b], b
            if h[b] >= target:
                return target, b
            if be == 1 and h[b] >= entry + risk:
                s = max(s, entry)
        else:
            if o[b] >= s:
                return o[b], b
            if h[b] >= s:
                return s, b
            if o[b] <= target:
                return o[b], b
            if l[b] <= target:
                return target, b
            if be == 1 and l[b] <= entry - risk:
                s = min(s, entry)
    return c[last], last


@njit(cache=True, parallel=True)
def simulate(tt, td, tlo, thi, text, tinv, o, h, l, c, a1, swing_lo, swing_hi,
             em, sk, sv, rr, mg, valid, max_hold, min_risk_atr, cost_bps):
    nt = tt.size
    R = np.full((nt, em.size, sk.size, rr.size, mg.size), np.nan, np.float32)
    XB = np.full((nt, em.size, sk.size, rr.size, mg.size), -1, np.int32)
    FB = np.full((nt, em.size), -1, np.int32)
    for i in prange(nt):
        t = tt[i]
        d = td[i]
        a = a1[t]
        if np.isnan(a) or a <= 0:
            continue
        for e in range(em.size):
            fb, entry = _fill(t, d, tlo[i], thi[i], tinv[i], em[e], o, h, l, c, valid)
            if fb < 0 or fb >= c.size - 1:
                continue
            FB[i, e] = fb
            for s in range(sk.size):
                kind = sk[s]
                v = sv[s]
                if kind == 0:
                    stop = tlo[i] - v * a if d == 1 else thi[i] + v * a
                elif kind == 1:
                    stop = entry - v * a if d == 1 else entry + v * a
                elif kind == 2:
                    ref = swing_lo[t] if d == 1 else swing_hi[t]
                    if np.isnan(ref):
                        continue
                    stop = ref - v * a if d == 1 else ref + v * a
                else:
                    stop = text[i] - v * a if d == 1 else text[i] + v * a
                risk = (entry - stop) if d == 1 else (stop - entry)
                if risk < min_risk_atr * a:
                    continue
                cost_r = cost_bps * 1e-4 * entry / risk
                for r in range(rr.size):
                    target = entry + rr[r] * risk if d == 1 else entry - rr[r] * risk
                    for m in range(mg.size):
                        xp, xb = _path(d, fb, entry, stop, target, mg[m], o, h, l, c,
                                       max_hold, em[e] != 0)
                        pnl = (xp - entry) if d == 1 else (entry - xp)
                        R[i, e, s, r, m] = pnl / risk - cost_r
                        XB[i, e, s, r, m] = xb
    return R, XB, FB


def run_simulation(ctx, p: ResearchParams, cost_bps: float):
    h1 = ctx.h1
    o, h, l, c = (h1[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    em, sk, sv, rr, mg = grid_arrays()
    tr = ctx.trig
    return simulate(tr.t, tr.dir, tr.lo, tr.hi, tr.ext, tr.inv, o, h, l, c, ctx.atr1,
                    ctx.swing_lo, ctx.swing_hi, em, sk, sv, rr, mg, p.limit_valid_bars,
                    p.max_hold_bars, p.min_risk_atr, cost_bps)
