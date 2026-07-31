#!/usr/bin/env python3
# Two more result figures: Monte Carlo fan chart + overfitting check.
import json, os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = "/home/user/Strong-Chicken-Journal/docs/figures_vysledky"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 140})
BLUE, RED, GREEN, GREY = "#2E5496", "#C0392B", "#2E8B57", "#7f8c8d"
pct = FuncFormatter(lambda y, _: f"{y:.0f}%")

# ---- final config NAV (g25pt) ----
d = json.load(open("/home/user/Strong-Chicken-Journal/scratchpad_impe_nav.json"))["g25pt"]
ts = np.array(sorted(int(k) for k in d)); nav = np.array([d[str(t)] for t in ts], float)
s = pd.Series(nav, index=pd.to_datetime(ts, unit="s"))
s = s.groupby(s.index.normalize()).last(); nav = s.values; dates = s.index
ret = np.diff(nav) / nav[:-1]

# ===== 5. MONTE CARLO FAN CHART =====
rng = np.random.default_rng(7); Npaths = 500; L = len(nav)
paths = np.empty((Npaths, L)); paths[:, 0] = nav[0]
for i in range(Npaths):
    r = rng.choice(ret, size=len(ret), replace=True)
    paths[i, 1:] = nav[0] * np.cumprod(1 + r)
p5, p50, p95 = (np.percentile(paths, q, axis=0) for q in (5, 50, 95))
fig, ax = plt.subplots(figsize=(8, 4.4))
for i in range(Npaths):
    ax.plot(dates, paths[i] / 1000, color=BLUE, lw=0.3, alpha=0.05)
ax.fill_between(dates, p5 / 1000, p95 / 1000, color=BLUE, alpha=0.15,
                label="5th–95th percentile")
ax.plot(dates, p50 / 1000, color="#111", lw=1.6, ls="--", label="median path")
ax.plot(dates, nav / 1000, color=RED, lw=1.8, label="observed backtest")
ax.set_title("Monte Carlo Equity Paths", fontsize=14, fontweight="bold", loc="left")
ax.set_ylabel("Account value (thousand USD)")
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}k"))
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/monte_carlo_fan.png"); plt.close(fig)

# ===== 6. OVERFITTING CHECK (1D band sensitivity, no-TP slice) =====
g = pd.read_csv("/home/user/Strong-Chicken-Journal/results/vwap_grid2d.csv")
col = g[g.tp_points == 0].sort_values("band_bps")
bands, shp = col.band_bps.values, col.sharpe.values
fig, ax = plt.subplots(figsize=(8, 4.4))
ax.axvspan(16, 24, color=GREEN, alpha=0.08)
ax.axhline(0, color=GREY, lw=0.9)
ax.plot(bands, shp, "-o", color=BLUE, lw=1.8, ms=5)
cx = 20; cy = shp[list(bands).index(20)]
ax.scatter([cx], [cy], s=170, facecolor=RED, edgecolor="#111", zorder=6)
ax.annotate("chosen setting\n(band = 20 bps)", (cx, cy), textcoords="offset points",
            xytext=(12, -6), color="#111", fontweight="bold", fontsize=10)
ax.text(20, ax.get_ylim()[0], "", ha="center")
ax.text(0.98, 0.05,
        "Sharpe stays clearly positive across the whole\nneighbourhood (band 16–24) — the result is not\nconfined to a single parameter value.",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=GREY)
ax.set_title("Overfitting Check", fontsize=14, fontweight="bold", loc="left")
ax.set_xlabel("Hysteresis band (bps)"); ax.set_ylabel("Sharpe ratio")
fig.tight_layout(); fig.savefig(f"{OUT}/overfitting_check.png"); plt.close(fig)

print("wrote monte_carlo_fan.png, overfitting_check.png")
print("fan median final:", f"{p50[-1]/1000:.0f}k  observed {nav[-1]/1000:.0f}k")
print("no-TP slice band:Sharpe", dict(zip(bands.tolist(), np.round(shp, 2).tolist())))
