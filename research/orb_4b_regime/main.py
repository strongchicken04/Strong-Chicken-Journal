# region imports
from AlgorithmImports import *
from collections import deque
import statistics
# endregion

# =====================================================================
# PROJEKT 4b — REGIME DIAGNOSTIKA (Fáze 1, condition-first, IS, NQ).
# Bere přesně 4b equity konfiguraci (RR 1.5:1, SL 1.5b buffer, RVOL≥1.2)
# a taguje KAŽDÝ obchod předem danými režimovými proměnnými k 9:30
# (look-ahead-free, jen dokončené předchozí dny):
#   VIX (včerejší close): <15 / 15-20 / 20-30 / >=30  (pevná pásma)
#   ATR% (denní ATR/cena): tercily z trailing 252d
#   RV (10d realized vol): tercily z trailing 252d
#   ADX(14) denní: <20 / 20-25 / >=25  (pevná pásma)
# Per kýbl agreguje net R -> lokálně edge + significance + monotónnost.
# OOS NEDOTČENO.
# =====================================================================

COST = 1.2 / 1e4
RISK_PCT = 0.01
RR = 1.5
SL_BUFFER = 1.5
RVOL_MIN = 1.2
PM_START = 9 * 60 + 15
PM_END = 9 * 60 + 30
CLOSE_MIN = 16 * 60


class Acc:
    def __init__(self):
        self.n = 0; self.wins = 0; self.tp = 0; self.sl = 0
        self.sumR = 0.0; self.sumR2 = 0.0
        self.yr = {}   # year -> [n, sumR]
    def add(self, R, kind, year):
        self.n += 1
        if R > 0: self.wins += 1
        if kind == "tp": self.tp += 1
        elif kind == "sl": self.sl += 1
        self.sumR += R; self.sumR2 += R * R
        e = self.yr.setdefault(year, [0, 0.0]); e[0] += 1; e[1] += R


class ORB4bRegime(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=True)
        self.sym = fut.symbol
        self.consolidate(self.sym, timedelta(minutes=1), self.on1)
        self.consolidate(self.sym, timedelta(days=1), self.on_daily)

        try:
            self.vix = self.add_index("VIX", Resolution.DAILY).symbol
        except Exception:
            self.vix = None

        self.atr = AverageTrueRange(14, MovingAverageType.WILDERS)
        self.adx = AverageDirectionalIndex(14)
        self.prev_close = None
        self.ret_hist = deque(maxlen=12)       # denní returny pro 10d RV
        self.atrpct_hist = deque(maxlen=252)
        self.rv_hist = deque(maxlen=252)
        self.cur_atrpct = None; self.cur_rv = None; self.cur_adx = None

        self.pmvol_hist = deque(maxlen=20)
        self.nav = 100000.0
        # bucket accumulators
        self.B = {
            "vix": {k: Acc() for k in ["lt15", "15_20", "20_30", "ge30", "na"]},
            "atr": {k: Acc() for k in ["lo", "mid", "hi", "na"]},
            "rv":  {k: Acc() for k in ["lo", "mid", "hi", "na"]},
            "adx": {k: Acc() for k in ["lt20", "20_25", "ge25", "na"]},
        }
        self.overall = Acc()
        self._reset_day(None)

    def _reset_day(self, day):
        self.day = day
        self.pm_hi = None; self.pm_lo = None; self.pm_vol = 0.0
        self.range_ready = False; self.traded = False; self.rvol_ok = False
        self.pos = 0; self.entry = 0.0; self.stop = 0.0; self.tp = 0.0
        self.stop_dist = 0.0; self.notional = 0.0; self.risk_dollars = 0.0
        self.lab = {"vix": "na", "atr": "na", "rv": "na", "adx": "na"}

    def on_daily(self, bar):
        self.atr.update(bar)
        self.adx.update(bar)
        if self.prev_close is not None and self.prev_close > 0:
            self.ret_hist.append((bar.close - self.prev_close) / self.prev_close)
        self.prev_close = bar.close
        if self.atr.is_ready and bar.close > 0:
            self.cur_atrpct = self.atr.current.value / bar.close
            self.atrpct_hist.append(self.cur_atrpct)
        if len(self.ret_hist) >= 10:
            self.cur_rv = statistics.pstdev(list(self.ret_hist)[-10:])
            self.rv_hist.append(self.cur_rv)
        if self.adx.is_ready:
            self.cur_adx = self.adx.current.value

    @staticmethod
    def _tercile(val, hist):
        if val is None or len(hist) < 60:
            return "na"
        s = sorted(hist)
        lo = s[int(len(s) * 0.3333)]
        hi = s[int(len(s) * 0.6667)]
        return "lo" if val < lo else ("hi" if val >= hi else "mid")

    def _snapshot_regime(self):
        # VIX pásma (včerejší close)
        if self.vix is not None and self.vix in self.securities:
            v = self.securities[self.vix].price
            if v and v > 0:
                self.lab["vix"] = ("lt15" if v < 15 else "15_20" if v < 20
                                   else "20_30" if v < 30 else "ge30")
        self.lab["atr"] = self._tercile(self.cur_atrpct, self.atrpct_hist)
        self.lab["rv"] = self._tercile(self.cur_rv, self.rv_hist)
        if self.cur_adx is not None:
            self.lab["adx"] = ("lt20" if self.cur_adx < 20 else "20_25" if self.cur_adx < 25 else "ge25")

    def _close(self, exit_px, kind):
        d = self.pos
        gross = self.notional * d * (exit_px - self.entry) / self.entry
        cost = self.notional * COST
        R = (gross - cost) / self.risk_dollars if self.risk_dollars > 0 else 0.0
        self.nav += (gross - cost)
        yr = self.day.year
        self.overall.add(R, kind, yr)
        for var in self.B:
            self.B[var][self.lab[var]].add(R, kind, yr)
        self.pos = 0

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        day = et.date()
        if self.day != day:
            if self.pos != 0:
                self._close(bar.open, "eod")
            self._reset_day(day)

        if PM_START + 1 <= em <= PM_END:
            self.pm_hi = bar.high if self.pm_hi is None else max(self.pm_hi, bar.high)
            self.pm_lo = bar.low if self.pm_lo is None else min(self.pm_lo, bar.low)
            self.pm_vol += bar.volume
            return

        if em > PM_END and not self.range_ready:
            self.range_ready = True
            self._snapshot_regime()
            if self.pm_hi is not None and len(self.pmvol_hist) >= 5:
                base = statistics.fmean(self.pmvol_hist)
                rvol = (self.pm_vol / base) if base > 0 else 0.0
                self.rvol_ok = (RVOL_MIN <= 0) or (rvol >= RVOL_MIN)
            else:
                self.rvol_ok = True
            if self.pm_hi is not None:
                self.pmvol_hist.append(self.pm_vol)

        if not self.range_ready or em > CLOSE_MIN:
            return

        if self.pos != 0:
            hit_sl = (bar.low <= self.stop) if self.pos == 1 else (bar.high >= self.stop)
            hit_tp = (bar.high >= self.tp) if self.pos == 1 else (bar.low <= self.tp)
            if hit_sl:
                self._close(self.stop, "sl")
            elif hit_tp:
                self._close(self.tp, "tp")

        if (self.rvol_ok and not self.traded and self.pos == 0
                and self.pm_hi is not None and em >= PM_END + 1 and em < CLOSE_MIN):
            d = 0
            if bar.close > self.pm_hi: d = 1
            elif bar.close < self.pm_lo: d = -1
            if d != 0:
                self.traded = True
                e = bar.close
                sl = (self.pm_lo - SL_BUFFER) if d == 1 else (self.pm_hi + SL_BUFFER)
                sd = abs(e - sl)
                if sd > 0:
                    self.pos = d; self.entry = e; self.stop = sl; self.stop_dist = sd
                    self.tp = e + d * RR * sd
                    risk_ret = sd / e
                    self.notional = min(self.nav, RISK_PCT * self.nav / risk_ret)
                    self.risk_dollars = self.notional * risk_ret

        if em >= CLOSE_MIN and self.pos != 0:
            self._close(bar.close, "eod")

    def on_end_of_algorithm(self):
        o = self.overall
        self.log(f"###REGO### n={o.n} wins={o.wins} tp={o.tp} sl={o.sl} sumR={o.sumR:.4f} sumR2={o.sumR2:.4f}")
        for var in ["vix", "atr", "rv", "adx"]:
            for k, a in self.B[var].items():
                if a.n > 0:
                    self.log(f"###REG### var={var} bucket={k} n={a.n} wins={a.wins} "
                             f"tp={a.tp} sl={a.sl} sumR={a.sumR:.4f} sumR2={a.sumR2:.4f}")
        # per-year rozpad vol proměnných (time-stability test)
        for var in ["atr", "rv", "vix"]:
            for k, a in self.B[var].items():
                for y, (n, s) in sorted(a.yr.items()):
                    self.log(f"###REGYR### var={var} bucket={k} year={y} n={n} sumR={s:.4f}")
