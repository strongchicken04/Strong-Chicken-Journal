"""FÁZE B — breakout proměnné B1–B8, testované jednotlivě na A1.
Lokální analýza (0 QC kliků). Primární instrument ES, SPY jako robustness.
Outcome sensitivity: rev30_excl (primární), rev30_raw, rev10_raw.

Spuštění: python3 analyze.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import numpy as np, pandas as pd
from stats import Proportion, fisher_exact, wilson_ci

a1 = pd.read_csv("data/cache/a1_all.csv", parse_dates=["date"])
cal = pd.read_csv("data/cache/a3_calendar.csv", parse_dates=["date"])
event_dates = set(cal["date"].dt.normalize())
a1["is_event"] = a1["date"].dt.normalize().isin(event_dates).astype(int)
fomc = set(cal[cal.event == "FOMC"]["date"].dt.normalize())
a1["is_fomc"] = a1["date"].dt.normalize().isin(fomc).astype(int)


def outcome_mask(df, name):
    """vrací (win_series, valid_mask) pro daný outcome."""
    if name == "rev30_raw":
        return (df["rev30"] == 2), pd.Series(True, index=df.index)
    if name == "rev30_excl":
        valid = df["rev30"] != 1
        return (df["rev30"] == 2), valid
    if name == "rev10_raw":
        return (df["rev10"] == 2), pd.Series(True, index=df.index)
    if name == "rev20_excl":
        valid = df["rev20"] != 1
        return (df["rev20"] == 2), valid
    raise ValueError(name)


def prop(df, outcome):
    win, valid = outcome_mask(df, outcome)
    d = df[valid]
    w = int(win[valid].sum())
    return Proportion(len(d), w)


def buckets_for(df, var):
    """vrací list (label, boolean_mask) pro danou proměnnou."""
    d = df
    if var == "B1_direction":
        return [("long", d.direction == 1), ("short", d.direction == -1)]
    if var == "B2_dist_atr":
        q = d.dist_atr.quantile([1/3, 2/3]).values
        return [("small", d.dist_atr <= q[0]),
                ("med", (d.dist_atr > q[0]) & (d.dist_atr <= q[1])),
                ("large", d.dist_atr > q[1])]
    if var == "B3_vol_ratio":
        return [("vol>1.0", d.vol_ratio > 1.0), ("vol<=1.0", d.vol_ratio <= 1.0)]
    if var == "B5_origin":
        return [("overnight/gap(2)", d.b5_origin == 2), ("rth_fresh(1)", d.b5_origin == 1)]
    if var == "B6_poc_dist_atr":
        q = d.poc_dist_atr.quantile([1/3, 2/3]).values
        return [("poc_low", d.poc_dist_atr <= q[0]),
                ("poc_mid", (d.poc_dist_atr > q[0]) & (d.poc_dist_atr <= q[1])),
                ("poc_high", d.poc_dist_atr > q[1])]
    if var == "B8_prevday_body":
        q = d.prevday_body.quantile([1/3, 2/3]).values
        return [("body_neg", d.prevday_body <= q[0]),
                ("body_mid", (d.prevday_body > q[0]) & (d.prevday_body <= q[1])),
                ("body_pos", d.prevday_body > q[1])]
    if var == "B8_inside_day":
        return [("inside_day", d.inside_day == 1), ("not_inside", d.inside_day == 0)]
    if var == "B7_calendar":
        return [("event", d.is_event == 1), ("non_event", d.is_event == 0)]
    raise ValueError(var)


VARS = ["B1_direction", "B2_dist_atr", "B3_vol_ratio", "B5_origin",
        "B6_poc_dist_atr", "B8_prevday_body", "B8_inside_day", "B7_calendar"]
OUTCOMES = ["rev30_excl", "rev30_raw", "rev10_raw"]

rows = []
for inst in ["ES", "SPY"]:
    df = a1[a1.instrument == inst]
    for outc in OUTCOMES:
        base = prop(df, outc)
        for var in VARS:
            bks = buckets_for(df, var)
            # win/n per bucket for Fisher vs complement
            for label, mask in bks:
                sub = df[mask]
                p = prop(sub, outc)
                comp = prop(df[~mask], outc)
                fp = fisher_exact(p.k, p.n, comp.k, comp.n) if p.n and comp.n else float("nan")
                rows.append({
                    "instrument": inst, "outcome": outc, "variable": var,
                    "bucket": label, "n": p.n, "win": p.k,
                    "win_rate": round(100 * p.rate, 2) if p.n else float("nan"),
                    "ci_lo": round(100 * p.ci95[0], 2) if p.n else float("nan"),
                    "ci_hi": round(100 * p.ci95[1], 2) if p.n else float("nan"),
                    "base_rate": round(100 * base.rate, 2) if base.n else float("nan"),
                    "delta_pp": round(100 * (p.rate - base.rate), 2) if p.n and base.n else float("nan"),
                    "fisher_p_vs_rest": round(fp, 4),
                    "flag": "n<30" if p.n < 30 else "",
                })

res = pd.DataFrame(rows)
os.makedirs("results", exist_ok=True)
res.to_csv("results/phaseB_raw.csv", index=False)
print("uloženo results/phaseB_raw.csv, řádků:", len(res))

# přehled baselines
print("\n=== overall baselines (breakout) ===")
for inst in ["ES", "SPY"]:
    df = a1[a1.instrument == inst]
    line = f"{inst}: "
    for outc in OUTCOMES:
        b = prop(df, outc)
        line += f"{outc}={100*b.rate:.1f}%(n={b.n})  "
    print(line)

# primární: ES / rev30_excl
print("\n=== ES | rev30_excl (primární) — proměnné jednotlivě ===")
sub = res[(res.instrument == "ES") & (res.outcome == "rev30_excl")]
for var in VARS:
    print(f"\n{var}:")
    for _, r in sub[sub.variable == var].iterrows():
        sig = "  *" if (not np.isnan(r.fisher_p_vs_rest) and r.fisher_p_vs_rest < 0.05) else ""
        print(f"  {r.bucket:16s} n={int(r.n):3d} wr={r.win_rate:5.1f}% "
              f"CI[{r.ci_lo:4.1f},{r.ci_hi:4.1f}] Δ={r.delta_pp:+5.1f}pp "
              f"p={r.fisher_p_vs_rest:.3f}{sig} {r.flag}")
