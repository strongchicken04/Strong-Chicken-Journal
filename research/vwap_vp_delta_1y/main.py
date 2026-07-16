# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 5 — DELTA GATE test (Kolej B). ES, IS, OOS NEDOTČENO.
# Kostra CONT (průraz ±1σ) + gate = AGRESE z footprint delty.
# Architektura: setup na MINUTOVÝCH barech (rychlé, plné IS); na každém
#   CONT triggeru se vyžádají TICKY té svíčky (self.history[Tick]) →
#   delta = buy_vol − sell_vol (Lee-Ready), ratio = delta/vol.
# Gate: znaménko(ratio)==směr & |ratio| ≥ thr. Grid thr {0,0.1,0.2,0.3,0.4}
#   + baseline (bez gate) = reprodukce kostry CONT.
# Cíl = nejbližší úroveň; stop 1:1; okno 10:00–16:00 ET; 1/den; EOD flat.
# =====================================================================

COST = 1.2 / 1e4
RISK_PCT = 0.01
VP_BIN = 1.0
SESS_ANCHOR = 18 * 60
WIN_START = 10 * 60
WIN_END = 16 * 60
MIN_STOP = 1.0
THRS = [0.0, 0.1, 0.2, 0.3, 0.4]


class Sim:
    def __init__(self, tag, thr):
        self.tag = tag
        self.thr = thr          # None = baseline (bez gate)
        self.nav = 100000.0
        self.pos = 0; self.entry = 0.0; self.stop = 0.0; self.tp = 0.0
        self.stop_dist = 0.0; self.notional = 0.0; self.risk_dollars = 0.0
        self.pending = 0
        self.n = 0; self.wins = 0; self.tp_n = 0; self.sl_n = 0; self.eod_n = 0
        self.sumR = 0.0; self.sumR2 = 0.0; self.yr = {}

    def gate_ok(self, d, ratio):
        if self.thr is None:
            return True
        return (ratio > 0) == (d == 1) and abs(ratio) >= self.thr

    def close(self, exit_px, kind, year):
        d = self.pos
        gross = self.notional * d * (exit_px - self.entry) / self.entry
        cost = self.notional * COST
        R = (gross - cost) / self.risk_dollars if self.risk_dollars > 0 else 0.0
        self.nav += (gross - cost)
        self.n += 1
        if (gross - cost) > 0: self.wins += 1
        if kind == "tp": self.tp_n += 1
        elif kind == "sl": self.sl_n += 1
        else: self.eod_n += 1
        self.sumR += R; self.sumR2 += R * R
        e = self.yr.setdefault(year, [0, 0.0]); e[0] += 1; e[1] += R
        self.pos = 0


class VwapVpDelta(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 10, 1)
        self.set_end_date(2025, 9, 30)   # OOS NEDOTČENO
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_benchmark(lambda t: 0)

        self.fut = self.add_future(
            Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=True)
        self.sym = self.fut.symbol
        self.consolidate(self.sym, timedelta(minutes=1), self.on1)

        self.sims = [Sim("base", None)] + [Sim(f"t{int(t*100):02d}", t) for t in THRS]
        self.skey = None
        self.diag = 0
        self.n_trig = 0; self.n_nodata = 0
        self._reset_session()

    def _reset_session(self):
        self.sPV = 0.0; self.sV = 0.0; self.sP2V = 0.0
        self.vp = {}
        self.traded = False
        for s in self.sims:
            s.pending = 0

    def _levels(self):
        if self.sV <= 0:
            return None
        vwap = self.sPV / self.sV
        var = self.sP2V / self.sV - vwap * vwap
        std = var ** 0.5 if var > 0 else 0.0
        up1 = vwap + std; dn1 = vwap - std
        poc = vah = val = vwap
        if self.vp:
            total = sum(self.vp.values())
            prices = sorted(self.vp)
            pocp = max(self.vp, key=self.vp.get)
            i = prices.index(pocp)
            lo = hi = i; acc = self.vp[pocp]
            while acc < 0.7 * total and (lo > 0 or hi < len(prices) - 1):
                left = self.vp[prices[lo - 1]] if lo > 0 else -1
                right = self.vp[prices[hi + 1]] if hi < len(prices) - 1 else -1
                if right >= left and hi < len(prices) - 1:
                    hi += 1; acc += self.vp[prices[hi]]
                elif lo > 0:
                    lo -= 1; acc += self.vp[prices[lo]]
                else:
                    break
            poc = pocp; vah = prices[hi]; val = prices[lo]
        return dict(vwap=vwap, up1=up1, dn1=dn1, poc=poc, vah=vah, val=val)

    def _target(self, lv, entry, d):
        cands = [lv["vwap"], lv["up1"], lv["dn1"], lv["poc"], lv["vah"], lv["val"]]
        if d == 1:
            above = [p for p in cands if p > entry + MIN_STOP]
            return min(above) if above else None
        below = [p for p in cands if p < entry - MIN_STOP]
        return max(below) if below else None

    def _bar_delta(self, bar):
        """Vyžádá ticky svíčky, vrátí (ratio=delta/vol, nticks, class%) nebo None."""
        try:
            ticks = self.history[Tick](self.fut.mapped, bar.time, bar.end_time, Resolution.TICK)
        except Exception as e:
            if self.diag < 5:
                self.log(f"###DIAG### history error: {str(e)[:120]}")
            return None
        bb = 0.0; ba = 0.0; buy = 0.0; sell = 0.0; vol = 0.0; nt = 0
        for t in ticks:
            if t.tick_type == TickType.Quote:
                if t.bid_price > 0: bb = t.bid_price
                if t.ask_price > 0: ba = t.ask_price
            elif t.tick_type == TickType.Trade:
                nt += 1; q = t.quantity; vol += q
                if ba > 0 and t.price >= ba: buy += q
                elif bb > 0 and t.price <= bb: sell += q
        if vol <= 0:
            return None
        ratio = (buy - sell) / vol
        cls = 100.0 * (buy + sell) / vol
        if self.diag < 12:
            self.log(f"###DIAG### {bar.end_time} nt={nt} vol={vol:.0f} ratio={ratio:+.3f} class%={cls:.1f}")
            self.diag += 1
        return ratio

    def on1(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        d0 = et.date()
        skey = d0 if em >= SESS_ANCHOR else (d0 - timedelta(days=1))
        if self.skey != skey:
            yr = self.skey.year if self.skey else d0.year
            for s in self.sims:
                if s.pos != 0:
                    s.close(bar.open, "eod", yr)
            self.skey = skey
            self._reset_session()

        p = (bar.high + bar.low + bar.close) / 3.0
        v = bar.volume
        if v > 0:
            self.sPV += p * v; self.sV += v; self.sP2V += p * p * v
            b = round(p / VP_BIN) * VP_BIN
            self.vp[b] = self.vp.get(b, 0.0) + v

        lv = self._levels()
        if lv is None:
            return
        yr = self.skey.year

        # 1) fill pending
        for s in self.sims:
            if s.pending != 0 and s.pos == 0:
                d = s.pending; e = bar.open
                tgt = self._target(lv, e, d)
                s.pending = 0
                if tgt is None:
                    continue
                sd = abs(tgt - e)
                if sd < MIN_STOP:
                    continue
                s.pos = d; s.entry = e; s.tp = tgt
                s.stop = e - d * sd; s.stop_dist = sd
                risk_ret = sd / e
                s.notional = min(s.nav, RISK_PCT * s.nav / risk_ret)
                s.risk_dollars = s.notional * risk_ret

        # 2) SL/TP
        for s in self.sims:
            if s.pos != 0:
                hit_sl = (bar.low <= s.stop) if s.pos == 1 else (bar.high >= s.stop)
                hit_tp = (bar.high >= s.tp) if s.pos == 1 else (bar.low <= s.tp)
                if hit_sl:
                    s.close(s.stop, "sl", yr)
                elif hit_tp:
                    s.close(s.tp, "tp", yr)

        # 3) CONT trigger (první za session, okno 10:00–16:00)
        if WIN_START <= em < WIN_END and not self.traded:
            d = 0
            if bar.close > lv["up1"]: d = 1
            elif bar.close < lv["dn1"]: d = -1
            if d != 0:
                self.traded = True
                self.n_trig += 1
                ratio = self._bar_delta(bar)
                if ratio is None:
                    self.n_nodata += 1
                    ratio = 0.0  # baseline stejně vezme; gated s thr>0 propadnou
                for s in self.sims:
                    if s.pos == 0 and s.gate_ok(d, ratio):
                        s.pending = d

        # 4) EOD flat
        if em >= WIN_END:
            for s in self.sims:
                if s.pos != 0:
                    s.close(bar.close, "eod", yr)
            for s in self.sims:
                self.plot("equity", s.tag + "_nav", s.nav)

    def on_end_of_algorithm(self):
        self.log(f"###DELTA### triggers={self.n_trig} nodata={self.n_nodata}")
        for s in self.sims:
            mean = s.sumR / s.n if s.n else 0.0
            self.set_runtime_statistic(s.tag + "_n", str(s.n))
            self.set_runtime_statistic(s.tag + "_meanR", f"{mean:.4f}")
            yrs = ",".join(f"{y}:{s.yr.get(y,[0,0.0])[1]:.3f}" for y in range(2018, 2026))
            self.log(f"###VVD### tag={s.tag} thr={s.thr} n={s.n} wins={s.wins} tp={s.tp_n} "
                     f"sl={s.sl_n} eod={s.eod_n} sumR={s.sumR:.4f} sumR2={s.sumR2:.4f} nav={s.nav:.1f} yrs={yrs}")
