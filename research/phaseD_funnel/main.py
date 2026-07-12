# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# =====================================================================
# FÁZE D — Funnel na C1 VWAP mean-reversion (ES, range-bound dny).
# Cross-tab reverze podle: band(±1,±2) × strana(upper/lower) ×
# 30min blok STARTU eventu × overnight tercina dne.
# Lokálně pak: C1 base -> +C3 timing (blok) -> +C4 overnight (tercina),
# upper/lower zvlášť.
#
# Definice VWAP/eventu/reverze = identické s Fází C (viz tam).
# Overnight tercina: |(day_open - prev_RTH_close)/prev_RTH_close|*100
#   vs. hranice z A2 (ES): t1=0.1754 %, t2=0.4178 %.
# =====================================================================

EXPORT_SYMBOL = "ES"

RTH_OPEN_MIN = 9 * 60 + 30
FIRST15_END_MIN = 9 * 60 + 45
VWAP_START_MIN = 10 * 60
RTH_CLOSE_MIN = 16 * 60
ON_T1 = 0.1754   # overnight tercina hranice (%)
ON_T2 = 0.4178


class PhaseD(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol

        self.daily = deque(maxlen=20)
        self._reset_day(None)

        # cross-tab buňky: (band, side, block, on_terc) -> [n, rev]
        self.cells = {}
        self.n_range_days = 0
        self.bars_seen = 0

    def _reset_day(self, d):
        self.cur_date = d
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None
        self.classified = None
        self.on_terc = None
        self.cv = 0.0
        self.cpv = 0.0
        self.cpv2 = 0.0
        # (k,side) -> (start_minute, cell_key) nebo None
        self.active = {(k, s): None for k in (1, 2) for s in ("upper", "lower")}

    def _band(self):
        hs = [b["h"] for b in list(self.daily)[-7:]]
        ls = [b["l"] for b in list(self.daily)[-7:]]
        return min(ls), max(hs)

    def _cell(self, key):
        if key not in self.cells:
            self.cells[key] = [0, 0]
        return self.cells[key]

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        self.bars_seen += 1
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        if self.cur_date != d:
            self._finalize_prev_day()
            self._reset_day(d)

        if not (RTH_OPEN_MIN + 1 <= minutes <= RTH_CLOSE_MIN):
            return

        if self.d_open is None:
            self.d_open = bar.open
        self.d_high = bar.high if self.d_high is None else max(self.d_high, bar.high)
        self.d_low = bar.low if self.d_low is None else min(self.d_low, bar.low)
        self.d_close = bar.close

        tp = (bar.high + bar.low + bar.close) / 3.0
        v = float(bar.volume)
        if v > 0:
            self.cv += v
            self.cpv += v * tp
            self.cpv2 += v * tp * tp

        if minutes == FIRST15_END_MIN and self.classified is None:
            if len(self.daily) >= 15:
                bl, bh = self._band()
                self.classified = (bl <= bar.close <= bh)
                # overnight tercina
                prevC = self.daily[-1]["c"]
                onr = abs((self.d_open - prevC) / prevC) * 100 if prevC else 0.0
                self.on_terc = 0 if onr <= ON_T1 else (1 if onr <= ON_T2 else 2)
            if self.classified:
                self.n_range_days += 1

        if not self.classified:
            return

        # C1 VWAP eventy (od 10:00)
        if self.cv > 0 and minutes >= VWAP_START_MIN:
            vwap = self.cpv / self.cv
            var = self.cpv2 / self.cv - vwap * vwap
            std = math.sqrt(var) if var > 0 else 0.0
            c = bar.close
            if std > 0:
                for k in (1, 2):
                    up = vwap + k * std
                    lo = vwap - k * std
                    # upper
                    key = (k, "upper")
                    if self.active[key] is None:
                        if c >= up:
                            blk = (minutes - RTH_OPEN_MIN) // 30
                            ck = (k, "upper", int(blk), self.on_terc)
                            self._cell(ck)[0] += 1
                            self.active[key] = ck
                    elif c <= vwap:
                        self._cell(self.active[key])[1] += 1
                        self.active[key] = None
                    # lower
                    key = (k, "lower")
                    if self.active[key] is None:
                        if c <= lo:
                            blk = (minutes - RTH_OPEN_MIN) // 30
                            ck = (k, "lower", int(blk), self.on_terc)
                            self._cell(ck)[0] += 1
                            self.active[key] = ck
                    elif c >= vwap:
                        self._cell(self.active[key])[1] += 1
                        self.active[key] = None

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})

    def on_end_of_algorithm(self):
        self._finalize_prev_day()
        self.set_runtime_statistic("export_symbol", EXPORT_SYMBOL)
        self.set_runtime_statistic("range_days", str(self.n_range_days))
        self.set_runtime_statistic("n_cells", str(len(self.cells)))
        self.log(f"###DSUM### sym={EXPORT_SYMBOL} range_days={self.n_range_days} cells={len(self.cells)}")
        # log všech nenulových buněk
        for (k, s, blk, ot), (n, rev) in sorted(self.cells.items()):
            self.log(f"###D### b={k} s={s} blk={blk} ot={ot} n={n} rev={rev}")
