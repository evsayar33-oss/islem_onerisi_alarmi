"""Stage B - 15-minute entry resolution (lower-timeframe confirmation).

Setup: every 1h trigger of the main engine, with all its higher-timeframe bits.
Confirmation: within 24 hours after the 1h zone completes, the first 15m FVG of
the same direction (gap >= 0.1 x ATR15) that overlaps the 1h zone. The setup is
cancelled if a 15m candle closes beyond the far edge of the 1h zone first.

Execution grid (2 x 3 x 11 x 3 = 198 settings):
  entry : market at the confirming 15m close | limit at the 15m FVG 50 % (valid 2 h)
  stop  : 15m pattern extreme - 0.1 ATR15 | 1h zone far edge - 0.1 ATR1h | 2 x ATR15
  RR    : 0.5 ... 6
  mgmt  : none | break-even at +1R | 2 x ATR15 trail after +1R
Trades last at most 120 hours; costs as in the main study.

Search, selection (robust rule) and the locked-holdout replay follow
scripts/rule_search.py. Triggers without 15m data are skipped.
Usage: PYTHONPATH=.:scripts python3 scripts/stage_b_ltf_entry.py BTC ETH NQ SPX XAU XAG
"""

from __future__ import annotations

import itertools
import json
import sys
import time

import numpy as np
import pandas as pd
from numba import njit, prange

from ictlab.combos import (combo_name, enumerate_combos, eval_topk, prior_from_moments,
                           replay_trades, to_frame)
from ictlab.config import ASSETS as SPECS
from ictlab.config import MGMT, RR_GRID, ResearchParams
from ictlab.context import build_context
from ictlab.features import atr
from ictlab.metrics import enrich, full_sample
from ictlab.simulate import _path
from stages_common import ASSETS, ROOT, growth, holdout_cut, verdict

OUT = ROOT / "results" / "stages"
CACHE = ROOT / "data" / "cache"
ENTRY = ("ltf_market", "ltf_limit_ce")
STOPS = ("ltf_pattern", "h1_zone", "ltf_atr2")


def load_ltf(key: str) -> pd.DataFrame:
    parts = []
    for name in (f"{key}_15m.parquet", f"{key}_15m_oanda.parquet", f"{key}_15m_epsoft.parquet",
                 f"{key}_15m_duka.parquet", f"{key}_15m_paxg.parquet", f"{key}_15m_etf.parquet"):
        f = CACHE / name
        if f.exists():
            parts.append(pd.read_parquet(f))
    df = pd.concat(parts).sort_index()
    return df[~df.index.duplicated(keep="last")]


def config_table() -> pd.DataFrame:
    rows = [(e, s, r, m, ENTRY[e], STOPS[s], RR_GRID[r], MGMT[m]) for e, s, r, m in
            itertools.product(range(2), range(3), range(len(RR_GRID)), range(len(MGMT)))]
    return pd.DataFrame(rows, columns=["e", "s", "r", "m", "entry", "stop", "rr", "mgmt"])


@njit(cache=True, parallel=True)
def simulate_ltf(t_close_ns, td, tlo, thi, a1t, lt_ns, o, h, l, c, a15, l2h, rr, mg,
                 window_ns, max_hold, cost_bps):
    nt = t_close_ns.size
    ne, ns, nr, nm = 2, 3, rr.size, mg.size
    R = np.full((nt, ne, ns, nr, nm), np.nan, np.float32)
    XB = np.full((nt, ne, ns, nr, nm), -1, np.int32)
    FB = np.full((nt, ne), -1, np.int32)
    n = c.size
    for i in prange(nt):
        s0 = np.searchsorted(lt_ns, t_close_ns[i])
        if s0 >= n or lt_ns[s0] - t_close_ns[i] > window_ns:
            continue
        d = td[i]
        conf = -1
        for j in range(max(s0, 2), n):
            if lt_ns[j] - t_close_ns[i] > window_ns:
                break
            if (d == 1 and c[j] < tlo[i]) or (d == -1 and c[j] > thi[i]):
                break  # 1h zone invalidated before confirmation
            a = a15[j]
            if d == 1 and l[j] > h[j - 2] and l[j] - h[j - 2] >= 0.1 * a:
                if h[j - 2] <= thi[i] and l[j] >= tlo[i]:
                    conf = j
                    break
            if d == -1 and h[j] < l[j - 2] and l[j - 2] - h[j] >= 0.1 * a:
                if h[j] <= thi[i] and l[j - 2] >= tlo[i]:
                    conf = j
                    break
        if conf < 0:
            continue
        j = conf
        a = a15[j]
        flo = h[j - 2] if d == 1 else h[j]
        fhi = l[j] if d == 1 else l[j - 2]
        ext = min(l[j - 2], min(l[j - 1], l[j])) if d == 1 else max(h[j - 2], max(h[j - 1], h[j]))
        for e in range(ne):
            if e == 0:
                fb, entry = j, c[j]
            else:
                px = 0.5 * (flo + fhi)
                fb, entry = -1, np.nan
                for b in range(j + 1, min(n, j + 9)):
                    if d == 1:
                        if l[b] <= px:
                            fb, entry = b, min(o[b], px)
                            break
                        if c[b] < flo:
                            break
                    else:
                        if h[b] >= px:
                            fb, entry = b, max(o[b], px)
                            break
                        if c[b] > fhi:
                            break
                if fb < 0:
                    continue
            if fb >= n - 1:
                continue
            FB[i, e] = l2h[fb]
            for s in range(ns):
                if s == 0:
                    stop = ext - 0.1 * a if d == 1 else ext + 0.1 * a
                elif s == 1:
                    stop = tlo[i] - 0.1 * a1t[i] if d == 1 else thi[i] + 0.1 * a1t[i]
                else:
                    stop = entry - 2 * a if d == 1 else entry + 2 * a
                risk = (entry - stop) if d == 1 else (stop - entry)
                if not risk > 0.05 * a:
                    continue
                cost_r = cost_bps * 1e-4 * entry / risk
                for r in range(nr):
                    target = entry + rr[r] * risk if d == 1 else entry - rr[r] * risk
                    for m in range(nm):
                        xp, xb = _path(d, fb, entry, stop, target, mg[m], o, h, l, c, max_hold,
                                       e != 0, 2.0 * a)
                        pnl = (xp - entry) if d == 1 else (entry - xp)
                        R[i, e, s, r, m] = pnl / risk - cost_r
                        XB[i, e, s, r, m] = l2h[xb]
    return R, XB, FB


def prepare_ltf(key: str, h1: pd.DataFrame, ltf: pd.DataFrame, p: ResearchParams) -> dict:
    ctx = build_context(h1, SPECS[key], p)
    tr = ctx.trig
    h1_ns = h1.index.as_unit("ns").asi8
    t_close = h1_ns[tr.t] + 3600 * 10**9
    lt = ltf.index.as_unit("ns").asi8
    o, hh, ll, c = (ltf[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    a15 = atr(hh, ll, c, 14)
    l2h = (np.searchsorted(h1_ns, lt, side="right") - 1).clip(0).astype(np.int64)
    mg = np.array([{"none": 0, "be1r": 1, "trail2atr": 2}[m] for m in MGMT], np.int64)
    R, XB, FB = simulate_ltf(t_close, tr.dir, tr.lo, tr.hi, ctx.atr1[tr.t], lt, o, hh, ll, c,
                             a15, l2h, np.array(RR_GRID), mg, 24 * 3600 * 10**9, 480,
                             SPECS[key].cost_bps)
    nt = R.shape[0]
    cfgs = config_table()
    key4 = {(e, s, r, m): i for i, (e, s, r, m) in enumerate(cfgs[["e", "s", "r", "m"]].values)}
    nbr = np.array([[key4.get((e, s, r - 1, m), -1), key4.get((e, s, r + 1, m), -1)]
                    for e, s, r, m in cfgs[["e", "s", "r", "m"]].values], np.int64)
    # only triggers that could be confirmed on 15m data take part in the search
    has = (FB >= 0).any(axis=1)
    masks, kmasks, _ = enumerate_combos(tr.bits[has], tr.kind[has], p.min_trades,
                                        p.max_combo_size)
    return {"key": key, "ctx": ctx, "R": R.reshape(nt, -1), "XB": XB.reshape(nt, -1), "FB": FB,
            "cfgs": cfgs, "cfg_e": cfgs["e"].to_numpy(np.int64), "nbr": nbr, "masks": masks,
            "kmasks": kmasks, "p": p, "has": has}


def evaluate_ltf(prep: dict, split_bar: int, end_cut: int) -> pd.DataFrame:
    ctx, p, cfgs = prep["ctx"], prep["p"], prep["cfgs"]
    stats, ids, stab, mom = eval_topk(prep["masks"], prep["kmasks"], ctx.trig.bits,
                                      ctx.trig.kind, prep["R"], prep["XB"], prep["FB"],
                                      prep["cfg_e"], 2, prep["nbr"], split_bar, end_cut - 1,
                                      24 * 365 * 2.0, end_cut, 12, p.min_trades)
    prior = prior_from_moments(mom)
    df = to_frame(stats, ids, stab, prep["masks"], prep["kmasks"], p.min_trades)
    df = enrich(df, 1.0, 1.0, n_trials=len(prep["masks"]) * len(cfgs), prior=prior,
                n_eff=len(prep["masks"]))
    df = full_sample(df, len(prep["masks"])).join(cfgs, on="cfg")
    df["combo"] = [combo_name(int(m), int(k)) for m, k in zip(df["mask"], df["kmask"])]
    return df


def robust_pick(g: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    c = g[(g["exp_is"] > 0) & (g["exp_oos"] > 0) & (g["n_oos"] >= 30) & (g["n_is"] >= 60)
          & (g["stab_raw"] > 0)].copy()
    c["t_oos"] = c["exp_oos"] / c["sd_oos"] * np.sqrt(c["n_oos"])
    c["t_min"] = np.minimum(c["t_is"], c["t_oos"])
    return c.sort_values("t_min", ascending=False).drop_duplicates("combo_id").head(k)


def run(key: str, p: ResearchParams) -> dict:
    t0 = time.time()
    h1 = pd.read_parquet(CACHE / f"{key}_1h.parquet")
    ltf = load_ltf(key)
    cut = holdout_cut(h1)
    prep = prepare_ltf(key, h1, ltf, p)
    idx = h1.index
    cut_bar = int(np.searchsorted(idx, cut))
    # IS / OOS split at 70 % of the pre-holdout trades that have 15m data
    tt = prep["ctx"].trig.t[prep["has"] & (prep["ctx"].trig.t < cut_bar)]
    split_bar = int(np.quantile(tt, 0.7)) if tt.size else cut_bar // 2
    g = evaluate_ltf(prep, split_bar, cut_bar)
    pick = robust_pick(g)
    rows = []
    for rank, (_, r) in enumerate(pick.iterrows(), 1):
        tr = replay_trades(prep["ctx"], prep["R"], prep["XB"], prep["FB"], int(r["mask"]),
                           int(r["kmask"]), int(r["cfg"]), int(r["e"]))
        hold = tr[tr.entry_time >= cut]
        u1, dd1 = growth(hold.R.to_numpy())
        rows.append({"rank": rank, "combo": r["combo"], "entry": r["entry"], "stop": r["stop"],
                     "rr": float(r["rr"]), "mgmt": r["mgmt"], "search_n": int(r["n_all"]),
                     "search_is_exp": float(r["exp_is"]), "search_oos_exp": float(r["exp_oos"]),
                     "hold_n": int(len(hold)),
                     "hold_wr": float((hold.R > 0).mean()) if len(hold) else None,
                     "hold_exp": float(hold.R.mean()) if len(hold) else None,
                     "hold_unit_1pct": u1, "hold_maxdd_1pct": dd1,
                     "hold_r": hold.R.round(4).tolist()})
    ltf_pre = ltf[ltf.index < cut]
    out = {"asset": key, "ltf_first": str(ltf.index[0]), "ltf_last": str(ltf.index[-1]),
           "ltf_pre_holdout_bars": int(len(ltf_pre)),
           "ltf_holdout_bars": int((ltf.index >= cut).sum()), "holdout_start": str(cut),
           "triggers_confirmed": int(prep["has"].sum()), "combos": int(len(prep["masks"])),
           "selected": rows, "seconds": round(time.time() - t0, 1)}
    print(f"[B] {key} done in {out['seconds']}s; confirmed triggers {out['triggers_confirmed']}, "
          f"combos {out['combos']}, picks {len(rows)}", flush=True)
    return out


if __name__ == "__main__":
    params = ResearchParams()
    res = {"stage": "B", "method": "15-minute confirmation entry inside 1h setups", "assets": {}}
    primary, allc = {}, {}
    for a in sys.argv[1:]:
        r = run(a, params)
        res["assets"][a] = r
        if r["selected"]:
            primary[a] = np.array(r["selected"][0]["hold_r"])
            allc[a] = np.concatenate([np.array(x["hold_r"]) for x in r["selected"]])
    res["verdict_primary"] = verdict(primary)
    res["verdict_all_candidates"] = verdict(allc)
    res["positive"] = res["verdict_primary"]["positive"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage_b.json").write_text(json.dumps(res, indent=1, default=str))
    for s in ("verdict_primary", "verdict_all_candidates"):
        v = res[s]
        print(f"{s}: trades={v['trades']} mean={v['mean_r']:+.3f} t={v['t']:+.2f} "
              f"assets+={v['assets_positive']}/{v['assets']} positive={v['positive']}")
    print("STAGE B POSITIVE:", res["positive"])
