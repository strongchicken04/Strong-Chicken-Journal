# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# LEV-ETF FÁZE 0 — verifikace dostupnosti dat.
# Cíl: zjistit, jestli QC má NAPLNĚNÁ fundamental pole (shares_outstanding,
# market_cap) pro leveraged/inverse ETF, a jak vypadá jejich růst v čase.
# Compute-only, žádné objednávky. In-sample rozsah (NENÍ OOS).
# =====================================================================

ETFS = ["TQQQ", "SPXL", "SSO", "SQQQ", "SPXS", "SDS", "UPRO", "SPXU", "QLD", "QID"]


class LevETFPhase0(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)

        # SPY minute (ověření, že podklad teče); ETF daily (kvůli fundamentals)
        spy = self.add_equity("SPY", Resolution.MINUTE)
        self._spy = spy.symbol
        self._etf = {}
        for t in ETFS:
            sec = self.add_equity(t, Resolution.DAILY)
            self._etf[t] = sec.symbol

        self._spy_bars = 0
        self._populated = {t: 0 for t in ETFS}   # kolikrát bylo so>0
        self._samples = {t: 0 for t in ETFS}
        # semi-annual sampling (leden + červenec)
        self.schedule.on(self.date_rules.month_start(),
                         self.time_rules.at(10, 0), self._sample)

    def on_data(self, data: Slice):
        if self._spy in data.bars:
            self._spy_bars += 1

    def _sample(self):
        if self.time.month not in (1, 7):
            return
        for t, sym in self._etf.items():
            sec = self.securities[sym]
            f = sec.fundamentals
            so = 0.0
            mc = 0.0
            try:
                if f is not None:
                    so = float(f.company_profile.shares_outstanding or 0)
                    mc = float(f.market_cap or 0)
            except Exception:
                pass
            px = float(sec.price or 0)
            aum_proxy = so * px
            self._samples[t] += 1
            if so > 0:
                self._populated[t] += 1
            self.log(f"###F### {self.time.date()} {t} so={so:.0f} mc={mc:.0f} "
                     f"px={px:.2f} aum_proxy={aum_proxy:.0f}")

    def on_end_of_algorithm(self):
        self.log(f"###P0SUM### spy_bars={self._spy_bars}")
        for t in ETFS:
            self.set_runtime_statistic(f"{t}_pop", f"{self._populated[t]}/{self._samples[t]}")
            self.log(f"###POP### {t} populated={self._populated[t]}/{self._samples[t]}")
