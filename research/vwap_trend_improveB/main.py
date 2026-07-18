# region imports
from AlgorithmImports import *
import math
# endregion

# =====================================================================
# PROJEKT 3 — VYLEPŠOVACÍ FÁZE B: režimový gate na ranní range (IS-only).
# Základ VŠECH variant: NQ, VWAP band=20bps, vstup až OD 10:00 (fhr je
# známé), JEN 1 obchod/den, exit opačné pásmo/EOD, fill next open,
# net_cons 1.2 bps. OOS spotřebováno -> vše jen IS 2018→2025-09-30.
#
# GATY (prahy = klouzavý percentil posledních 250 dní, min 60 obs,
#       počítáno JEN z minulých dní -> žádný lookahead):
#   base   = bez filtru (replikace e1000_t1 z Fáze A, sanity +101 %)
#   fhr40  = obchoduj jen když fhr (range 9:30-10:00) >= 40. pct
#   fhr50  = ... >= 50. pct
#   fhr60  = ... >= 60. pct
#   gap20  = vynech dny s |overnight gap| < 20. pct (Q1 byl záporný)
#   pt60   = vynech dny s ptrend (trendovost včerejška) > 60. pct
#   cmb    = fhr50 AND pt60
#   cmbg   = fhr50 AND gap20
# Export: 8 denních NAV sérií + per-rok snapshoty v ###IMPB### logu.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
ENTRY_START = 10 * 60          # vstupy až od 10:00 (fhr kompletní)
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
RANK_WIN = 250
RANK_MIN = 60


class Sim:
    def __init__(self, tag, fhr_min=None, gap_min=None, pt_max=None):
        self.tag = tag
        self.fhr_min = fhr_min        # minimální percentil fhr (0..1)
        self.gap_min = gap_min        # minimální percentil gapu
        self.pt_max = pt_max          # maximální percentil ptrend
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

    def gate(self, fhr_rank, gap_rank, pt_rank):
        if self.fhr_min is not None and (fhr_rank is None or fhr_rank < self.fhr_min):
            return False
        if self.gap_min is not None and (gap_rank is None or gap_rank < self.gap_min):
            return False
        if self.pt_max is not None and (pt_rank is None or pt_rank > self.pt_max):
            return False
        return True

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
    """percentil value vůči historii (0..1); None když málo dat."""
    if value is None or len(hist) < RANK_MIN:
        return None
    below = sum(1 for h in hist if h <= value)
    return below / len(hist)


class VwapImproveB(QCAlgorithm):

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
            Sim("fhr40", fhr_min=0.40),
            Sim("fhr50", fhr_min=0.50),
            Sim("fhr60", fhr_min=0.60),
            Sim("gap20", gap_min=0.20),
            Sim("pt60", pt_max=0.60),
            Sim("cmb", fhr_min=0.50, pt_max=0.60),
            Sim("cmbg", fhr_min=0.50, gap_min=0.20),
        ]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        # podmínky dneška + historie pro percentily (jen minulé dny)
        self.hist_fhr = []
        self.hist_gap = []
        self.hist_pt = []
        self.prev_rth_close = None
        self.day_open = None
        self.fh_hi = None; self.fh_lo = None
        self.d_hi = None; self.d_lo = None; self.d_open = None
        self.prev_ptrend = None
        self.today_fhr = None
        self.today_gap = None
        self.gates_set = False

    def _finalize_day(self):
        for s in self.sims:
            s.new_day(self.last_close)
            self.plot("nav", s.tag, s.nav)
        # historie podmínek (až PO dni — dnešek se do ranků nepočítal)
        if self.today_fhr is not None:
            self.hist_fhr.append(self.today_fhr)
            if len(self.hist_fhr) > RANK_WIN:
                self.hist_fhr.pop(0)
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
        self.fh_hi = None; self.fh_lo = None
        self.day_open = None
        self.today_fhr = None
        self.today_gap = None
        self.gates_set = False

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

        # ---- podmínky dne ----
        if self.day_open is None:
            self.day_open = bar.open
            if self.prev_rth_close and self.prev_rth_close > 0:
                self.today_gap = abs(bar.open / self.prev_rth_close - 1) * 1e4
        self.d_open = self.d_open if self.d_open is not None else bar.open
        self.d_hi = bar.high if self.d_hi is None else max(self.d_hi, bar.high)
        self.d_lo = bar.low if self.d_lo is None else min(self.d_lo, bar.low)
        if minutes <= 10 * 60:
            self.fh_hi = bar.high if self.fh_hi is None else max(self.fh_hi, bar.high)
            self.fh_lo = bar.low if self.fh_lo is None else min(self.fh_lo, bar.low)
            if minutes == 10 * 60 and self.fh_lo is not None and self.day_open:
                self.today_fhr = (self.fh_hi - self.fh_lo) / self.day_open * 1e4

        # ---- gaty v 10:00 (ranky jen z minulých dní) ----
        if minutes == ENTRY_START and not self.gates_set:
            fr = rank_of(self.hist_fhr, self.today_fhr)
            gr = rank_of(self.hist_gap, self.today_gap)
            pr = rank_of(self.hist_pt, self.prev_ptrend)
            for s in self.sims:
                s.allowed_today = s.gate(fr, gr, pr)
            self.gates_set = True

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
                if (minutes >= ENTRY_START and self.gates_set
                        and s.allowed_today and not s.traded_today):
                    if bar.close > up:
                        s.pending_entry = 1; s.traded_today = True
                    elif bar.close < dn:
                        s.pending_entry = -1; s.traded_today = True

    def on_end_of_algorithm(self):
        self._finalize_day()
        for s in self.sims:
            self.plot("nav", s.tag, s.nav)
            snap = "|".join(f"{y}:{v:.1f}" for y, v in sorted(s.snap.items()))
            self.log(f"###IMPB### tag={s.tag} nav={s.nav:.1f} n={s.n} wins={s.wins} "
                     f"days={s.days_traded} snap={snap}")
