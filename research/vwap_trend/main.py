# region imports
from AlgorithmImports import *
# endregion

# =====================================================================
# PROJEKT 3 — VWAP Trend Trading (Zarattini/Aziz, SSRN 4631351).
# Compute-engine simulace (žádné QC objednávky) — přesná replikace pravidel:
#  - session VWAP (RTH only, reset denně): sum(HLC/3 * V) / sum(V)
#  - 9:31 close prvního baru vs VWAP -> long/short na OPEN dalšího baru
#  - close baru na opačné straně VWAP -> close + okamžitý flip na open
#    dalšího baru (průnik intra-bar bez close za VWAP nespouští nic)
#  - EOD 16:00: vše flat na close; žádné overnight
#  - 100 % kapitálu, frakční shares, plný reinvest
# MODE:
#  R1 = QQQ+TQQQ, 2018-01-02 -> 2023-09-28, fee $0.0005/share/side (paper)
#  R2 = SPY+ES,   2018-01-02 -> 2025-09-30, GROSS (reálné bps costs lokálně);
#       ES: VWAP i obchodování ukotveny na RTH 9:30-16:00 ET (vědomé
#       rozhodnutí), kontinuální kontrakt, notional 1x NAV (bez páky).
# Export: chart "nav" série {tick}_nav (denní NAV) + {tick}_trd (obchody/den);
# runtime stats: trades/wins/sum_win/sum_loss per ticker.
# =====================================================================

MODE = "R2"   # "R1" | "R2"

OPEN_BAR_MIN = 9 * 60 + 31    # 571 = end-time prvního RTH baru (9:30->9:31)
CLOSE_MIN = 16 * 60           # 960


class Sim:
    """Nezávislý simulovaný účet pro jeden instrument."""
    def __init__(self, fee_per_share):
        self.nav = 25000.0
        self.fee = fee_per_share
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0
        self.pending = None       # cílová pozice k fillnutí na open dalšího baru
        self.trades = 0
        self.wins = 0
        self.sum_win = 0.0        # suma kladných trade returnů (pct)
        self.sum_loss = 0.0       # suma |záporných| trade returnů (pct)
        self.trades_today = 0

    def fill_open(self, price):
        if self.pending is None:
            return
        tgt = self.pending
        self.pending = None
        if self.pos != 0:
            self.close_at(price)
        if tgt != 0 and price > 0:
            self.pos = tgt
            self.entry = price
            self.shares = self.nav / price
            self.nav -= self.shares * self.fee

    def close_at(self, price):
        if self.pos == 0:
            return
        pnl = self.pos * (price - self.entry) * self.shares
        ret = pnl / (self.entry * self.shares) if self.entry > 0 and self.shares > 0 else 0.0
        self.nav += pnl
        self.nav -= self.shares * self.fee
        self.trades += 1
        self.trades_today += 1
        if pnl > 0:
            self.wins += 1
            self.sum_win += ret
        else:
            self.sum_loss += -ret
        self.pos = 0
        self.entry = 0.0
        self.shares = 0.0


class VWAPTrend(QCAlgorithm):

    def initialize(self):
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.sims = {}
        self.state = {}
        if MODE == "R1":
            self.set_start_date(2018, 1, 2)
            self.set_end_date(2023, 9, 28)
            for t in ("QQQ", "TQQQ"):
                sec = self.add_equity(t, Resolution.MINUTE)
                self.sims[sec.symbol] = Sim(0.0005)
                self.state[sec.symbol] = self._fresh(t)
        else:
            self.set_start_date(2018, 1, 2)
            self.set_end_date(2025, 9, 30)   # vyhrazené okno 2025-10+ NEDOTČENO
            sec = self.add_equity("SPY", Resolution.MINUTE,
                                  data_normalization_mode=DataNormalizationMode.RAW)
            self.sims[sec.symbol] = Sim(0.0)
            self.state[sec.symbol] = self._fresh("SPY")
            fut = self.add_future(
                Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE,
                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                contract_depth_offset=0, extended_market_hours=False)
            fut.set_filter(0, 182)
            self.sims[fut.symbol] = Sim(0.0)
            self.state[fut.symbol] = self._fresh("ES")

    def _fresh(self, label):
        return {"label": label, "date": None, "cum_pv": 0.0, "cum_v": 0.0,
                "last_close": None}

    def on_data(self, data: Slice):
        for sym, sim in self.sims.items():
            if sym not in data.bars:
                continue
            bar = data.bars[sym]
            st = self.state[sym]
            t = self.time
            minutes = t.hour * 60 + t.minute
            d = t.date()

            # --- rollover dne ---
            if st["date"] != d:
                if st["date"] is not None:
                    # half-day/gap pojistka: flat na posledním známém close
                    sim.pending = None
                    if sim.pos != 0 and st["last_close"]:
                        sim.close_at(st["last_close"])
                    self.plot("nav", f"{st['label']}_nav", sim.nav)
                    self.plot("nav", f"{st['label']}_trd", sim.trades_today)
                    sim.trades_today = 0
                st["date"] = d
                st["cum_pv"] = 0.0
                st["cum_v"] = 0.0
                st["last_close"] = None

            if not (OPEN_BAR_MIN <= minutes <= CLOSE_MIN):
                continue

            # 1) fill pending na open tohoto baru
            sim.fill_open(bar.open)

            # 2) update VWAP (RTH bary)
            v = float(bar.volume)
            if v > 0:
                st["cum_pv"] += ((bar.high + bar.low + bar.close) / 3.0) * v
                st["cum_v"] += v
            st["last_close"] = bar.close
            if st["cum_v"] <= 0:
                continue
            vwap = st["cum_pv"] / st["cum_v"]
            c = bar.close

            # 3) signály (jen close vs VWAP)
            if minutes == OPEN_BAR_MIN:
                if c > vwap:
                    sim.pending = 1
                elif c < vwap:
                    sim.pending = -1
            elif sim.pos > 0 and c < vwap:
                sim.pending = -1
            elif sim.pos < 0 and c > vwap:
                sim.pending = 1

            # 4) EOD flat
            if minutes == CLOSE_MIN:
                sim.pending = None
                if sim.pos != 0:
                    sim.close_at(bar.close)

    def on_end_of_algorithm(self):
        for sym, sim in self.sims.items():
            st = self.state[sym]
            lbl = st["label"]
            # poslední den
            sim.pending = None
            if sim.pos != 0 and st["last_close"]:
                sim.close_at(st["last_close"])
            self.plot("nav", f"{lbl}_nav", sim.nav)
            self.plot("nav", f"{lbl}_trd", sim.trades_today)
            losses = sim.trades - sim.wins
            self.set_runtime_statistic(f"{lbl}_trades", str(sim.trades))
            self.set_runtime_statistic(f"{lbl}_wins", str(sim.wins))
            self.set_runtime_statistic(f"{lbl}_final_nav", f"{sim.nav:.2f}")
            aw = (sim.sum_win / sim.wins) if sim.wins else 0.0
            al = (sim.sum_loss / losses) if losses else 0.0
            self.set_runtime_statistic(f"{lbl}_avg_win_pct", f"{100*aw:.4f}")
            self.set_runtime_statistic(f"{lbl}_avg_loss_pct", f"{100*al:.4f}")
            self.log(f"###R### {lbl} mode={MODE} trades={sim.trades} wins={sim.wins} "
                     f"final_nav={sim.nav:.2f} avg_win={100*aw:.4f}% avg_loss={100*al:.4f}%")
