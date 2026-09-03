#!/usr/bin/env python3
# Overfitting check = band x take-profit heatmap of IS total return (viridis),
# deployed setting marked with an X. Real data from vwap_grid2d.csv.
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/home/user/Strong-Chicken-Journal/docs/figures_vysledky/overfitting_check.png"
g = pd.read_csv("/home/user/Strong-Chicken-Journal/results/vwap_grid2d.csv")

bands = sorted(g.band_bps.unique())
tps = [0, 250, 180, 130, 100, 75, 55, 40]           # top -> bottom (0 = none/no TP)
M = np.full((len(tps), len(bands)), np.nan)
for _, r in g.iterrows():
    yi = tps.index(int(r.tp_points)); xi = bands.index(int(r.band_bps))
    M[yi, xi] = r.is_total_ret_pct

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "figure.dpi": 140})
fig, ax = plt.subplots(figsize=(9.6, 5.4))
im = ax.imshow(M, cmap="viridis", aspect="auto")
ax.set_xticks(range(len(bands))); ax.set_xticklabels([int(b) for b in bands])
ax.set_yticks(range(len(tps)))
ax.set_yticklabels(["none" if t == 0 else int(t) for t in tps])
ax.set_xlabel("hysteresis band width (bps)")
ax.set_ylabel("take-profit distance (NQ points)")
ax.set_title("Overfitting Check", fontsize=15, fontweight="bold", loc="left", pad=30)
ax.text(0, 1.02, "parameter heatmap: band × take-profit — isolated spike vs. broad plateau",
        transform=ax.transAxes, fontsize=10, color="#555")

# deployed setting: band = 20, no TP (top row)
cx = bands.index(20); cy = tps.index(0)
ax.scatter([cx], [cy], marker="X", s=260, color="#fff", edgecolors="#111",
           linewidths=1.6, zorder=6)
ax.annotate("Deployed setting (band = 20, no TP)", (cx, cy),
            textcoords="offset points", xytext=(16, 0), va="center", fontsize=10,
            color="#fff", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", fc="#3b2f16", ec="#111"))
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("IS total return (%)")
fig.tight_layout(); fig.savefig(OUT); plt.close(fig)
print("wrote", OUT)
print("deployed cell IS total return:", M[cy, cx], "%")
