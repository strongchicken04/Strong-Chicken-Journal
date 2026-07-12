"""C4 — overnight drift jako kontext (lokálně z A2 range-bound datasetu).
Korelace |overnight move| vs RTH realized range + bucket srovnání."""
import pandas as pd, numpy as np
from scipy import stats

a2 = pd.read_csv("data/cache/a2_all.csv", parse_dates=["date"])
rows = []
for inst in ["ES", "SPY"]:
    d = a2[a2.instrument == inst].copy()
    d["abs_on"] = d["on_ret_pct"].abs()
    # Pearson + Spearman korelace
    pear = stats.pearsonr(d["abs_on"], d["realized_range_atr"])
    spear = stats.spearmanr(d["abs_on"], d["realized_range_atr"])
    print(f"\n=== {inst} (n={len(d)} range-bound dní) ===")
    print(f"  Pearson r(|overnight%|, RTH range/ATR) = {pear[0]:.3f} (p={pear[1]:.2e})")
    print(f"  Spearman rho = {spear[0]:.3f} (p={spear[1]:.2e})")
    # terciny |overnight|
    d["on_bucket"] = pd.qcut(d["abs_on"], 3, labels=["small", "med", "large"])
    g = d.groupby("on_bucket", observed=True)["realized_range_atr"].agg(["count", "mean", "median"])
    print("  RTH realized_range/ATR podle |overnight| terciny:")
    print(g.round(3).to_string())
    for b in ["small", "med", "large"]:
        sub = d[d.on_bucket == b]["realized_range_atr"]
        rows.append({"instrument": inst, "bucket": b, "n": len(sub),
                     "mean_rr": round(sub.mean(), 3), "median_rr": round(sub.median(), 3)})
    # test malý vs velký overnight (Mann-Whitney)
    small = d[d.on_bucket == "small"]["realized_range_atr"]
    large = d[d.on_bucket == "large"]["realized_range_atr"]
    mw = stats.mannwhitneyu(small, large)
    print(f"  Mann-Whitney small vs large: p={mw[1]:.2e}")

pd.DataFrame(rows).to_csv("results/phaseC_c4.csv", index=False)
print("\nuloženo results/phaseC_c4.csv")
