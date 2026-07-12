# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# =====================================================================
# FÁZE E — REFORMULACE (IN-SAMPLE 2021-01-01→2025-09-30). NENÍ OOS.
# Cíl: zachránit VWAP reverzi fixními bariérami + trend filtrem.
#
# Fade entry na ±1 A ±2 std VWAP pásmu (morning 10:00-12:00, range-bound).
# Místo pohyblivého VWAP cíle -> FIXNÍ bodové bariéry: first-passage
# +B (favorable, k VWAP) vs -B (adverse) pro grid B. Symetrická bariéra
# => win rate přímo měří edge nad 50 %.
# Trend filtr: sklon VWAP za 15 min vůči směru excursion:
#   0 = counter-trend (dobré), 1 = flat, 2 = with-trend (adverse).
# Export: cell (band, side, B, slope_bucket) -> n, win, loss, timeout, pnl_to.
# =====================================================================

RTH_OPEN_MIN = 9 * 60 + 30
FIRST15_END_MIN = 9 * 60 + 45
VWAP_START_MIN = 10 * 60
MORN_START = 10 * 60
MORN_END = 12 * 60
RTH_CLOSE_MIN = 16 * 60

B_LIST = [4, 6, 8, 10, 12, 15]        # bodové bariéry (symetrické)
SLOPE_FLAT = 1.0                       # |15min vwap change| < 1 bod = flat


class PhaseEReform(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)     # IN-SAMPLE
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
        self.cells = {}
        self.n_entries = {1: 0, 2: 0}

    def _reset_day(self, d):
        self.cur_date = d
        self.d_open = self.d_high = self.d_low = self.d_close = None
        self.classified = None
        self.cv = self.cpv = self.cpv2 = 0.0
        self.vwhist = deque(maxlen=16)
        self.outside = {(k, s): False for k in (1, 2) for s in ("upper", "lower")}
        self.trades = []

    def _band7(self):
        hs = [b["h"] for b in list(self.daily)[-7:]]
        ls = [b["l"] for b in list(self.daily)[-7:]]
        return min(ls), max(hs)

    def _cell(self, key):
        if key not in self.cells:
            self.cells[key] = {"n": 0, "win": 0, "loss": 0, "to": 0, "pnl_to": 0.0}
        return self.cells[key]

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
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
            self.cv += v; self.cpv += v * tp; self.cpv2 += v * tp * tp
        if minutes == FIRST15_END_MIN and self.classified is None:
            if len(self.daily) >= 15:
                bl, bh = self._band7()
                self.classified = (bl <= bar.close <= bh)
        if not self.classified or self.cv <= 0 or minutes < VWAP_START_MIN:
            return
        vwap = self.cpv / self.cv
        var = self.cpv2 / self.cv - vwap * vwap
        std = math.sqrt(var) if var > 0 else 0.0
        self.vwhist.append(vwap)
        if std <= 0:
            return

        for tr in self.trades:
            self._update(tr, bar, minutes)
        still = []
        for tr in self.trades:
            if tr["done"]:
                self._tally(tr)
            else:
                still.append(tr)
        self.trades = still

        c = bar.close
        for k in (1, 2):
            up = vwap + k * std
            lo = vwap - k * std
            key = (k, "upper")
            if not self.outside[key]:
                if c >= up:
                    self.outside[key] = True
                    if MORN_START <= minutes < MORN_END:
                        self._open(k, "upper", bar.close, minutes)
            elif c <= vwap:
                self.outside[key] = False
            key = (k, "lower")
            if not self.outside[key]:
                if c <= lo:
                    self.outside[key] = True
                    if MORN_START <= minutes < MORN_END:
                        self._open(k, "lower", bar.close, minutes)
            elif c >= vwap:
                self.outside[key] = False

    def _slope_bucket(self, side):
        if len(self.vwhist) < 16:
            return 1
        slope = self.vwhist[-1] - self.vwhist[0]
        adverse = slope if side == "upper" else -slope
        if adverse > SLOPE_FLAT:
            return 2
        if adverse < -SLOPE_FLAT:
            return 0
        return 1

    def _open(self, band, side, entry, minutes):
        self.n_entries[band] += 1
        self.trades.append({
            "band": band, "side": side, "entry": entry, "emin": minutes,
            "slope": self._slope_bucket(side),
            "t_fav": {B: None for B in B_LIST},
            "t_adv": {B: None for B in B_LIST},
            "last": entry, "done": False,
        })

    def _update(self, tr, bar, minutes):
        el = minutes - tr["emin"]
        tr["last"] = bar.close
        side = tr["side"]; entry = tr["entry"]
        if side == "upper":
            fav = entry - bar.low
            adv = bar.high - entry
        else:
            fav = bar.high - entry
            adv = entry - bar.low
        allres = True
        for B in B_LIST:
            if tr["t_fav"][B] is None and fav >= B:
                tr["t_fav"][B] = el
            if tr["t_adv"][B] is None and adv >= B:
                tr["t_adv"][B] = el
            if tr["t_fav"][B] is None and tr["t_adv"][B] is None:
                allres = False
        if allres:
            tr["done"] = True

    def _tally(self, tr):
        band, side, sb = tr["band"], tr["side"], tr["slope"]
        entry = tr["entry"]
        for B in B_LIST:
            cell = self._cell((band, side, B, sb))
            cell["n"] += 1
            tf = tr["t_fav"][B]; ta = tr["t_adv"][B]
            if tf is not None and (ta is None or tf <= ta):
                cell["win"] += 1
            elif ta is not None and (tf is None or ta < tf):
                cell["loss"] += 1
            else:
                pnl = (entry - tr["last"]) if side == "upper" else (tr["last"] - entry)
                cell["to"] += 1; cell["pnl_to"] += pnl

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})
        for tr in self.trades:
            self._tally(tr)
        self.trades = []

    def on_end_of_algorithm(self):
        self._finalize_prev_day()
        self.set_runtime_statistic("entries_b1", str(self.n_entries[1]))
        self.set_runtime_statistic("entries_b2", str(self.n_entries[2]))
        self.log(f"###RSUM### entries_b1={self.n_entries[1]} entries_b2={self.n_entries[2]}")
        for (band, side, B, sb), cell in sorted(self.cells.items()):
            self.log(f"###R### band={band} side={side} B={B} slope={sb} "
                     f"n={cell['n']} win={cell['win']} loss={cell['loss']} "
                     f"to={cell['to']} pnl_to={cell['pnl_to']:.1f}")
