#!/usr/bin/env python3
# Result figures for the final VWAP-trend NQ config, from REAL backtest data.
# English test-name titles only, no strategy name on the figures.
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = "/home/user/Strong-Chicken-Journal/docs/figures_vysledky"
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 140,
})
BLUE, RED, GREEN, GREY = "#2E5496", "#C0392B", "#2E8B57", "#7f8c8d"

# ---- load FINAL config NAV: g25pt = gap gate 25 + trend gate (CAGR 10.5%, Sharpe 1.40, MDD -6.4%) ----
raw = json.load(open("/home/user/Strong-Chicken-Journal/scratchpad_impe_nav.json"))
d = raw["g25pt"]
ts = np.array(sorted(int(k) for k in d.keys()))
nav = np.array([d[str(t)] for t in ts], float)
dates = pd.to_datetime(ts, unit="s")
s = pd.Series(nav, index=dates)
# collapse to one point per day (EOD)
s = s.groupby(s.index.normalize()).last()
nav = s.values; dates = s.index

ret = np.diff(nav) / nav[:-1]
years = (dates[-1] - dates[0]).days / 365.25
cagr = (nav[-1] / nav[0]) ** (1 / years) - 1
sharpe = np.mean(ret) / np.std(ret, ddof=1) * np.sqrt(252)
run_max = np.maximum.accumulate(nav)
dd = nav / run_max - 1.0
mdd = dd.min()
tot = nav[-1] / nav[0] - 1
print(f"span {dates[0].date()}..{dates[-1].date()}  n={len(nav)}  years={years:.2f}")
print(f"TOTAL={tot*100:.1f}%  CAGR={cagr*100:.2f}%  Sharpe={sharpe:.2f}  MDD={mdd*100:.2f}%")

pct = FuncFormatter(lambda y, _: f"{y:.0f}%")

# ===== 1. EQUITY CURVE =====
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.plot(dates, nav / 1000, color=BLUE, lw=1.7)
ax.fill_between(dates, nav / 1000, nav[0] / 1000, color=BLUE, alpha=0.07)
ax.axhline(nav[0] / 1000, color=GREY, lw=0.9, ls="--")
ax.set_title("Equity Curve", fontsize=14, fontweight="bold", loc="left")
ax.set_ylabel("Account value (thousand USD)")
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}k"))
fig.tight_layout(); fig.savefig(f"{OUT}/equity_curve.png"); plt.close(fig)

# ===== 2. DRAWDOWN SCHEME =====
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.fill_between(dates, dd * 100, 0, color=RED, alpha=0.35)
ax.plot(dates, dd * 100, color=RED, lw=1.1)
i_tr = int(np.argmin(dd))
ax.scatter([dates[i_tr]], [mdd * 100], color=RED, zorder=5, s=30)
ax.annotate(f"max drawdown {mdd*100:.1f}%", (dates[i_tr], mdd * 100),
            textcoords="offset points", xytext=(10, 8), color=RED, fontweight="bold")
ax.set_title("Drawdown", fontsize=14, fontweight="bold", loc="left")
ax.set_ylabel("Drawdown"); ax.yaxis.set_major_formatter(pct)
ax.set_ylim(min(mdd * 100 * 1.25, -1), 1)
fig.tight_layout(); fig.savefig(f"{OUT}/drawdown.png"); plt.close(fig)

# ===== 3. ROBUSTNESS HEATMAP (band x TP, Sharpe) =====
g = pd.read_csv("/home/user/Strong-Chicken-Journal/results/vwap_grid2d.csv")
piv = g.pivot(index="band_bps", columns="tp_points", values="sharpe").sort_index(ascending=False)
fig, ax = plt.subplots(figsize=(7.6, 5.2))
im = ax.imshow(piv.values, cmap="RdYlGn", aspect="auto",
               vmin=-np.nanmax(np.abs(piv.values)), vmax=np.nanmax(np.abs(piv.values)))
ax.set_xticks(range(len(piv.columns)))
ax.set_xticklabels([("no TP" if c == 0 else int(c)) for c in piv.columns])
ax.set_yticks(range(len(piv.index))); ax.set_yticklabels([int(b) for b in piv.index])
ax.set_xlabel("Take-profit distance (points)"); ax.set_ylabel("Hysteresis band (bps)")
for yi, b in enumerate(piv.index):
    for xi, c in enumerate(piv.columns):
        v = piv.values[yi, xi]
        ax.text(xi, yi, f"{v:.2f}", ha="center", va="center", fontsize=7,
                color="#111" if abs(v) < 0.55 else "#fff")
# mark chosen config band=20, tp=0 (no TP)
cy = list(piv.index).index(20); cx = list(piv.columns).index(0)
ax.add_patch(plt.Rectangle((cx - 0.5, cy - 0.5), 1, 1, fill=False, edgecolor="#111", lw=2.5))
ax.set_title("Robustness Heatmap", fontsize=14, fontweight="bold", loc="left")
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04); cb.set_label("Sharpe ratio")
fig.tight_layout(); fig.savefig(f"{OUT}/robustness_heatmap.png"); plt.close(fig)

# ===== 4. MONTE CARLO (dotted, return vs drawdown) =====
rng = np.random.default_rng(42)
N = 4000; L = len(ret)
tr_list, dd_list = [], []
for _ in range(N):
    r = rng.choice(ret, size=L, replace=True)
    eq = nav[0] * np.cumprod(1 + r)
    tr_list.append(eq[-1] / nav[0] - 1)
    dd_list.append((eq / np.maximum.accumulate(eq) - 1).min())
tr = np.array(tr_list) * 100; ddv = np.array(dd_list) * 100
fig, ax = plt.subplots(figsize=(7.4, 5.0))
colors = np.where(tr >= 0, GREEN, RED)
ax.scatter(ddv, tr, s=7, c=colors, alpha=0.35, edgecolors="none")
ax.axhline(0, color=GREY, lw=0.9)
ax.scatter([mdd * 100], [tot * 100], marker="*", s=320, color="#111",
           zorder=6, edgecolors="#fff", linewidths=0.8)
ax.annotate("observed backtest", (mdd * 100, tot * 100),
            textcoords="offset points", xytext=(-14, -26), ha="right",
            fontweight="bold", color="#111",
            arrowprops=dict(arrowstyle="->", color="#111", lw=1.1))
ax.set_title("Monte Carlo Simulation", fontsize=14, fontweight="bold", loc="left")
ax.set_xlabel("Maximum drawdown"); ax.set_ylabel("Total return")
ax.xaxis.set_major_formatter(pct); ax.yaxis.set_major_formatter(pct)
p_loss = (tr < 0).mean() * 100
ax.text(0.02, 0.97, f"{N} resamples of daily returns\nP(total return < 0) = {p_loss:.1f}%",
        transform=ax.transAxes, ha="left", va="top", fontsize=9, color=GREY)
fig.tight_layout(); fig.savefig(f"{OUT}/monte_carlo.png"); plt.close(fig)

print("figures ->", OUT)
print("MC: median total return", f"{np.median(tr):.1f}%", "| P(loss)", f"{p_loss:.1f}%")
