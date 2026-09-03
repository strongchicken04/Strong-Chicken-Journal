# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# =====================================================================
# FÁZE A — Extrakce sdílených datasetů A1 (breakout) + A2 (range-bound)
# Compute-engine backtest, ŽÁDNÉ objednávky.
#
# Kanál exportu: chart série (limit 10 sérií / 4000 bodů). Každý den
# emituju featury v čase 16:00 ET (jeden timestamp = jeden den), takže
# se všechny série dají lokálně zjoinovat přes timestamp. Kategoriální
# featury jsou bezztrátově zabalené do jednoho integer série "a_cat".
#
# Instrument řídí EXPORT_SYMBOL (SPY / ES) — spouští se 2× (push mezi tím).
#
# Global rules: look-ahead-free (pásmo/ATR/POC/prev-day jen z DOKONČENÝCH
# předchozích dnů; dnešek se přidá až po emisi); OOS 2025-10-01+ vyloučeno.
# =====================================================================

EXPORT_SYMBOL = "ES"           # <<< přepínač: "SPY" nebo "ES"

RTH_OPEN_MIN = 9 * 60 + 30     # 570  9:30
FIRST15_END_MIN = 9 * 60 + 45  # 585  9:45
RTH_CLOSE_MIN = 16 * 60        # 960  16:00

# grid prahů pro naivní reverzi, v ES-bodech (u SPY /10)
REV_GRID_ES = [10.0, 20.0, 30.0, 40.0]


class PhaseADatasets(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)      # IN-SAMPLE; OOS rezervováno pro Fázi E
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)

        if EXPORT_SYMBOL == "SPY":
            sec = self.add_equity("SPY", Resolution.MINUTE,
                                  data_normalization_mode=DataNormalizationMode.RAW)
            self.sym = sec.symbol
            self.point_scale = 0.1          # SPY ≈ ES/10
            self.poc_bin = 0.1
            self.is_future = False
        else:
            fut = self.add_future(
                Futures.Indices.SP_500_E_MINI,
                resolution=Resolution.MINUTE,
                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                contract_depth_offset=0,
                extended_market_hours=True,   # overnight/Globex pro on_ret + B5
            )
            fut.set_filter(0, 182)
            self.sym = fut.symbol
            self.point_scale = 1.0
            self.poc_bin = 1.0
            self.is_future = True

        self.rev_thresholds = [t * self.point_scale for t in REV_GRID_ES]

        # --- denní historie (DOKONČENÉ RTH dny) ---
        self.daily = deque(maxlen=20)       # dict(date,o,h,l,c) posl. dnů (band/ATR/prevday/inside)
        self.first15_vol_hist = deque(maxlen=20)  # objem 1. svíčky posl. 20 dnů
        self.poc_days = deque(maxlen=7)     # posl. 7 denních volume-profile dictů {bin: vol}

        # --- intradenní stav ---
        self._reset_day(None)

        # čítače pro runtime statistics
        self.c_break = 0
        self.c_range = 0
        self.c_long = 0
        self.c_short = 0
        self.c_skip_warmup = 0
        self.c_days = 0
        self.bars_seen = 0

    def _reset_day(self, d):
        self.cur_date = d
        self.day_open = None      # 9:30 open
        self.day_high = None
        self.day_low = None
        self.day_close = None     # poslední RTH close (~16:00)
        self.f15_open = None
        self.f15_high = None
        self.f15_low = None
        self.f15_close = None
        self.f15_vol = 0.0
        self.today_profile = {}   # {price_bin: vol} pro dnešní RTH (dnešní POC den)
        self.emitted = False
        self.pending = None       # klasifikace dne (breakout/range), None dokud 9:45
        # reverze: pro každý práh stav 'open'/'win'/'loss'; naplní se po klasifikaci
        self.rev_state = None
        self.rev_entry = None
        self.rev_dir = 0          # +1 long reverze / -1 short reverze

    # ---------- helpery ----------
    def _band(self):
        hs = [b["h"] for b in list(self.daily)[-7:]]
        ls = [b["l"] for b in list(self.daily)[-7:]]
        return min(ls), max(hs)

    def _atr14(self):
        bars = list(self.daily)[-15:]   # 15 barů -> 14 TR
        trs = []
        for i in range(1, len(bars)):
            h, l, pc = bars[i]["h"], bars[i]["l"], bars[i-1]["c"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs) / len(trs) if trs else None

    def _poc_price(self):
        agg = {}
        for prof in self.poc_days:
            for k, v in prof.items():
                agg[k] = agg.get(k, 0.0) + v
        if not agg:
            return None
        best = max(agg.items(), key=lambda kv: kv[1])[0]
        return best * self.poc_bin

    # ---------- hlavní smyčka ----------
    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        self.bars_seen += 1
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        # rollover dne
        if self.cur_date != d:
            self._finalize_prev_day()
            self._reset_day(d)

        in_rth = (RTH_OPEN_MIN + 1 <= minutes <= RTH_CLOSE_MIN)

        # 9:30 open (bar končící 9:31 nese open sekce; použijeme jeho open)
        if minutes == RTH_OPEN_MIN + 1 and self.day_open is None:
            self.day_open = bar.open

        if in_rth:
            hi, lo = bar.high, bar.low
            self.day_high = hi if self.day_high is None else max(self.day_high, hi)
            self.day_low = lo if self.day_low is None else min(self.day_low, lo)
            self.day_close = bar.close
            # dnešní volume profile (pro budoucí POC dny)
            b = round(bar.close / self.poc_bin)
            self.today_profile[b] = self.today_profile.get(b, 0.0) + float(bar.volume)

        # první 15min svíčka (bary končící 9:31..9:45)
        if RTH_OPEN_MIN + 1 <= minutes <= FIRST15_END_MIN:
            if self.f15_open is None:
                self.f15_open = bar.open
            self.f15_high = bar.high if self.f15_high is None else max(self.f15_high, bar.high)
            self.f15_low = bar.low if self.f15_low is None else min(self.f15_low, bar.low)
            self.f15_vol += float(bar.volume)
            if minutes == FIRST15_END_MIN:
                self.f15_close = bar.close
                self._classify_and_arm()   # rozhodni breakout/range + naaostři reverzi

        # sledování reverze (9:46 .. 16:00)
        if self.rev_state is not None and FIRST15_END_MIN < minutes <= RTH_CLOSE_MIN:
            self._track_reversion(bar)

        # emise na konci RTH
        if minutes == RTH_CLOSE_MIN and not self.emitted:
            self._emit()
            self.emitted = True

    def _classify_and_arm(self):
        # potřebujeme warmup: 15 denních barů (ATR14) a 7 pro POC
        if len(self.daily) < 15 or len(self.poc_days) < 7:
            self.pending = None
            return
        band_low, band_high = self._band()
        c = self.f15_close
        if c > band_high:
            direction = 1     # long breakout (nad High)
        elif c < band_low:
            direction = -1    # short breakout (pod Low)
        else:
            direction = 0     # range-bound
        self.pending = {"dir": direction, "band_low": band_low, "band_high": band_high}
        if direction != 0:
            # reverze = proti směru breakoutu
            self.rev_dir = -direction
            self.rev_entry = c
            self.rev_state = {thr: "open" for thr in self.rev_thresholds}

    def _track_reversion(self, bar):
        for thr, st in list(self.rev_state.items()):
            if st != "open":
                continue
            tp = self.rev_entry + self.rev_dir * thr     # cíl ve směru reverze
            sl = self.rev_entry - self.rev_dir * thr     # stop proti reverzi
            hit_tp = (bar.high >= tp) if self.rev_dir > 0 else (bar.low <= tp)
            hit_sl = (bar.low <= sl) if self.rev_dir > 0 else (bar.high >= sl)
            if hit_tp and hit_sl:
                self.rev_state[thr] = "loss"   # konzervativně: adverse first
            elif hit_tp:
                self.rev_state[thr] = "win"
            elif hit_sl:
                self.rev_state[thr] = "loss"

    def _finalize_prev_day(self):
        # ulož dokončený předchozí RTH den do denních struktur
        if self.cur_date is None or self.day_high is None or self.day_close is None:
            return
        self.daily.append({"date": self.cur_date, "o": self.day_open,
                           "h": self.day_high, "l": self.day_low, "c": self.day_close})
        self.first15_vol_hist.append(self.f15_vol)
        self.poc_days.append(self.today_profile)

    def _emit(self):
        p = getattr(self, "pending", None)
        if p is None:
            self.c_skip_warmup += 1
            return
        self.c_days += 1
        atr = self._atr14()
        if atr is None or atr <= 0:
            return
        prevC = self.daily[-1]["c"]
        day_open = self.day_open if self.day_open is not None else self.f15_open
        on_ret = (day_open - prevC) / prevC if prevC else 0.0
        ts = "a"  # chart
        direction = p["dir"]

        if direction == 0:
            # ---- A2 range-bound ----
            self.c_range += 1
            rr = (self.day_high - self.day_low) / atr
            rth_ret = (self.day_close - day_open) / day_open if day_open else 0.0
            self.plot(ts, "a_rr", rr)
            self.plot(ts, "a_rth_ret", rth_ret * 100.0)   # v %
            self.plot(ts, "a_on_ret", on_ret * 100.0)
            return

        # ---- A1 breakout ----
        self.c_break += 1
        if direction > 0:
            self.c_long += 1
            dist_pts = self.f15_close - p["band_high"]
        else:
            self.c_short += 1
            dist_pts = p["band_low"] - self.f15_close
        dist_atr = dist_pts / atr

        # objem
        if self.first15_vol_hist:
            avg20 = sum(self.first15_vol_hist) / len(self.first15_vol_hist)
        else:
            avg20 = 0.0
        vol_ratio = (self.f15_vol / avg20) if avg20 > 0 else 0.0

        # prev-day kontext (poslední DOKONČENÝ den = včera)
        y = self.daily[-1]
        rng = (y["h"] - y["l"])
        prevday_body = ((y["c"] - y["o"]) / rng) if rng > 0 else 0.0
        inside_day = 0
        if len(self.daily) >= 2:
            y2 = self.daily[-2]
            if y["h"] < y2["h"] and y["l"] > y2["l"]:
                inside_day = 1

        # POC
        poc = self._poc_price()
        poc_dist_atr = ((self.f15_close - poc) / atr) if poc else 0.0

        # B5 origin: 2=overnight-driven (9:30 open už mimo pásmo),
        #            1=RTH-fresh (open uvnitř, 9:45 close mimo), 0=n/a
        b5 = 0
        if day_open is not None:
            open_outside = (day_open > p["band_high"]) or (day_open < p["band_low"])
            b5 = 2 if open_outside else 1

        # reverze outcomes (grid) -> 2 win / 1 tie / 0 loss
        rev_codes = []
        for thr in self.rev_thresholds:
            st = self.rev_state.get(thr, "open") if self.rev_state else "open"
            rev_codes.append({"win": 2, "loss": 0}.get(st, 1))

        # zabal kategoriální do jednoho intu (mixed radix)
        dir3 = direction + 1                      # 0,1,2
        cat = dir3
        cat += 3 * inside_day                     # ×3
        cat += 6 * b5                             # ×3×2
        mult = 18
        for rc in rev_codes:                      # 4× práh, každý 0..2
            cat += mult * rc
            mult *= 3

        self.plot(ts, "a_cat", cat)
        self.plot(ts, "a_dist_atr", dist_atr)
        self.plot(ts, "a_vol_ratio", vol_ratio)
        self.plot(ts, "a_prevday_body", prevday_body)
        self.plot(ts, "a_poc_dist_atr", poc_dist_atr)
        self.plot(ts, "a_on_ret", on_ret * 100.0)

    def on_end_of_algorithm(self):
        # poslední den se emituje uvnitř on_data (16:00); tady jen souhrn
        self.set_runtime_statistic("export_symbol", EXPORT_SYMBOL)
        self.set_runtime_statistic("days_classified", str(self.c_days))
        self.set_runtime_statistic("n_breakout", str(self.c_break))
        self.set_runtime_statistic("n_rangebound", str(self.c_range))
        self.set_runtime_statistic("n_long", str(self.c_long))
        self.set_runtime_statistic("n_short", str(self.c_short))
        self.set_runtime_statistic("skip_warmup", str(self.c_skip_warmup))
        self.set_runtime_statistic("bars_seen", str(self.bars_seen))
        self.log(f"###SUMMARY### sym={EXPORT_SYMBOL} days={self.c_days} "
                 f"breakout={self.c_break} range={self.c_range} "
                 f"long={self.c_long} short={self.c_short} "
                 f"skip_warmup={self.c_skip_warmup} bars={self.bars_seen}")
