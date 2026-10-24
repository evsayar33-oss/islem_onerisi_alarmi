"""Self-improving knowledge base.

Every research run:
  1. ingest  - replays each earlier recommendation on the bars that arrived after it
               was made (a true forward test) and adds the result to decayed forward stats;
  2. calibrate - learns per asset how much of the predicted (back-tested) edge survives
               forward (kappa); backtests are optimistic, kappa measures by how much;
  3. rank    - fuses back-test posterior x kappa with forward evidence (precision
               weighted, forward evidence counts double) into the final score;
  4. record  - stores the new top recommendations with their predictions.

The loop closes: the more the system runs, the more its scores reflect
forward reality instead of in-sample fit, and stale edges decay away.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .combos import replay_trades

KB_DIR = Path(__file__).resolve().parent.parent / "results" / "knowledge"
KEY = ["asset", "mask", "kmask", "cfg"]
FWD_HALFLIFE_DAYS = 365.0
PRIOR_WEIGHT_TRADES = 200.0


class KnowledgeBase:
    def __init__(self, root: Path = KB_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rec_path = self.root / "recommendations.parquet"
        self.fwd_path = self.root / "forward.parquet"
        self.cal_path = self.root / "calibration.json"
        self.recs = pd.read_parquet(self.rec_path) if self.rec_path.exists() else pd.DataFrame()
        self.fwd = pd.read_parquet(self.fwd_path) if self.fwd_path.exists() else pd.DataFrame(
            columns=KEY + ["n", "sum", "sum2", "pred_sum", "updated"])
        self.cal = json.loads(self.cal_path.read_text()) if self.cal_path.exists() else {}

    # ------------------------------------------------------------------ persistence
    def save(self) -> None:
        if len(self.recs):
            self.recs.to_parquet(self.rec_path)
        self.fwd.to_parquet(self.fwd_path)
        self.cal_path.write_text(json.dumps(self.cal, indent=2, default=str))

    # ------------------------------------------------------------------ 1. ingest
    def ingest(self, prep: dict) -> int:
        """Forward-test earlier recommendations of this asset on newly arrived bars."""
        asset = prep["key"]
        if self.recs.empty:
            return 0
        h1 = prep["ctx"].h1
        data_end = h1.index[-1]
        cu = pd.to_datetime(self.recs["counted_until"], utc=True)
        mine = self.recs[(self.recs["asset"] == asset) & (cu < data_end)]
        added = 0
        # One forward stream per strategy key, however often it was recommended:
        # count from the earliest pending point, attribute to the latest prediction.
        for _, grp in mine.groupby(KEY, sort=False):
            since = pd.to_datetime(grp["counted_until"], utc=True).min()
            rec = grp.iloc[-1]
            tr = replay_trades(prep["ctx"], prep["R"], prep["XB"], prep["FB"], int(rec["mask"]),
                               int(rec["kmask"]), int(rec["cfg"]), int(rec["e"]))
            new = tr[tr["entry_time"] > since]
            if len(new):
                self._add_forward(rec, new["R"].to_numpy(), data_end)
                added += len(new)
            self.recs.loc[grp.index, "counted_until"] = str(data_end)
        return added

    def _add_forward(self, rec: pd.Series, r: np.ndarray, now: pd.Timestamp) -> None:
        key = {k: rec[k] for k in KEY}
        m = np.ones(len(self.fwd), bool)
        for k, v in key.items():
            m &= self.fwd[k].to_numpy() == v
        row = {**key, "n": float(r.size), "sum": float(r.sum()), "sum2": float((r * r).sum()),
               "pred_sum": float(rec["pred_exp"]) * r.size, "updated": str(now)}
        if m.any():
            i = np.nonzero(m)[0][0]
            age = (now - pd.Timestamp(self.fwd.iloc[i]["updated"])).days
            decay = 0.5 ** (max(age, 0) / FWD_HALFLIFE_DAYS)
            for c in ("n", "sum", "sum2", "pred_sum"):
                self.fwd.iloc[i, self.fwd.columns.get_loc(c)] = \
                    self.fwd.iloc[i][c] * decay + row[c]
            self.fwd.iloc[i, self.fwd.columns.get_loc("updated")] = row["updated"]
        else:
            self.fwd = pd.concat([self.fwd, pd.DataFrame([row])], ignore_index=True)

    # ------------------------------------------------------------------ 2. calibrate
    def calibrate(self, asset: str) -> float:
        f = self.fwd[self.fwd["asset"] == asset]
        n = float(f["n"].sum()) if len(f) else 0.0
        realized = float(f["sum"].sum()) if len(f) else 0.0
        predicted = float(f["pred_sum"].sum()) if len(f) else 0.0
        ratio = realized / predicted if predicted > 1e-9 else 1.0
        kappa = (PRIOR_WEIGHT_TRADES * 1.0 + n * ratio) / (PRIOR_WEIGHT_TRADES + n)
        # 0 = back-test evidence ignored (only forward evidence counts); never inverted.
        kappa = float(np.clip(kappa, 0.0, 1.5))
        self.cal[asset] = {"kappa": kappa, "forward_trades": n, "realized_r": realized,
                           "predicted_r": predicted, "updated": time.strftime("%Y-%m-%d %H:%M")}
        return kappa

    # ------------------------------------------------------------------ 3. rank
    def rank(self, grid: pd.DataFrame, asset: str, z: float = 1.645) -> pd.DataFrame:
        kappa = self.cal.get(asset, {}).get("kappa", 1.0)
        g = grid.copy()
        mu_b = g["exp_shrunk"] * kappa
        var_b = (g["post_sd"] ** 2).clip(lower=1e-6)
        f = self.fwd[self.fwd["asset"] == asset]
        if len(f):
            g = g.merge(f[KEY + ["n", "sum", "sum2"]].rename(
                columns={"n": "fwd_n", "sum": "fwd_sum", "sum2": "fwd_sum2"}), on=KEY, how="left")
        else:
            g["fwd_n"] = g["fwd_sum"] = g["fwd_sum2"] = np.nan
        for c in ("fwd_n", "fwd_sum", "fwd_sum2"):
            g[c] = pd.to_numeric(g[c], errors="coerce").astype(float)
        fn = g["fwd_n"].fillna(0.0)
        fmean = g["fwd_sum"] / fn.where(fn > 0)
        fvar = (g["sd_is"].fillna(1.0) ** 2) / fn.where(fn > 0) / 2.0  # forward counts double
        vb = var_b.to_numpy(float)
        prec = 1 / vb + np.where(fn > 0, 1 / fvar, 0.0).astype(float)
        mu = (mu_b.to_numpy(float) / vb + np.where(fn > 0, fmean / fvar, 0.0)) / prec
        g["kappa"] = kappa
        g["fwd_exp"] = fmean
        g["final_mean"] = mu
        g["final_sd"] = np.sqrt(1 / prec)
        g["final_score"] = g["final_mean"] - z * g["final_sd"]
        return g.sort_values("final_score", ascending=False)

    def thompson(self, ranked: pd.DataFrame, k: int = 10, seed: int = 0) -> pd.DataFrame:
        """Exploration list: one posterior draw per row, top-k by the draw."""
        rng = np.random.default_rng(seed)
        best = ranked.drop_duplicates("combo_id")
        draw = rng.normal(best["final_mean"], best["final_sd"])
        return best.assign(draw=draw).sort_values("draw", ascending=False).head(k)

    # ------------------------------------------------------------------ 4. record
    def record(self, ranked: pd.DataFrame, asset: str, as_of: pd.Timestamp, run_id: str,
               k: int = 20) -> None:
        top = ranked[(ranked["stab"] > 0) & (ranked["final_mean"] > 0)].drop_duplicates(
            "combo_id").head(k)
        if top.empty:
            return
        rec = top[KEY + ["e", "combo", "entry", "stop", "rr", "mgmt", "final_mean",
                         "final_sd", "final_score"]].rename(
            columns={"final_mean": "pred_exp", "final_sd": "pred_sd", "final_score": "pred_score"})
        rec = rec.assign(run_id=run_id, as_of=str(as_of), counted_until=str(as_of))
        self.recs = pd.concat([self.recs, rec], ignore_index=True)
