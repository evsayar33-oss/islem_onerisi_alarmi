"""Shared pieces for the follow-up stages (A-D).

Pre-registered success criterion (fixed before any stage was run):
    A method, chosen with pre-holdout data only, is POSITIVE when in the locked
    holdout (last 2 years) the pooled trades of the six assets have mean R > 0 with
    t >= 2, AND at least 4 of the 6 assets have a positive mean.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ictlab.combos import combo_name, replay_trades
from ictlab.config import ResearchParams
from ictlab.data import load_asset
from ictlab.research import prepare

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ["NQ", "SPX", "XAU", "XAG", "BTC", "ETH"]
HOLDOUT_YEARS = 2


def holdout_cut(h1: pd.DataFrame) -> pd.Timestamp:
    return h1.index[-1] - pd.DateOffset(years=HOLDOUT_YEARS)


def candidates(key: str) -> list[dict]:
    """Rules selected on pre-holdout data by earlier studies (no holdout knowledge)."""
    out = []
    rs = ROOT / "results" / "rule_search" / f"{key}_selection.json"
    if rs.exists():
        for c in json.loads(rs.read_text())["candidates"]:
            out.append({"source": f"rule_search/{c['method']}#{c['rank']}", "combo": c["combo"],
                        "entry": c["entry_mode"], "stop": c["stop"], "rr": c["rr"],
                        "mgmt": c["management"],
                        "primary": c["method"] == "robust" and c["rank"] == 1})
    wr = ROOT / "results" / "winrate" / f"{key}_winrate.json"
    if wr.exists():
        for i, c in enumerate(json.loads(wr.read_text())["selected"], 1):
            if c.get("entry"):
                out.append({"source": f"winrate#{i}", "combo": c["combo"], "entry": c["entry"],
                            "stop": c["stop"], "rr": c["rr"], "mgmt": c["mgmt"],
                            "primary": False})
    return out


def full_prep(key: str, p: ResearchParams | None = None) -> tuple[dict, pd.DataFrame]:
    h1 = load_asset(key, source="cache")
    return prepare(key, h1, p or ResearchParams()), h1


def trades_for(prep: dict, cand: dict) -> pd.DataFrame | None:
    """Replay one candidate (by combo name + config names) on prepared data."""
    if "_names" not in prep:  # build once; setdefault would rebuild it on every call
        prep["_names"] = {combo_name(int(m), int(k)): (int(m), int(k))
                          for m, k in zip(prep["masks"], prep["kmasks"])}
    names = prep["_names"]
    if cand["combo"] not in names:
        return None
    m, k = names[cand["combo"]]
    cf = prep["cfgs"]
    sel = cf[(cf.entry == cand["entry"]) & (cf.stop == cand["stop"]) & (cf.rr == cand["rr"])
             & (cf.mgmt == cand["mgmt"])]
    if sel.empty:
        return None
    cfg = int(sel.index[0])
    return replay_trades(prep["ctx"], prep["R"], prep["XB"], prep["FB"], m, k, cfg,
                         int(cf.loc[cfg, "e"]))


def verdict(per_asset: dict[str, np.ndarray]) -> dict:
    """Apply the pre-registered criterion to holdout R streams (already weighted)."""
    allr = np.concatenate([v for v in per_asset.values() if len(v)]) if per_asset else np.array([])
    n = allr.size
    mean = float(allr.mean()) if n else float("nan")
    t = float(mean / allr.std(ddof=1) * np.sqrt(n)) if n > 1 and allr.std() > 0 else 0.0
    pos = int(sum(1 for v in per_asset.values() if len(v) and v.mean() > 0))
    return {"trades": int(n), "mean_r": mean, "t": t, "assets_positive": pos,
            "assets": len(per_asset),
            "per_asset_mean": {k: (float(v.mean()) if len(v) else None)
                               for k, v in per_asset.items()},
            "positive": bool(n > 1 and mean > 0 and t >= 2 and pos >= 4)}


def growth(r: np.ndarray, risk: float = 0.01) -> tuple[float, float]:
    if len(r) == 0:
        return 1.0, 0.0
    eq = np.cumprod(1 + risk * np.asarray(r))
    pk = np.maximum.accumulate(eq)
    return float(eq[-1]), float(((pk - eq) / pk).max() * 100)
