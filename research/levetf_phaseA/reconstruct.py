"""Rekonstrukce EOD momentum datasetu. python3 reconstruct.py <ES|SPY>"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import pandas as pd, numpy as np
import qc_fetch as qc
SYM = sys.argv[1] if len(sys.argv) > 1 else "ES"
PID = qc.project_id("research/levetf_phaseA")
bt = qc.latest_backtest(PID); BID = bt["backtestId"]
rs = qc.runtime_stats(PID, BID)
print(f"[{SYM}] PID={PID} BID={BID}", {k: rs.get(k) for k in ("export_symbol","n_days")})
assert rs.get("export_symbol") == SYM, f"backtest je {rs.get('export_symbol')}, ne {SYM}"
S = qc.chart_series(PID, BID, "a")
cols = ["r_pre60","r_last60","r_pre30","r_last30","atr_pct"]
df = pd.DataFrame({n: pd.Series(S.get(n, {})) for n in cols})
df.index = (pd.to_datetime(list(df.index), unit="s", utc=True)
            .tz_convert("America/New_York").normalize().tz_localize(None))
df.index.name="date"; df=df.sort_index(); df["year"]=df.index.year; df["instrument"]=SYM
df["agree60"] = (np.sign(df.r_pre60)==np.sign(df.r_last60)).astype(int)
df["agree30"] = (np.sign(df.r_pre30)==np.sign(df.r_last30)).astype(int)
os.makedirs("data/cache", exist_ok=True)
df.to_csv(f"data/cache/eod_{SYM.lower()}.csv")
print("rows:", len(df))
print(df.head(5).to_string())
print("\nagree60 overall: %.1f%% | agree30 overall: %.1f%%" % (100*df.agree60.mean(), 100*df.agree30.mean()))
print("r_last60 mean/std bps: %.1f/%.1f | r_last30 mean/std: %.1f/%.1f" % (df.r_last60.mean(),df.r_last60.std(),df.r_last30.mean(),df.r_last30.std()))
