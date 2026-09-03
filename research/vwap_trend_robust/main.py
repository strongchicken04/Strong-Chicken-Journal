# region imports
from AlgorithmImports import *
from datetime import date
# endregion

# =====================================================================
# PROJEKT 3 — ROBUSTNOST + OOS pro "nav_band" (poslední verze indikátoru).
# ZAMRAZENÝ SPEC (nav_band): NQ, session VWAP RTH 9:30-16:00 ET
#   (HLC3xvol, denní reset), pásmo 20 bps, 1 vstup/den, exit = close za
#   opačným pásmem / 16:00 ET, BEZ reverzu, BEZ TP, fill na next open,
#   náklad 1.2 bps round-turn.
#
# Tento běh dělá dvě věci v JEDNOM backtestu:
#   1) FROZEN band=20 obchoduje CELÝ rozsah 2018-01-02 -> 2026-07-11
#      (tj. IS 2018..2025-09-30 + OOS 2025-10-01..2026-07-11).
#      -> plotuje denní NAV "nav_frozen" (z toho se dělá fan chart + OOS).
#   2) GRID pásem {8,10,12,15,18,20,22,25,30} bps obchoduje JEN IS
#      (do 2025-09-30 včetně); po IS se zmrazí. Loguje per-rok NAV
#      snapshoty -> parameter-stability heatmapa (band x rok).
# GRID slouží JEN k ukázce robustnosti; band=20 se podle něj NEMĚNÍ.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
COST = 1.2 / 1e4
IS_END = date(2025, 9, 30)
FROZEN_BPS = 20.0
GRID_BPS = [8, 10, 12, 15, 18, 20, 22, 25, 30]


class Sim:
    def __init__(self, tag, band_bps, is_frozen):
        self.tag = tag
        self.band = band_bps / 1e4
        self.is_frozen = is_frozen        # True = obchoduje i OOS + plotuje denně
        self.nav = 100000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending_entry = 0
        self.pending_exit = False
        self.traded_today = False
        self.n = 0
        self.wins = 0
        self.snap = {}                    # rok -> NAV na začátku roku (IS)
        self.stopped = False              # grid: po IS zmrazeno

    def do_entry(self, price, direction):
        self.pos = direction
        self.entry = price
        self.shares = self.nav / price

    def do_close(self, price):
        gross = self.pos * (price - self.entry) * self.shares
        notional = self.entry * self.shares
        self.nav += gross - notional * COST
        self.n += 1
        if gross - notional * COST > 0:
            self.wins += 1
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0

    def new_day(self, last_close):
        self.pending_entry = 0
        self.pending_exit = False
        if self.pos != 0 and last_close:
            self.do_close(last_close)
        self.traded_today = False


class VwapRobust(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2026, 7, 11)      # IS + OOS; grid se zmrazí na IS_END
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.frozen = Sim("frozen", FROZEN_BPS, True)
        self.grid = [Sim(f"b{int(b)}", b, False) for b in GRID_BPS]
        self.sims = [self.frozen] + self.grid
        self.cur_date = None
        self.cur_year = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None

    def _step_sim(self, s, bar, up, dn, is_eod, is_is):
        # grid: obchoduje jen do IS_END, pak zmrazit
        if not s.is_frozen and not is_is:
            if not s.stopped:
                s.snap["END"] = s.nav
                s.stopped = True
            return
        if s.stopped:
            return

        # 1) fill pending na OPEN
        if s.pending_exit and s.pos != 0:
            s.do_close(bar.open)
        s.pending_exit = False
        if s.pending_entry != 0 and s.pos == 0:
            s.do_entry(bar.open, s.pending_entry)
        s.pending_entry = 0

        if is_eod:
            s.pending_entry = 0
            s.pending_exit = False
            if s.pos != 0:
                s.do_close(bar.close)
            return

        # 2) signály (na close, fill příští open)
        if s.pos == 1:
            if bar.close < dn:
                s.pending_exit = True
        elif s.pos == -1:
            if bar.close > up:
                s.pending_exit = True
        else:
            if not s.traded_today:
                if bar.close > up:
                    s.pending_entry = 1; s.traded_today = True
                elif bar.close < dn:
                    s.pending_entry = -1; s.traded_today = True

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        is_is = d <= IS_END

        # ---- nový rok: snapshot NAV (IS) ----
        if self.cur_year != t.year and is_is:
            self.cur_year = t.year
            for s in self.sims:
                s.snap[t.year] = s.nav

        # ---- nový den ----
        if self.cur_date != d:
            if self.cur_date is not None:
                for s in self.sims:
                    if s.is_frozen or not s.stopped:
                        s.new_day(self.last_close)
                self.plot("nav", "nav_frozen", self.frozen.nav)
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # VWAP (pásma potřebují všechny sims, počítá se jednou)
        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        is_eod = (minutes == CLOSE_MIN)

        for s in self.sims:
            up = vwap * (1 + s.band)
            dn = vwap * (1 - s.band)
            self._step_sim(s, bar, up, dn, is_eod, is_is)

    def on_end_of_algorithm(self):
        for s in self.sims:
            if s.pos != 0 and self.last_close:
                s.do_close(self.last_close)
        self.plot("nav", "nav_frozen", self.frozen.nav)

        # frozen: IS-end a OOS-end NAV pro verdikt (dopočítá se přesně z chart série)
        self.set_runtime_statistic("frozen_final_nav", f"{self.frozen.nav:.0f}")
        self.set_runtime_statistic("frozen_trades", str(self.frozen.n))
        self.log(f"###ROB_FROZEN### final_nav={self.frozen.nav:.2f} "
                 f"trades={self.frozen.n} wins={self.frozen.wins}")

        # grid: per-rok snapshoty -> heatmapa (band x rok)
        for s in self.grid:
            if "END" not in s.snap:
                s.snap["END"] = s.nav
            parts = []
            for k in sorted(s.snap.keys(), key=lambda x: (0, x) if isinstance(x, int) else (1, 0)):
                parts.append(f"{k}:{s.snap[k]:.1f}")
            self.log(f"###ROB_GRID### band={s.tag} n={s.n} wins={s.wins} "
                     f"snap={'|'.join(parts)}")
