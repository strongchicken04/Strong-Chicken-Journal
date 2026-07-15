# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — R3: JEDNORÁZOVÝ OOS BĚH (frozen spec r3_frozen_spec.md,
# VÝSLOVNĚ POTVRZENO uživatelem). NQ, hysterezní pásmo 20 bps.
# OOS okno 2025-10-01 → 2026-07-11. Export gross NAV + trades/den;
# costs (0,4/1,2 bps) a vol-targeting (EWMA20, cap 1×, target 15 %)
# se aplikují LOKÁLNĚ identicky s IS pipeline. ŽÁDNÉ ITEROVÁNÍ.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4     # FROZEN 20 bps


class R3OOS(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2025, 10, 1)    # OOS
        self.set_end_date(2026, 7, 11)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.trades = 0
        self.wins = 0
        self.trades_today = 0
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None

    def _close_at(self, price):
        if self.pos == 0:
            return
        pnl = self.pos * (price - self.entry) * self.shares
        self.nav += pnl
        self.trades += 1
        if pnl > 0:
            self.wins += 1
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0

    def _fill_open(self, price):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self._close_at(price)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            self.trades_today += 1

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        if self.cur_date != d:
            if self.cur_date is not None:
                self.pending = None
                if self.pos != 0 and self.last_close:
                    self._close_at(self.last_close)
                self.plot("nav", "NQ_nav", self.nav)
                self.plot("nav", "NQ_trd", self.trades_today)
                self.trades_today = 0
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None
        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return
        self._fill_open(bar.open)
        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        c = bar.close
        up = vwap * (1 + BAND)
        dn = vwap * (1 - BAND)
        if minutes < CLOSE_MIN:
            if self.pos == 0:
                if c > up:
                    self.pending = 1
                elif c < dn:
                    self.pending = -1
            elif self.pos > 0 and c < dn:
                self.pending = -1
            elif self.pos < 0 and c > up:
                self.pending = 1
        else:
            self.pending = None
            if self.pos != 0:
                self._close_at(bar.close)

    def on_end_of_algorithm(self):
        self.pending = None
        if self.pos != 0 and self.last_close:
            self._close_at(self.last_close)
        self.plot("nav", "NQ_nav", self.nav)
        self.plot("nav", "NQ_trd", self.trades_today)
        self.set_runtime_statistic("trades", str(self.trades))
        self.set_runtime_statistic("wins", str(self.wins))
        self.set_runtime_statistic("final_nav", f"{self.nav:.2f}")
        self.log(f"###R3### trades={self.trades} wins={self.wins} final_nav={self.nav:.2f}")
