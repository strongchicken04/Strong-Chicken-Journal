# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — VWAP TREND "poslední verze" (1 TRADE/DEN, bez reverzu).
# Věrná kopie poslední verze indikátoru vwap_trend_nq.pine:
#   - session VWAP (RTH 9:30-16:00 ET, HLC3 x volume, denní reset)
#   - hysterezní pásmo b = 20 bps
#   - JEN 1 VSTUP/DEN: close za pásmem -> vstup; close za OPAČNÝM pásmem
#     = zavřít (BEZ otočení); další vstup až následující den
#   - EOD flat na 16:00 ET
#   - fill na OPEN následující svíčky (jak QC backtest)
# Dvě NAV křivky v jednom běhu:
#   nav_band = přesně poslední verze (TP jen vizuál, exit = pásmo/EOD)
#   nav_tp   = totéž + reálný TP = entry +/- 74.375 bodu (intrabar limit)
# NQ, 2018-01-02 -> 2025-09-30 (IN-SAMPLE). OOS okno NEDOTČENO.
# Náklad 1.2 bps round-turn (net_cons). NAV = 100k, 1x notional/trade.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
TP_POINTS = 74.375


class Sim:
    def __init__(self, tag, tp_points):
        self.tag = tag
        self.tp_points = tp_points     # None = bez reálného TP
        self.nav = 100000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.tp_level = None
        self.pending_entry = 0         # ±1 = vstup na next open
        self.pending_exit = False      # zavřít na next open
        self.traded_today = False
        self.n = 0
        self.wins = 0

    def do_entry(self, price, direction):
        self.pos = direction
        self.entry = price
        self.shares = self.nav / price
        self.tp_level = (price + direction * self.tp_points) if self.tp_points else None

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
        self.tp_level = None

    def new_day(self, last_close):
        self.pending_entry = 0
        self.pending_exit = False
        if self.pos != 0 and last_close:
            self.do_close(last_close)
        self.traded_today = False


class VwapTrend1TD(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)      # IN-SAMPLE only, OOS nedotčeno
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = [Sim("band", None), Sim("tp", TP_POINTS)]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        # ---- nový den ----
        if self.cur_date != d:
            if self.cur_date is not None:
                for s in self.sims:
                    s.new_day(self.last_close)
                    self.plot("nav", f"nav_{s.tag}", s.nav)
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # ---- 1) fill pending na OPEN ----
        for s in self.sims:
            if s.pending_exit and s.pos != 0:
                s.do_close(bar.open)
            s.pending_exit = False
            if s.pending_entry != 0 and s.pos == 0:
                s.do_entry(bar.open, s.pending_entry)
            s.pending_entry = 0

        # ---- 2) update VWAP ----
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
                    s.do_close(bar.close)
                continue

            # TP jako reálný intrabar limit (jen tp-sim)
            if s.pos != 0 and s.tp_level is not None:
                if s.pos == 1 and bar.high >= s.tp_level:
                    s.do_close(s.tp_level); continue
                if s.pos == -1 and bar.low <= s.tp_level:
                    s.do_close(s.tp_level); continue

            if s.pos == 1:
                if bar.close < dn:
                    s.pending_exit = True          # zavřít (bez otočení)
            elif s.pos == -1:
                if bar.close > up:
                    s.pending_exit = True
            else:
                if not s.traded_today:             # jen 1 vstup/den
                    if bar.close > up:
                        s.pending_entry = 1; s.traded_today = True
                    elif bar.close < dn:
                        s.pending_entry = -1; s.traded_today = True

    def on_end_of_algorithm(self):
        for s in self.sims:
            if s.pos != 0 and self.last_close:
                s.do_close(self.last_close)
            self.plot("nav", f"nav_{s.tag}", s.nav)
            self.set_runtime_statistic(f"{s.tag}_trades", str(s.n))
            self.set_runtime_statistic(f"{s.tag}_wins", str(s.wins))
            self.log(f"###VT1TD### tag={s.tag} trades={s.n} wins={s.wins} final_nav={s.nav:.2f}")
