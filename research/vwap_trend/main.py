# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — R4b: konfirmační (hysterezní) pásmo kolem VWAP, NQ.
# PŘEDREGISTROVANÝ grid: b ∈ {2.5, 5, 10, 20} bps ceny. 4 paralelní simy
# v jednom běhu na identických datech. Pravidla jinak BEZE ZMĚNY:
#  - signál (vstup i flip) vyžaduje close ZA pásmem: close > vwap*(1+b)
#    pro long, close < vwap*(1-b) pro short (hystereze; pouhý návrat
#    k VWAP flip nespouští)
#  - první vstup dne: první bar (od 9:31), jehož close je za pásmem
#  - EOD flat 16:00; 100% kapitálu; gross (costs lokálně)
# Okno 2018-01-02→2025-09-30. Export: nav+trd série per band (8 sérií).
# Metrika úspěchu (předregistrováno): net_cons CAGR/Sharpe, plateau>peak,
# kladný net_opt v OBOU érách, výrazně nižší trades/den.
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60
BANDS_BPS = [2.5, 5.0, 10.0, 20.0]


class Sim:
    def __init__(self, band_bps):
        self.b = band_bps / 1e4
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.trades = 0
        self.wins = 0
        self.sum_win = 0.0
        self.sum_loss = 0.0
        self.trades_today = 0

    def fill_open(self, price):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close_at(price)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            self.trades_today += 1

    def close_at(self, price):
        if self.pos == 0:
            return
        pnl = self.pos * (price - self.entry) * self.shares
        ret = pnl / (self.entry * self.shares) if self.entry > 0 and self.shares > 0 else 0.0
        self.nav += pnl
        self.trades += 1
        if pnl > 0:
            self.wins += 1
            self.sum_win += ret
        else:
            self.sum_loss += -ret
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


class VWAPTrendR4b(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        fut.set_filter(0, 182)
        self.sym = fut.symbol
        self.sims = {b: Sim(b) for b in BANDS_BPS}
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

        if self.cur_date != d:
            if self.cur_date is not None:
                for b, sim in self.sims.items():
                    sim.pending = None
                    if sim.pos != 0 and self.last_close:
                        sim.close_at(self.last_close)
                    self.plot("nav", f"b{b}_nav", sim.nav)
                    self.plot("nav", f"b{b}_trd", sim.trades_today)
                    sim.trades_today = 0
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        for sim in self.sims.values():
            sim.fill_open(bar.open)

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
                    sim.close_at(bar.close)

    def on_end_of_algorithm(self):
        for b, sim in self.sims.items():
            sim.pending = None
            if sim.pos != 0 and self.last_close:
                sim.close_at(self.last_close)
            self.plot("nav", f"b{b}_nav", sim.nav)
            self.plot("nav", f"b{b}_trd", sim.trades_today)
            losses = sim.trades - sim.wins
            aw = (sim.sum_win / sim.wins) if sim.wins else 0.0
            al = (sim.sum_loss / losses) if losses else 0.0
            self.set_runtime_statistic(f"b{b}_trades", str(sim.trades))
            self.set_runtime_statistic(f"b{b}_wins", str(sim.wins))
            self.set_runtime_statistic(f"b{b}_final_nav", f"{sim.nav:.2f}")
            self.log(f"###R4B### b={b} trades={sim.trades} wins={sim.wins} "
                     f"final_nav={sim.nav:.2f} avg_win={100*aw:.4f}% avg_loss={100*al:.4f}%")
