"""Price-action primitives (numba): ATR, swings, FVG, order blocks, MSB, liquidity sweeps.

Every event carries the bar index at which it becomes *known* (bar close), so the
higher-timeframe projection in `context.py` is free of lookahead.
"""

from __future__ import annotations

import numpy as np
from numba import njit

BULL, BEAR = 1, -1


@njit(cache=True)
def atr(h, l, c, n):
    out = np.full(h.size, np.nan)
    if h.size == 0:
        return out
    tr = np.empty(h.size)
    tr[0] = h[0] - l[0]
    for i in range(1, h.size):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    if h.size < n:
        acc = 0.0
        for i in range(h.size):
            acc += tr[i]
            out[i] = acc / (i + 1)
        return out
    s = 0.0
    for i in range(n):
        s += tr[i]
        out[i] = s / (i + 1)
    for i in range(n, h.size):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


@njit(cache=True)
def swings_asof(h, l, k):
    """Last confirmed fractal swing high/low known at each bar close.

    A pivot at bar p is confirmed at bar p + k. Returns price and pivot index arrays.
    """
    n = h.size
    sh_p = np.full(n, np.nan)
    sh_i = np.full(n, -1, np.int64)
    sl_p = np.full(n, np.nan)
    sl_i = np.full(n, -1, np.int64)
    cur_hp, cur_hi, cur_lp, cur_li = np.nan, -1, np.nan, -1
    for t in range(n):
        p = t - k
        if p - k >= 0:
            is_h = True
            is_l = True
            for j in range(p - k, p + k + 1):
                if j == p:
                    continue
                if j < p:
                    if h[j] >= h[p]:
                        is_h = False
                    if l[j] <= l[p]:
                        is_l = False
                else:
                    if h[j] > h[p]:
                        is_h = False
                    if l[j] < l[p]:
                        is_l = False
            if is_h:
                cur_hp, cur_hi = h[p], p
            if is_l:
                cur_lp, cur_li = l[p], p
        sh_p[t], sh_i[t], sl_p[t], sl_i[t] = cur_hp, cur_hi, cur_lp, cur_li
    return sh_p, sh_i, sl_p, sl_i


@njit(cache=True)
def detect_fvg(h, l, c, atr_arr, min_atr):
    """Three-candle fair value gaps.

    Bullish at bar i: low[i] > high[i-2] -> zone [high[i-2], low[i]].
    Bearish at bar i: high[i] < low[i-2] -> zone [high[i], low[i-2]].
    Invalidated at the first later close beyond the distal edge.
    Returns (bar, dir, lo, hi, pattern_extreme, invalid_bar).
    """
    n = h.size
    cap = n
    bar = np.empty(cap, np.int64)
    dr = np.empty(cap, np.int64)
    lo = np.empty(cap)
    hi = np.empty(cap)
    ext = np.empty(cap)
    inv = np.empty(cap, np.int64)
    m = 0
    for i in range(2, n):
        a = atr_arr[i]
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= min_atr * a:
            bar[m], dr[m], lo[m], hi[m] = i, BULL, h[i - 2], l[i]
            ext[m] = min(l[i - 2], min(l[i - 1], l[i]))
            m += 1
        elif h[i] < l[i - 2] and (l[i - 2] - h[i]) >= min_atr * a:
            bar[m], dr[m], lo[m], hi[m] = i, BEAR, h[i], l[i - 2]
            ext[m] = max(h[i - 2], max(h[i - 1], h[i]))
            m += 1
    for z in range(m):
        inv[z] = n
        for j in range(bar[z] + 1, n):
            if (dr[z] == BULL and c[j] < lo[z]) or (dr[z] == BEAR and c[j] > hi[z]):
                inv[z] = j
                break
    return bar[:m], dr[:m], lo[:m], hi[:m], ext[:m], inv[:m]


@njit(cache=True)
def detect_structure(o, h, l, c, k, lookback):
    """Market structure breaks and the order blocks that caused them.

    Bullish MSB at bar j: close[j] breaks the last confirmed, unbroken swing high.
    The bullish order block is the last down-close candle in the leg that produced
    the break (searched back up to `lookback` bars, not before the swing low that
    started the leg). Bearish is symmetric.
    Returns (msb_bar, msb_dir, ob_bar, ob_dir, ob_lo, ob_hi, ob_ext, ob_inv).
    """
    n = h.size
    sh_p, sh_i, sl_p, sl_i = swings_asof(h, l, k)
    msb_bar = np.empty(n, np.int64)
    msb_dir = np.empty(n, np.int64)
    ob_bar = np.empty(n, np.int64)
    ob_dir = np.empty(n, np.int64)
    ob_lo = np.empty(n)
    ob_hi = np.empty(n)
    ob_ext = np.empty(n)
    ob_inv = np.empty(n, np.int64)
    nm = 0
    no = 0
    used_h = -1
    used_l = -1
    for j in range(1, n):
        # Swing known at the previous close.
        hp, hi_ = sh_p[j - 1], sh_i[j - 1]
        lp, li_ = sl_p[j - 1], sl_i[j - 1]
        if hi_ >= 0 and hi_ != used_h and c[j] > hp:
            used_h = hi_
            msb_bar[nm], msb_dir[nm] = j, BULL
            nm += 1
            start = max(j - lookback, li_ if li_ >= 0 else 0)
            for q in range(j - 1, start - 1, -1):
                if c[q] < o[q]:
                    ob_bar[no], ob_dir[no] = j, BULL
                    ob_lo[no], ob_hi[no] = l[q], h[q]
                    e = l[q]
                    for r in range(q, j + 1):
                        e = min(e, l[r])
                    ob_ext[no] = e
                    no += 1
                    break
        if li_ >= 0 and li_ != used_l and c[j] < lp:
            used_l = li_
            msb_bar[nm], msb_dir[nm] = j, BEAR
            nm += 1
            start = max(j - lookback, hi_ if hi_ >= 0 else 0)
            for q in range(j - 1, start - 1, -1):
                if c[q] > o[q]:
                    ob_bar[no], ob_dir[no] = j, BEAR
                    ob_lo[no], ob_hi[no] = l[q], h[q]
                    e = h[q]
                    for r in range(q, j + 1):
                        e = max(e, h[r])
                    ob_ext[no] = e
                    no += 1
                    break
    for z in range(no):
        ob_inv[z] = n
        for j in range(ob_bar[z] + 1, n):
            if (ob_dir[z] == BULL and c[j] < ob_lo[z]) or (ob_dir[z] == BEAR and c[j] > ob_hi[z]):
                ob_inv[z] = j
                break
    return (msb_bar[:nm], msb_dir[:nm], ob_bar[:no], ob_dir[:no], ob_lo[:no],
            ob_hi[:no], ob_ext[:no], ob_inv[:no])


@njit(cache=True)
def liquidity_sweeps(l, h, c, prev_lo, prev_hi, lookback):
    """Monthly liquidity sweep state on the 1h stream.

    prev_lo / prev_hi: previous *completed* month low / high for every 1h bar.
    A bullish sweep happens when price trades below the previous month low; the
    long context is active within `lookback` bars of the sweep on every bar that
    closes back above the swept level (reclaim). Bearish is symmetric.
    Returns (long_active, short_active).
    """
    n = l.size
    la = np.zeros(n, np.bool_)
    sa = np.zeros(n, np.bool_)
    last_bs, lvl_bs = -10**9, np.nan
    last_ss, lvl_ss = -10**9, np.nan
    for t in range(n):
        if not np.isnan(prev_lo[t]) and l[t] < prev_lo[t]:
            last_bs, lvl_bs = t, prev_lo[t]
        if not np.isnan(prev_hi[t]) and h[t] > prev_hi[t]:
            last_ss, lvl_ss = t, prev_hi[t]
        la[t] = (t - last_bs) <= lookback and c[t] > lvl_bs
        sa[t] = (t - last_ss) <= lookback and c[t] < lvl_ss
    return la, sa


# --------------------------------------------------------------------------- ICT block family
# Type codes shared by zones, triggers and condition bits.
ZONE_TYPES = ("FVG", "OB", "BB", "MB", "RB", "PB", "VB")
BLOCK_NAMES = {
    "FVG": "Fair value gap", "OB": "Order block", "BB": "Breaker block",
    "MB": "Mitigation block", "RB": "Rejection block", "PB": "Propulsion block",
    "VB": "Vacuum block",
}


@njit(cache=True)
def _invalidate(bar, dr, lo, hi, c):
    n = c.size
    inv = np.full(bar.size, n, np.int64)
    for z in range(bar.size):
        for j in range(bar[z] + 1, n):
            if (dr[z] == BULL and c[j] < lo[z]) or (dr[z] == BEAR and c[j] > hi[z]):
                inv[z] = j
                break
    return inv


@njit(cache=True)
def detect_breaker_mitigation(o, h, l, c, k, lookback):
    """Breaker and mitigation blocks at each market structure break.

    Bullish case at MSB bar j (close breaks the swing high at index ih):
      zone      = last up-close candle at or before ih (the candle that made the high
                  before the decline);
      leg low   = lowest low between ih and j;
      breaker   = leg low swept the previous swing low (sell-side liquidity taken);
      mitigation= leg low held above it (failure swing, higher low).
    Bearish is symmetric. Returns (bar, dir, lo, hi, ext, is_breaker).
    """
    n = h.size
    sh_p, sh_i, sl_p, sl_i = swings_asof(h, l, k)
    bar = np.empty(n, np.int64)
    dr = np.empty(n, np.int64)
    lo = np.empty(n)
    hi = np.empty(n)
    ext = np.empty(n)
    brk = np.empty(n, np.bool_)
    m = 0
    used_h = -1
    used_l = -1
    for j in range(1, n):
        hp, ih = sh_p[j - 1], sh_i[j - 1]
        lp, il = sl_p[j - 1], sl_i[j - 1]
        if ih >= 0 and ih != used_h and c[j] > hp:
            used_h = ih
            leg = l[ih]
            for r in range(ih, j + 1):
                leg = min(leg, l[r])
            prior = sl_p[ih]
            if not np.isnan(prior):
                for q in range(ih, max(ih - lookback, 0) - 1, -1):
                    if c[q] > o[q]:
                        bar[m], dr[m], lo[m], hi[m], ext[m] = j, BULL, l[q], h[q], leg
                        brk[m] = leg < prior
                        m += 1
                        break
        if il >= 0 and il != used_l and c[j] < lp:
            used_l = il
            leg = h[il]
            for r in range(il, j + 1):
                leg = max(leg, h[r])
            prior = sh_p[il]
            if not np.isnan(prior):
                for q in range(il, max(il - lookback, 0) - 1, -1):
                    if c[q] < o[q]:
                        bar[m], dr[m], lo[m], hi[m], ext[m] = j, BEAR, l[q], h[q], leg
                        brk[m] = leg > prior
                        m += 1
                        break
    return bar[:m], dr[:m], lo[:m], hi[:m], ext[:m], brk[:m]


@njit(cache=True)
def detect_rejection(o, h, l, c, k, min_wick):
    """Rejection blocks: long-wick candles that form a confirmed swing point.

    Bullish: swing low whose lower wick >= min_wick of the range; zone = [low, body low].
    Known when the pivot is confirmed (k bars later).
    """
    n = h.size
    bar = np.empty(n, np.int64)
    dr = np.empty(n, np.int64)
    lo = np.empty(n)
    hi = np.empty(n)
    ext = np.empty(n)
    m = 0
    for p in range(k, n - k):
        rng = h[p] - l[p]
        if rng <= 0:
            continue
        is_h = True
        is_l = True
        for j in range(p - k, p + k + 1):
            if j == p:
                continue
            if (j < p and h[j] >= h[p]) or (j > p and h[j] > h[p]):
                is_h = False
            if (j < p and l[j] <= l[p]) or (j > p and l[j] < l[p]):
                is_l = False
        body_lo = min(o[p], c[p])
        body_hi = max(o[p], c[p])
        if is_l and (body_lo - l[p]) >= min_wick * rng:
            bar[m], dr[m], lo[m], hi[m], ext[m] = p + k, BULL, l[p], body_lo, l[p]
            m += 1
        if is_h and (h[p] - body_hi) >= min_wick * rng:
            bar[m], dr[m], lo[m], hi[m], ext[m] = p + k, BEAR, body_hi, h[p], h[p]
            m += 1
    return bar[:m], dr[:m], lo[:m], hi[:m], ext[:m]


@njit(cache=True)
def detect_vacuum(h, l, c, o, atr_arr, min_gap_atr):
    """Vacuum blocks: price gaps between the previous close and the next open."""
    n = h.size
    bar = np.empty(n, np.int64)
    dr = np.empty(n, np.int64)
    lo = np.empty(n)
    hi = np.empty(n)
    ext = np.empty(n)
    m = 0
    for i in range(1, n):
        a = atr_arr[i - 1]
        g = o[i] - c[i - 1]
        if g >= min_gap_atr * a and a > 0:
            bar[m], dr[m], lo[m], hi[m], ext[m] = i, BULL, c[i - 1], o[i], min(l[i], c[i - 1])
            m += 1
        elif -g >= min_gap_atr * a and a > 0:
            bar[m], dr[m], lo[m], hi[m], ext[m] = i, BEAR, o[i], c[i - 1], max(h[i], c[i - 1])
            m += 1
    return bar[:m], dr[:m], lo[:m], hi[:m], ext[:m]


@njit(cache=True)
def propulsion_flags(ob_bar, ob_dir, ob_lo, ob_hi, ob_inv):
    """An order block is a propulsion block when it trades into an earlier, still
    valid order block of the same direction (re-accumulation inside an OB)."""
    out = np.zeros(ob_bar.size, np.bool_)
    for z in range(ob_bar.size):
        for y in range(z):
            if ob_dir[y] != ob_dir[z] or ob_bar[y] >= ob_bar[z] or ob_inv[y] <= ob_bar[z]:
                continue
            if ob_lo[z] <= ob_hi[y] and ob_hi[z] >= ob_lo[y]:
                out[z] = True
                break
    return out


def detect_all(o, h, l, c, atr_arr, p) -> dict:
    """Every zone type on one timeframe -> {type: (bar, dir, lo, hi, ext, inv)}."""
    out = {}
    fb, fd, flo, fhi, fext, finv = detect_fvg(h, l, c, atr_arr, p.fvg_min_atr)
    out["FVG"] = (fb, fd, flo, fhi, fext, finv)
    _, _, ob, od, olo, ohi, oext, oinv = detect_structure(o, h, l, c, p.swing_k, 20)
    out["OB"] = (ob, od, olo, ohi, oext, oinv)
    pf = propulsion_flags(ob, od, olo, ohi, oinv)
    out["PB"] = (ob[pf], od[pf], olo[pf], ohi[pf], oext[pf], oinv[pf])
    bb, bd, blo, bhi, bext, brk = detect_breaker_mitigation(o, h, l, c, p.swing_k, 20)
    binv = _invalidate(bb, bd, blo, bhi, c)
    out["BB"] = (bb[brk], bd[brk], blo[brk], bhi[brk], bext[brk], binv[brk])
    mm = ~brk
    out["MB"] = (bb[mm], bd[mm], blo[mm], bhi[mm], bext[mm], binv[mm])
    rb, rd, rlo, rhi, rext = detect_rejection(o, h, l, c, p.swing_k, p.rejection_wick)
    out["RB"] = (rb, rd, rlo, rhi, rext, _invalidate(rb, rd, rlo, rhi, c))
    vb, vd, vlo, vhi, vext = detect_vacuum(h, l, c, o, atr_arr, p.vacuum_gap_atr)
    out["VB"] = (vb, vd, vlo, vhi, vext, _invalidate(vb, vd, vlo, vhi, c))
    return out
