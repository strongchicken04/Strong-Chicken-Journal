# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# =====================================================================
# PROJEKT 5 — DELTA GATE v2: kumulativní delta (agrese) + absorpce/divergence.
# Kostra CONT (průraz ±1σ). Na triggeru se vyžádají ticky POSLEDNÍCH K=10
#   minut → CVD (buy−sell) a cvd_ratio=CVD/vol; price_move = close − close[K].
# Varianty:
#   base                 : bez gate (= kostra CONT)
#   A_sign               : sign(CVD)==směr (slabá agrese-konfirmace)
#   A_005 / A_010        : |cvd_ratio| ≥ 0.05 / 0.10 & sign match
#   B_agree              : cena i delta souhlasí se směrem (anti-divergence)
#   AB                   : A_005 & B_agree
# Cíl=nejbližší úroveň; stop 1:1; okno 10:00–16:00 ET; 1/den; EOD flat.
# 1 rok (2024-10→2025-09) pro rychlost. OOS NEDOTČENO.
# =====================================================================

COST = 1.2 / 1e4
RISK_PCT = 0.01
VP_BIN = 1.0
SESS_ANCHOR = 18 * 60
WIN_START = 10 * 60
WIN_END = 16 * 60
MIN_STOP = 1.0
K_BARS = 10


class Sim:
    def __init__(self, tag, kind):
        self.tag = tag
        self.kind = kind        # gate typ
        self.nav = 100000.0
        self.pos = 0; self.entry = 0.0; self.stop = 0.0; self.tp = 0.0
        self.stop_dist = 0.0; self.notional = 0.0; self.risk_dollars = 0.0
        self.pending = 0
        self.n = 0; self.wins = 0; self.tp_n = 0; self.sl_n = 0; self.eod_n = 0
        self.sumR = 0.0; self.sumR2 = 0.0; self.yr = {}

    def gate_ok(self, d, cvd_ratio, price_move):
        agree_delta = (cvd_ratio > 0) == (d == 1)
        agree_price = (price_move > 0) == (d == 1)
        k = self.kind
        if k == "base":
            return True
        if k == "A_sign":
            return agree_delta
        if k == "A_005":
            return agree_delta and abs(cvd_ratio) >= 0.05
        if k == "A_010":
            return agree_delta and abs(cvd_ratio) >= 0.10
        if k == "B_agree":
            return agree_delta and agree_price
        if k == "AB":
            return agree_delta and agree_price and abs(cvd_ratio) >= 0.05
        return True

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


class VwapVpDelta2(QCAlgorithm):

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

        self.sims = [Sim("base", "base"), Sim("A_sign", "A_sign"),
                     Sim("A_005", "A_005"), Sim("A_010", "A_010"),
                     Sim("B_agree", "B_agree"), Sim("AB", "AB")]
        self.closes = deque(maxlen=K_BARS + 1)
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

    def _cvd(self, et):
        """CVD za posledních K minut (buy−sell) / vol."""
        try:
            ticks = self.history[Tick](self.fut.mapped, et - timedelta(minutes=K_BARS), et, Resolution.TICK)
        except Exception as e:
            if self.diag < 3:
                self.log(f"###DIAG### history error: {str(e)[:120]}")
            return None
        bb = 0.0; ba = 0.0; buy = 0.0; sell = 0.0; vol = 0.0
        for t in ticks:
            if t.tick_type == TickType.Quote:
                if t.bid_price > 0: bb = t.bid_price
                if t.ask_price > 0: ba = t.ask_price
            elif t.tick_type == TickType.Trade:
                q = t.quantity; vol += q
                if ba > 0 and t.price >= ba: buy += q
                elif bb > 0 and t.price <= bb: sell += q
        if vol <= 0:
            return None
        return (buy - sell) / vol

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
        self.closes.append(bar.close)

        lv = self._levels()
        if lv is None:
            return
        yr = self.skey.year

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

        for s in self.sims:
            if s.pos != 0:
                hit_sl = (bar.low <= s.stop) if s.pos == 1 else (bar.high >= s.stop)
                hit_tp = (bar.high >= s.tp) if s.pos == 1 else (bar.low <= s.tp)
                if hit_sl:
                    s.close(s.stop, "sl", yr)
                elif hit_tp:
                    s.close(s.tp, "tp", yr)

        if WIN_START <= em < WIN_END and not self.traded:
            d = 0
            if bar.close > lv["up1"]: d = 1
            elif bar.close < lv["dn1"]: d = -1
            if d != 0:
                self.traded = True
                self.n_trig += 1
                cvd_ratio = self._cvd(et)
                if cvd_ratio is None:
                    self.n_nodata += 1
                    cvd_ratio = 0.0
                price_move = (bar.close - self.closes[0]) if len(self.closes) > K_BARS else 0.0
                if self.diag < 12:
                    self.log(f"###DIAG### {et} dir={d} cvd_ratio={cvd_ratio:+.3f} price_move={price_move:+.2f}")
                    self.diag += 1
                for s in self.sims:
                    if s.pos == 0 and s.gate_ok(d, cvd_ratio, price_move):
                        s.pending = d

        if em >= WIN_END:
            for s in self.sims:
                if s.pos != 0:
                    s.close(bar.close, "eod", yr)

    def on_end_of_algorithm(self):
        self.log(f"###DELTA### triggers={self.n_trig} nodata={self.n_nodata}")
        for s in self.sims:
            mean = s.sumR / s.n if s.n else 0.0
            self.log(f"###VVD2### tag={s.tag} n={s.n} wins={s.wins} tp={s.tp_n} "
                     f"sl={s.sl_n} eod={s.eod_n} sumR={s.sumR:.4f} sumR2={s.sumR2:.4f} nav={s.nav:.1f}")
