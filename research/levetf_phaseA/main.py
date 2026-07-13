# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# =====================================================================
# LEV-ETF FÁZE A — EOD momentum dataset (compute-only).
# Per RTH den: returny na disjunktních oknech (žádný překryv):
#   r_o_t60 = 9:30->14:00, r_t60_c = 14:00->16:00
#   r_o_t30 = 9:30->15:00, r_t30_c = 15:00->16:00
# + atr% (ATR14 do včerejška / cena). Rok = z timestampu.
# Look-ahead-free (v čase T jen data do T). In-sample only.
# Export přes chart série (bps). EXPORT_SYMBOL: ES / SPY.
# =====================================================================

EXPORT_SYMBOL = "ES"

OPEN_MIN = 9 * 60 + 30          # 570  (open bar končí 571)
T60_MIN = 14 * 60              # 840  (14:00)
T30_MIN = 15 * 60             # 900  (15:00)
CLOSE_MIN = 16 * 60          # 960  (16:00)
RTH_OPEN_MIN = 9 * 60 + 30


class LevETFPhaseA(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)     # IN-SAMPLE
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
        self.p_open = self.p_t60 = self.p_t30 = self.p_close = None
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
        # denní OHLC (RTH)
        if self.d_open is None:
            self.d_open = bar.open
        self.d_high = bar.high if self.d_high is None else max(self.d_high, bar.high)
        self.d_low = bar.low if self.d_low is None else min(self.d_low, bar.low)
        self.d_close = bar.close
        # snímky cen
        if minutes == OPEN_MIN + 1 and self.p_open is None:
            self.p_open = bar.open       # 9:30 open
        if minutes == T60_MIN:
            self.p_t60 = bar.close       # 14:00
        if minutes == T30_MIN:
            self.p_t30 = bar.close       # 15:00
        if minutes == CLOSE_MIN and not self.emitted:
            self.p_close = bar.close     # 16:00
            self._emit()
            self.emitted = True

    def _emit(self):
        if None in (self.p_open, self.p_t60, self.p_t30, self.p_close):
            return
        if len(self.daily) < 15:
            return
        atr = self._atr14()
        if atr is None or atr <= 0 or self.p_open <= 0:
            return
        r_o_t60 = (self.p_t60 / self.p_open - 1) * 10000   # bps
        r_t60_c = (self.p_close / self.p_t60 - 1) * 10000
        r_o_t30 = (self.p_t30 / self.p_open - 1) * 10000
        r_t30_c = (self.p_close / self.p_t30 - 1) * 10000
        atr_pct = (atr / self.p_open) * 100
        self.plot("a", "r_o_t60", r_o_t60)
        self.plot("a", "r_t60_c", r_t60_c)
        self.plot("a", "r_o_t30", r_o_t30)
        self.plot("a", "r_t30_c", r_t30_c)
        self.plot("a", "atr_pct", atr_pct)
        self.n_emit += 1

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("export_symbol", EXPORT_SYMBOL)
        self.set_runtime_statistic("n_days", str(self.n_emit))
        self.set_runtime_statistic("bars_seen", str(self.bars_seen))
        self.log(f"###ASUM### sym={EXPORT_SYMBOL} n_days={self.n_emit} bars={self.bars_seen}")
