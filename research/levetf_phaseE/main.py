# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# FÁZE E — KROK 1: jednorázový OOS outcome test size-weighted momenta.
# ZAMRAZENÁ specifikace (phase_e_frozen_spec.md), SCHVÁLENO uživatelem.
# SPY, OOS 2025-10-01 -> 2026-07-11. Aplikuje se PŘESNĚ JEDNOU.
#
# Pravidlo: na dnech |r_pre60| >= 62.1987 bps vstup v 15:00 ve směru
# sign(r_pre60), výstup 16:00 close, konstantní 1 jednotka.
# P&L/obchod (bps) = sign(r_pre60) * r_last60.
# =====================================================================

RTH_OPEN_MIN = 9 * 60 + 30    # 570
CUT60_MIN = 15 * 60           # 900 (15:00)
CLOSE_MIN = 16 * 60           # 960 (16:00)
LARGE_THR_BPS = 62.1987       # FROZEN


class LevETFPhaseE_Step1(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2025, 10, 1)
        self.set_end_date(2026, 7, 11)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        sec = self.add_equity("SPY", Resolution.MINUTE,
                              data_normalization_mode=DataNormalizationMode.RAW)
        self.sym = sec.symbol
        self._reset_day(None)
        self.pnls = []        # per-trade P&L v bps (sign(r_pre60)*r_last60)

    def _reset_day(self, d):
        self.cur_date = d
        self.p_open = None
        self.p_cut = None
        self.r_pre60 = None
        self.traded = False

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        if self.cur_date != d:
            self._reset_day(d)
        if minutes == RTH_OPEN_MIN + 1 and self.p_open is None:
            self.p_open = bar.open
        if minutes == CUT60_MIN and self.p_cut is None and self.p_open is not None:
            self.p_cut = bar.close
            self.r_pre60 = (self.p_cut / self.p_open - 1) * 10000
        if minutes == CLOSE_MIN and not self.traded and self.r_pre60 is not None:
            # frozen pravidlo
            if abs(self.r_pre60) >= LARGE_THR_BPS:
                r_last60 = (bar.close / self.p_cut - 1) * 10000
                pnl = (1.0 if self.r_pre60 > 0 else -1.0) * r_last60
                self.pnls.append(round(pnl, 4))
            self.traded = True

    def on_end_of_algorithm(self):
        n = len(self.pnls)
        wins = sum(1 for p in self.pnls if p > 0)
        gross = sum(self.pnls) / n if n else 0.0
        self.set_runtime_statistic("N_trades", str(n))
        self.set_runtime_statistic("wins", str(wins))
        self.set_runtime_statistic("gross_exp_bps", f"{gross:.4f}")
        self.log(f"###E1SUM### N={n} wins={wins} gross_exp_bps={gross:.4f}")
        self.log(f"###E1PNL### {','.join(str(p) for p in self.pnls)}")
