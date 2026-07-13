# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# =====================================================================
# LEV-ETF FÁZE A — EOD momentum dataset (compute-only). OPRAVENÉ cutoffy.
# Hypotéza = posledních 30-60 min RTH:
#   K=60: predictor r(9:30->15:00), outcome r(15:00->16:00)  [posl. 60 min]
#   K=30: predictor r(9:30->15:30), outcome r(15:30->16:00)  [posl. 30 min]
# Disjunktní predictor/outcome okna. + atr% (ATR14 do včerejška / cena).
# Look-ahead-free, in-sample only. Export chart série (bps). ES / SPY.
# =====================================================================

EXPORT_SYMBOL = "ES"

RTH_OPEN_MIN = 9 * 60 + 30    # 570
CUT60_MIN = 15 * 60           # 900  (15:00) = T-60
CUT30_MIN = 15 * 60 + 30      # 930  (15:30) = T-30
CLOSE_MIN = 16 * 60           # 960  (16:00)


class LevETFPhaseA(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        if EXPORT_SYMBOL == "SPY":
            sec = self.add_equity("SPY", Resolution.MINUTE,
                                  data_normalization_mode=DataNormalizationMode.RAW)
            self.sym = sec.symbol
        else:
            fut = self.add_future(
                Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                contract_depth_offset=0, extended_market_hours=False)
            fut.set_filter(0, 182)
            self.sym = fut.symbol
        self.daily = deque(maxlen=20)
        self._reset_day(None)
        self.n_emit = 0
        self.bars_seen = 0

    def _reset_day(self, d):
        self.cur_date = d
        self.d_open = self.d_high = self.d_low = self.d_close = None
        self.p_open = self.p_c60 = self.p_c30 = self.p_close = None
        self.emitted = False

    def _atr14(self):
        bars = list(self.daily)[-15:]
        trs = [max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i-1]["c"]),
                   abs(bars[i]["l"] - bars[i-1]["c"])) for i in range(1, len(bars))]
        return sum(trs) / len(trs) if trs else None

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
        if not (RTH_OPEN_MIN + 1 <= minutes <= CLOSE_MIN):
            return
        if self.d_open is None:
            self.d_open = bar.open
        self.d_high = bar.high if self.d_high is None else max(self.d_high, bar.high)
        self.d_low = bar.low if self.d_low is None else min(self.d_low, bar.low)
        self.d_close = bar.close
        if minutes == RTH_OPEN_MIN + 1 and self.p_open is None:
            self.p_open = bar.open
        if minutes == CUT60_MIN:
            self.p_c60 = bar.close
        if minutes == CUT30_MIN:
            self.p_c30 = bar.close
        if minutes == CLOSE_MIN and not self.emitted:
            self.p_close = bar.close
            self._emit()
            self.emitted = True

    def _emit(self):
        if None in (self.p_open, self.p_c60, self.p_c30, self.p_close):
            return
        if len(self.daily) < 15:
            return
        atr = self._atr14()
        if atr is None or atr <= 0 or self.p_open <= 0:
            return
        self.plot("a", "r_pre60", (self.p_c60 / self.p_open - 1) * 10000)
        self.plot("a", "r_last60", (self.p_close / self.p_c60 - 1) * 10000)
        self.plot("a", "r_pre30", (self.p_c30 / self.p_open - 1) * 10000)
        self.plot("a", "r_last30", (self.p_close / self.p_c30 - 1) * 10000)
        self.plot("a", "atr_pct", (atr / self.p_open) * 100)
        self.n_emit += 1

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("export_symbol", EXPORT_SYMBOL)
        self.set_runtime_statistic("n_days", str(self.n_emit))
        self.log(f"###ASUM### sym={EXPORT_SYMBOL} n_days={self.n_emit} bars={self.bars_seen}")
