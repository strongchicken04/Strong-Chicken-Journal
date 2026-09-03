# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# TICK PROBE — ověření dostupnosti ES tickových dat pro footprint deltu.
# Krátké okno (10 dní). Zjišťuje: tečou trade ticky? tečou quote ticky
# (nutné pro klasifikaci agresora)? kolik jich je/den (feasibility)?
# rekonstruuje net deltu (buy vol − sell vol) přes Lee-Ready pravidlo.
# =====================================================================


class TickProbe(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 6, 3)
        self.set_end_date(2024, 6, 14)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)

        fut = self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.TICK,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.RAW,
            contract_depth_offset=0, extended_market_hours=True)
        self.sym = fut.symbol
        self.best_bid = 0.0
        self.best_ask = 0.0
        self.d = None
        self._reset(None)

    def _reset(self, day):
        self.d = day
        self.nt = 0      # trade ticks
        self.nq = 0      # quote ticks
        self.vol = 0.0
        self.buy = 0.0
        self.sell = 0.0
        self.unclass = 0.0

    def on_data(self, slice):
        for sym, ticks in slice.ticks.items():
            for t in ticks:
                day = t.time.date()
                if self.d != day:
                    if self.d is not None:
                        self._flush()
                    self._reset(day)
                if t.tick_type == TickType.Quote:
                    if t.bid_price > 0:
                        self.best_bid = t.bid_price
                    if t.ask_price > 0:
                        self.best_ask = t.ask_price
                    self.nq += 1
                elif t.tick_type == TickType.Trade:
                    self.nt += 1
                    q = t.quantity
                    self.vol += q
                    if self.best_ask > 0 and t.price >= self.best_ask:
                        self.buy += q
                    elif self.best_bid > 0 and t.price <= self.best_bid:
                        self.sell += q
                    else:
                        self.unclass += q

    def _flush(self):
        delta = self.buy - self.sell
        cls = 100.0 * (self.buy + self.sell) / self.vol if self.vol > 0 else 0.0
        self.log(f"###TICK### date={self.d} trades={self.nt} quotes={self.nq} "
                 f"vol={self.vol:.0f} buy={self.buy:.0f} sell={self.sell:.0f} "
                 f"delta={delta:.0f} classified%={cls:.1f}")

    def on_end_of_algorithm(self):
        if self.d is not None:
            self._flush()
