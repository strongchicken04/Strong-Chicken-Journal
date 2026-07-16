# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# OVERNIGHT DRIFT — doložený jev: akciové indexy tvoří výnos PŘES NOC.
# Koupit na close, prodat na open, držet jen overnight. Intraday ~placatý.
# QQQ (primár) + SPY (robustnost). 2008-01-01 → 2025-09-30, denní data.
# Série: overnight gross/net, intraday, buy&hold. Náklad 0.5 bps round-turn.
# =====================================================================

COST = 0.5 / 1e4     # round-turn (ETF, MOC/MOO)


class Nav:
    def __init__(self):
        self.v = 100000.0
        self.n = 0; self.wins = 0; self.sr = 0.0; self.sr2 = 0.0
    def step(self, ret, count=True):
        self.v *= (1 + ret)
        if count:
            self.n += 1
            if ret > 0: self.wins += 1
            self.sr += ret; self.sr2 += ret * ret


class Overnight(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2008, 1, 1)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        self.symbols = {}
        for t in ["QQQ", "SPY"]:
            eq = self.add_equity(t, Resolution.DAILY)
            self.symbols[t] = eq.symbol
        # QQQ: on_gross, on_net, intraday, bh ; SPY: on_net, bh
        self.q_on_g = Nav(); self.q_on_n = Nav(); self.q_intr = Nav(); self.q_bh = Nav()
        self.s_on_n = Nav(); self.s_bh = Nav()
        self.prevc = {}

    def on_data(self, slice):
        for t, sym in self.symbols.items():
            if sym not in slice.bars:
                continue
            bar = slice.bars[sym]
            o, c = bar.open, bar.close
            pc = self.prevc.get(t)
            self.prevc[t] = c
            if pc is None or pc <= 0 or o <= 0:
                continue
            overnight = o / pc - 1        # close(t-1) → open(t)
            intraday = c / o - 1          # open(t) → close(t)
            c2c = c / pc - 1              # buy & hold
            if t == "QQQ":
                self.q_on_g.step(overnight)
                self.q_on_n.step(overnight - COST)
                self.q_intr.step(intraday - COST)
                self.q_bh.step(c2c, count=False)
                self.plot("equity", "QQQ_overnight_gross", self.q_on_g.v)
                self.plot("equity", "QQQ_overnight_net", self.q_on_n.v)
                self.plot("equity", "QQQ_intraday_net", self.q_intr.v)
                self.plot("equity", "QQQ_buyhold", self.q_bh.v)
            else:
                self.s_on_n.step(overnight - COST)
                self.s_bh.step(c2c, count=False)
                self.plot("equity", "SPY_overnight_net", self.s_on_n.v)
                self.plot("equity", "SPY_buyhold", self.s_bh.v)

    def on_end_of_algorithm(self):
        for name, nv in [("QQQ_on_gross", self.q_on_g), ("QQQ_on_net", self.q_on_n),
                         ("QQQ_intraday", self.q_intr), ("SPY_on_net", self.s_on_n)]:
            mean = nv.sr / nv.n if nv.n else 0
            self.log(f"###ON### tag={name} n={nv.n} wins={nv.wins} mean_bps={mean*1e4:.3f} "
                     f"sr2={nv.sr2:.8f} nav={nv.v:.1f}")
        self.log(f"###ONBH### QQQ_bh={self.q_bh.v:.1f} SPY_bh={self.s_bh.v:.1f}")
