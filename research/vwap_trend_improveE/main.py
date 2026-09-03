# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — UZAVÍRACÍ BĚH VYLEPŠOVÁNÍ (Fáze E-improve, IS-only).
# Základ všech variant: NQ, vstup od 9:31, band=20bps, 1 obchod/den,
# exit opačné pásmo/EOD, fill next open, net_cons 1.2 bps.
# Gaty: klouzavý 250d percentil (min 60 obs), JEN minulé dny.
#
# PŘEDREGISTROVANÁ KRITÉRIA:
#   pt60 vrstva se PŘIJME, když: MDD klesne aspoň o 3 pb proti g25
#   a total nebude horší než o 10 % relativně. Long/short dekompozice
#   je POUZE popisná (žádné rozhodnutí o long-only bez dalšího OOS).
#   Po tomto běhu se vylepšovací kapitola UZAVÍRÁ (zápis do playbooku).
#
# Varianty (6):
#   base     bez filtru                     (sanity: 191105.8)
#   g25      gap gate >= 25. pct            (sanity: ~202206 z Fáze D)
#   g25pt    gap25 + pt60 (vynech dny po trendovém včerejšku)
#   g25L     gap25, JEN long vstupy
#   g25S     gap25, JEN short vstupy
#   g25ptL   gap25 + pt60, JEN long vstupy
# Export: 6 denních NAV sérií + per-rok snapshoty v ###IMPE### logu.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
RANK_WIN = 250
RANK_MIN = 60


class Sim:
    def __init__(self, tag, gap_min=None, pt_max=None, dir_only=0):
        self.tag = tag
        self.gap_min = gap_min
        self.pt_max = pt_max
        self.dir_only = dir_only       # 0 = oba směry, 1 = jen long, -1 = jen short
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


def rank_of(hist, value):
    if value is None or len(hist) < RANK_MIN:
        return None
    return sum(1 for h in hist if h <= value) / len(hist)


class VwapImproveE(QCAlgorithm):

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
        self.sims = [
            Sim("base"),
            Sim("g25", gap_min=0.25),
            Sim("g25pt", gap_min=0.25, pt_max=0.60),
            Sim("g25L", gap_min=0.25, dir_only=1),
            Sim("g25S", gap_min=0.25, dir_only=-1),
            Sim("g25ptL", gap_min=0.25, pt_max=0.60, dir_only=1),
        ]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        self.hist_gap = []
        self.hist_pt = []
        self.prev_rth_close = None
        self.day_open = None
        self.today_gap = None
        self.d_hi = None; self.d_lo = None; self.d_open = None
        self.prev_ptrend = None

    def _finalize_day(self):
        for s in self.sims:
            s.new_day(self.last_close)
            self.plot("nav", s.tag, s.nav)
        if self.today_gap is not None:
            self.hist_gap.append(self.today_gap)
            if len(self.hist_gap) > RANK_WIN:
                self.hist_gap.pop(0)
        if self.prev_ptrend is not None:
            self.hist_pt.append(self.prev_ptrend)
            if len(self.hist_pt) > RANK_WIN:
                self.hist_pt.pop(0)
        if self.last_close is not None:
            self.prev_rth_close = self.last_close
        if (self.d_hi is not None and self.d_lo is not None
                and self.d_open is not None and self.d_hi > self.d_lo):
            self.prev_ptrend = abs(self.last_close - self.d_open) / (self.d_hi - self.d_lo)
        self.d_hi = None; self.d_lo = None; self.d_open = None
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

        # ---- podmínky + gaty na prvním RTH baru (gap i ptrend známy v 9:30) ----
        if self.day_open is None:
            self.day_open = bar.open
            if self.prev_rth_close and self.prev_rth_close > 0:
                self.today_gap = abs(bar.open / self.prev_rth_close - 1) * 1e4
            gr = rank_of(self.hist_gap, self.today_gap)
            pr = rank_of(self.hist_pt, self.prev_ptrend)
            for s in self.sims:
                ok = True
                if s.gap_min is not None and (gr is None or gr < s.gap_min):
                    ok = False
                if s.pt_max is not None and (pr is not None and pr > s.pt_max):
                    ok = False
                s.allowed_today = ok
        self.d_open = self.d_open if self.d_open is not None else bar.open
        self.d_hi = bar.high if self.d_hi is None else max(self.d_hi, bar.high)
        self.d_lo = bar.low if self.d_lo is None else min(self.d_lo, bar.low)

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
                if s.allowed_today and not s.traded_today:
                    if bar.close > up and s.dir_only >= 0:
                        s.pending_entry = 1; s.traded_today = True
                    elif bar.close < dn and s.dir_only <= 0:
                        s.pending_entry = -1; s.traded_today = True

    def on_end_of_algorithm(self):
        self._finalize_day()
        for s in self.sims:
            self.plot("nav", s.tag, s.nav)
            snap = "|".join(f"{y}:{v:.1f}" for y, v in sorted(s.snap.items()))
            self.log(f"###IMPE### tag={s.tag} nav={s.nav:.1f} n={s.n} wins={s.wins} "
                     f"days={s.days_traded} snap={snap}")
