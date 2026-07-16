# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — DIAGNOSTIKA D2 (jen výpočet; nic se nevybírá/nenasazuje).
# 5 paralelních simů NQ: band ∈ {10,15,20,25,30} bps, NAV už NET_CONS
# (1,2 bps notional odečtené při každém uzavření obchodu v simu).
# b=20 navíc exportuje trade-level GROSS P&L (bps) v čase uzavření:
# série tr_a (do 2021), tr_b (2022+) kvůli 4000-bodovému limitu.
# Okno 2018-01-02 -> konec dat (~2026-04-16); segment 2025-10+ =
# spotřebovaná OOS, jen pro OOS bootstrap. Grid metriky jen IS (lokálně).
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BANDS = [10.0, 15.0, 20.0, 25.0, 30.0]
COST = 1.2 / 1e4    # net_cons v simu


class Sim:
    def __init__(self, band_bps, algo=None, tag=None):
        self.b = band_bps / 1e4
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.algo = algo      # jen b=20: plot trade pnl
        self.tag = tag
        self.yr = {}

    def fill_open(self, price, year):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close_at(price, year)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price

    def close_at(self, price, year):
        if self.pos == 0:
            return
        gross = self.pos * (price - self.entry) * self.shares
        notional = self.entry * self.shares
        self.nav += gross - notional * COST
        ret_bps = (gross / notional) * 1e4 if notional > 0 else 0.0
        a = self.yr.setdefault(year, [0, 0])
        a[0] += 1
        if gross - notional * COST > 0:
            a[1] += 1
        if self.algo is not None:
            ser = "tr_a" if year <= 2021 else "tr_b"
            self.algo.plot("tr", ser, ret_bps)
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0

    def signal(self, close, vwap):
        up = vwap * (1 + self.b)
        dn = vwap * (1 - self.b)
        if self.pos == 0:
            if close > up:
                self.pending = 1
            elif close < dn:
                self.pending = -1
        elif self.pos > 0 and close < dn:
            self.pending = -1
        elif self.pos < 0 and close > up:
            self.pending = 1


class D2Diag(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2026, 7, 11)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = {}
        for b in BANDS:
            self.sims[b] = Sim(b, algo=self if b == 20.0 else None)
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
        year = t.year
        if self.cur_date != d:
            if self.cur_date is not None:
                py = self.cur_date.year
                for b, sim in self.sims.items():
                    sim.pending = None
                    if sim.pos != 0 and self.last_close:
                        sim.close_at(self.last_close, py)
                    self.plot("nav", f"b{int(b)}_nav", sim.nav)
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None
        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return
        for sim in self.sims.values():
            sim.fill_open(bar.open, year)
        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        if minutes < CLOSE_MIN:
            for sim in self.sims.values():
                sim.signal(bar.close, vwap)
        else:
            for sim in self.sims.values():
                sim.pending = None
                if sim.pos != 0:
                    sim.close_at(bar.close, year)

    def on_end_of_algorithm(self):
        for b, sim in self.sims.items():
            sim.pending = None
            if sim.pos != 0 and self.last_close:
                sim.close_at(self.last_close, self.cur_date.year)
            self.plot("nav", f"b{int(b)}_nav", sim.nav)
            for y in sorted(sim.yr):
                tr, w = sim.yr[y]
                self.log(f"###D2### band={int(b)} year={y} trades={tr} wins={w}")
            self.set_runtime_statistic(f"b{int(b)}_trades",
                                       str(sum(v[0] for v in sim.yr.values())))
