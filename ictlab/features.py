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
