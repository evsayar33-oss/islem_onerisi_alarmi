"""Combination engine.

A combo = one choice per higher-timeframe slot (M, W, D, H4: none / FVG / one block
type / any block / FVG inside a block), the M_LIQ and H4_MSB flags, and a 1h entry
filter (FVG, one block type, any block, anything). Enumeration is exhaustive with
pruning: a branch stops as soon as it has fewer than `min_trades` triggers, because
adding conditions can only remove triggers. Combos that select the identical
trigger set are evaluated once.

Each combo is evaluated on every execution config (entry x stop x RR x management);
the kernel keeps the best `topk` configs per combo and streams the moments that the
empirical-Bayes prior and the deflated Sharpe hurdle need over *all* trials.
Trades are taken one at a time, accepted in fill order.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from numba import njit, prange

from .config import (BIT, CONDITIONS, ENTRY_FILTERS, ENTRY_MODES, FILTERS, HTF, MGMT, RR_GRID,
                     STOPS, filter_options, slot_options)

NSTAT = 18
STAT_COLS = [
    "n_is", "win_is", "sum_is", "sum2_is", "gw_is", "gl_is", "dd_is",
    "n_oos", "win_oos", "sum_oos", "sum2_oos", "gw_oos", "gl_oos", "dd_oos",
    "w_sum", "w_sumr", "w_sumr2", "dd_all",
]
VAR_FLOOR = 0.25
NMOM = 7  # count, sum w, sum w*m, sum w*m^2, sum w^2, sum sr, sum sr^2  (w = 1/se^2)


def config_table() -> pd.DataFrame:
    rows = []
    for e, s, r, m in itertools.product(range(len(ENTRY_MODES)), range(len(STOPS)),
                                        range(len(RR_GRID)), range(len(MGMT))):
        rows.append((e, s, r, m, ENTRY_MODES[e], STOPS[s].name, RR_GRID[r], MGMT[m]))
    return pd.DataFrame(rows, columns=["e", "s", "r", "m", "entry", "stop", "rr", "mgmt"])


def rr_neighbours(cfgs: pd.DataFrame) -> np.ndarray:
    """Config index of RR-1 and RR+1 (same entry/stop/mgmt), -1 if none."""
    key = {(e, s, r, m): i for i, (e, s, r, m) in enumerate(cfgs[["e", "s", "r", "m"]].values)}
    out = np.full((len(cfgs), 2), -1, np.int64)
    for i, (e, s, r, m) in enumerate(cfgs[["e", "s", "r", "m"]].values):
        out[i, 0] = key.get((e, s, r - 1, m), -1)
        out[i, 1] = key.get((e, s, r + 1, m), -1)
    return out


# --------------------------------------------------------------------------- naming
def combo_name(mask: int, kmask: int) -> str:
    parts = []
    for tf in HTF:
        sel = [name for name, m in slot_options(tf)[1:] if m == (mask & _tf_bits(tf))]
        if sel:
            parts.append(f"{tf}:{sel[0]}")
    if mask >> BIT["M_LIQ"] & 1:
        parts.append("M:LIQ")
    if mask >> BIT["H4_MSB"] & 1:
        parts.append("H4:MSB")
    f = _filter_name(mask)
    if f != "-":
        parts.append(f"F:{f}")
    entry = next((k for k, v in ENTRY_FILTERS.items() if v == kmask), f"k{kmask}")
    parts.append(f"H1:{entry}")
    return " | ".join(parts)


def _tf_bits(tf: str) -> int:
    """Zone bits of one timeframe slot (the M_LIQ / H4_MSB flags are separate)."""
    return sum(1 << BIT[c] for c in CONDITIONS
               if c.startswith(f"{tf}_") and c not in ("M_LIQ", "H4_MSB"))


def _filter_name(mask: int) -> str:
    fb = sum(1 << BIT[f] for f in FILTERS)
    sel = [name for name, m in filter_options() if m == (mask & fb)]
    return sel[0] if sel else "?"


def parse_slots(mask: int) -> dict[str, str]:
    out = {}
    for tf in HTF:
        sel = [name for name, m in slot_options(tf) if m == (mask & _tf_bits(tf))]
        out[tf] = sel[0] if sel else "?"
    out["LIQ"] = bool(mask >> BIT["M_LIQ"] & 1)
    out["MSB"] = bool(mask >> BIT["H4_MSB"] & 1)
    out["FILTER"] = _filter_name(mask)
    return out


# --------------------------------------------------------------------------- enumeration
def enumerate_combos(bits: np.ndarray, kind: np.ndarray, min_trades: int,
                     max_slots: int = 6) -> tuple[np.ndarray, np.ndarray, int]:
    """Exhaustive pruned DFS. Returns (masks, kmasks, n_raw_candidates)."""
    slots = [slot_options(tf) for tf in HTF]
    slots.append([("-", 0), ("LIQ", 1 << BIT["M_LIQ"])])
    slots.append([("-", 0), ("MSB", 1 << BIT["H4_MSB"])])
    slots.append(filter_options())
    masks, kmasks, seen = [], [], set()
    raw = 0
    kbit = np.left_shift(1, kind)

    def dfs(level, idx, mask, used, kmask):
        nonlocal raw
        if level == len(slots):
            raw += 1
            key = (idx.size, int(idx.sum()), int((idx * idx).sum() % 1_000_000_007))
            if key not in seen:
                seen.add(key)
                masks.append(mask)
                kmasks.append(kmask)
            return
        for _, m in slots[level]:
            if m == 0:
                dfs(level + 1, idx, mask, used, kmask)
                continue
            if used >= max_slots:
                continue
            sub = idx[(bits[idx] & m) == m]
            if sub.size >= min_trades:
                dfs(level + 1, sub, mask | m, used + 1, kmask)

    for _, km in ENTRY_FILTERS.items():
        idx = np.nonzero(kbit & km)[0]
        if idx.size >= min_trades:
            dfs(0, idx, 0, 0, km)
    return np.array(masks, np.int64), np.array(kmasks, np.int64), raw


# --------------------------------------------------------------------------- kernel
@njit(cache=True)
def _combo_stats(idx_e, m_e, R, XB, FB, cfg_e, split_bar, end_bar, halflife, end_cut, nc):
    st_all = np.zeros((nc, NSTAT))
    for cfg in range(nc):
        e = cfg_e[cfg]
        idx = idx_e[e]
        m = m_e[e]
        last_exit = -1
        eq = 0.0
        peak = 0.0
        eq_p = np.zeros(2)
        peak_p = np.zeros(2)
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
            st_all[cfg, o] += 1.0
            if r > 0:
                st_all[cfg, o + 1] += 1.0
                st_all[cfg, o + 4] += r
            else:
                st_all[cfg, o + 5] -= r
            st_all[cfg, o + 2] += r
            st_all[cfg, o + 3] += r * r
            eq_p[part] += r
            peak_p[part] = max(peak_p[part], eq_p[part])
            st_all[cfg, o + 6] = max(st_all[cfg, o + 6], peak_p[part] - eq_p[part])
            w = 0.5 ** ((end_bar - fb) / halflife)
            st_all[cfg, 14] += w
            st_all[cfg, 15] += w * r
            st_all[cfg, 16] += w * r * r
            eq += r
            peak = max(peak, eq)
            st_all[cfg, 17] = max(st_all[cfg, 17], peak - eq)
    return st_all


@njit(cache=True, parallel=True)
def eval_topk(masks, kmasks, bits, kind, R, XB, FB, cfg_e, ne, nbr, split_bar, end_bar,
              halflife, end_cut, topk, min_is):
    nk = masks.size
    nt, nc = R.shape
    out = np.zeros((nk, topk, NSTAT), np.float32)
    out_cfg = np.full((nk, topk), -1, np.int32)
    out_stab = np.full((nk, topk), np.nan, np.float32)
    mom = np.zeros((nk, NMOM))
    for k in prange(nk):
        mask = masks[k]
        km = kmasks[k]
        sel = np.empty(nt, np.int64)
        ns = 0
        for i in range(nt):
            if (bits[i] & mask) == mask and ((1 << kind[i]) & km) != 0:
                sel[ns] = i
                ns += 1
        idx_e = np.empty((ne, max(ns, 1)), np.int64)
        m_e = np.zeros(ne, np.int64)
        key = np.empty(ns, np.int64)
        for e in range(ne):
            for q in range(ns):
                f = FB[sel[q], e]
                key[q] = f if f >= 0 else 2147483647
            srt = np.argsort(key, kind="mergesort")
            for q in range(ns):
                i = sel[srt[q]]
                if FB[i, e] < 0:
                    break
                idx_e[e, m_e[e]] = i
                m_e[e] += 1
        st = _combo_stats(idx_e, m_e, R, XB, FB, cfg_e, split_bar, end_bar, halflife,
                          end_cut, nc)
        mean = np.full(nc, np.nan)
        lcb = np.full(nc, -np.inf)
        for cfg in range(nc):
            n = st[cfg, 0]
            if n >= 2:
                mu = st[cfg, 2] / n
                var = max((st[cfg, 3] - n * mu * mu) / (n - 1), 1e-12)
                mean[cfg] = mu
                if n >= min_is:
                    # sd floor 0.5 R: an all-losers config (R == -1 every time) has ~0
                    # variance and would otherwise dominate every weighted statistic
                    vf = max(var, VAR_FLOOR)
                    lcb[cfg] = mu - 1.645 * np.sqrt(vf / n)
                    w = n / vf
                    mom[k, 0] += 1.0
                    mom[k, 1] += w
                    mom[k, 2] += w * mu
                    mom[k, 3] += w * mu * mu
                    mom[k, 4] += w * w
                    sr = mu / np.sqrt(vf)
                    mom[k, 5] += sr
                    mom[k, 6] += sr * sr
        for t in range(topk):
            best = -1
            bv = -np.inf
            for cfg in range(nc):
                if lcb[cfg] > bv:
                    bv = lcb[cfg]
                    best = cfg
            if best < 0:
                break
            lcb[best] = -np.inf
            out_cfg[k, t] = best
            for s in range(NSTAT):
                out[k, t, s] = st[best, s]
            acc = 0.0
            cnt = 0
            for j in range(2):
                nb = nbr[best, j]
                if nb >= 0 and not np.isnan(mean[nb]):
                    acc += mean[nb]
                    cnt += 1
            if cnt > 0:
                out_stab[k, t] = acc / cnt
    return out, out_cfg, out_stab, mom


def to_frame(stats, cfg_ids, stab, masks, kmasks, min_trades: int) -> pd.DataFrame:
    nk, tk, _ = stats.shape
    flat = stats.reshape(nk * tk, NSTAT)
    cfg = cfg_ids.reshape(-1)
    n_tot = flat[:, 0] + flat[:, 7]
    keep = np.nonzero((cfg >= 0) & (n_tot >= min_trades))[0]
    df = pd.DataFrame(flat[keep].astype(np.float64), columns=STAT_COLS)
    df["combo_id"] = keep // tk
    df["cfg"] = cfg[keep].astype(np.int64)
    df["stab_raw"] = stab.reshape(-1)[keep].astype(np.float64)
    df["mask"] = masks[df["combo_id"].to_numpy()]
    df["kmask"] = kmasks[df["combo_id"].to_numpy()]
    return df


def prior_from_moments(mom: np.ndarray) -> dict:
    """DerSimonian-Laird random-effects prior over all trials, plus SR variance (DSR).

    mu0  = precision-weighted grand mean expectancy
    tau2 = between-trial variance of true expectancy beyond sampling noise
    Trials share trades, so tau2 is biased low (conservative); `calibrate_prior`
    re-estimates it from walk-forward predictions.
    """
    m = mom.sum(axis=0)
    k, sw, swm, swm2, sw2 = m[0], m[1], m[2], m[3], m[4]
    if k < 3 or sw <= 0:
        return {"mu0": 0.0, "tau2": 1e-2, "sr_var": 0.0, "trials": int(k)}
    mu0 = swm / sw
    q = swm2 - swm * swm / sw
    denom = sw - sw2 / sw
    tau2 = max((q - (k - 1)) / denom, 1e-6) if denom > 0 else 1e-6
    sr_mean = m[5] / k
    sr_var = max(m[6] / k - sr_mean ** 2, 0.0)
    return {"mu0": float(mu0), "tau2": float(tau2), "sr_var": float(sr_var), "trials": int(k),
            "source": "dersimonian-laird"}


def select_mask(trig, mask: int, kmask: int) -> np.ndarray:
    return ((trig.bits & mask) == mask) & ((np.left_shift(1, trig.kind) & kmask) != 0)


def replay_trades(ctx, R, XB, FB, mask: int, kmask: int, cfg: int, cfg_e: int) -> pd.DataFrame:
    """Trade list for one (combo, config); same rules as the kernel."""
    tr = ctx.trig
    sel = select_mask(tr, mask, kmask) & (FB[:, cfg_e] >= 0)
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
