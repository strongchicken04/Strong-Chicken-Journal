# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# FÁZE E — KROK 0: outcome-BLIND počítání N (velko-pohybové dny v OOS).
# ČTE JEN 9:30 open a 15:00 close (filtr velikosti pohybu do cutoffu).
# NIKDY NEČTE 16:00 (outcome). Nesmí prozradit nic o last60.
# OOS okno 2025-10-01 -> 2026-07-11. SPY. Frozen práh z in-sample.
# =====================================================================

RTH_OPEN_MIN = 9 * 60 + 30    # 570
CUT60_MIN = 15 * 60           # 900 (15:00) = cutoff (day_return_to_cutoff konec)
LARGE_THR_BPS = 62.1987       # FROZEN in-sample 2/3 kvantil |r_pre60| (SPY)


class LevETFPhaseE_Ncount(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2025, 10, 1)   # OOS start
        self.set_end_date(2026, 7, 11)     # OOS end
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        sec = self.add_equity("SPY", Resolution.MINUTE,
                              data_normalization_mode=DataNormalizationMode.RAW)
        self.sym = sec.symbol
        self._reset_day(None)
        self.n_days = 0        # obchodní dny s validním open+15:00
        self.n_large = 0       # z toho velko-pohybové
        self.large_dates = []

    def _reset_day(self, d):
        self.cur_date = d
        self.p_open = None
        self.p_cut = None
        self.counted = False

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        if self.cur_date != d:
            self._reset_day(d)
        # ČTEME POUZE do 15:00 vč. Po 15:00 den ignorujeme (žádné 16:00!).
        if minutes == RTH_OPEN_MIN + 1 and self.p_open is None:
            self.p_open = bar.open
        if minutes == CUT60_MIN and self.p_cut is None and self.p_open is not None:
            self.p_cut = bar.close
            r_pre60 = (self.p_cut / self.p_open - 1) * 10000  # bps
            self.n_days += 1
            if abs(r_pre60) >= LARGE_THR_BPS and not self.counted:
                self.n_large += 1
                self.counted = True
                self.large_dates.append(str(d))
            # sign zámerně NELOGUJEME zde jako outcome; jen velikost rozhodla.

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("oos_trading_days", str(self.n_days))
        self.set_runtime_statistic("N_large_move", str(self.n_large))
        self.set_runtime_statistic("large_thr_bps", str(LARGE_THR_BPS))
        self.log(f"###ENSUM### oos_days={self.n_days} N_large={self.n_large} thr_bps={LARGE_THR_BPS}")
        self.log(f"###LARGEDATES### {','.join(self.large_dates)}")
