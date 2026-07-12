# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# =====================================================================
# FÁZE C — Range-bound proměnné C1 (VWAP reverze), C2 (IB extension),
# C3 (intradenní sezónnost). Compute-engine backtest, ŽÁDNÉ objednávky.
# Počítá se jen na RANGE-BOUND dnech (9:45 close UVNITŘ 7d pásma).
# Export = agregáty přes Log() (vejde se do 10 KB) + runtime statistics.
# C4 (overnight drift) se dělá lokálně z A2.
#
# Definice (dokumentované, kvůli reprodukovatelnosti):
#  VWAP: anchored 9:30, typical price (H+L+C)/3, objemově vážený.
#        std = sqrt(sum(v*tp^2)/sum(v) - vwap^2). Pásma = vwap ± k*std.
#  C1 event: close protne vwap ± k*std (k=1,2), detekce od 10:00 (warmup
#        VWAP). "Reverze" = close se vrátí k VWAP před 16:00; time-to-revert
#        v minutách. Debounce: nový event pro daný (band,side) až po návratu.
#  C2 IB: high/low 9:30-10:30. Po 10:30 první průraz IB high/low -> směr,
#        velikost první extension (max vzdálenost za IB / ATR), a outcome
#        jednoduchého trend-following vstupu (TP=SL=1x ATR, exit 16:00).
#  C3: 13 30min bloků, průměrný high-low range a průměrný |close-open|.
# =====================================================================

EXPORT_SYMBOL = "ES"           # "SPY" nebo "ES"

RTH_OPEN_MIN = 9 * 60 + 30     # 570
FIRST15_END_MIN = 9 * 60 + 45  # 585
VWAP_START_MIN = 10 * 60       # 600  (VWAP warmup do 10:00)
IB_END_MIN = 10 * 60 + 30      # 630
RTH_CLOSE_MIN = 16 * 60        # 960
TTR_BIN = 5                    # min/bin pro time-to-revert histogram
TTR_NBINS = 60                 # 0..300 min + overflow


class PhaseC(QCAlgorithm):

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

        self.daily = deque(maxlen=20)   # dokončené RTH denní bary (band + ATR)
        self._reset_day(None)

        # ---- agregátory C1 ----
        self.c1 = {(k, s): {"n": 0, "rev": 0, "hist": [0] * (TTR_NBINS + 1)}
                   for k in (1, 2) for s in ("upper", "lower")}
        # ---- agregátory C2 ----
        self.c2 = {"days": 0, "ext_days": 0, "up": 0, "down": 0,
                   "ext_sum_atr": 0.0, "tf_win": 0, "tf_loss": 0, "tf_tie": 0}
        # ---- agregátory C3: blok -> [sum_range, sum_absmove, n] ----
        self.c3 = {b: [0.0, 0.0, 0] for b in range(13)}

        self.n_range_days = 0
        self.bars_seen = 0

    def _reset_day(self, d):
        self.cur_date = d
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None
        self.f15_close = None
        self.classified = None      # True=range-bound, False=breakout, None=warmup
        # VWAP akumulace
        self.cv = 0.0
        self.cpv = 0.0
        self.cpv2 = 0.0
        # C1 stav
        self.c1_active = {(k, s): None for k in (1, 2) for s in ("upper", "lower")}
        # IB
        self.ib_high = None
        self.ib_low = None
        self.ib_broken = False
        self.ib_dir = 0
        self.ib_entry = None
        self.ib_ext_max = 0.0
        self.ib_tf_done = False

    def _band(self):
        hs = [b["h"] for b in list(self.daily)[-7:]]
        ls = [b["l"] for b in list(self.daily)[-7:]]
        return min(ls), max(hs)

    def _atr14(self):
        bars = list(self.daily)[-15:]
        trs = []
        for i in range(1, len(bars)):
            h, l, pc = bars[i]["h"], bars[i]["l"], bars[i-1]["c"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
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

        in_rth = (RTH_OPEN_MIN + 1 <= minutes <= RTH_CLOSE_MIN)
        if not in_rth:
            return

        if self.d_open is None:
            self.d_open = bar.open
        self.d_high = bar.high if self.d_high is None else max(self.d_high, bar.high)
        self.d_low = bar.low if self.d_low is None else min(self.d_low, bar.low)
        self.d_close = bar.close

        # VWAP akumulace (typical price)
        tp = (bar.high + bar.low + bar.close) / 3.0
        v = float(bar.volume)
        if v > 0:
            self.cv += v
            self.cpv += v * tp
            self.cpv2 += v * tp * tp

        # klasifikace v 9:45
        if minutes == FIRST15_END_MIN and self.classified is None:
            self.f15_close = bar.close
            if len(self.daily) >= 15:
                bl, bh = self._band()
                self.classified = (bl <= bar.close <= bh)  # True = range-bound
            if self.classified:
                self.n_range_days += 1

        if not self.classified:
            return

        # ---- C3 bloky ----
        if RTH_OPEN_MIN <= minutes < RTH_CLOSE_MIN:
            blk = (minutes - RTH_OPEN_MIN) // 30
            if 0 <= blk <= 12:
                self.c3[blk][0] += (bar.high - bar.low)
                self.c3[blk][1] += abs(bar.close - bar.open)
                self.c3[blk][2] += 1

        # ---- C1 VWAP reverze (od 10:00) ----
        if self.cv > 0 and minutes >= VWAP_START_MIN:
            vwap = self.cpv / self.cv
            var = self.cpv2 / self.cv - vwap * vwap
            std = math.sqrt(var) if var > 0 else 0.0
            c = bar.close
            if std > 0:
                for k in (1, 2):
                    up = vwap + k * std
                    lo = vwap - k * std
                    key = (k, "upper")
                    if self.c1_active[key] is None:
                        if c >= up:
                            self.c1_active[key] = minutes
                            self.c1[key]["n"] += 1
                    elif c <= vwap:
                        self._ttr(key, minutes - self.c1_active[key])
                        self.c1[key]["rev"] += 1
                        self.c1_active[key] = None
                    key = (k, "lower")
                    if self.c1_active[key] is None:
                        if c <= lo:
                            self.c1_active[key] = minutes
                            self.c1[key]["n"] += 1
                    elif c >= vwap:
                        self._ttr(key, minutes - self.c1_active[key])
                        self.c1[key]["rev"] += 1
                        self.c1_active[key] = None

        # ---- C2 Initial Balance ----
        if minutes <= IB_END_MIN:
            self.ib_high = bar.high if self.ib_high is None else max(self.ib_high, bar.high)
            self.ib_low = bar.low if self.ib_low is None else min(self.ib_low, bar.low)
        elif self.ib_high is not None:
            atr = self._atr14()
            if atr and atr > 0:
                if not self.ib_broken:
                    if bar.high >= self.ib_high:
                        self.ib_broken = True; self.ib_dir = 1; self.ib_entry = self.ib_high
                    elif bar.low <= self.ib_low:
                        self.ib_broken = True; self.ib_dir = -1; self.ib_entry = self.ib_low
                if self.ib_broken:
                    if self.ib_dir > 0:
                        self.ib_ext_max = max(self.ib_ext_max, (bar.high - self.ib_high) / atr)
                    else:
                        self.ib_ext_max = max(self.ib_ext_max, (self.ib_low - bar.low) / atr)
                    if not self.ib_tf_done:
                        tp_lvl = self.ib_entry + self.ib_dir * atr
                        sl_lvl = self.ib_entry - self.ib_dir * atr
                        hit_tp = (bar.high >= tp_lvl) if self.ib_dir > 0 else (bar.low <= tp_lvl)
                        hit_sl = (bar.low <= sl_lvl) if self.ib_dir > 0 else (bar.high >= sl_lvl)
                        if hit_tp and hit_sl:
                            self.c2["tf_loss"] += 1; self.ib_tf_done = True
                        elif hit_tp:
                            self.c2["tf_win"] += 1; self.ib_tf_done = True
                        elif hit_sl:
                            self.c2["tf_loss"] += 1; self.ib_tf_done = True

    def _ttr(self, key, ttr):
        b = min(ttr // TTR_BIN, TTR_NBINS)
        self.c1[key]["hist"][int(b)] += 1

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})
        if self.classified and self.ib_high is not None:
            self.c2["days"] += 1
            if self.ib_broken:
                self.c2["ext_days"] += 1
                if self.ib_dir > 0:
                    self.c2["up"] += 1
                else:
                    self.c2["down"] += 1
                self.c2["ext_sum_atr"] += self.ib_ext_max
                if not self.ib_tf_done:
                    self.c2["tf_tie"] += 1

    def on_end_of_algorithm(self):
        self._finalize_prev_day()
        self.set_runtime_statistic("export_symbol", EXPORT_SYMBOL)
        self.set_runtime_statistic("range_days", str(self.n_range_days))
        self.set_runtime_statistic("bars_seen", str(self.bars_seen))
        self.log(f"###CSUM### sym={EXPORT_SYMBOL} range_days={self.n_range_days} bars={self.bars_seen}")
        for (k, s), v in self.c1.items():
            wr = (100.0 * v["rev"] / v["n"]) if v["n"] else 0.0
            self.log(f"###C1### band={k} side={s} n={v['n']} rev={v['rev']} wr={wr:.2f}")
            self.log(f"###C1TTR### band={k} side={s} bin={TTR_BIN} hist={v['hist']}")
        c2 = self.c2
        pct = (100.0 * c2["ext_days"] / c2["days"]) if c2["days"] else 0.0
        avg_ext = (c2["ext_sum_atr"] / c2["ext_days"]) if c2["ext_days"] else 0.0
        tf_n = c2["tf_win"] + c2["tf_loss"] + c2["tf_tie"]
        tf_wr = (100.0 * c2["tf_win"] / tf_n) if tf_n else 0.0
        self.log(f"###C2### days={c2['days']} ext_days={c2['ext_days']} pct_ext={pct:.2f} "
                 f"up={c2['up']} down={c2['down']} avg_ext_atr={avg_ext:.3f} "
                 f"tf_win={c2['tf_win']} tf_loss={c2['tf_loss']} tf_tie={c2['tf_tie']} tf_wr={tf_wr:.2f}")
        for b in range(13):
            sr, sm, n = self.c3[b]
            ar = (sr / n) if n else 0.0
            am = (sm / n) if n else 0.0
            hhmm = RTH_OPEN_MIN + b * 30
            self.log(f"###C3### block={b} t={hhmm//60:02d}{hhmm%60:02d} "
                     f"avg_range={ar:.4f} avg_absmove={am:.4f} n={n}")
