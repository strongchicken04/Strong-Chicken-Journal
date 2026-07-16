# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — TP GRID EXPERIMENT (jen sranda, IN-SAMPLE, exploratorní).
# Zamrazený zbytek pravidel (b=20 bps, RTH VWAP, stop&reverse, EOD),
# PŘIDÁN fixní TP = tp_mult × R, kde R = |entry − opačné pásmo při entry|.
# tp_mult ∈ {0.25, 0.5, 1.0, None(bez TP)}. NQ, 2018→2025-09-30 (IS).
# OOS okno NEDOTČENO. NAV = net_cons (1.2 bps v simu).
# TP = resting limit (fill intrabar high/low); stop&reverse = na close
#   (fill open další svíčky) — beze změny; TP má tedy prioritu, když se
#   dotkne uvnitř svíčky (mechanicky správně, limit).
# Re-entry po TP: až když se close vrátí dovnitř pásma (debounce).
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BAND = 20.0 / 1e4
COST = 1.2 / 1e4
TPS = [("025", 0.25), ("050", 0.5), ("100", 1.0), ("none", None)]


class Sim:
    def __init__(self, tag, tp_mult):
        self.tag = tag
        self.tp = tp_mult
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.tp_level = None
        self.armed = True
        self.yr = {}

    def fill_open(self, price, up, dn, year):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close(price, year)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            if tgt == 1:
                R = max(price - dn, 1e-9)
                self.tp_level = price + self.tp * R if self.tp else None
            else:
                R = max(up - price, 1e-9)
                self.tp_level = price - self.tp * R if self.tp else None

    def close(self, price, year):
        gross = self.pos * (price - self.entry) * self.shares
        notional = self.entry * self.shares
        self.nav += gross - notional * COST
        a = self.yr.setdefault(year, [0, 0])
        a[0] += 1
        if gross - notional * COST > 0:
            a[1] += 1
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.tp_level = None


class TPGrid(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)      # IN-SAMPLE only
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = [Sim(tag, m) for tag, m in TPS]
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None
        self.prev_up = None
        self.prev_dn = None

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()
        year = t.year
        if self.cur_date != d:
            if self.cur_date is not None:
                py = self.cur_date.year
                for s in self.sims:
                    s.pending = None
                    if s.pos != 0 and self.last_close:
                        s.close(self.last_close, py)
                    s.armed = True
                    self.plot("nav", f"tp{s.tag}_nav", s.nav)
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None
            self.prev_up = None
            self.prev_dn = None
        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        # 1) fill pending na open (použij pásma z předchozího baru pro R)
        pu = self.prev_up if self.prev_up is not None else bar.open
        pd_ = self.prev_dn if self.prev_dn is not None else bar.open
        for s in self.sims:
            s.fill_open(bar.open, pu, pd_, year)

        # 2) update VWAP
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
                s.pending = None
                if s.pos != 0:
                    s.close(bar.close, year)
                continue
            if s.pos == 1:
                if s.tp_level is not None and bar.high >= s.tp_level:
                    s.close(s.tp_level, year); s.armed = False
                elif bar.close < dn:
                    s.pending = -1
            elif s.pos == -1:
                if s.tp_level is not None and bar.low <= s.tp_level:
                    s.close(s.tp_level, year); s.armed = False
                elif bar.close > up:
                    s.pending = 1
            else:
                if not s.armed and dn <= bar.close <= up:
                    s.armed = True
                if s.armed:
                    if bar.close > up:
                        s.pending = 1
                    elif bar.close < dn:
                        s.pending = -1
        self.prev_up = up
        self.prev_dn = dn

    def on_end_of_algorithm(self):
        for s in self.sims:
            s.pending = None
            if s.pos != 0 and self.last_close:
                s.close(self.last_close, self.cur_date.year)
            self.plot("nav", f"tp{s.tag}_nav", s.nav)
            tot = sum(v[0] for v in s.yr.values())
            wins = sum(v[1] for v in s.yr.values())
            self.set_runtime_statistic(f"tp{s.tag}_trades", str(tot))
            self.set_runtime_statistic(f"tp{s.tag}_wins", str(wins))
            self.log(f"###TP### tag={s.tag} trades={tot} wins={wins} final_nav={s.nav:.2f}")
