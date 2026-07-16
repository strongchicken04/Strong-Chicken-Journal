# region imports
from AlgorithmImports import *
from collections import deque
import random
# endregion

# =====================================================================
# PROJEKT 7 — LEVEL EDGE STUDY. ~50 úrovní na ES, IS 2018-2025.
# Pro každou úroveň: na PRVNÍ dotek v RTH spustí symetrický závod
#   odraz (zpět o B ticků) vs průraz (skrz o B ticků) do M minut.
#   rejection_rate = P(odraz dřív). Náhodná úroveň = kontrola (~50%).
#   + velikost reakce (max excursion do M min). Tisíce doteků/úroveň.
# Cíl: které úrovně reagují víc než náhoda / mají směrový bias →
#   mapa, kde má smysl číst order flow. OOS NEDOTČENO.
# B = 2.0 bodu (8 ticků ES), M = 15 min.
# =====================================================================

B = 2.0          # práh odrazu/průrazu (body)
M = 15           # okno závodu (minuty)
VP_BIN = 1.0
SESS_ANCHOR = 18 * 60
RTH_OPEN = 9 * 60 + 31
RTH_CLOSE = 16 * 60


class Lvl:
    __slots__ = ("price", "active", "touched", "rej", "brk", "bars", "mx", "mn",
                 "n_touch", "n_rej", "n_brk", "n_amb", "n_to", "sum_react")
    def __init__(self):
        self.n_touch = 0; self.n_rej = 0; self.n_brk = 0; self.n_amb = 0
        self.n_to = 0; self.sum_react = 0.0
        self.reset_day()
    def reset_day(self):
        self.price = None; self.active = False; self.touched = False
        self.rej = None; self.brk = None; self.bars = 0; self.mx = 0.0; self.mn = 0.0


class Levels(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        fut = self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=True)
        self.sym = fut.symbol
        self.consolidate(self.sym, timedelta(minutes=1), self.on1)

        names = []
        names += ["PDH", "PDL", "PDC", "PDO", "PDmid", "PD_POC", "PD_VAH", "PD_VAL"]
        names += ["PWH", "PWL", "PWC", "Wk_open"]
        names += ["ONH", "ONL", "ONmid", "GBX_open"]
        names += ["SMA20", "SMA50", "SMA200"]
        names += ["OR5H", "OR5L", "OR15H", "OR15L", "OR30H", "OR30L"]
        names += ["IBH", "IBL", "IBmid", "IB_extU", "IB_extD"]
        names += ["sVWAP", "sV+1", "sV-1", "sV+2", "sV-2", "sV+3", "sV-3"]
        names += ["rVWAP", "rV+1", "rV-1", "rV+2", "rV-2"]
        names += ["POC", "VAH", "VAL"]
        names += ["round25", "round50", "round100"]
        names += ["RANDOM"]
        self.names = names
        self.L = {n: Lvl() for n in names}

        # denní closes pro SMA
        self.dcloses = deque(maxlen=210)
        # prior-day RTH stat
        self.pd = {}
        # prior week
        self.pw = {}; self.cur_week = None; self.wk_hi = None; self.wk_lo = None; self.wk_close = None; self.wk_open = None
        # session (18:00) VWAP + VP + overnight
        self.skey = None
        # RTH date
        self.rdate = None

    # ---------- VP helper ----------
    @staticmethod
    def _vp_levels(vp):
        if not vp:
            return None, None, None
        total = sum(vp.values())
        prices = sorted(vp)
        pocp = max(vp, key=vp.get)
        i = prices.index(pocp)
        lo = hi = i; acc = vp[pocp]
        while acc < 0.7 * total and (lo > 0 or hi < len(prices) - 1):
            left = vp[prices[lo - 1]] if lo > 0 else -1
            right = vp[prices[hi + 1]] if hi < len(prices) - 1 else -1
            if right >= left and hi < len(prices) - 1:
                hi += 1; acc += vp[prices[hi]]
            elif lo > 0:
                lo -= 1; acc += vp[prices[lo]]
            else:
                break
        return pocp, prices[hi], prices[lo]

    def _reset_session(self):
        self.sPV = 0.0; self.sV = 0.0; self.sP2V = 0.0
        self.svp = {}

    def _reset_rth(self, day):
        self.rdate = day
        self.rth_hi = None; self.rth_lo = None; self.rth_open = None
        self.rvp = {}
        self.rPV = 0.0; self.rV = 0.0; self.rP2V = 0.0
        self.or5h = self.or5l = self.or15h = self.or15l = self.or30h = self.or30l = None
        self.ibh = self.ibl = None
        for n in self.names:
            self.L[n].reset_day()
        self._set_static_levels()

    def _set_static_levels(self):
        pd = self.pd
        if pd:
            for k, nm in [("H", "PDH"), ("L", "PDL"), ("C", "PDC"), ("O", "PDO"),
                          ("mid", "PDmid"), ("POC", "PD_POC"), ("VAH", "PD_VAH"), ("VAL", "PD_VAL")]:
                if pd.get(k) is not None:
                    self.L[nm].price = pd[k]; self.L[nm].active = True
        if self.pw:
            for k, nm in [("H", "PWH"), ("L", "PWL"), ("C", "PWC")]:
                if self.pw.get(k) is not None:
                    self.L[nm].price = self.pw[k]; self.L[nm].active = True
        if self.wk_open is not None:
            self.L["Wk_open"].price = self.wk_open; self.L["Wk_open"].active = True
        cl = list(self.dcloses)
        for win, nm in [(20, "SMA20"), (50, "SMA50"), (200, "SMA200")]:
            if len(cl) >= win:
                self.L[nm].price = sum(cl[-win:]) / win; self.L[nm].active = True

    def _touch_and_race(self, lvl, bar, em):
        # dynamický přepočet ceny do doteku už proběhl venku; tady jen dotek+závod
        if lvl.price is None or not lvl.active:
            return
        if not lvl.touched:
            # dotek pouze v RTH
            if RTH_OPEN <= em <= RTH_CLOSE and bar.low <= lvl.price <= bar.high:
                lvl.touched = True
                lvl.n_touch += 1
                # směr příchodu podle open baru vs level
                from_above = bar.open > lvl.price
                if from_above:
                    lvl.rej = lvl.price + B; lvl.brk = lvl.price - B
                else:
                    lvl.rej = lvl.price - B; lvl.brk = lvl.price + B
                lvl.bars = 0; lvl.mx = bar.high; lvl.mn = bar.low
            return
        # probíhá závod
        if lvl.rej is None:
            return
        lvl.bars += 1
        lvl.mx = max(lvl.mx, bar.high); lvl.mn = min(lvl.mn, bar.low)
        hit_rej = (bar.high >= lvl.rej) if lvl.rej > lvl.price else (bar.low <= lvl.rej)
        hit_brk = (bar.low <= lvl.brk) if lvl.brk < lvl.price else (bar.high >= lvl.brk)
        react = max(lvl.mx - lvl.price, lvl.price - lvl.mn)
        if hit_rej and hit_brk:
            lvl.n_amb += 1; lvl.sum_react += react; lvl.rej = None
        elif hit_rej:
            lvl.n_rej += 1; lvl.sum_react += react; lvl.rej = None
        elif hit_brk:
            lvl.n_brk += 1; lvl.sum_react += react; lvl.rej = None
        elif lvl.bars >= M:
            lvl.n_to += 1; lvl.sum_react += react; lvl.rej = None

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        d0 = et.date()
        skey = d0 if em >= SESS_ANCHOR else (d0 - timedelta(days=1))

        # nová session (18:00): reset session VWAP + VP; over-night start
        if self.skey != skey:
            self.skey = skey
            self._reset_session()
            self.on_hi = None; self.on_lo = None; self.gbx_open = None

        # overnight (18:00 → 9:30): akumuluj ON high/low a globex open
        if self.gbx_open is None:
            self.gbx_open = bar.open
        if not (RTH_OPEN <= em <= RTH_CLOSE):
            self.on_hi = bar.high if self.on_hi is None else max(self.on_hi, bar.high)
            self.on_lo = bar.low if self.on_lo is None else min(self.on_lo, bar.low)

        # session VWAP + VP (celá session)
        p = (bar.high + bar.low + bar.close) / 3.0
        v = bar.volume
        if v > 0:
            self.sPV += p * v; self.sV += v; self.sP2V += p * p * v
            b = round(p / VP_BIN) * VP_BIN
            self.svp[b] = self.svp.get(b, 0.0) + v

        # nový RTH den (na prvním RTH baru)
        if em == RTH_OPEN and self.rdate != d0:
            # roll prior-day z dokončeného RTH
            if self.rth_hi is not None:
                poc, vah, val = self._vp_levels(self.rvp)
                self.pd = {"H": self.rth_hi, "L": self.rth_lo, "C": self.prev_rth_close,
                           "O": self.rth_open, "mid": (self.rth_hi + self.rth_lo) / 2.0,
                           "POC": poc, "VAH": vah, "VAL": val}
                # týden
                wk = et.isocalendar()[1]
                if self.cur_week is None:
                    self.cur_week = wk; self.wk_hi = self.rth_hi; self.wk_lo = self.rth_lo
                    self.wk_close = self.prev_rth_close; self.wk_open = self.rth_open
                elif wk != self.cur_week:
                    self.pw = {"H": self.wk_hi, "L": self.wk_lo, "C": self.wk_close}
                    self.cur_week = wk; self.wk_hi = self.rth_hi; self.wk_lo = self.rth_lo
                    self.wk_close = self.prev_rth_close; self.wk_open = self.rth_open
                else:
                    self.wk_hi = max(self.wk_hi, self.rth_hi); self.wk_lo = min(self.wk_lo, self.rth_lo)
                    self.wk_close = self.prev_rth_close
            self._reset_rth(d0)
            self.rth_open = bar.open
            # ON úrovně
            if self.on_hi is not None:
                self.L["ONH"].price = self.on_hi; self.L["ONH"].active = True
                self.L["ONL"].price = self.on_lo; self.L["ONL"].active = True
                self.L["ONmid"].price = (self.on_hi + self.on_lo) / 2.0; self.L["ONmid"].active = True
            if self.gbx_open is not None:
                self.L["GBX_open"].price = self.gbx_open; self.L["GBX_open"].active = True
            # random kontrola: náhodný offset v ON rozsahu kolem open
            rng = (self.on_hi - self.on_lo) if (self.on_hi and self.on_lo) else 20.0
            random.seed(d0.toordinal())
            self.L["RANDOM"].price = bar.open + random.uniform(-0.5, 0.5) * max(rng, 5.0)
            self.L["RANDOM"].active = True

        # RTH akumulace + intraday úrovně
        if RTH_OPEN <= em <= RTH_CLOSE:
            self.rth_hi = bar.high if self.rth_hi is None else max(self.rth_hi, bar.high)
            self.rth_lo = bar.low if self.rth_lo is None else min(self.rth_lo, bar.low)
            self.prev_rth_close = bar.close
            if v > 0:
                self.rPV += p * v; self.rV += v; self.rP2V += p * p * v
                b = round(p / VP_BIN) * VP_BIN
                self.rvp[b] = self.rvp.get(b, 0.0) + v
            # opening ranges
            if em == 9 * 60 + 35: self.or5h, self.or5l = self.rth_hi, self.rth_lo
            if em == 9 * 60 + 45: self.or15h, self.or15l = self.rth_hi, self.rth_lo
            if em == 10 * 60: self.or30h, self.or30l = self.rth_hi, self.rth_lo
            if em == 10 * 60 + 30:
                self.ibh, self.ibl = self.rth_hi, self.rth_lo
            for nm, val in [("OR5H", self.or5h), ("OR5L", self.or5l), ("OR15H", self.or15h),
                            ("OR15L", self.or15l), ("OR30H", self.or30h), ("OR30L", self.or30l),
                            ("IBH", self.ibh), ("IBL", self.ibl)]:
                if val is not None and not self.L[nm].active:
                    self.L[nm].price = val; self.L[nm].active = True
            if self.ibh is not None and not self.L["IBmid"].active:
                self.L["IBmid"].price = (self.ibh + self.ibl) / 2.0; self.L["IBmid"].active = True
                self.L["IB_extU"].price = self.ibh + (self.ibh - self.ibl); self.L["IB_extU"].active = True
                self.L["IB_extD"].price = self.ibl - (self.ibh - self.ibl); self.L["IB_extD"].active = True

        # dynamické úrovně (VWAP bandy, VP, round) — přepočítej cenu do doteku
        self._update_dynamic(bar, em)

        # dotek + závod pro všechny
        for n in self.names:
            self._touch_and_race(self.L[n], bar, em)

    def _update_dynamic(self, bar, em):
        # session VWAP + bandy
        if self.sV > 0:
            vw = self.sPV / self.sV
            var = self.sP2V / self.sV - vw * vw
            sd = var ** 0.5 if var > 0 else 0.0
            for nm, val in [("sVWAP", vw), ("sV+1", vw + sd), ("sV-1", vw - sd),
                            ("sV+2", vw + 2 * sd), ("sV-2", vw - 2 * sd),
                            ("sV+3", vw + 3 * sd), ("sV-3", vw - 3 * sd)]:
                L = self.L[nm]
                if not L.touched:
                    L.price = val; L.active = True
            poc, vah, val_ = self._vp_levels(self.svp)
            for nm, vv in [("POC", poc), ("VAH", vah), ("VAL", val_)]:
                L = self.L[nm]
                if vv is not None and not L.touched:
                    L.price = vv; L.active = True
        # RTH VWAP + bandy
        if self.rV > 0:
            vw = self.rPV / self.rV
            var = self.rP2V / self.rV - vw * vw
            sd = var ** 0.5 if var > 0 else 0.0
            for nm, val in [("rVWAP", vw), ("rV+1", vw + sd), ("rV-1", vw - sd),
                            ("rV+2", vw + 2 * sd), ("rV-2", vw - 2 * sd)]:
                L = self.L[nm]
                if not L.touched:
                    L.price = val; L.active = True
        # round numbers (nejbližší netknutý multiple)
        for nm, step in [("round25", 25.0), ("round50", 50.0), ("round100", 100.0)]:
            L = self.L[nm]
            if not L.touched:
                L.price = round(bar.close / step) * step; L.active = True

    def on_end_of_algorithm(self):
        for n in self.names:
            L = self.L[n]
            dec = L.n_rej + L.n_brk
            self.log(f"###LVL### name={n} touch={L.n_touch} rej={L.n_rej} brk={L.n_brk} "
                     f"amb={L.n_amb} to={L.n_to} sum_react={L.sum_react:.1f}")
