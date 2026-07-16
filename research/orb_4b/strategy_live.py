# region imports
from AlgorithmImports import *
from collections import deque
import statistics
# endregion

# =====================================================================
# PRE-MARKET ORB — 1-min breakout, strukturální stop, 1:1 RR (NQ)
# Spustitelná strategie s reálnými ordery (ne compute-engine sim).
#
# Pravidla:
#   • Range = high/low svíček 9:15–9:30 ET (PŘED cash-open; nutné
#     extended hours). Range = jediná "pre-market" 15-min zóna.
#   • Breakout = 1-min close VENKU z range (>high long, <low short),
#     první za den, od 9:30/9:31 dál.
#   • Vstup: market order po 1-min close mimo range (fill ~ vzápětí).
#   • Stop-loss = 1.5 bodu ZA opačnou stranou range
#     (long → range_low − 1.5, short → range_high + 1.5).
#   • Take-profit = 1.5:1 k riziku (RR × |ref − SL|).
#   • Volitelný RVOL filtr: objem pre-market zóny / průměr za N dní.
#   • Max 1 obchod/den, EOD flat 16:00 ET.
#
# Poznámka k realitě: tato konfigurace v in-sample výzkumu (2018–2025)
# vyšla ~breakeven až mírně záporně po nákladech. Parametry níže NEJSOU
# ověřený edge — jsou to čisté defaulty k experimentování.
# =====================================================================


class PreMarketORB(QCAlgorithm):

    # ---- PARAMETRY (uprav dle libosti) -------------------------------
    RANGE_START   = 9 * 60 + 15    # 9:15 ET — začátek pre-market range
    RANGE_END     = 9 * 60 + 30    # 9:30 ET — konec range (cash open)
    SIGNAL_END    = 16 * 60        # nejpozdější breakout (16:00 = bez cutoffu;
                                   #   zkus zúžit na 10*60+30 = jen do 10:30)
    EOD_FLAT      = 16 * 60        # 16:00 ET — nucený výstup
    RVOL_MIN      = 1.2            # relative-volume filtr (0.0 = vypnuto)
    RVOL_LOOKBACK = 20             # dny pro RVOL baseline
    RISK_PCT      = 0.005          # riziko na obchod jako podíl equity (0.5 %)
    RR            = 1.5            # take-profit jako násobek rizika (1.5:1)
    SL_BUFFER     = 1.5            # body ZA opačnou stranou range (NQ)
    # ------------------------------------------------------------------

    def initialize(self):
        self.set_start_date(2018, 1, 2)
        self.set_end_date(2025, 9, 30)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)

        fut = self.add_future(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            contract_depth_offset=0, extended_market_hours=True)
        self.fut = fut
        self.consolidate(fut.symbol, timedelta(minutes=1), self.on_minute)

        self.pmvol_hist = deque(maxlen=self.RVOL_LOOKBACK)
        self.stop_ticket = None
        self.tp_ticket = None
        self._reset_day(None)

    def _reset_day(self, day):
        self.day = day
        self.pm_hi = None
        self.pm_lo = None
        self.pm_vol = 0.0
        self.range_ready = False
        self.traded = False
        self.rvol_ok = False

    def on_minute(self, bar):
        et = bar.end_time
        em = et.hour * 60 + et.minute
        day = et.date()

        if self.day != day:
            self._reset_day(day)

        # 1) stavba pre-market range 9:15–9:30
        if self.RANGE_START + 1 <= em <= self.RANGE_END:
            self.pm_hi = bar.high if self.pm_hi is None else max(self.pm_hi, bar.high)
            self.pm_lo = bar.low if self.pm_lo is None else min(self.pm_lo, bar.low)
            self.pm_vol += bar.volume
            return

        # 2) dokončení range + RVOL filtr (jednou, první bar po 9:30)
        if em > self.RANGE_END and not self.range_ready:
            self.range_ready = True
            if self.pm_hi is not None and len(self.pmvol_hist) >= 5:
                base = statistics.fmean(self.pmvol_hist)
                rvol = (self.pm_vol / base) if base > 0 else 0.0
                self.rvol_ok = (self.RVOL_MIN <= 0) or (rvol >= self.RVOL_MIN)
            else:
                self.rvol_ok = True  # warmup: nefiltruj (jinak krátká historie = 0 obchodů)
            if self.pm_hi is not None:
                self.pmvol_hist.append(self.pm_vol)

        # 3) EOD flat
        if em >= self.EOD_FLAT:
            if self.portfolio.invested:
                self.transactions.cancel_open_orders()
                self.liquidate()
                self.stop_ticket = None
                self.tp_ticket = None
            return

        # 4) breakout signál (první za den)
        if (self.range_ready and not self.traded and self.rvol_ok
                and not self.portfolio.invested and self.pm_hi is not None
                and self.RANGE_END < em <= self.SIGNAL_END):
            direction = 0
            if bar.close > self.pm_hi:
                direction = 1
            elif bar.close < self.pm_lo:
                direction = -1
            if direction != 0:
                self.traded = True
                self._enter(direction, bar.close)

    def _enter(self, direction, ref_price):
        contract = self.fut.mapped
        if contract is None:
            return
        stop = (self.pm_lo - self.SL_BUFFER) if direction == 1 else (self.pm_hi + self.SL_BUFFER)
        risk = abs(ref_price - stop)
        if risk <= 0:
            return
        tp = ref_price + direction * self.RR * risk
        mult = self.securities[contract].symbol_properties.contract_multiplier
        pv = self.portfolio.total_portfolio_value
        qty = int((self.RISK_PCT * pv) / (risk * mult))
        qty = max(1, qty) * direction

        self.market_order(contract, qty)
        # bracket: SL na opačné straně range, TP 1:1 (OCO řešeno v on_order_event)
        self.stop_ticket = self.stop_market_order(contract, -qty, stop)
        self.tp_ticket = self.limit_order(contract, -qty, tp)

    def on_order_event(self, oe):
        if oe.status != OrderStatus.FILLED:
            return
        # OCO: naplní-li se SL nebo TP, zruš sourozence
        if self.stop_ticket is not None and oe.order_id == self.stop_ticket.order_id:
            if self.tp_ticket is not None:
                self.tp_ticket.cancel()
            self.stop_ticket = None
            self.tp_ticket = None
        elif self.tp_ticket is not None and oe.order_id == self.tp_ticket.order_id:
            if self.stop_ticket is not None:
                self.stop_ticket.cancel()
            self.stop_ticket = None
            self.tp_ticket = None
