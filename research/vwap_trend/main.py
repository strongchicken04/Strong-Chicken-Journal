# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — DIAGNOSTIKA D1 (jen výpočet, nic se nevaliduje).
# 2 paralelní simy na NQ: b=0 (raw paper pravidla) a b=20 bps (frozen).
# Okno 2018-01-02 -> 2026-07-11 (platforma utne ~2026-04-16; segment
# 2025-10+ = SPOTŘEBOVANÁ OOS, používá se zde jen diagnosticky).
# Export: denní NAV+trades per sim, denní NQ RTH return (pro realizovanou
# vol), per-year trades/wins per sim (hit ratio po letech).
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BANDS = [0.0, 20.0]   # bps


class Sim:
    def __init__(self, band_bps):
        self.b = band_bps / 1e4
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.trades_today = 0
        self.yr = {}   # year -> [trades, wins]

    def _yr(self, year):
        return self.yr.setdefault(year, [0, 0])

    def fill_open(self, price, year):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close_at(price, year)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            self.trades_today += 1

    def close_at(self, price, year):
        if self.pos == 0:
            return
        pnl = self.pos * (price - self.entry) * self.shares
        self.nav += pnl
        a = self._yr(year)
        a[0] += 1
        if pnl > 0:
            a[1] += 1
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0

    def signal(self, close, vwap, first_bar):
        up = vwap * (1 + self.b)
        dn = vwap * (1 - self.b)
        if self.b == 0.0 and first_bar:
            # raw paperové pravidlo: vstup jen podle prvního baru
            if close > vwap:
                self.pending = 1
            elif close < vwap:
                self.pending = -1
            return
        if self.pos == 0:
            if close > up:
                self.pending = 1
            elif close < dn:
                self.pending = -1
        elif self.pos > 0 and close < dn:
            self.pending = -1
        elif self.pos < 0 and close > up:
            self.pending = 1


class D1Diag(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2026, 7, 11)   # platforma utne na konci dostupnych dat
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = {b: Sim(b) for b in BANDS}
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        self.day_open = None

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        year = t.year
        if self.cur_date != d:
            if self.cur_date is not None:
                py = self.cur_date.year
                for b, sim in self.sims.items():
                    sim.pending = None
                    if sim.pos != 0 and self.last_close:
                        sim.close_at(self.last_close, py)
                    lbl = "b0" if b == 0.0 else "b20"
                    self.plot("nav", f"{lbl}_nav", sim.nav)
                    self.plot("nav", f"{lbl}_trd", sim.trades_today)
                    sim.trades_today = 0
                if self.day_open and self.last_close:
                    self.plot("nav", "nq_ret",
                              (self.last_close / self.day_open - 1) * 1e4)
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None
            self.day_open = None
        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return
        if self.day_open is None:
            self.day_open = bar.open
        for sim in self.sims.values():
            sim.fill_open(bar.open, year)
        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        if minutes < CLOSE_MIN:
            for sim in self.sims.values():
                sim.signal(bar.close, vwap, minutes == OPEN_BAR_MIN)
        else:
            for sim in self.sims.values():
                sim.pending = None
                if sim.pos != 0:
                    sim.close_at(bar.close, year)

    def on_end_of_algorithm(self):
        for b, sim in self.sims.items():
            sim.pending = None
            if sim.pos != 0 and self.last_close:
                sim.close_at(self.last_close, self.cur_date.year)
            lbl = "b0" if b == 0.0 else "b20"
            self.plot("nav", f"{lbl}_nav", sim.nav)
            self.plot("nav", f"{lbl}_trd", sim.trades_today)
            for y in sorted(sim.yr):
                tr, w = sim.yr[y]
                self.log(f"###D1### band={lbl} year={y} trades={tr} wins={w}")
            self.set_runtime_statistic(f"{lbl}_trades",
                                       str(sum(v[0] for v in sim.yr.values())))
