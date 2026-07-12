"""Rekonstrukce A1 (breakout) + A2 (range-bound) datasetů z chart sérií Fáze A.
Použití: python3 reconstruct.py <SPY|ES>"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import pandas as pd, numpy as np
from datetime import datetime, timezone
import qc_fetch as qc

SYM = sys.argv[1] if len(sys.argv) > 1 else "SPY"
PID = qc.project_id("research/phaseA_datasets")
bt = qc.latest_backtest(PID)
BID = bt["backtestId"]
print(f"[{SYM}] project={PID} backtest={BID} completed={bt.get('completed')}")
rs = qc.runtime_stats(PID, BID)
print("runtime:", {k: rs[k] for k in rs if k in
      ("export_symbol","days_classified","n_breakout","n_rangebound","n_long","n_short","skip_warmup","bars_seen")})
assert rs.get("export_symbol") == SYM, f"POZOR: backtest exportoval {rs.get('export_symbol')}, ne {SYM}!"

S = qc.chart_series(PID, BID, "a")
def ser(name): return pd.Series(S.get(name, {}), name=name)

def ts_to_date(ix):
    return (pd.to_datetime(list(ix), unit="s", utc=True)
            .tz_convert("America/New_York").normalize().tz_localize(None))

def decode_cat(v):
    v = int(round(v))
    dir3 = v % 3; v //= 3
    inside = v % 2; v //= 2
    b5 = v % 3; v //= 3
    r = []
    for _ in range(4):
        r.append(v % 3); v //= 3
    return dir3 - 1, inside, b5, r  # direction, inside_day, b5_origin, [r10,r20,r30,r40]

# ---- A1 breakout ----
cat = ser("a_cat")
a1 = pd.DataFrame(index=cat.index)
dec = cat.apply(decode_cat)
a1["direction"] = [d[0] for d in dec]
a1["inside_day"] = [d[1] for d in dec]
a1["b5_origin"] = [d[2] for d in dec]
for i, thr in enumerate([10,20,30,40]):
    a1[f"rev{thr}"] = [d[3][i] for d in dec]   # 2=win,1=tie,0=loss
a1["dist_atr"] = ser("a_dist_atr")
a1["vol_ratio"] = ser("a_vol_ratio")
a1["prevday_body"] = ser("a_prevday_body")
a1["poc_dist_atr"] = ser("a_poc_dist_atr")
on = ser("a_on_ret")
a1["on_ret_pct"] = on.reindex(a1.index)
a1.index = ts_to_date(a1.index)
a1 = a1.sort_index()
a1.insert(0, "instrument", SYM)

# ---- A2 range-bound ----
rr = ser("a_rr")
a2 = pd.DataFrame(index=rr.index)
a2["realized_range_atr"] = rr
a2["rth_ret_pct"] = ser("a_rth_ret")
a2["on_ret_pct"] = on.reindex(a2.index)
a2.index = ts_to_date(a2.index)
a2 = a2.sort_index()
a2.insert(0, "instrument", SYM)

os.makedirs("data/cache", exist_ok=True)
a1.index.name = "date"
a2.index.name = "date"
a1.to_csv(f"data/cache/a1_{SYM.lower()}.csv")
a2.to_csv(f"data/cache/a2_{SYM.lower()}.csv")

print(f"\nA1 breakout rows: {len(a1)} | long={int((a1.direction>0).sum())} short={int((a1.direction<0).sum())}")
print("A1 head:\n", a1.head(6).to_string())
print("\nA2 range-bound rows:", len(a2))
print("A2 head:\n", a2.head(4).to_string())

# ---- naivní reverze win rate ----
print("\n--- naivní reverze (win=TP reversion first, tie=neither by close, loss=SL first) ---")
for thr in [10,20,30,40]:
    col = a1[f"rev{thr}"]
    n = len(col); w=int((col==2).sum()); t=int((col==1).sum()); l=int((col==0).sum())
    wr_raw = 100*w/n
    wr_excl = 100*w/(w+l) if (w+l)>0 else float('nan')
    print(f"  thr={thr:>2} ES-pts (SPY {thr/10:.1f}$): n={n} win={w} tie={t} loss={l} | raw={wr_raw:.2f}% | excl-tie={wr_excl:.2f}%")
