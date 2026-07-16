# region imports
from AlgorithmImports import *
from collections import deque
import statistics
# endregion

# =====================================================================
# PROJEKT 4b — ORB pre-market range, 1-min breakout, 1:1 RR + filtry.
# EXPLORATORNÍ / IN-SAMPLE, OOS NEDOTČENO. NQ, extended hours.
# Pravidla (orb_4b_frozen_assumptions.md, potvrzeno):
#   Range = high/low JEDINÉ svíčky 9:15-9:30 ET (PŘED cash-open).
#   Breakout: 1-min close venku z range (od 9:31), první za den.
#   Vstup: open další 1-min svíčky. SL = opačná strana range
#     (long→range_low, short→range_high). TP = entry ± |entry−SL| (1:1).
#   SL-first při ambiguitě; max 1 obchod/den; EOD flat 16:00.
#   Costs 1.2 bps net_cons. Metrika: net R/obchod (R=|entry−SL|).
# Filtry (grid 18 kombinací, 1 běh = baseline+marginály+grid):
#   range percentil P∈{0(off),50,75} z trailing 60d premkt-range;
#   RVOL r∈{0(off),1.2,1.5} = premkt vol / 20d avg téže svíčky;
#   ATR percentil aP∈{0(off),50} z trailing 60d denního ATR(14), PRO vol.
#   Vše look-ahead-free (rozhodnuto na 9:30, jen minulé dny).
# IS 2018-01-02 → 2025-09-30.
# =====================================================================

COST_CONS = 1.2 / 1e4
PM_START = 9 * 60 + 15      # 9:15
PM_END = 9 * 60 + 30        # 9:30
CLOSE_MIN = 16 * 60
P_LEVELS = [0, 50, 75]
R_LEVELS = [0.0, 1.2, 1.5]
A_LEVELS = [0, 50]


class Combo:
    def __init__(self, P, r, aP):
        self.P = P; self.r = r; self.aP = aP
        self.tag = f"r{P}v{int(round(r*10)):02d}a{aP}"
        self.n = 0; self.wins = 0
        self.n_tp = 0; self.n_sl = 0; self.n_eod = 0
        self.sumR = 0.0; self.sumR2 = 0.0
        self.yr = {}

    def add(self, r_net, kind, year):
        self.n += 1
        if r_net > 0: self.wins += 1
        if kind == "tp": self.n_tp += 1
        elif kind == "sl": self.n_sl += 1
        else: self.n_eod += 1
        self.sumR += r_net; self.sumR2 += r_net * r_net
        self.yr[year] = self.yr.get(year, 0.0) + r_net


class ORB4b(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)     # OOS NEDOTČENO
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=True)
        self.sym = fut.symbol
        self.consolidate(self.sym, timedelta(minutes=1), self.on1)
        self.consolidate(self.sym, timedelta(days=1), self.on_daily)
        self.atr = AverageTrueRange(14, MovingAverageType.WILDERS)

        self.combos = [Combo(P, r, aP) for P in P_LEVELS for r in R_LEVELS for aP in A_LEVELS]

        # rolling historie (look-ahead-free: obsahují jen minulé dny)
        self.range_hist = deque(maxlen=60)
        self.pmvol_hist = deque(maxlen=20)
        self.atr_hist = deque(maxlen=60)

        self._reset_day(None)

    def _reset_day(self, day):
        self.cur_date = day
        self.pm_hi = None; self.pm_lo = None; self.pm_vol = 0.0
        self.range_done = False
        self.traded = False
        self.pass_range = {}; self.pass_rvol = {}; self.pass_atr = {}
        self.can_trade = False
        # pozice
        self.pos = 0; self.entry = 0.0; self.stop = 0.0; self.tp = 0.0
        self.stop_dist = 0.0; self.pending = 0

    def on_daily(self, bar):
        self.atr.update(bar)
        if self.atr.is_ready:
            self.atr_hist.append(self.atr.current.value)

    def _finalize_range(self):
        """Zavolá se jednou po 9:30 — spočítá filtry z minulé historie."""
        self.range_done = True
        if self.pm_hi is None:
            return
        rw = self.pm_hi - self.pm_lo
        # warmup: potřebujeme dost historie
        if len(self.range_hist) < 20 or len(self.pmvol_hist) < 10 or len(self.atr_hist) < 20:
            self._push_hist(rw)
            return
        self.can_trade = True
        rl = sorted(self.range_hist)
        self.pass_range = {P: rw >= _pct(rl, P) for P in P_LEVELS}
        base_vol = statistics.fmean(self.pmvol_hist)
        rvol = (self.pm_vol / base_vol) if base_vol > 0 else 0.0
        self.pass_rvol = {r: rvol >= r for r in R_LEVELS}
        al = sorted(self.atr_hist)
        atr_val = self.atr.current.value
        self.pass_atr = {aP: atr_val >= _pct(al, aP) for aP in A_LEVELS}
        self._push_hist(rw)

    def _push_hist(self, rw):
        self.range_hist.append(rw)
        self.pmvol_hist.append(self.pm_vol)

    def _passes(self, c):
        return self.pass_range.get(c.P, False) and self.pass_rvol.get(c.r, False) and self.pass_atr.get(c.aP, False)

    def _close(self, exit_px, kind):
        d = self.pos
        r_gross = d * (exit_px - self.entry) / self.stop_dist
        cost_r = COST_CONS * self.entry / self.stop_dist
        r_net = r_gross - cost_r
        year = self.cur_date.year
        for c in self.combos:
            if self._passes(c):
                c.add(r_net, kind, year)
        self.pos = 0

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        day = et.date()

        if self.cur_date != day:
            # nový den: pokud visí pozice z minula (nemělo by), zavři
            if self.pos != 0:
                self._close(bar.open, "eod")
            self._reset_day(day)

        # pre-market range 9:15-9:30 (end_time 9:16..9:30)
        if PM_START + 1 <= em <= PM_END:
            self.pm_hi = bar.high if self.pm_hi is None else max(self.pm_hi, bar.high)
            self.pm_lo = bar.low if self.pm_lo is None else min(self.pm_lo, bar.low)
            self.pm_vol += bar.volume
            return

        # po 9:30 jednou dokonči range + filtry
        if em > PM_END and not self.range_done:
            self._finalize_range()

        if not self.range_done or em > CLOSE_MIN:
            return

        # 1) fill pending na open této 1-min svíčky
        if self.pending != 0 and self.pos == 0:
            d = self.pending; e = bar.open
            sl = self.pm_lo if d == 1 else self.pm_hi
            sd = (e - sl) if d == 1 else (sl - e)
            self.pending = 0
            if sd > 0:
                self.pos = d; self.entry = e; self.stop = sl
                self.stop_dist = sd
                self.tp = e + d * sd   # 1:1

        # 2) SL/TP kontrola (SL-first)
        if self.pos != 0:
            hit_sl = (bar.low <= self.stop) if self.pos == 1 else (bar.high >= self.stop)
            hit_tp = (bar.high >= self.tp) if self.pos == 1 else (bar.low <= self.tp)
            if hit_sl:
                self._close(self.stop, "sl")
            elif hit_tp:
                self._close(self.tp, "tp")

        # 3) breakout signál (první za den) — od 9:31
        if self.can_trade and not self.traded and self.pos == 0 and em >= PM_END + 1:
            d = 0
            if bar.close > self.pm_hi: d = 1
            elif bar.close < self.pm_lo: d = -1
            if d != 0:
                self.traded = True
                self.pending = d

        # 4) EOD flat
        if em >= CLOSE_MIN and self.pos != 0:
            self._close(bar.close, "eod")

    def on_end_of_algorithm(self):
        for c in self.combos:
            mean = (c.sumR / c.n) if c.n else 0.0
            self.set_runtime_statistic(c.tag + "_meanR", f"{mean:.4f}")
            self.set_runtime_statistic(c.tag + "_n", str(c.n))
            yrs = ",".join(f"{y}:{c.yr.get(y,0.0):.3f}" for y in range(2018, 2026))
            self.log(f"###C4B### tag={c.tag} P={c.P} r={c.r} aP={c.aP} n={c.n} wins={c.wins} "
                     f"tp={c.n_tp} sl={c.n_sl} eod={c.n_eod} sumR={c.sumR:.4f} "
                     f"sumR2={c.sumR2:.4f} yrs={yrs}")


def _pct(sorted_list, p):
    """p-tý percentil (0 → min, tj. filtr off)."""
    if not sorted_list:
        return float("-inf")
    if p <= 0:
        return float("-inf")
    k = (len(sorted_list) - 1) * (p / 100.0)
    f = int(k); c = min(f + 1, len(sorted_list) - 1)
    return sorted_list[f] + (sorted_list[c] - sorted_list[f]) * (k - f)
