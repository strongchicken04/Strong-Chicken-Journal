# region imports
from AlgorithmImports import *
from collections import deque
import statistics
# endregion

# =====================================================================
# PROJEKT 4b — EQUITY CURVE varianty (RR 1.5:1, SL 1.5b za range, RVOL 1.2)
# Compute-engine: simuluje NAV, exportuje denní equity křivku.
# Pravidla: range 9:15-9:30 ET (extended hours); 1-min close mimo range
#   (první za den); vstup na CLOSE breakout svíčky; SL = opačná strana
#   range ∓ 1.5 bodu; TP = 1.5:1; RVOL≥1.2 (warmup passthrough);
#   max 1/den; EOD flat 16:00; net_cons 1.2 bps; 1% risk, cap ≤1×.
# NQ, IS 2018-01-02 → 2025-09-30. OOS NEDOTČENO.
# =====================================================================

COST = 1.2 / 1e4
RISK_PCT = 0.01
RR = 1.5
SL_BUFFER = 1.5
RVOL_MIN = 1.2
PM_START = 9 * 60 + 15
PM_END = 9 * 60 + 30
CLOSE_MIN = 16 * 60


class ORB4bEquity(QCAlgorithm):

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

        self.pmvol_hist = deque(maxlen=20)
        self.nav = 100000.0
        # agregáty
        self.n = 0; self.wins = 0; self.n_tp = 0; self.n_sl = 0; self.n_eod = 0
        self.sumR = 0.0; self.sumR2 = 0.0; self.yr = {}
        self._reset_day(None)

    def _reset_day(self, day):
        self.day = day
        self.pm_hi = None; self.pm_lo = None; self.pm_vol = 0.0
        self.range_ready = False; self.traded = False; self.rvol_ok = False
        self.pos = 0; self.entry = 0.0; self.stop = 0.0; self.tp = 0.0
        self.stop_dist = 0.0; self.notional = 0.0; self.risk_dollars = 0.0

    def _close(self, exit_px, kind):
        d = self.pos
        gross = self.notional * d * (exit_px - self.entry) / self.entry
        cost = self.notional * COST
        pnl = gross - cost
        R = (gross - cost) / self.risk_dollars if self.risk_dollars > 0 else 0.0
        self.nav += pnl
        self.n += 1
        if pnl > 0: self.wins += 1
        if kind == "tp": self.n_tp += 1
        elif kind == "sl": self.n_sl += 1
        else: self.n_eod += 1
        self.sumR += R; self.sumR2 += R * R
        self.yr[self.day.year] = self.yr.get(self.day.year, 0.0) + pnl
        self.pos = 0

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        day = et.date()
        if self.day != day:
            if self.pos != 0:
                self._close(bar.open, "eod")
            self._reset_day(day)

        # pre-market range 9:15-9:30
        if PM_START + 1 <= em <= PM_END:
            self.pm_hi = bar.high if self.pm_hi is None else max(self.pm_hi, bar.high)
            self.pm_lo = bar.low if self.pm_lo is None else min(self.pm_lo, bar.low)
            self.pm_vol += bar.volume
            return

        # dokončení range + RVOL
        if em > PM_END and not self.range_ready:
            self.range_ready = True
            if self.pm_hi is not None and len(self.pmvol_hist) >= 5:
                base = statistics.fmean(self.pmvol_hist)
                rvol = (self.pm_vol / base) if base > 0 else 0.0
                self.rvol_ok = (RVOL_MIN <= 0) or (rvol >= RVOL_MIN)
            else:
                self.rvol_ok = True  # warmup passthrough
            if self.pm_hi is not None:
                self.pmvol_hist.append(self.pm_vol)

        if not self.range_ready or em > CLOSE_MIN:
            return

        # SL/TP kontrola (na svíčkách PO vstupu; vstup byl na close předchozí)
        if self.pos != 0:
            hit_sl = (bar.low <= self.stop) if self.pos == 1 else (bar.high >= self.stop)
            hit_tp = (bar.high >= self.tp) if self.pos == 1 else (bar.low <= self.tp)
            if hit_sl:
                self._close(self.stop, "sl")
            elif hit_tp:
                self._close(self.tp, "tp")

        # breakout signál → vstup na CLOSE této svíčky
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

        # EOD flat + denní NAV sample
        if em >= CLOSE_MIN:
            if self.pos != 0:
                self._close(bar.close, "eod")
            self.plot("equity", "nav", self.nav)

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("finalnav", f"{self.nav:.1f}")
        self.set_runtime_statistic("n", str(self.n))
        self.set_runtime_statistic("wins", str(self.wins))
        self.set_runtime_statistic("tp", str(self.n_tp))
        self.set_runtime_statistic("sl", str(self.n_sl))
        self.set_runtime_statistic("eod", str(self.n_eod))
        mean = self.sumR / self.n if self.n else 0.0
        self.set_runtime_statistic("meanR", f"{mean:.4f}")
        yrs = ",".join(f"{y}:{self.yr.get(y,0.0):.1f}" for y in range(2018, 2026))
        self.log(f"###EQ### finalnav={self.nav:.1f} n={self.n} wins={self.wins} "
                 f"tp={self.n_tp} sl={self.n_sl} eod={self.n_eod} sumR={self.sumR:.4f} "
                 f"sumR2={self.sumR2:.4f} yrs={yrs}")
