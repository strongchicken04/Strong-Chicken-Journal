# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — VYLEPŠOVACÍ FÁZE D: je gap gate nezávislý na vstupu?
# Poslední kontrola řetězu: Fáze B/C běžely na základu se vstupem 10:00
# (sám o sobě podezřelý spike z Fáze A). Gap je znám už v 9:30, takže
# gate lze aplikovat i na PŮVODNÍ baseline (vstup 9:31).
# 6 variant (NQ, band=20bps, 1 obchod/den, exit opačné pásmo/EOD,
# fill next open, net_cons 1.2 bps, IS 2018→2025-09-30):
#   e931       vstup od 9:31, bez filtru   (sanity: 191 105.8)
#   e931_g15   vstup od 9:31, gap >= 15. pct
#   e931_g25   vstup od 9:31, gap >= 25. pct
#   e1000      vstup od 10:00, bez filtru  (sanity: 200 713.0)
#   e1000_g15  vstup od 10:00, gap >= 15. pct
#   e1000_g25  vstup od 10:00, gap >= 25. pct
# Prahy = klouzavý 250d percentil |overnight gapu|, jen minulé dny.
# Čtení: zvedne-li gate i 9:31 větev srovnatelně -> gate je robustní
# nezávisle na vstupu. Nezvedne-li -> vylepšení stálo na 10:00 spiku.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
RANK_WIN = 250
RANK_MIN = 60


class Sim:
    def __init__(self, tag, entry_start, gap_min=None):
        self.tag = tag
        self.entry_start = entry_start
        self.gap_min = gap_min
        self.nav = 100000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending_entry = 0
        self.pending_exit = False
        self.traded_today = False
        self.allowed_today = True
        self.n = 0
        self.wins = 0
        self.days_traded = 0
        self.snap = {}

    def entry_(self, price, d):
        self.pos = d; self.entry = price; self.shares = self.nav / price

    def close_(self, price):
        gross = self.pos * (price - self.entry) * self.shares
        net = gross - self.entry * self.shares * COST
        self.nav += net
        self.n += 1
        if net > 0:
            self.wins += 1
        self.pos = 0; self.entry = 0.0; self.shares = 0.0

    def new_day(self, last_close):
        self.pending_entry = 0
        self.pending_exit = False
        if self.pos != 0 and last_close:
            self.close_(last_close)
        if self.traded_today:
            self.days_traded += 1
        self.traded_today = False
        self.allowed_today = True


class VwapImproveD(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)          # IS ONLY
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        E931 = OPEN_BAR_MIN
        E1000 = 10 * 60
        self.sims = [
            Sim("e931", E931),
            Sim("e931_g15", E931, gap_min=0.15),
            Sim("e931_g25", E931, gap_min=0.25),
            Sim("e1000", E1000),
            Sim("e1000_g15", E1000, gap_min=0.15),
            Sim("e1000_g25", E1000, gap_min=0.25),
        ]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        self.hist_gap = []
        self.prev_rth_close = None
        self.day_open = None
        self.today_gap = None

    def _finalize_day(self):
        for s in self.sims:
            s.new_day(self.last_close)
            self.plot("nav", s.tag, s.nav)
        if self.today_gap is not None:
            self.hist_gap.append(self.today_gap)
            if len(self.hist_gap) > RANK_WIN:
                self.hist_gap.pop(0)
        if self.last_close is not None:
            self.prev_rth_close = self.last_close
        self.day_open = None
        self.today_gap = None

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        if self.cur_date != d:
            if self.cur_date is not None:
                self._finalize_day()
            if self.cur_date is None or self.cur_date.year != d.year:
                for s in self.sims:
                    s.snap[d.year] = s.nav
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # ---- gap + gaty hned na prvním RTH baru (gap znám v 9:30) ----
        if self.day_open is None:
            self.day_open = bar.open
            if self.prev_rth_close and self.prev_rth_close > 0:
                self.today_gap = abs(bar.open / self.prev_rth_close - 1) * 1e4
            rank = None
            if self.today_gap is not None and len(self.hist_gap) >= RANK_MIN:
                rank = sum(1 for h in self.hist_gap if h <= self.today_gap) / len(self.hist_gap)
            for s in self.sims:
                s.allowed_today = (s.gap_min is None) or (rank is not None and rank >= s.gap_min)

        # ---- fill pending na open ----
        for s in self.sims:
            if s.pending_exit and s.pos != 0:
                s.close_(bar.open)
            s.pending_exit = False
            if s.pending_entry != 0 and s.pos == 0:
                s.entry_(bar.open, s.pending_entry)
            s.pending_entry = 0

        # ---- VWAP ----
        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        up = vwap * (1 + BAND)
        dn = vwap * (1 - BAND)
        is_eod = (minutes == CLOSE_MIN)

        for s in self.sims:
            if is_eod:
                s.pending_entry = 0
                s.pending_exit = False
                if s.pos != 0:
                    s.close_(bar.close)
                continue
            if s.pos == 1:
                if bar.close < dn:
                    s.pending_exit = True
            elif s.pos == -1:
                if bar.close > up:
                    s.pending_exit = True
            else:
                if (minutes >= s.entry_start and s.allowed_today
                        and not s.traded_today):
                    if bar.close > up:
                        s.pending_entry = 1; s.traded_today = True
                    elif bar.close < dn:
                        s.pending_entry = -1; s.traded_today = True

    def on_end_of_algorithm(self):
        self._finalize_day()
        for s in self.sims:
            self.plot("nav", s.tag, s.nav)
            snap = "|".join(f"{y}:{v:.1f}" for y, v in sorted(s.snap.items()))
            self.log(f"###IMPD### tag={s.tag} nav={s.nav:.1f} n={s.n} wins={s.wins} "
                     f"days={s.days_traded} snap={snap}")
