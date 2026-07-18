# region imports
from AlgorithmImports import *
import math
# endregion

# =====================================================================
# PROJEKT 3 — VYLEPŠOVACÍ FÁZE A (IS-only, OOS spotřebováno).
# Základ: VWAP Trend 1td (band=20bps, bez reverzu, exit opačné pásmo/EOD,
# fill next open, net_cons 1.2bps). Baseline = e931_t1 (sanity: +89 %).
#
# GRID 12 variant: entry_start {9:31, 9:45, 10:00, 10:30}
#                  × max_trades/den {1, 2, 4}
#   -> H1 (přeskočit chaos openu) a H2 (re-entry po whipsawu).
#   Pozn.: po band-exitu je cena za opačným pásmem, takže re-entry
#   při max_trades>1 přirozeně funguje jako capovaný stop-and-reverse.
#
# EXPORT: chart "nav": 12 sérií denních NAV (jméno eHHMM_tN)
#         chart "cond": denní podmínky PŘED/na začátku dne:
#           rv20   = 20d realizovaná vol denních close-to-close (ann. %)
#           gap    = |open9:30 / prev RTH close − 1| v bps
#           or5r   = range 9:30–9:35 v bps ceny
#           fhr    = range 9:30–10:00 v bps ceny
#           ptrend = |close−open| / (high−low) včerejšího RTH (0..1)
# Podmínky slouží k lokální condition-first analýze režimového filtru.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
ENTRY_STARTS = [(9 * 60 + 31, "e931"), (9 * 60 + 45, "e945"),
                (10 * 60, "e1000"), (10 * 60 + 30, "e1030")]
MAX_TRADES = [1, 2, 4]


class Sim:
    def __init__(self, tag, entry_start, max_trades):
        self.tag = tag
        self.entry_start = entry_start
        self.max_tr = max_trades
        self.nav = 100000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending_entry = 0
        self.pending_exit = False
        self.trades_today = 0
        self.n = 0
        self.wins = 0

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
        self.trades_today = 0


class VwapImproveA(QCAlgorithm):

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
        self.sims = [Sim(f"{en}_t{mt}", es, mt)
                     for es, en in ENTRY_STARTS for mt in MAX_TRADES]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        # denní podmínky
        self.daily_closes = []          # RTH close historie pro rv20
        self.prev_rth_close = None
        self.day_open = None
        self.or5_hi = None; self.or5_lo = None
        self.fh_hi = None; self.fh_lo = None
        self.d_hi = None; self.d_lo = None; self.d_open = None
        self.prev_ptrend = None
        self.cond_today = {}

    def _finalize_day(self):
        """konec dne: zapiš NAV všech sims + podmínky dne."""
        for s in self.sims:
            s.new_day(self.last_close)
            self.plot("nav", s.tag, s.nav)
        for k, v in self.cond_today.items():
            if v is not None:
                self.plot("cond", k, v)
        self.cond_today = {}
        # ulož včerejší RTH statistiky
        if self.last_close is not None:
            self.daily_closes.append(self.last_close)
            if len(self.daily_closes) > 25:
                self.daily_closes.pop(0)
            self.prev_rth_close = self.last_close
        if (self.d_hi is not None and self.d_lo is not None
                and self.d_open is not None and self.d_hi > self.d_lo):
            self.prev_ptrend = abs(self.last_close - self.d_open) / (self.d_hi - self.d_lo)
        self.d_hi = None; self.d_lo = None; self.d_open = None
        self.or5_hi = None; self.or5_lo = None
        self.fh_hi = None; self.fh_lo = None
        self.day_open = None

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
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # ---- denní podmínky ----
        if self.day_open is None:
            self.day_open = bar.open
            if self.prev_rth_close and self.prev_rth_close > 0:
                self.cond_today["gap"] = abs(bar.open / self.prev_rth_close - 1) * 1e4
            if len(self.daily_closes) >= 21:
                rs = []
                for i in range(1, 21):
                    a, b = self.daily_closes[-i - 1], self.daily_closes[-i]
                    if a > 0:
                        rs.append(math.log(b / a))
                if len(rs) >= 10:
                    m = sum(rs) / len(rs)
                    var = sum((x - m) ** 2 for x in rs) / (len(rs) - 1)
                    self.cond_today["rv20"] = math.sqrt(var * 252) * 100
            if self.prev_ptrend is not None:
                self.cond_today["ptrend"] = self.prev_ptrend
        self.d_open = self.d_open if self.d_open is not None else bar.open
        self.d_hi = bar.high if self.d_hi is None else max(self.d_hi, bar.high)
        self.d_lo = bar.low if self.d_lo is None else min(self.d_lo, bar.low)
        if minutes <= 9 * 60 + 35:
            self.or5_hi = bar.high if self.or5_hi is None else max(self.or5_hi, bar.high)
            self.or5_lo = bar.low if self.or5_lo is None else min(self.or5_lo, bar.low)
            if minutes == 9 * 60 + 35 and self.or5_lo and self.day_open:
                self.cond_today["or5r"] = (self.or5_hi - self.or5_lo) / self.day_open * 1e4
        if minutes <= 10 * 60:
            self.fh_hi = bar.high if self.fh_hi is None else max(self.fh_hi, bar.high)
            self.fh_lo = bar.low if self.fh_lo is None else min(self.fh_lo, bar.low)
            if minutes == 10 * 60 and self.fh_lo and self.day_open:
                self.cond_today["fhr"] = (self.fh_hi - self.fh_lo) / self.day_open * 1e4

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
                if minutes >= s.entry_start and s.trades_today < s.max_tr:
                    if bar.close > up:
                        s.pending_entry = 1; s.trades_today += 1
                    elif bar.close < dn:
                        s.pending_entry = -1; s.trades_today += 1

    def on_end_of_algorithm(self):
        self._finalize_day()
        for s in self.sims:
            self.plot("nav", s.tag, s.nav)
            self.log(f"###IMP### tag={s.tag} nav={s.nav:.1f} n={s.n} wins={s.wins}")
