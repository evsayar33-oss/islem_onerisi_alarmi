"""True forward test: combos chosen on Oanda data (<= 2020-05-14) replayed on Dukascopy to today."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ictlab.data import load_asset
from ictlab.config import ResearchParams
from ictlab.research import prepare
from ictlab.combos import replay_trades
from ictlab.report import rank_full

CUT = pd.Timestamp("2020-05-14", tz="UTC")  # last bar of the data used for selection
p = ResearchParams()
rows = []
fig, axs = plt.subplots(1, 3, figsize=(16, 4.8))
for a, ax in zip(["NQ", "SPX", "XAU"], axs):
    g = pd.read_parquet(f"results/{a}_grid.parquet")  # grid built on Oanda data only
    r = rank_full(g, 1).iloc[0]
    h1 = load_asset(a, source="cache")  # Dukascopy 2012 -> today
    prep = prepare(a, h1, p)
    tr = replay_trades(prep["ctx"], prep["R"], prep["XB"], prep["FB"], int(r["mask"]),
                       int(r["kmask"]), int(r["cfg"]), int(r["e"]))
    fwd = tr[tr.entry_time > CUT]
    back = tr[tr.entry_time <= CUT]
    out = {"asset": a, "combo": r["combo"], "entry": r["entry"], "stop": r["stop"], "rr": r["rr"],
           "mgmt": r["mgmt"], "data_end": str(h1.index[-1].date()),
           "back_trades": len(back), "back_avg_R": round(back.R.mean(), 3) if len(back) else np.nan,
           "fwd_trades": len(fwd), "fwd_win%": round((fwd.R > 0).mean() * 100, 1) if len(fwd) else np.nan,
           "fwd_avg_R": round(fwd.R.mean(), 3) if len(fwd) else np.nan,
           "fwd_total_R": round(fwd.R.sum(), 1)}
    for risk in (0.01, 0.02):
        eq = np.cumprod(1 + risk * fwd.R.values) if len(fwd) else np.array([1.0])
        peak = np.maximum.accumulate(eq)
        out[f"fwd_1unit_{int(risk*100)}%"] = round(float(eq[-1]), 3)
        out[f"fwd_maxDD_{int(risk*100)}%"] = round(float(((peak - eq) / peak).max() * 100), 1)
        if len(fwd):
            ax.plot(fwd.exit_time, eq, label=f"%{int(risk*100)} risk")
    ax.axhline(1, c="k", lw=.5)
    ax.set_title(f"{a} ileri test (2020-05 -> {out['data_end']})\n{r['combo']}\n"
                 f"{r['entry']}, {r['stop']}, RR{r['rr']}, {r['mgmt']}", fontsize=8)
    ax.legend(fontsize=7)
    rows.append(out)
plt.suptitle("Gerçek ileri test: 2020-05 sonrası, seçimde hiç kullanılmamış veri")
plt.tight_layout()
plt.savefig("reports/figures/6_forward_test_nq_spx_xau.png", dpi=110)
df = pd.DataFrame(rows)
df.to_csv("results/forward_test_nq_spx_xau.csv", index=False)
pd.set_option("display.width", 300)
print(df.T.to_string())
