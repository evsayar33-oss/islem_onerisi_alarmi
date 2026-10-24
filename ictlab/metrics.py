"""Performance statistics, multiple-testing control and empirical-Bayes shrinkage."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def _part(df: pd.DataFrame, sfx: str) -> pd.DataFrame:
    n = df[f"n_{sfx}"]
    s, s2 = df[f"sum_{sfx}"], df[f"sum2_{sfx}"]
    mean = s / n.where(n > 0)
    var = (s2 - n * mean ** 2) / (n - 1).where(n > 1)
    sd = np.sqrt(var.clip(lower=1e-12))
    return pd.DataFrame({
        f"exp_{sfx}": mean,
        f"sd_{sfx}": sd,
        f"wr_{sfx}": df[f"win_{sfx}"] / n.where(n > 0),
        f"pf_{sfx}": df[f"gw_{sfx}"] / df[f"gl_{sfx}"].where(df[f"gl_{sfx}"] > 0),
        f"sr_{sfx}": mean / sd,
        f"t_{sfx}": mean / sd * np.sqrt(n),
    })


def enrich(df: pd.DataFrame, years_is: float, years_oos: float, n_trials: int | None = None,
           prior: dict | None = None, n_eff: int | None = None) -> pd.DataFrame:
    """Adds performance columns, EB shrinkage and deflated Sharpe.

    `prior` (from `combos.prior_from_moments`) carries the grand mean, between-trial
    variance and SR variance over *all* trials; without it they come from `df`.
    """
    df = pd.concat([df, _part(df, "is"), _part(df, "oos")], axis=1)
    n_all = df["n_is"] + df["n_oos"]
    df["n_all"] = n_all
    df["exp_all"] = (df["sum_is"] + df["sum_oos"]) / n_all
    df["total_r"] = df["sum_is"] + df["sum_oos"]
    df["tpy_is"] = df["n_is"] / max(years_is, 1e-9)
    df["ann_sr_is"] = df["sr_is"] * np.sqrt(df["tpy_is"])
    df["mar_is"] = (df["sum_is"] / max(years_is, 1e-9)) / df["dd_is"].clip(lower=1.0)
    w = df["w_sum"].where(df["w_sum"] > 0)
    df["exp_recent"] = df["w_sumr"] / w

    # Empirical Bayes (normal-normal) shrinkage of IS expectancy towards the grand mean.
    ok = df["n_is"] >= 10
    se2 = (df["sd_is"].clip(lower=0.5) ** 2) / df["n_is"].where(df["n_is"] > 0)
    if prior is not None:
        mu0, tau2 = prior["mu0"], prior["tau2"]
    else:
        mu0 = float(np.average(df.loc[ok, "exp_is"], weights=1 / se2[ok])) if ok.any() else 0.0
        tau2 = float(max(df.loc[ok, "exp_is"].var() - se2[ok].mean(), 1e-6)) \
            if ok.sum() > 2 else 1e-2
    wgt = tau2 / (tau2 + se2)
    df["exp_shrunk"] = wgt * df["exp_is"] + (1 - wgt) * mu0
    df["post_sd"] = np.sqrt(wgt * se2)
    df["score"] = df["exp_shrunk"] - 1.645 * df["post_sd"]
    df.attrs["eb_mu0"], df.attrs["eb_tau2"] = mu0, tau2

    # Multiple-testing deflation in t-stat space (see t_hurdle / full_sample).
    trials = n_trials or int(ok.sum())
    sr = df["sr_is"]
    denom = np.sqrt(1 + 0.5 * sr ** 2)
    df["psr_is"] = norm.cdf(sr * np.sqrt((df["n_is"] - 1).clip(lower=1)) / denom)
    t0 = t_hurdle(n_eff or trials)
    df["dsr_is"] = norm.cdf(df["t_is"] - t0)
    df.attrs["t_hurdle"] = t0
    df.attrs["trials"] = trials
    return df


def t_hurdle(n_eff: int) -> float:
    """Expected maximum t-statistic of n_eff independent null trials (Bailey/LdP)."""
    if n_eff <= 1:
        return 0.0
    return float((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_eff)
                 + EULER_GAMMA * norm.ppf(1 - 1 / (n_eff * np.e)))


def full_sample(df: pd.DataFrame, n_eff: int) -> pd.DataFrame:
    """Whole-period statistics and a multiple-testing-deflated significance.

    `dsr_all` = P(true edge > the luckiest of n_eff null trials), computed in
    t-stat space so trials with different sample sizes are comparable. The configs
    of one combo share trades, so n_eff = number of distinct combos.
    """
    n = df["n_is"] + df["n_oos"]
    s = df["sum_is"] + df["sum_oos"]
    s2 = df["sum2_is"] + df["sum2_oos"]
    mean = s / n.where(n > 0)
    sd = np.sqrt(((s2 - n * mean ** 2) / (n - 1).where(n > 1)).clip(lower=1e-12))
    out = df.copy()
    out["sd_all"] = sd
    out["t_all"] = mean / sd * np.sqrt(n)
    gl = df["gl_is"] + df["gl_oos"]
    out["pf_all"] = (df["gw_is"] + df["gw_oos"]) / gl.where(gl > 0)
    out["wr_all"] = (df["win_is"] + df["win_oos"]) / n.where(n > 0)
    t0 = t_hurdle(n_eff)
    out["dsr_all"] = norm.cdf(out["t_all"] - t0)
    out.attrs.update(df.attrs)
    out.attrs["t_hurdle"] = t0
    return out
