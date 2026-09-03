# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — 2D PARAMETER GRID (band x TP) pro overfitting diagnózu.
# "Poslední verze" strategie (1 trade/den, bez reverzu) na NQ, IS only
# 2018-01-02 -> 2025-09-30. Pro každou kombinaci (band_bps, tp_points)
# spočítá IS total return + Sharpe. Cíl: spike (overfit) vs plateau
# (robust) heatmapa. Nasazená buňka = band=20, tp=none.
# TP > 0 = reálný intrabar limit exit; tp=0 = bez TP (exit pásmo/EOD).
# Náklad 1.2 bps round-turn. NIC se nemění podle výsledku (diagnóza).
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
COST = 1.2 / 1e4
BANDS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
TPS = [0, 250, 180, 130, 100, 75, 55, 40]     # 0 = bez TP


class Sim:
    def __init__(self, band_bps, tp_pts):
        self.band = band_bps / 1e4
        self.band_bps = band_bps
        self.tp = tp_pts
        self.nav = 100000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.tp_level = None
        self.pending_entry = 0
        self.pending_exit = False
        self.traded_today = False
        self.n = 0
        self.wins = 0
        self.prev_day_nav = None
        self.sr = 0.0
        self.sr2 = 0.0
        self.nd = 0

    def entry_(self, price, d):
        self.pos = d; self.entry = price; self.shares = self.nav / price
        self.tp_level = (price + d * self.tp) if self.tp else None

    def close_(self, price):
        gross = self.pos * (price - self.entry) * self.shares
        self.nav += gross - self.entry * self.shares * COST
        self.n += 1
        if gross - self.entry * self.shares * COST > 0:
            self.wins += 1
        self.pos = 0; self.entry = 0.0; self.shares = 0.0; self.tp_level = None

    def day_return(self):
        if self.prev_day_nav:
            r = self.nav / self.prev_day_nav - 1
            self.sr += r; self.sr2 += r * r; self.nd += 1
        self.prev_day_nav = self.nav


class Grid2D(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)          # IS only
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = [Sim(b, tp) for b in BANDS for tp in TPS]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        if self.cur_date != d:
            if self.cur_date is not None:
                for s in self.sims:
                    if s.pos != 0 and self.last_close:
                        s.close_(self.last_close)
                    s.pending_entry = 0; s.pending_exit = False
                    s.traded_today = False
                    s.day_return()
            self.cur_date = d
            self.cum_pv = 0.0; self.cum_v = 0.0; self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # fill pending na open
        for s in self.sims:
            if s.pending_exit and s.pos != 0:
                s.close_(bar.open)
            s.pending_exit = False
            if s.pending_entry != 0 and s.pos == 0:
                s.entry_(bar.open, s.pending_entry)
            s.pending_entry = 0

        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        is_eod = (minutes == CLOSE_MIN)

        for s in self.sims:
            up = vwap * (1 + s.band); dn = vwap * (1 - s.band)
            if is_eod:
                s.pending_entry = 0; s.pending_exit = False
                if s.pos != 0:
                    s.close_(bar.close)
                continue
            # TP intrabar limit
            if s.pos != 0 and s.tp_level is not None:
                if s.pos == 1 and bar.high >= s.tp_level:
                    s.close_(s.tp_level); continue
                if s.pos == -1 and bar.low <= s.tp_level:
                    s.close_(s.tp_level); continue
            if s.pos == 1:
                if bar.close < dn: s.pending_exit = True
            elif s.pos == -1:
                if bar.close > up: s.pending_exit = True
            else:
                if not s.traded_today:
                    if bar.close > up:
                        s.pending_entry = 1; s.traded_today = True
                    elif bar.close < dn:
                        s.pending_entry = -1; s.traded_today = True

    def on_end_of_algorithm(self):
        import math
        for s in self.sims:
            if s.pos != 0 and self.last_close:
                s.close_(self.last_close)
            s.day_return()
            ret = s.nav / 100000.0 - 1
            if s.nd > 1:
                mean = s.sr / s.nd
                var = max(s.sr2 / s.nd - mean * mean, 0.0)
                sd = math.sqrt(var)
                sharpe = (mean / sd * math.sqrt(252)) if sd > 0 else 0.0
            else:
                sharpe = 0.0
            self.log(f"###G2D### band={s.band_bps} tp={s.tp} "
                     f"ret={ret*100:.2f} sharpe={sharpe:.3f} n={s.n} wins={s.wins}")
