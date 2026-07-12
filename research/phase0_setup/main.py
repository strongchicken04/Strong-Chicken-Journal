# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# =====================================================================
# FÁZE 0 — Baseline statistika (compute-engine backtest, ŽÁDNÉ objednávky)
#
# Otázka: podíl dní, kdy CLOSE první 15min RTH svíčky (9:30–9:45 ET)
# leží UVNITŘ vs. MIMO kompletní 7denní High/Low pásmo předchozích
# 7 obchodních dnů (bez dnešního dne) — zvlášť pro SPY a pro ES.
#
# Global rules dodržené:
#  - Look-ahead: pásmo se počítá jen z 7 DOKONČENÝCH předchozích dnů;
#    dnešní denní bar se do pásma přidá až po jeho uzavření.
#  - OOS: end date = 2025-09-30 (posledních ~9-12 měsíců je rezervováno
#    pro Fázi E, sem se nikdy nenačte).
#  - Kontrolované srovnání: pásmo = RTH-only (9:30-16:00) H/L u OBOU
#    instrumentů, aby se izoloval efekt instrumentu, ne definice pásma.
#
# Timezone: algoritmus je připnutý na New York (ET). self.time je tedy
# ET a rovná se end-time právě zpracovávaného minutového baru, což
# odstraňuje CME/CT dvojznačnost u ES.
# =====================================================================

RTH_OPEN_MIN = 9 * 60 + 30      # 570  (9:30)
FIRST15_END_MIN = 9 * 60 + 45   # 585  (9:45)  -> end-time baru 9:44->9:45
RTH_CLOSE_MIN = 16 * 60         # 960  (16:00)


class SymbolState:
    def __init__(self):
        self.days = deque(maxlen=7)   # (high, low) posledních 7 DOKONČENÝCH RTH dnů
        self.cur_date = None
        self.day_high = None
        self.day_low = None
        self.first15_close = None
        self.checked_today = False
        # čítače
        self.n = 0
        self.inside = 0
        self.bars_seen = 0
        # per-rok rozpad: rok -> [n, inside]
        self.by_year = {}


class Phase0Baseline(QCAlgorithm):

    def initialize(self):
        # --- IN-SAMPLE okno pouze; OOS (2025-10-01+) rezervováno pro Fázi E ---
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)                 # nepoužito, žádné obchody
        self.set_time_zone(TimeZones.NEW_YORK)  # připnout ET

        # SPY — RAW ceny (band i close na stejné reálné cenové škále)
        spy = self.add_equity("SPY", Resolution.MINUTE,
                              data_normalization_mode=DataNormalizationMode.RAW)
        self._spy = spy.symbol

        # ES kontinuální kontrakt — BACKWARDS_RATIO (hladké rolly),
        # mapování dle open interest, front month (depth 0)
        es = self.add_future(
            Futures.Indices.SP_500_E_MINI,
            resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0,
        )
        es.set_filter(0, 182)
        self._es = es.symbol   # kanonický symbol -> nese kontinuální bary

        self._state = {self._spy: SymbolState(), self._es: SymbolState()}
        self._labels = {self._spy: "SPY", self._es: "ES"}

    def on_data(self, data: Slice):
        st_time = self.time  # ET, end-time aktuálního minutového baru
        minutes = st_time.hour * 60 + st_time.minute
        d = st_time.date()

        for sym, state in self._state.items():
            bar = data.bars.get(sym) if data.bars is not None else None
            if bar is None:
                continue
            state.bars_seen += 1

            # --- rollover dne: dokončený předchozí den ulož do 7denního okna ---
            if state.cur_date != d:
                if state.cur_date is not None and state.day_high is not None:
                    state.days.append((state.day_high, state.day_low))
                state.cur_date = d
                state.day_high = None
                state.day_low = None
                state.first15_close = None
                state.checked_today = False

            # --- akumulace RTH-only denního High/Low (end-time v (9:30, 16:00]) ---
            if RTH_OPEN_MIN + 1 <= minutes <= RTH_CLOSE_MIN:
                hi = bar.high
                lo = bar.low
                state.day_high = hi if state.day_high is None else max(state.day_high, hi)
                state.day_low = lo if state.day_low is None else min(state.day_low, lo)

            # --- první 15min RTH svíčka: close baru končícího v 9:45 ---
            if minutes == FIRST15_END_MIN and state.first15_close is None:
                state.first15_close = bar.close
                if len(state.days) == 7 and not state.checked_today:
                    band_high = max(h for h, l in state.days)
                    band_low = min(l for h, l in state.days)
                    inside = band_low <= state.first15_close <= band_high
                    state.n += 1
                    if inside:
                        state.inside += 1
                    yr = d.year
                    if yr not in state.by_year:
                        state.by_year[yr] = [0, 0]
                    state.by_year[yr][0] += 1
                    if inside:
                        state.by_year[yr][1] += 1
                    state.checked_today = True

    def on_end_of_algorithm(self):
        self.log("=================  PHASE0 BASELINE RESULTS  =================")
        for sym, state in self._state.items():
            label = self._labels[sym]
            n = state.n
            ins = state.inside
            out = n - ins
            pct_in = (100.0 * ins / n) if n else 0.0
            pct_out = (100.0 * out / n) if n else 0.0
            self.log(f"###RESULT### {label} bars_seen={state.bars_seen} "
                     f"n={n} inside={ins} outside={out} "
                     f"pct_inside={pct_in:.4f} pct_outside={pct_out:.4f}")
            for yr in sorted(state.by_year):
                yn, yi = state.by_year[yr]
                ypct = (100.0 * yi / yn) if yn else 0.0
                self.log(f"###YEAR### {label} year={yr} n={yn} inside={yi} "
                         f"pct_inside={ypct:.4f}")
        self.log("============================================================")
