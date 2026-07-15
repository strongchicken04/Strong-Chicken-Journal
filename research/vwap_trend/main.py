# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — R4a: NQ baseline + ANATOMIE P&L.
# Přesná VWAP trend pravidla (viz R1/R2, beze změny), NQ kontinuální
# kontrakt, RTH-only VWAP 9:30-16:00 ET (vědomé ukotvení jako ES),
# notional 1x NAV, GROSS (costs 0,4/1,2 bps lokálně).
# Okno 2018-01-02 -> 2025-09-30 (vyhrazené okno NEDOTČENO).
#
# Export navíc: agregáty "kde bydlí edge":
#  ###HOUR### éra × hodina vstupu   (n, wins, sum_pnl_pct)
#  ###IDX###  éra × pořadí obchodu v dni (1..9, 10+)
#  ###DUR###  éra × délka držení (<5, 5-15, 15-30, 30-60, 60+ min)
#  ###CONC### éra: koncentrace gross P&L (top 1/5/10 % obchodů)
# Éra 0 = 2018-2021, éra 1 = 2022-2025 (stabilita napříč režimy).
# =====================================================================

OPEN_BAR_MIN = 9 * 60 + 31
CLOSE_MIN = 16 * 60


class Sim:
    def __init__(self):
        self.nav = 25000.0
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None
        self.entry_min = 0
        self.trades = 0
        self.wins = 0
        self.sum_win = 0.0
        self.sum_loss = 0.0
        self.trades_today = 0
        # anatomie
        self.hour = {}    # (era, hour) -> [n, w, sum_pnl]
        self.idx = {}     # (era, idx_bucket) -> [n, w, sum]
        self.dur = {}     # (era, dur_bucket) -> [n, w, sum]
        self.pnls = {0: [], 1: []}

    def _agg(self, d, key, ret):
        a = d.setdefault(key, [0, 0, 0.0])
        a[0] += 1
        if ret > 0:
            a[1] += 1
        a[2] += ret

    def fill_open(self, price, minutes):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close_at(price, minutes, era=self._era)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            self.entry_min = minutes
            self.trades_today += 1

    def close_at(self, price, minutes, era):
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
        # anatomie
        h = min(max(self.entry_min // 60, 9), 15)
        ib = self.trades_today if self.trades_today < 10 else 10
        dmin = minutes - self.entry_min
        db = 0 if dmin < 5 else (1 if dmin < 15 else (2 if dmin < 30 else (3 if dmin < 60 else 4)))
        self._agg(self.hour, (era, h), ret)
        self._agg(self.idx, (era, ib), ret)
        self._agg(self.dur, (era, db), ret)
        self.pnls[era].append(ret)
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0


class VWAPTrendNQ(QCAlgorithm):

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
        self.sim = Sim()
        self.cur_date = None
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.last_close = None

    @property
    def era(self):
        return 0 if self.time.year <= 2021 else 1

    def on_data(self, data: Slice):
        if self.sym not in data.bars:
            return
        bar = data.bars[self.sym]
        sim = self.sim
        sim._era = self.era
        t = self.time
        minutes = t.hour * 60 + t.minute
        d = t.date()

        if self.cur_date != d:
            if self.cur_date is not None:
                sim.pending = None
                if sim.pos != 0 and self.last_close:
                    sim.close_at(self.last_close, CLOSE_MIN, era=sim._era)
                self.plot("nav", "NQ_nav", sim.nav)
                self.plot("nav", "NQ_trd", sim.trades_today)
                sim.trades_today = 0
            self.cur_date = d
            self.cum_pv = 0.0
            self.cum_v = 0.0
            self.last_close = None

        if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
            return

        sim.fill_open(bar.open, minutes)

        v = float(bar.volume)
        if v > 0:
            self.cum_pv += ((bar.high + bar.low + bar.close) / 3.0) * v
            self.cum_v += v
        self.last_close = bar.close
        if self.cum_v <= 0:
            return
        vwap = self.cum_pv / self.cum_v
        c = bar.close

        if minutes == OPEN_BAR_MIN:
            if c > vwap:
                sim.pending = 1
            elif c < vwap:
                sim.pending = -1
        elif sim.pos > 0 and c < vwap:
            sim.pending = -1
        elif sim.pos < 0 and c > vwap:
            sim.pending = 1

        if minutes == CLOSE_MIN:
            sim.pending = None
            if sim.pos != 0:
                sim.close_at(bar.close, minutes, era=sim._era)

    def on_end_of_algorithm(self):
        sim = self.sim
        sim.pending = None
        if sim.pos != 0 and self.last_close:
            sim.close_at(self.last_close, CLOSE_MIN, era=1)
        self.plot("nav", "NQ_nav", sim.nav)
        self.plot("nav", "NQ_trd", sim.trades_today)
        losses = sim.trades - sim.wins
        self.set_runtime_statistic("NQ_trades", str(sim.trades))
        self.set_runtime_statistic("NQ_wins", str(sim.wins))
        self.set_runtime_statistic("NQ_final_nav", f"{sim.nav:.2f}")
        aw = (sim.sum_win / sim.wins) if sim.wins else 0.0
        al = (sim.sum_loss / losses) if losses else 0.0
        self.set_runtime_statistic("NQ_avg_win_pct", f"{100*aw:.4f}")
        self.set_runtime_statistic("NQ_avg_loss_pct", f"{100*al:.4f}")
        for (era, h), a in sorted(sim.hour.items()):
            self.log(f"###HOUR### era={era} h={h} n={a[0]} w={a[1]} sum={100*a[2]:.3f}")
        for (era, ib), a in sorted(sim.idx.items()):
            self.log(f"###IDX### era={era} i={ib} n={a[0]} w={a[1]} sum={100*a[2]:.3f}")
        for (era, db), a in sorted(sim.dur.items()):
            self.log(f"###DUR### era={era} d={db} n={a[0]} w={a[1]} sum={100*a[2]:.3f}")
        for era in (0, 1):
            p = sorted(sim.pnls[era], reverse=True)
            n = len(p)
            if n:
                tot = sum(p)
                t1 = sum(p[:max(1, n // 100)])
                t5 = sum(p[:max(1, n // 20)])
                t10 = sum(p[:max(1, n // 10)])
                self.log(f"###CONC### era={era} n={n} total={100*tot:.2f} "
                         f"top1={100*t1:.2f} top5={100*t5:.2f} top10={100*t10:.2f}")
