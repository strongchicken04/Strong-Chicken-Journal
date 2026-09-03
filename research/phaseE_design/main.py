# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# =====================================================================
# FÁZE E — DESIGN (IN-SAMPLE, 2021-01-01 → 2025-09-30). NENÍ OOS.
# Simulace stop-loss + time-box pro C1 ±1 VWAP reverzi v RANNÍM okně
# (10:00–12:00), ES, range-bound dny. Upper i lower zvlášť.
#
# Pro každý ±1 event (trigger = close protne vwap±std, debounce = návrat
# k VWAP) v ranním okně nasimuluje FADE trade:
#   entry = close v trigger baru; target = VWAP; stop = entry ± S*ATR;
#   time-box = zavřít na trhu po T min, když ani target ani stop.
# Grid: S ∈ {0.5,1,1.5,2, no-stop}, T ∈ {60,90,120, do close}.
# Konzervativně: same-bar stop+target => stop (loss).
# Exportuje se P&L v BODECH (na $ a komise/slippage se převádí lokálně).
# =====================================================================

RTH_OPEN_MIN = 9 * 60 + 30
FIRST15_END_MIN = 9 * 60 + 45
VWAP_START_MIN = 10 * 60
MORN_START = 10 * 60      # ranní okno 10:00
MORN_END = 12 * 60        # ...do 12:00 (exkluzivně)
RTH_CLOSE_MIN = 16 * 60

S_LIST = [0.5, 1.0, 1.5, 2.0, 99.0]   # 99 = no-stop
T_LIST = [60, 90, 120, 9999]          # 9999 = do close


class PhaseEDesign(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)       # IN-SAMPLE ONLY
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

        # cell (side, Sidx, Tidx) -> dict čítačů + P&L sum (v bodech)
        self.cells = {}
        for side in ("upper", "lower"):
            for si in range(len(S_LIST)):
                for ti in range(len(T_LIST)):
                    self.cells[(side, si, ti)] = {"n": 0, "win": 0, "loss": 0, "to": 0,
                                                   "pnl": 0.0, "pnl_win": 0.0,
                                                   "pnl_loss": 0.0, "pnl_to": 0.0}
        self.n_events_morn = 0
        self.atr_sum = 0.0
        self.gain_sum = 0.0     # avg entry->vwap gain (win path, no-stop)
        self.gain_cnt = 0

    def _reset_day(self, d):
        self.cur_date = d
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None
        self.classified = None
        self.atr = None
        self.cv = 0.0
        self.cpv = 0.0
        self.cpv2 = 0.0
        self.outside = {"upper": False, "lower": False}
        self.trade = {"upper": None, "lower": None}

    def _band7(self):
        hs = [b["h"] for b in list(self.daily)[-7:]]
        ls = [b["l"] for b in list(self.daily)[-7:]]
        return min(ls), max(hs)

    def _atr14(self):
        bars = list(self.daily)[-15:]
        trs = [max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i-1]["c"]),
                   abs(bars[i]["l"] - bars[i-1]["c"])) for i in range(1, len(bars))]
        return sum(trs) / len(trs) if trs else None

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
            self.cv += v
            self.cpv += v * tp
            self.cpv2 += v * tp * tp

        if minutes == FIRST15_END_MIN and self.classified is None:
            if len(self.daily) >= 15:
                bl, bh = self._band7()
                self.classified = (bl <= bar.close <= bh)
                self.atr = self._atr14()
            if self.classified:
                pass

        if not self.classified or self.atr is None or self.atr <= 0:
            return
        if self.cv <= 0 or minutes < VWAP_START_MIN:
            return

        vwap = self.cpv / self.cv
        var = self.cpv2 / self.cv - vwap * vwap
        std = math.sqrt(var) if var > 0 else 0.0
        if std <= 0:
            return

        # --- update otevřených trades (obě strany) ---
        for side in ("upper", "lower"):
            tr = self.trade[side]
            if tr is not None:
                self._update_trade(tr, bar, vwap, minutes)

        c = bar.close
        # --- upper excursion (fade short) ---
        if not self.outside["upper"]:
            if c >= vwap + std:
                self.outside["upper"] = True
                if MORN_START <= minutes < MORN_END and self.trade["upper"] is None:
                    self._open_trade("upper", bar.close, minutes)
        else:
            if c <= vwap:      # návrat k VWAP -> konec excursion
                self.outside["upper"] = False
        # --- lower excursion (fade long) ---
        if not self.outside["lower"]:
            if c <= vwap - std:
                self.outside["lower"] = True
                if MORN_START <= minutes < MORN_END and self.trade["lower"] is None:
                    self._open_trade("lower", bar.close, minutes)
        else:
            if c >= vwap:
                self.outside["lower"] = False

    def _open_trade(self, side, entry, minutes):
        self.trade[side] = {
            "side": side, "entry": entry, "entry_min": minutes, "atr": self.atr,
            "mae": 0.0, "t_stop": {s: None for s in S_LIST},
            "t_win": None, "gain": None, "px": {60: None, 90: None, 120: None},
            "last_px": entry,
        }
        self.n_events_morn += 1
        self.atr_sum += self.atr

    def _update_trade(self, tr, bar, vwap, minutes):
        el = minutes - tr["entry_min"]
        tr["last_px"] = bar.close
        side = tr["side"]
        entry = tr["entry"]
        atr = tr["atr"]
        # adverse / MAE
        if side == "upper":       # short: adverse = cena nahoru
            adverse = bar.high - entry
            fav_touch = bar.low <= vwap
        else:                      # long: adverse = cena dolu
            adverse = entry - bar.low
            fav_touch = bar.high >= vwap
        if adverse > tr["mae"]:
            tr["mae"] = adverse
        for s in S_LIST:
            if tr["t_stop"][s] is None and tr["mae"] >= s * atr:
                tr["t_stop"][s] = el
        # záznam ceny na 60/90/120 (první bar s el>=T)
        for T in (60, 90, 120):
            if tr["px"][T] is None and el >= T:
                tr["px"][T] = bar.close
        # výhra (dotyk VWAP)
        if tr["t_win"] is None and fav_touch:
            tr["t_win"] = el
            tr["gain"] = (entry - vwap) if side == "upper" else (vwap - entry)
            self.gain_sum += tr["gain"]
            self.gain_cnt += 1
            self._resolve_trade(tr)
            self.trade[side] = None

    def _resolve_trade(self, tr):
        side = tr["side"]
        entry = tr["entry"]
        atr = tr["atr"]
        tw = tr["t_win"]
        for si, s in enumerate(S_LIST):
            ts = tr["t_stop"][s]
            for ti, T in enumerate(T_LIST):
                cell = self.cells[(side, si, ti)]
                cell["n"] += 1
                # rozhodnutí: stop (pokud <=T a <=tw), jinak win (tw<=T), jinak timeout
                if ts is not None and ts <= T and (tw is None or ts <= tw):
                    pnl = -s * atr
                    cell["loss"] += 1; cell["pnl_loss"] += pnl
                elif tw is not None and tw <= T:
                    pnl = tr["gain"]
                    cell["win"] += 1; cell["pnl_win"] += pnl
                else:
                    # timeout na trhu v čase T (nebo close)
                    if T == 9999:
                        pxT = tr["last_px"]
                    else:
                        pxT = tr["px"][T] if tr["px"].get(T) is not None else tr["last_px"]
                    pnl = (entry - pxT) if side == "upper" else (pxT - entry)
                    cell["to"] += 1; cell["pnl_to"] += pnl
                cell["pnl"] += pnl

    def _finalize_prev_day(self):
        if self.cur_date is not None and self.d_high is not None and self.d_close is not None:
            self.daily.append({"o": self.d_open, "h": self.d_high,
                               "l": self.d_low, "c": self.d_close})
        # doresit otevřené trades (VWAP nedotčen -> t_win None)
        for side in ("upper", "lower"):
            tr = self.trade[side]
            if tr is not None:
                self._resolve_trade(tr)
                self.trade[side] = None

    def on_end_of_algorithm(self):
        self._finalize_prev_day()
        self.set_runtime_statistic("events_morning", str(self.n_events_morn))
        avg_atr = self.atr_sum / self.n_events_morn if self.n_events_morn else 0
        avg_gain = self.gain_sum / self.gain_cnt if self.gain_cnt else 0
        self.set_runtime_statistic("avg_atr_pts", f"{avg_atr:.2f}")
        self.set_runtime_statistic("avg_win_gain_pts", f"{avg_gain:.3f}")
        self.log(f"###ESUM### events={self.n_events_morn} avg_atr={avg_atr:.2f} avg_gain={avg_gain:.3f}")
        for (side, si, ti), cell in sorted(self.cells.items()):
            s = S_LIST[si]; T = T_LIST[ti]
            self.log(f"###E### side={side} stop={s} tbox={T} n={cell['n']} "
                     f"win={cell['win']} loss={cell['loss']} to={cell['to']} "
                     f"pnl={cell['pnl']:.1f} pnl_win={cell['pnl_win']:.1f} "
                     f"pnl_loss={cell['pnl_loss']:.1f} pnl_to={cell['pnl_to']:.1f}")
