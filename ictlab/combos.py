"""Combination engine: every subset of confluence conditions x every execution config.

A combo is (condition bitmask, entry type). It selects the triggers whose bits
contain the mask. Trades are taken one at a time per asset (no overlap), so each
(combo, config) is a realistic single-strategy equity stream.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from numba import njit, prange

from .config import CONDITIONS, ENTRY_MODES, ENTRY_TYPES, MGMT, RR_GRID, STOPS

NSTAT = 18
STAT_COLS = [
    "n_is", "win_is", "sum_is", "sum2_is", "gw_is", "gl_is", "dd_is",
    "n_oos", "win_oos", "sum_oos", "sum2_oos", "gw_oos", "gl_oos", "dd_oos",
    "w_sum", "w_sumr", "w_sumr2", "dd_all",
]


def config_table() -> pd.DataFrame:
    rows = []
    for e, s, r, m in itertools.product(range(len(ENTRY_MODES)), range(len(STOPS)),
                                        range(len(RR_GRID)), range(len(MGMT))):
        rows.append((e, s, r, m, ENTRY_MODES[e], STOPS[s].name, RR_GRID[r], MGMT[m]))
    return pd.DataFrame(rows, columns=["e", "s", "r", "m", "entry", "stop", "rr", "mgmt"])


def combo_name(mask: int, etype: int) -> str:
    conds = [c for i, c in enumerate(CONDITIONS) if mask >> i & 1]
    return "+".join(conds + [f"H1_{ENTRY_TYPES[etype]}"])


def enumerate_combos(bits: np.ndarray, kind: np.ndarray, min_trades: int, max_size: int):
    """All (mask, entry_type) pairs with at least `min_trades` raw triggers."""
    nc = len(CONDITIONS)
    out = []
    for size in range(0, min(max_size, nc) + 1):
        for subset in itertools.combinations(range(nc), size):
            mask = 0
            for b in subset:
                mask |= 1 << b
            hit = (bits & mask) == mask
            for et in range(len(ENTRY_TYPES)):
                sel = hit if et == 2 else hit & (kind == et)
                if int(sel.sum()) >= min_trades:
                    out.append((mask, et))
    return np.array([m for m, _ in out], np.int64), np.array([e for _, e in out], np.int64)


def fill_order(FB: np.ndarray) -> np.ndarray:
    """Per entry mode: trigger indices sorted by fill bar (unfilled last).

    Trades must be accepted in *fill* order. Processing them in trigger order
    leaks the future: a pending limit that fills later would block a trade that
    filled earlier, and whether it fills depends on the path after that trade.
    """
    key = np.where(FB < 0, np.iinfo(np.int32).max, FB)
    return np.argsort(key, axis=0, kind="stable").T.copy()


@njit(cache=True, parallel=True)
def eval_all(masks, etypes, bits, kind, R, XB, FB, cfg_e, order, split_bar, end_bar, halflife,
             end_cut):
    nk = masks.size
    nt, nc = R.shape
    ne = order.shape[0]
    out = np.zeros((nk, nc, NSTAT), np.float32)
    for k in prange(nk):
        mask = masks[k]
        et = etypes[k]
        idx_e = np.empty((ne, nt), np.int64)
        m_e = np.zeros(ne, np.int64)
        for e in range(ne):
            for q in range(nt):
                i = order[e, q]
                if FB[i, e] < 0:
                    break
                if (bits[i] & mask) == mask and (et == 2 or kind[i] == et):
                    idx_e[e, m_e[e]] = i
                    m_e[e] += 1
        for cfg in range(nc):
            e = cfg_e[cfg]
            idx = idx_e[e]
            m = m_e[e]
            last_exit = -1
            eq = 0.0
            peak = 0.0
            eq_p = np.zeros(2)
            peak_p = np.zeros(2)
            st = np.zeros(NSTAT)
            for q in range(m):
                i = idx[q]
                r = R[i, cfg]
                if np.isnan(r):
                    continue
                fb = FB[i, e]
                if fb >= end_cut:
                    break
                if fb <= last_exit:
                    continue
                last_exit = XB[i, cfg]
                part = 0 if fb < split_bar else 1
                o = part * 7
                st[o] += 1.0
                if r > 0:
                    st[o + 1] += 1.0
                    st[o + 4] += r
                else:
                    st[o + 5] -= r
                st[o + 2] += r
                st[o + 3] += r * r
                eq_p[part] += r
                peak_p[part] = max(peak_p[part], eq_p[part])
                st[o + 6] = max(st[o + 6], peak_p[part] - eq_p[part])
                w = 0.5 ** ((end_bar - fb) / halflife)
                st[14] += w
                st[15] += w * r
                st[16] += w * r * r
                eq += r
                peak = max(peak, eq)
                st[17] = max(st[17], peak - eq)
            for s in range(NSTAT):
                out[k, cfg, s] = st[s]
    return out


def to_frame(stats: np.ndarray, masks: np.ndarray, etypes: np.ndarray,
             min_trades: int) -> pd.DataFrame:
    nk, nc, _ = stats.shape
    flat = stats.reshape(nk * nc, NSTAT)
    n_tot = flat[:, 0] + flat[:, 7]
    keep = np.nonzero(n_tot >= min_trades)[0]
    df = pd.DataFrame(flat[keep].astype(np.float64), columns=STAT_COLS)
    df["combo_id"] = keep // nc
    df["cfg"] = keep % nc
    df["mask"] = masks[df["combo_id"].to_numpy()]
    df["etype"] = etypes[df["combo_id"].to_numpy()]
    return df


def replay_trades(ctx, R, XB, FB, mask: int, etype: int, cfg: int, cfg_e: int) -> pd.DataFrame:
    """Trade list for one (combo, config); same rules as `eval_all`."""
    tr = ctx.trig
    sel = ((tr.bits & mask) == mask) & ((tr.kind == etype) | (etype == 2)) & (FB[:, cfg_e] >= 0)
    rows = []
    last_exit = -1
    idx = ctx.h1.index
    cand = np.nonzero(sel)[0]
    for i in cand[np.argsort(FB[cand, cfg_e], kind="stable")]:
        r = R[i, cfg]
        fb = FB[i, cfg_e]
        if np.isnan(r) or fb <= last_exit:
            continue
        last_exit = XB[i, cfg]
        rows.append((idx[fb], idx[last_exit], int(tr.dir[i]), float(r), int(fb), int(i)))
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "dir", "R", "fill_bar", "trig"])
