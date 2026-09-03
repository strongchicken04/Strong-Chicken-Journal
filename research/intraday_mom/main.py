# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 6 — MARKET INTRADAY MOMENTUM (Gao, Han, Li, Zhou 2018, JFE).
# ES, RTH, day-trade: return prvních 30 min (a varianty) předpovídá
# posledních 30 min. Vstup 15:30 ET, výstup 16:00 close, flat přes noc.
# Signály (směr, vše známé v 15:30 → look-ahead-free):
#   first: sign(r 9:30→10:00)
#   pen  : sign(r 15:00→15:30)  (penultimate půlhodina)
#   cum  : sign(r 9:30→15:30)
#   combo: obchoduj jen když first & pen souhlasí, směr = ten
# P&L = směr × r(15:30→16:00) − cost. net_cons 1.2 bps. 1 trade/den.
# Regrese r_first→r_last (β, korelace) akumulovaná pro report.
# IS 2018-01-02→2025-09-30. OOS NEDOTČENO.
# =====================================================================

COST = 1.2 / 1e4
OPEN_MIN = 9 * 60 + 31     # první RTH minuta (end_time 9:31)
T_1000 = 10 * 60
T_1500 = 15 * 60
T_1530 = 15 * 60 + 30
T_1600 = 16 * 60


class Sim:
    def __init__(self, tag):
        self.tag = tag
        self.nav = 100000.0
        self.n = 0; self.wins = 0
        self.sum_net = 0.0; self.sum_net2 = 0.0
        self.yr = {}

    def trade(self, d, r_last, year):
        if d == 0:
            return
        net = d * r_last - COST
        self.nav *= (1 + net)
        self.n += 1
        if net > 0: self.wins += 1
        self.sum_net += net; self.sum_net2 += net * net
        e = self.yr.setdefault(year, [0, 0.0]); e[0] += 1; e[1] += net


class IntradayMom(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        sym = list(self.securities.keys())[0]
        self.sym = sym
        self.consolidate(sym, timedelta(minutes=1), self.on1)

        self.sims = {k: Sim(k) for k in ["first", "pen", "cum", "combo"]}
        # regrese r_first -> r_last
        self.rx = 0.0; self.ry = 0.0; self.rxy = 0.0; self.rx2 = 0.0; self.ry2 = 0.0; self.rn = 0
        self._reset(None)

    def _reset(self, day):
        self.day = day
        self.p_open = None; self.p_1000 = None
        self.p_1500 = None; self.p_1530 = None; self.p_1600 = None

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        day = et.date()
        if self.day != day:
            self._reset(day)

        if em == OPEN_MIN and self.p_open is None:
            self.p_open = bar.open
        if em == T_1000:
            self.p_1000 = bar.close
        if em == T_1500:
            self.p_1500 = bar.close
        if em == T_1530:
            self.p_1530 = bar.close
        if em == T_1600:
            self.p_1600 = bar.close
            self._settle()

    def _settle(self):
        if None in (self.p_open, self.p_1000, self.p_1500, self.p_1530, self.p_1600):
            return
        r_first = self.p_1000 / self.p_open - 1
        r_pen = self.p_1530 / self.p_1500 - 1
        r_cum = self.p_1530 / self.p_open - 1
        r_last = self.p_1600 / self.p_1530 - 1
        year = self.day.year

        self.sims["first"].trade(self._sgn(r_first), r_last, year)
        self.sims["pen"].trade(self._sgn(r_pen), r_last, year)
        self.sims["cum"].trade(self._sgn(r_cum), r_last, year)
        cd = self._sgn(r_first) if self._sgn(r_first) == self._sgn(r_pen) else 0
        self.sims["combo"].trade(cd, r_last, year)

        # regrese
        x, y = r_first, r_last
        self.rx += x; self.ry += y; self.rxy += x * y; self.rx2 += x * x; self.ry2 += y * y; self.rn += 1

        for k, s in self.sims.items():
            self.plot("equity", k + "_nav", s.nav)

    @staticmethod
    def _sgn(v):
        return 1 if v > 0 else (-1 if v < 0 else 0)

    def on_end_of_algorithm(self):
        n = self.rn
        if n > 1:
            mx = self.rx / n; my = self.ry / n
            cov = self.rxy / n - mx * my
            vx = self.rx2 / n - mx * mx
            vy = self.ry2 / n - my * my
            beta = cov / vx if vx > 0 else 0
            corr = cov / (vx * vy) ** 0.5 if vx > 0 and vy > 0 else 0
            self.log(f"###REG### n={n} beta={beta:.5f} corr={corr:.4f} "
                     f"sx={self.rx2:.6f} sy={self.ry2:.6f} sxy={self.rxy:.6f} sumx={self.rx:.6f} sumy={self.ry:.6f}")
        for k, s in self.sims.items():
            mean = s.sum_net / s.n if s.n else 0.0
            self.set_runtime_statistic(k + "_nav", f"{s.nav:.1f}")
            self.set_runtime_statistic(k + "_hit", f"{100*s.wins/s.n:.1f}" if s.n else "0")
            yrs = ",".join(f"{y}:{s.yr.get(y,[0,0.0])[1]*1e4:.1f}" for y in range(2018, 2026))
            self.log(f"###IMOM### tag={k} n={s.n} wins={s.wins} mean_bps={mean*1e4:.3f} "
                     f"sum_net2={s.sum_net2:.8f} nav={s.nav:.1f} yrs_bps={yrs}")
