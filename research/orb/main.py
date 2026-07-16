# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 4 — ORB VARIANTA B: fixní TP 10 bodů, SL = opačná strana OR.
# EXPLORATORNÍ, IN-SAMPLE, OOS NEDOTČENO.
# Pravidla:
#   OR = high/low prvních dvou 15-min svíček (9:30-10:00 ET = 30 min).
#   Signál: 15-min close mimo OR (>high long, <low short), první za den.
#   Vstup: open NÁSLEDUJÍCÍ 15-min svíčky. SL/TP aktivní od vstupu.
#   TP = entry ± 10.0 BODŮ (fixní). SL = OPAČNÁ strana OR
#        (long → SL = OR_low; short → SL = OR_high).
#   Svíčka protne SL i TP → konzervativně SL first.
#   Max 1 obchod/den; EOD flat 16:00; RTH only; look-ahead-free.
#   Sizing: fixed-fractional risk 1% equity (risk = |entry−SL|),
#           notional cap ≤ 1× (bez páky). Costs 1.2 bps net_cons.
#   POZOR: 10 bodů = ~20 bps na ES (~5000) vs ~5 bps na NQ (~20000)
#          — na obou doslova 10 bodů; NQ číst s tímto vědomím.
# Instrumenty: ES + NQ. Varianty: base + filt (10:00-ET news filtr).
# IS 2018-01-02 → 2025-09-30.
# =====================================================================

RISK_FRAC = 0.01
PT_FIXED = 10.0         # fixní TP = 10 bodů (absolutní, adj. kontrakt)
COST_CONS = 1.2 / 1e4   # NAV je net_cons
OR_END_MIN = 10 * 60          # OR okno končí 10:00 (svíčky 9:45 a 10:00 end_time)
FIRST_SIGNAL_MIN = 10 * 60 + 15   # první eligible signální bar end_time = 10:15
CLOSE_MIN = 16 * 60           # 16:00 EOD

NEWS_DAYS = frozenset([
    "2018-01-02", "2018-01-04", "2018-01-12", "2018-01-26", "2018-01-30", "2018-02-01", "2018-02-05", "2018-02-09",
    "2018-02-23", "2018-02-27", "2018-03-01", "2018-03-05", "2018-03-09", "2018-03-27", "2018-03-30", "2018-04-02",
    "2018-04-04", "2018-04-13", "2018-04-24", "2018-04-27", "2018-05-01", "2018-05-03", "2018-05-11", "2018-05-25",
    "2018-05-29", "2018-06-01", "2018-06-05", "2018-06-08", "2018-06-26", "2018-06-29", "2018-07-02", "2018-07-05",
    "2018-07-13", "2018-07-27", "2018-07-31", "2018-08-01", "2018-08-03", "2018-08-10", "2018-08-28", "2018-08-31",
    "2018-09-04", "2018-09-06", "2018-09-14", "2018-09-25", "2018-09-28", "2018-10-01", "2018-10-03", "2018-10-12",
    "2018-10-26", "2018-10-30", "2018-11-01", "2018-11-05", "2018-11-09", "2018-11-27", "2018-11-30", "2018-12-03",
    "2018-12-05", "2018-12-14", "2018-12-28", "2019-01-02", "2019-01-04", "2019-01-11", "2019-01-25", "2019-01-29",
    "2019-02-01", "2019-02-05", "2019-02-08", "2019-02-22", "2019-02-26", "2019-03-01", "2019-03-05", "2019-03-08",
    "2019-03-26", "2019-03-29", "2019-04-01", "2019-04-03", "2019-04-12", "2019-04-26", "2019-04-30", "2019-05-01",
    "2019-05-03", "2019-05-10", "2019-05-28", "2019-05-31", "2019-06-03", "2019-06-05", "2019-06-14", "2019-06-25",
    "2019-06-28", "2019-07-01", "2019-07-03", "2019-07-12", "2019-07-26", "2019-07-30", "2019-08-01", "2019-08-05",
    "2019-08-09", "2019-08-27", "2019-08-30", "2019-09-03", "2019-09-05", "2019-09-13", "2019-09-24", "2019-09-27",
    "2019-10-01", "2019-10-03", "2019-10-11", "2019-10-25", "2019-10-29", "2019-11-01", "2019-11-05", "2019-11-08",
    "2019-11-26", "2019-11-29", "2019-12-02", "2019-12-04", "2019-12-13", "2019-12-27", "2019-12-31", "2020-01-02",
    "2020-01-06", "2020-01-10", "2020-01-28", "2020-01-31", "2020-02-03", "2020-02-05", "2020-02-14", "2020-02-25",
    "2020-02-28", "2020-03-02", "2020-03-04", "2020-03-13", "2020-03-27", "2020-03-31", "2020-04-01", "2020-04-03",
    "2020-04-10", "2020-04-24", "2020-04-28", "2020-05-01", "2020-05-05", "2020-05-08", "2020-05-26", "2020-05-29",
    "2020-06-01", "2020-06-03", "2020-06-12", "2020-06-26", "2020-06-30", "2020-07-01", "2020-07-06", "2020-07-10",
    "2020-07-28", "2020-07-31", "2020-08-03", "2020-08-05", "2020-08-14", "2020-08-25", "2020-08-28", "2020-09-01",
    "2020-09-03", "2020-09-11", "2020-09-25", "2020-09-29", "2020-10-01", "2020-10-05", "2020-10-09", "2020-10-27",
    "2020-10-30", "2020-11-02", "2020-11-04", "2020-11-13", "2020-11-24", "2020-11-27", "2020-12-01", "2020-12-03",
    "2020-12-11", "2020-12-29", "2021-01-04", "2021-01-06", "2021-01-08", "2021-01-26", "2021-01-29", "2021-02-01",
    "2021-02-03", "2021-02-12", "2021-02-23", "2021-02-26", "2021-03-01", "2021-03-03", "2021-03-12", "2021-03-26",
    "2021-03-30", "2021-04-01", "2021-04-05", "2021-04-09", "2021-04-27", "2021-04-30", "2021-05-03", "2021-05-05",
    "2021-05-14", "2021-05-25", "2021-05-28", "2021-06-01", "2021-06-03", "2021-06-11", "2021-06-25", "2021-06-29",
    "2021-07-01", "2021-07-06", "2021-07-09", "2021-07-27", "2021-07-30", "2021-08-02", "2021-08-04", "2021-08-13",
    "2021-08-27", "2021-08-31", "2021-09-01", "2021-09-03", "2021-09-10", "2021-09-24", "2021-09-28", "2021-10-01",
    "2021-10-05", "2021-10-08", "2021-10-26", "2021-10-29", "2021-11-01", "2021-11-03", "2021-11-12", "2021-11-26",
    "2021-11-30", "2021-12-01", "2021-12-03", "2021-12-10", "2021-12-28", "2022-01-03", "2022-01-05", "2022-01-14",
    "2022-01-25", "2022-01-28", "2022-02-01", "2022-02-03", "2022-02-11", "2022-02-22", "2022-02-25", "2022-03-01",
    "2022-03-03", "2022-03-11", "2022-03-25", "2022-03-29", "2022-04-01", "2022-04-05", "2022-04-08", "2022-04-26",
    "2022-04-29", "2022-05-02", "2022-05-04", "2022-05-13", "2022-05-27", "2022-05-31", "2022-06-01", "2022-06-03",
    "2022-06-10", "2022-06-24", "2022-06-28", "2022-07-01", "2022-07-06", "2022-07-08", "2022-07-26", "2022-07-29",
    "2022-08-01", "2022-08-03", "2022-08-12", "2022-08-26", "2022-08-30", "2022-09-01", "2022-09-06", "2022-09-09",
    "2022-09-27", "2022-09-30", "2022-10-03", "2022-10-05", "2022-10-14", "2022-10-25", "2022-10-28", "2022-11-01",
    "2022-11-03", "2022-11-25", "2022-11-29", "2022-12-01", "2022-12-05", "2022-12-09", "2022-12-27", "2022-12-30",
    "2023-01-03", "2023-01-05", "2023-01-13", "2023-01-27", "2023-01-31", "2023-02-01", "2023-02-03", "2023-02-10",
    "2023-02-24", "2023-02-28", "2023-03-01", "2023-03-03", "2023-03-10", "2023-03-28", "2023-03-31", "2023-04-03",
    "2023-04-05", "2023-04-14", "2023-04-25", "2023-04-28", "2023-05-01", "2023-05-03", "2023-05-12", "2023-05-26",
    "2023-05-30", "2023-06-01", "2023-06-05", "2023-06-09", "2023-06-27", "2023-06-30", "2023-07-03", "2023-07-06",
    "2023-07-14", "2023-07-25", "2023-07-28", "2023-08-01", "2023-08-03", "2023-08-11", "2023-08-25", "2023-08-29",
    "2023-09-01", "2023-09-06", "2023-09-08", "2023-09-26", "2023-09-29", "2023-10-02", "2023-10-04", "2023-10-13",
    "2023-10-27", "2023-10-31", "2023-11-01", "2023-11-03", "2023-11-24", "2023-11-28", "2023-12-01", "2023-12-05",
    "2023-12-08", "2023-12-26", "2023-12-29", "2024-01-02", "2024-01-04", "2024-01-12", "2024-01-26", "2024-01-30",
    "2024-02-01", "2024-02-05", "2024-02-09", "2024-02-23", "2024-02-27", "2024-03-01", "2024-03-05", "2024-03-08",
    "2024-03-26", "2024-03-29", "2024-04-01", "2024-04-03", "2024-04-12", "2024-04-26", "2024-04-30", "2024-05-01",
    "2024-05-03", "2024-05-10", "2024-05-28", "2024-05-31", "2024-06-03", "2024-06-05", "2024-06-14", "2024-06-25",
    "2024-06-28", "2024-07-01", "2024-07-03", "2024-07-12", "2024-07-26", "2024-07-30", "2024-08-01", "2024-08-05",
    "2024-08-09", "2024-08-27", "2024-08-30", "2024-09-03", "2024-09-05", "2024-09-13", "2024-09-24", "2024-09-27",
    "2024-10-01", "2024-10-03", "2024-10-11", "2024-10-25", "2024-10-29", "2024-11-01", "2024-11-05", "2024-11-08",
    "2024-11-26", "2024-11-29", "2024-12-02", "2024-12-04", "2024-12-13", "2024-12-27", "2024-12-31", "2025-01-02",
    "2025-01-06", "2025-01-10", "2025-01-28", "2025-01-31", "2025-02-03", "2025-02-05", "2025-02-14", "2025-02-25",
    "2025-02-28", "2025-03-03", "2025-03-05", "2025-03-14", "2025-03-25", "2025-03-28", "2025-04-01", "2025-04-03",
    "2025-04-11", "2025-04-25", "2025-04-29", "2025-05-01", "2025-05-05", "2025-05-09", "2025-05-27", "2025-05-30",
    "2025-06-02", "2025-06-04", "2025-06-13", "2025-06-24", "2025-06-27", "2025-07-01", "2025-07-03", "2025-07-11",
    "2025-07-25", "2025-07-29", "2025-08-01", "2025-08-05", "2025-08-08", "2025-08-26", "2025-08-29", "2025-09-02",
    "2025-09-04", "2025-09-12", "2025-09-26", "2025-09-30",
])


class Sim:
    """Jedna varianta (instrument × filtr). Simuluje NAV, žádné reálné ordery."""
    def __init__(self, tag, use_filter):
        self.tag = tag
        self.use_filter = use_filter
        self.nav = 100000.0
        self.pos = 0            # 0/+1/-1
        self.entry = 0.0
        self.stop = 0.0
        self.tp = 0.0
        self.notional = 0.0
        self.risk_dollars = 0.0
        self.pending = 0        # +1/-1 = čeká vstup na open další svíčky
        self.pending_orhi = 0.0
        self.pending_orlo = 0.0
        # agregáty
        self.n = 0; self.wins = 0
        self.n_tp = 0; self.n_sl = 0; self.n_eod = 0
        self.n_ambig = 0; self.n_skip_news = 0
        self.sum_gross = 0.0; self.sum_net = 0.0
        self.sumR = 0.0; self.sumR2 = 0.0
        self.sum_stop_pts = 0.0; self.sum_stop_pct = 0.0   # sumy |entry−SL| v bodech a v %
        # MAE analýza: histogram přes 25 binů frakce MAE/R (0..1, SL→bin24)
        self.NB = 25
        self.h_cnt = [0] * self.NB      # počet obchodů v binu
        self.h_tp = [0] * self.NB       # z toho skončilo na TP
        self.h_sumR = [0.0] * self.NB   # suma gross R v binu
        self.tot_costR = 0.0            # suma cost v R (na obchod)
        self.worst = None               # nejhorší (adverse) cena za otevřený obchod
        self.yr = {}   # year -> [n, wins, sumR_gross, sum_net]

    def _close(self, exit_px, kind):
        d = self.pos
        gross_ret = d * (exit_px - self.entry) / self.entry
        pnl_gross = self.notional * gross_ret
        cost = self.notional * COST_CONS
        pnl_net = pnl_gross - cost
        R = (pnl_gross / self.risk_dollars) if self.risk_dollars > 0 else 0.0
        self.nav += pnl_net
        self.n += 1
        if pnl_net > 0:
            self.wins += 1
        if kind == "tp": self.n_tp += 1
        elif kind == "sl": self.n_sl += 1
        else: self.n_eod += 1
        self.sum_gross += pnl_gross
        self.sum_net += pnl_net
        self.sumR += R
        self.sumR2 += R * R
        # --- MAE bucketing ---
        risk_pts = abs(self.entry - self.stop)
        if risk_pts > 0 and self.worst is not None:
            mae_pts = (self.entry - self.worst) if d == 1 else (self.worst - self.entry)
            mae_frac = mae_pts / risk_pts
            b = int(mae_frac * self.NB)
            if b < 0: b = 0
            if b >= self.NB: b = self.NB - 1
            self.h_cnt[b] += 1
            if kind == "tp": self.h_tp[b] += 1
            self.h_sumR[b] += R
            self.tot_costR += (cost / self.risk_dollars) if self.risk_dollars > 0 else 0.0
        self.worst = None
        self.pos = 0

    def _year_bump(self, year):
        # zavolá se při KAŽDÉM uzavření, ale R/net dopočítáme z last close
        pass


class ORBInstrument:
    """OR/denní stav pro jeden symbol + 2 simy (base, filt)."""
    def __init__(self, symbol, name):
        self.symbol = symbol
        self.name = name
        self.cur_date = None
        self.or_high = None
        self.or_low = None
        self.or_bars = 0
        self.traded = False       # base varianta obchodovala dnes
        self.is_news = False
        self.sims = {"base": Sim(name + "_base", False),
                     "filt": Sim(name + "_filt", True)}


class ORB(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)     # OOS NEDOTČENO
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        self.instruments = []
        for fclass, nm in [(Futures.Indices.SP_500_E_MINI, "es"),
                           (Futures.Indices.NASDAQ_100_E_MINI, "nq")]:
            fut = self.add_future(
                fclass, resolution=Resolution.MINUTE,
                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                contract_depth_offset=0, extended_market_hours=False)
            inst = ORBInstrument(fut.symbol, nm)
            self.instruments.append(inst)
            self.consolidate(fut.symbol, timedelta(minutes=15),
                             lambda bar, i=inst: self.on15(i, bar))

        # denní NAV sampling
        self.last_nav_day = None

    # -------------------------------------------------------------
    def on15(self, inst, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        # jen RTH 9:45..16:00 end_time (první 15-min bar končí 9:45)
        if em < 9 * 60 + 45 or em > CLOSE_MIN:
            return
        day = et.date()
        dstr = et.strftime("%Y-%m-%d")

        # nový den?
        if inst.cur_date != day:
            # safety: pokud z předchozího dne zůstala otevřená pozice, zavři na open
            for s in inst.sims.values():
                if s.pos != 0:
                    s._close(bar.open, "eod")
                s.pending = 0
            inst.cur_date = day
            inst.or_high = None
            inst.or_low = None
            inst.or_bars = 0
            inst.traded = False
            inst.is_news = dstr in NEWS_DAYS

        # 1) fill pending vstupu na OPEN této svíčky
        for s in inst.sims.values():
            if s.pending != 0 and s.pos == 0:
                d = s.pending
                e = bar.open
                # SL = opačná strana OR; TP = entry ± 10 bodů (fixní)
                stop = s.pending_orlo if d == 1 else s.pending_orhi
                tp = e + d * PT_FIXED
                risk_pts = (e - stop) if d == 1 else (stop - e)
                s.pending = 0
                if risk_pts <= 0:
                    continue   # entry už za SL (gap) → obchod se neotevře
                s.pos = d
                s.entry = e
                s.stop = stop
                s.tp = tp
                risk_per_unit_ret = risk_pts / e   # = |stop-entry|/entry
                want = RISK_FRAC * s.nav / risk_per_unit_ret if risk_per_unit_ret > 0 else 0.0
                s.notional = min(s.nav, want)     # cap ≤ 1× (bez páky)
                s.risk_dollars = s.notional * risk_per_unit_ret
                s.worst = e   # init MAE tracker na entry
                s.sum_stop_pts += risk_pts
                s.sum_stop_pct += risk_per_unit_ret

        # 2) SL/TP kontrola na [low, high] této svíčky (aktivní od vstupu vč. vstupní svíčky)
        for s in inst.sims.values():
            if s.pos != 0:
                # MAE update: nejhorší adverse cena za trade
                if s.pos == 1:
                    if s.worst is None or bar.low < s.worst: s.worst = bar.low
                else:
                    if s.worst is None or bar.high > s.worst: s.worst = bar.high
                hit_sl = (bar.low <= s.stop) if s.pos == 1 else (bar.high >= s.stop)
                hit_tp = (bar.high >= s.tp) if s.pos == 1 else (bar.low <= s.tp)
                if hit_sl and hit_tp:
                    s.n_ambig += 1
                    self._record(inst, s, s.stop, "sl")   # konzervativně SL first
                elif hit_sl:
                    self._record(inst, s, s.stop, "sl")
                elif hit_tp:
                    self._record(inst, s, s.tp, "tp")

        # 3) OR building (svíčky end_time 9:45 a 10:00)
        if em <= OR_END_MIN:
            hi, lo = bar.high, bar.low
            inst.or_high = hi if inst.or_high is None else max(inst.or_high, hi)
            inst.or_low = lo if inst.or_low is None else min(inst.or_low, lo)
            inst.or_bars += 1
            return   # během OR okna se neobchoduje

        # 4) signál (první breakout dne), eligible od 10:15 end_time
        if (inst.or_bars >= 2 and not inst.traded and em >= FIRST_SIGNAL_MIN
                and inst.or_high is not None):
            d = 0
            if bar.close > inst.or_high:
                d = 1
            elif bar.close < inst.or_low:
                d = -1
            if d != 0:
                inst.traded = True   # max 1 obchod/den (i pro filt, pro férové srovnání "první breakout")
                for key, s in inst.sims.items():
                    if s.pos != 0:
                        continue
                    if s.use_filter and inst.is_news:
                        s.n_skip_news += 1
                        continue
                    s.pending = d
                    s.pending_orhi = inst.or_high
                    s.pending_orlo = inst.or_low

        # 5) EOD flat na 16:00 close
        if em >= CLOSE_MIN:
            for s in inst.sims.values():
                if s.pos != 0:
                    self._record(inst, s, bar.close, "eod")
                s.pending = 0
            # denní NAV sample
            self._sample(inst, et)

    def _record(self, inst, s, px, kind):
        year = inst.cur_date.year
        pre_nav = s.nav
        s._close(px, kind)
        yr = s.yr.setdefault(year, [0, 0, 0.0, 0.0])
        yr[0] += 1
        if s.nav > pre_nav:
            yr[1] += 1
        yr[3] += (s.nav - pre_nav)

    def _sample(self, inst, et):
        # denní NAV do chart série (jedna série na sim)
        for s in inst.sims.values():
            self.plot("nav", s.tag + "_nav", s.nav)

    # -------------------------------------------------------------
    def on_end_of_algorithm(self):
        for inst in self.instruments:
            for s in inst.sims.values():
                self.set_runtime_statistic(s.tag + "_n", str(s.n))
                self.set_runtime_statistic(s.tag + "_wins", str(s.wins))
                self.set_runtime_statistic(s.tag + "_tp", str(s.n_tp))
                self.set_runtime_statistic(s.tag + "_sl", str(s.n_sl))
                self.set_runtime_statistic(s.tag + "_eod", str(s.n_eod))
                self.set_runtime_statistic(s.tag + "_ambig", str(s.n_ambig))
                self.set_runtime_statistic(s.tag + "_skip", str(s.n_skip_news))
                self.set_runtime_statistic(s.tag + "_sumR", f"{s.sumR:.4f}")
                self.set_runtime_statistic(s.tag + "_sumR2", f"{s.sumR2:.4f}")
                self.set_runtime_statistic(s.tag + "_net", f"{s.sum_net:.1f}")
                self.set_runtime_statistic(s.tag + "_finalnav", f"{s.nav:.1f}")
                avg_pts = (s.sum_stop_pts / s.n) if s.n else 0.0
                avg_pct = (s.sum_stop_pct / s.n * 100) if s.n else 0.0
                self.set_runtime_statistic(s.tag + "_avgstop_pts", f"{avg_pts:.2f}")
                self.set_runtime_statistic(s.tag + "_avgstop_pct", f"{avg_pct:.3f}")
                self.log(f"###ORB### tag={s.tag} n={s.n} wins={s.wins} tp={s.n_tp} "
                         f"sl={s.n_sl} eod={s.n_eod} ambig={s.n_ambig} skip={s.n_skip_news} "
                         f"sumR={s.sumR:.4f} sumR2={s.sumR2:.4f} net={s.sum_net:.1f} nav={s.nav:.1f}")
                for y in sorted(s.yr):
                    n, w, _, net = s.yr[y]
                    self.log(f"###ORBYR### tag={s.tag} year={y} n={n} wins={w} net={net:.1f}")
                cnt = ",".join(str(x) for x in s.h_cnt)
                tp = ",".join(str(x) for x in s.h_tp)
                sr = ",".join(f"{x:.4f}" for x in s.h_sumR)
                self.log(f"###MAE### tag={s.tag} nb={s.NB} n={s.n} costR={s.tot_costR:.4f} "
                         f"cnt={cnt} tp={tp} sumR={sr}")
