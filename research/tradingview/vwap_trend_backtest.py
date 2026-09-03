#!/usr/bin/env python3
# =====================================================================
# NQ VWAP Trend — LOKÁLNÍ BACKTEST (přesná kopie poslední verze indikátoru)
# Strong Chicken, Projekt 3.
#
# Logika (1:1 s vwap_trend_nq.pine, poslední verze):
#   - session VWAP: RTH 9:30-16:00 ET, HLC3 x volume, reset každý den
#   - hysterezní pásmo b = 20 bps:
#       LONG  když close > VWAP*(1+b)
#       SHORT když close < VWAP*(1-b)
#     (návrat k VWAP nic nespouští)
#   - JEN 1 TRADE/DEN: close za OPAČNÝM pásmem = zavřít (BEZ otočení),
#     další vstup až následující den
#   - EOD: flat v 16:00 ET; žádné overnight pozice
#   - TP = entry +/- 74.375 bodu (v indikátoru jen vizuální; tady volitelně
#     jako reálný exit, viz USE_TP_EXIT)
#
# POUŽITÍ:
#   python vwap_trend_backtest.py data_nq_1min.csv
#
# CSV formát (hlavička libovolné pořadí, jména case-insensitive):
#   datetime, open, high, low, close, volume
#   - datetime: cokoli, co pandas přečte (napr. 2025-09-30 09:31:00)
#   - když jsou časy v UTC, nastav INPUT_TZ = "UTC" (převede se na ET)
#   - když jsou už v ET, nech INPUT_TZ = "America/New_York"
# =====================================================================
import sys
import pandas as pd
import numpy as np
from datetime import time as dtime

# ------------------------- parametry -------------------------
BAND_BPS      = 20.0                  # hysterezní pásmo (bps) — zamrazeno
TP_POINTS     = 74.375                # poloviční TP (body)
USE_TP_EXIT   = False                 # False = jak indikátor (TP jen vizuál, exit = pásmo/EOD)
                                      # True  = TP je reálný exit (intrabar fill na TP)
FILL          = "next_open"           # "next_open" (jak QC backtest) nebo "close"
COST_POINTS   = 0.0                   # náklady round-turn v bodech (spread+komise), volitelně
INPUT_TZ      = "America/New_York"    # tz vstupních timestampů ("UTC" pokud jsou v UTC)
SESS_START    = dtime(9, 30)
SESS_END      = dtime(16, 0)          # inSess = [9:30, 16:00)
EOD_H, EOD_M  = 15, 59                # EOD bar (signál), fill na open 16:00 / close 15:59


# ------------------------- načtení dat -------------------------
def load(path):
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    dtc = pick("datetime", "date", "time", "timestamp", "dt")
    o = pick("open", "o"); h = pick("high", "h")
    l = pick("low", "l");  c = pick("close", "c"); v = pick("volume", "vol", "v")
    if None in (dtc, o, h, l, c):
        raise ValueError(f"CSV musí mít datetime/open/high/low/close (+ volume). Našel jsem: {list(df.columns)}")

    df = df.rename(columns={dtc: "dt", o: "open", h: "high", l: "low", c: "close",
                            (v or "close"): "volume"})
    if v is None:
        df["volume"] = 1.0  # kdyby chybělo volume, VWAP degeneruje na cenový průměr

    df["dt"] = pd.to_datetime(df["dt"])
    # timezone -> America/New_York
    if df["dt"].dt.tz is None:
        df["dt"] = df["dt"].dt.tz_localize(INPUT_TZ)
    df["dt"] = df["dt"].dt.tz_convert("America/New_York")
    df = df.sort_values("dt").reset_index(drop=True)
    return df[["dt", "open", "high", "low", "close", "volume"]]


# ------------------------- backtest -------------------------
def run(df):
    n = len(df)
    t   = df["dt"].dt
    o   = df["open"].to_numpy(float)
    hi  = df["high"].to_numpy(float)
    lo  = df["low"].to_numpy(float)
    cl  = df["close"].to_numpy(float)
    vol = df["volume"].to_numpy(float)
    tt  = df["dt"].dt.time.to_numpy()
    dd  = df["dt"].dt.date.to_numpy()

    inSess = np.array([(x >= SESS_START and x < SESS_END) for x in tt])
    b = BAND_BPS / 10000.0

    def next_fill(i, band_exit=False):
        # fill na open další svíčky ve stejném RTH dni, jinak close aktuální
        if FILL == "next_open" and i + 1 < n and dd[i + 1] == dd[i]:
            return o[i + 1]
        return cl[i]

    cumPV = cumV = 0.0
    pos = 0
    traded_today = False
    entry_px = np.nan
    entry_dt = None
    entry_dir = 0
    trades = []

    def close_trade(exit_px, exit_dt, reason):
        pts = entry_dir * (exit_px - entry_px) - COST_POINTS
        trades.append({
            "entry_dt": entry_dt, "exit_dt": exit_dt,
            "dir": "LONG" if entry_dir == 1 else "SHORT",
            "entry": round(entry_px, 4), "exit": round(exit_px, 4),
            "points": round(pts, 4), "reason": reason,
            "year": entry_dt.year,
        })

    for i in range(n):
        new_sess = inSess[i] and not (i > 0 and inSess[i - 1])
        if new_sess:
            cumPV = 0.0; cumV = 0.0
            pos = 0
            traded_today = False

        if not inSess[i]:
            continue

        hlc3 = (hi[i] + lo[i] + cl[i]) / 3.0
        cumPV += hlc3 * vol[i]
        cumV  += vol[i]
        if cumV <= 0:
            continue
        vwap = cumPV / cumV
        up = vwap * (1 + b)
        dn = vwap * (1 - b)

        is_eod = (t.hour[i] == EOD_H and t.minute[i] == EOD_M)

        # --- volitelný TP exit (intrabar), má přednost před pásmem/EOD ---
        if USE_TP_EXIT and pos != 0:
            tp_lvl = entry_px + entry_dir * TP_POINTS
            hit_tp = (hi[i] >= tp_lvl) if entry_dir == 1 else (lo[i] <= tp_lvl)
            if hit_tp:
                close_trade(tp_lvl, df["dt"][i], "TP")
                pos = 0
                continue

        if is_eod:
            if pos != 0:
                close_trade(next_fill(i, band_exit=True), df["dt"][i], "EOD")
                pos = 0
            continue

        if pos == 0:
            if not traded_today:
                if cl[i] > up:
                    pos = 1; traded_today = True
                    entry_px = next_fill(i); entry_dt = df["dt"][i]; entry_dir = 1
                elif cl[i] < dn:
                    pos = -1; traded_today = True
                    entry_px = next_fill(i); entry_dt = df["dt"][i]; entry_dir = -1
        elif pos == 1 and cl[i] < dn:
            close_trade(next_fill(i, band_exit=True), df["dt"][i], "BAND")
            pos = 0
        elif pos == -1 and cl[i] > up:
            close_trade(next_fill(i, band_exit=True), df["dt"][i], "BAND")
            pos = 0

    return pd.DataFrame(trades)


# ------------------------- statistika -------------------------
def stats(tr):
    if tr.empty:
        print("Žádné obchody."); return
    pts = tr["points"].to_numpy()
    wins = pts > 0
    n = len(pts)
    gross_win = pts[wins].sum()
    gross_loss = -pts[~wins].sum()
    eq = np.cumsum(pts)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak

    print("=" * 56)
    print("NQ VWAP Trend — lokální backtest (1 trade/den)")
    print("=" * 56)
    print(f"Období:          {tr['entry_dt'].min():%Y-%m-%d} → {tr['exit_dt'].max():%Y-%m-%d}")
    print(f"Parametry:       band={BAND_BPS}bps  TP={TP_POINTS}b  "
          f"TP_exit={USE_TP_EXIT}  fill={FILL}  cost={COST_POINTS}b")
    print("-" * 56)
    print(f"Obchodů:         {n}")
    print(f"Win rate:        {wins.mean()*100:5.1f} %   ({wins.sum()}W / {n-wins.sum()}L)")
    print(f"Celkem bodů:     {pts.sum():+.2f}")
    print(f"Průměr/obchod:   {pts.mean():+.3f} b   (medián {np.median(pts):+.3f})")
    print(f"Průměrný zisk:   {pts[wins].mean() if wins.any() else 0:+.3f} b")
    print(f"Průměrná ztráta: {pts[~wins].mean() if (~wins).any() else 0:+.3f} b")
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    print(f"Profit factor:   {pf:.2f}")
    print(f"Max drawdown:    {dd.min():.2f} b")
    exp_std = pts.std(ddof=1) if n > 1 else 0
    if exp_std > 0:
        print(f"Sharpe (per-trade, nean.): {pts.mean()/exp_std:.3f}")
    print("-" * 56)
    print("Podle roku:")
    by = tr.groupby("year")["points"]
    for yr, g in by:
        w = (g > 0).mean() * 100
        print(f"  {yr}:  n={len(g):4d}  win={w:4.1f}%  body={g.sum():+8.2f}")
    print("-" * 56)
    print("Důvod exitu:")
    for r, g in tr.groupby("reason")["points"]:
        print(f"  {r:5s}: n={len(g):4d}  body={g.sum():+8.2f}")
    print("=" * 56)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Použití: python vwap_trend_backtest.py <cesta_k_csv>")
        print("CSV sloupce: datetime, open, high, low, close, volume")
        sys.exit(1)
    data = load(sys.argv[1])
    tr = run(data)
    stats(tr)
    out = sys.argv[1].rsplit(".", 1)[0] + "_trades.csv"
    tr.to_csv(out, index=False)
    print(f"Seznam obchodů uložen: {out}")
