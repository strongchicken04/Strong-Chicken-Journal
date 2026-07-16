# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 4 — ORB VARIANTA C: ES grid, zkrácený stop × RR-based TP.
# EXPLORATORNÍ / IN-SAMPLE FITTING, OOS NEDOTČENO.
# Motivace: dosud testováno jen nepříznivé RR (A: 2:1 proti; B: mrňavý
#   TP/obří stop). Zde se testuje PŘÍZNIVÉ RR = zkrácený stop + širší TP,
#   jediná dosud nevyzkoušená geometrie ORB continuation.
# Pravidla (jen ES): OR = 9:30-10:00 (2×15min). Signál = první 15-min
#   close mimo OR. Vstup = open další svíčky. Pro každou buňku (s,m):
#     stop_dist = s × šířka_OR ; SL = entry ∓ stop_dist
#     TP = entry ± m × stop_dist  (RR = 1:m)
#   SL-first při ambiguitě; max 1 obchod/den; EOD flat 16:00; RTH.
# Metrika: net R na obchod (R = |entry−SL|). cost_R = 1.2bps×entry/stop_dist
#   (těsnější stop → vyšší náklad v R). Breakeven hit = 1/(1+m).
# Grid s∈{.3,.4,.5,.6,.8,1.0} × m∈{1.0,1.5,2.0,3.0} = 24 buněk.
# IS 2018-01-02 → 2025-09-30.
# =====================================================================

COST_CONS = 1.2 / 1e4
OR_END_MIN = 10 * 60
FIRST_SIGNAL_MIN = 10 * 60 + 15
CLOSE_MIN = 16 * 60

S_GRID = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
M_GRID = [1.0, 1.5, 2.0, 3.0]


class Cell:
    """Jedna (s,m) buňka. Účtuje net R na obchod, žádné reálné ordery."""
    def __init__(self, s, m):
        self.s = s
        self.m = m
        self.tag = f"s{int(round(s*100)):03d}m{int(round(m*10)):02d}"
        self.pos = 0
        self.entry = 0.0
        self.stop = 0.0
        self.tp = 0.0
        self.stop_dist = 0.0
        self.pending = 0
        self.p_orhi = 0.0
        self.p_orlo = 0.0
        # agregáty (vše v net R)
        self.n = 0; self.wins = 0
        self.n_tp = 0; self.n_sl = 0; self.n_eod = 0
        self.sumR = 0.0; self.sumR2 = 0.0
        self.yr = {}   # year -> sum net R

    def close(self, exit_px, kind, year):
        d = self.pos
        r_gross = d * (exit_px - self.entry) / self.stop_dist   # v R (risk=stop_dist)
        cost_r = COST_CONS * self.entry / self.stop_dist
        r_net = r_gross - cost_r
        self.n += 1
        if r_net > 0:
            self.wins += 1
        if kind == "tp": self.n_tp += 1
        elif kind == "sl": self.n_sl += 1
        else: self.n_eod += 1
        self.sumR += r_net
        self.sumR2 += r_net * r_net
        self.yr[year] = self.yr.get(year, 0.0) + r_net
        self.pos = 0


class ORBGrid(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)     # OOS NEDOTČENO
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        fut = self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=False)
        self.sym = fut.symbol
        self.cells = [Cell(s, m) for s in S_GRID for m in M_GRID]

        self.cur_date = None
        self.or_high = None
        self.or_low = None
        self.or_bars = 0
        self.traded = False
        self.consolidate(self.sym, timedelta(minutes=15), self.on15)

    def on15(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        if em < 9 * 60 + 45 or em > CLOSE_MIN:
            return
        day = et.date()

        if self.cur_date != day:
            for c in self.cells:
                if c.pos != 0:
                    c.close(bar.open, "eod", self.cur_date.year)
                c.pending = 0
            self.cur_date = day
            self.or_high = None
            self.or_low = None
            self.or_bars = 0
            self.traded = False

        yr = day.year

        # 1) fill pending na open této svíčky
        for c in self.cells:
            if c.pending != 0 and c.pos == 0:
                d = c.pending
                e = bar.open
                r_or = (e - c.p_orlo) if d == 1 else (c.p_orhi - e)  # šířka od entry k opačné straně
                c.pending = 0
                if r_or <= 0:
                    continue
                c.stop_dist = c.s * r_or
                c.pos = d
                c.entry = e
                c.stop = e - d * c.stop_dist
                c.tp = e + d * c.m * c.stop_dist

        # 2) SL/TP kontrola (SL-first při ambiguitě)
        for c in self.cells:
            if c.pos != 0:
                hit_sl = (bar.low <= c.stop) if c.pos == 1 else (bar.high >= c.stop)
                hit_tp = (bar.high >= c.tp) if c.pos == 1 else (bar.low <= c.tp)
                if hit_sl:
                    c.close(c.stop, "sl", yr)
                elif hit_tp:
                    c.close(c.tp, "tp", yr)

        # 3) OR building
        if em <= OR_END_MIN:
            self.or_high = bar.high if self.or_high is None else max(self.or_high, bar.high)
            self.or_low = bar.low if self.or_low is None else min(self.or_low, bar.low)
            self.or_bars += 1
            return

        # 4) signál (první breakout dne)
        if (self.or_bars >= 2 and not self.traded and em >= FIRST_SIGNAL_MIN
                and self.or_high is not None):
            d = 0
            if bar.close > self.or_high:
                d = 1
            elif bar.close < self.or_low:
                d = -1
            if d != 0:
                self.traded = True
                for c in self.cells:
                    if c.pos == 0:
                        c.pending = d
                        c.p_orhi = self.or_high
                        c.p_orlo = self.or_low

        # 5) EOD flat
        if em >= CLOSE_MIN:
            for c in self.cells:
                if c.pos != 0:
                    c.close(bar.close, "eod", yr)
                c.pending = 0

    def on_end_of_algorithm(self):
        for c in self.cells:
            mean = (c.sumR / c.n) if c.n else 0.0
            self.set_runtime_statistic(c.tag + "_meanR", f"{mean:.4f}")
            self.set_runtime_statistic(c.tag + "_n", str(c.n))
            yrs = ",".join(f"{y}:{c.yr.get(y,0.0):.3f}" for y in range(2018, 2026))
            self.log(f"###CELL### tag={c.tag} s={c.s} m={c.m} n={c.n} wins={c.wins} "
                     f"tp={c.n_tp} sl={c.n_sl} eod={c.n_eod} sumR={c.sumR:.4f} "
                     f"sumR2={c.sumR2:.4f} yrs={yrs}")
