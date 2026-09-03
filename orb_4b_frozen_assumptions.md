# PROJEKT 4b — ORB pre-market range, 1-min breakout, 1:1 RR + filtry — KROK 0

> **Status:** čeká na výslovné potvrzení. **Žádný backtest kód se nepíše, dokud tohle nepotvrdíš.**
> Odlišná varianta ORB, NE náhrada Projektu 4. Výsledky se drží oddělené: sekce „Varianta 4b" v `PLAYBOOK_orb.md`, samostatný QC projekt.
> **Prior: neutrálně-skeptický.** Nezávislá MNQ falsifikační studie (Structural Limits of OHLCV-Based Intraday Signals in MNQ) už ORB varianty vč. pullback entry na mikro-NQ zamítla po frikci (pullback: N=83, WR 19,3 %, t=−1,27, FAIL). Není to důvod nezkoušet — je to důvod nečekat, že filtry samy zaručí edge.

---

## 0. Design / infrastruktura, co si žádá pozornost

- **Extended hours NUTNÉ:** range 9:15–9:30 ET je **před cash-open** → `extended_market_hours=True` (Projekt 4 měl RTH-only False). Bez toho pre-market svíčka v datech chybí.
- **1:1 RR → breakeven hit rate = 50 %** (před náklady). Se strukturálním stopem (opačná strana range) je vzdálenost k SL = |entry − opačná strana| (range + overshoot), TP stejně daleko. Po nákladech potřebuje **> ~50–52 % win rate**. To je mírnější podmínka než Projekt 4 (66,7 %), ale MNQ studie ukazuje, že i to bývá po frikci nedosažitelné.
- **Náklad vs šířka range:** cost v R = 1,2 bps × entry / stop_dist. Malá pre-market range → těsný stop → velký náklad v R. Range filtr s tímhle přímo interaguje.
- **Optimizer's curse:** 3 nové filtrové parametry → grid. Aplikuju **stejnou disciplínu jako Projekt 3 D2** — heatmapa, a kandidát se bere jen když sedí v souvislém stabilním ostrově sousedících kombinací, ne jako izolovaný peak.

---

## 1–6. Odpovědi na Krok-0 body

### 1. Instrument — **NQ** (potvrzuji)
NQ (E-mini Nasdaq-100), kontinuální kontrakt, `add_future(Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.MINUTE, data_mapping_mode=OPEN_INTEREST, data_normalization_mode=BACKWARDS_RATIO, contract_depth_offset=0, extended_market_hours=True)`, `set_time_zone(NEW_YORK)`. Konzistentní s VWAP trend projektem.

### 2. High-low range filter — **percentil trailing rozdělení, ne hardcoded body** (návrh)
- **Definice:** `range_width` = high−low pre-market svíčky (9:15–9:30) v bodech.
- **Filtr:** trade jen když `range_width ≥ P-tý percentil` šířek pre-market range za **posledních 60 obchodních dní** (rolling, look-ahead-free, jen minulé dny). Regime-adaptivní, nepřebírá QQQ čísla.
- **Směr:** **MINIMUM** (Pinede: větší range → větší následný pohyb; malé „mrtvé" range = chop). Volitelně horní strop otestuju zvlášť, pokud dá smysl.
- **Grid úrovně:** P ∈ {off, 50, 75}.
- *Pozn.: NEnormalizuju na ATR přímo (to dělá filtr 4), aby filtry nebyly kolineární — range percentil měří dnešní open vs vlastní historii, ATR filtr měří celkový režim.*

### 3. Relative volume filter — **same-time-of-day baseline** (návrh)
- **Definice:** `RVOL` = objem pre-market svíčky (9:15–9:30) / průměr objemu **téže 9:15–9:30 svíčky za posledních 20 dní** (look-ahead-free). Same-window baseline kontroluje intradenní objemovou sezónnost.
- **Filtr:** trade jen když `RVOL ≥ r`. Vyšší RVOL = víc participace = „reálnější" breakout.
- **Grid úrovně:** r ∈ {off, 1.2, 1.5}.

### 4. ATR filter — **denní ATR(14), FILTR PRO volatilitu (min)** (návrh, směr explicitní)
- **Definice:** `ATR%` = denní ATR(14) / close, jako percentil za posledních 60 dní (rolling). Denní (ne 15-min) — měří **režim**, ne mikrostrukturu.
- **Směr:** **PRO vyšší volatilitu** (trade jen když ATR% ≥ práh). Breakout potřebuje pohyb; nízko-vol dny chopují. — *Toto je explicitní volba; opačná (proti extrémům, horní strop) je taky legitimní. Default = min-práh; pokud grid ukáže, že extrémní-vol dny škodí, otestuju i horní strop jako druhou variantu.*
- **Grid úrovně:** percentil ∈ {off, 50}.
- *Pozor na možnou redundanci s range filtrem (oba selektují „velké dny") — proto ATR jako denní režim vs range jako dnešní-vs-vlastní-historie; marginální efekty otestuju i samostatně.*

### 5. Fill timing — **open NÁSLEDUJÍCÍ 1-min svíčky** (návrh)
- Signál: 1-min **close** venku z range (>high long, <low short), první za den, od 9:31 (první 1-min bar po 9:30).
- Vstup: **open další 1-min svíčky** (look-ahead-free, konzistentní s Projektem 4 a zbytkem výzkumu).
- SL/TP aktivní od vstupu, kontrola na 1-min high/low; **SL-first** při svíčce co protne obě (konzervativní).
- **SL = opačná strana range** (long → range_low; short → range_high). **TP = entry + dir × |entry − SL|** (1:1).
- **Max 1 obchod/den** (první breakout), **EOD flat 16:00**, RTH výstup. *Bez pozdního entry cutoffu (první breakout stejně padne brzy ráno); volitelně můžu přidat „jen do 11:00", pokud chceš.*

### 6. News filtr — **10:00 filtr obsoletní; default OFF, volitelně skip-NFP** (návrh)
- Projekt 4 měl „žádný trade při news v 10:00+". Tady **vstupy padnou ~9:31–9:35**, tedy **dávno před 10:00** → 10:00 filtr je pro 4b prakticky irelevantní (obchod už běží/skončil).
- Relevantní shock je teď **8:30 ET releasy** (NFP, CPI, PPI, retail sales, GDP), které **deformují samotnou 9:15–9:30 range** a časnou seanci. Kompletní 8:30 kalendář ale (a) nejde levně deterministicky postavit (CPI/PPI/retail mají nepravidelná data), (b) živé kalendáře jsou blokované síťovou politikou (ověřeno v Projektu 4).
- **Návrh:** news filtr **default OFF** (default = obsoletní 10:00 nedává smysl, plný 8:30 nejde levně). **Volitelná jedna sensitivity: „skip NFP dny"** = první pátek v měsíci (čistě deterministické, jediný největší 8:30 pre-open shock). Když base strategie ukáže náznak, teprv pak řešit širší 8:30 filtr.

---

## 7. Náklady, sizing, metriky (konzistentní se zbytkem výzkumu)
- **Costs:** round-turn **0,4 bps opt / 1,2 bps cons**, per obchod. Verdikt dle **net_cons**.
- **Metrika:** primárně **net R na obchod** (R = |entry − SL|, sizing-independent) + **hit rate vs 50 % breakeven** (Wilson CI) + obchodů/den + per-year stabilita. Equity/CAGR/Sharpe/MDD z NAV série pro finální kandidáty (1 % risk sizing, cap ≤ 1×).
- **Plán běhů:** (a) baseline bez filtrů; (b) každý filtr **samostatně** (marginální efekt); (c) malý kombinovaný grid (range × RVOL × ATR, ~3×3×2 = 18 kombinací) s **D2-style island checkem**. Vše NQ, IS.

## 8. Backtesting disciplína
- **IS:** do 2025-09-30 (stejná hranice).
- **OOS 2025-10-01 → 2026-07-11: ROZHODNUTÍ ODLOŽENO — NESPOTŘEBOVÁNO.** Už 2× použité (2b Fáze E, Projekt 3 R3), navíc blízká breakout/momentum rodina → laťka pro další použití vysoká. Nerozhoduje se teď; jen pokud se najde konkrétní robustní kandidát, řeší se gated ceremonií zvlášť.

## 9. Výstup
Sekce **„Varianta 4b"** v `PLAYBOOK_orb.md`: zamrazené předpoklady, IS metriky (CAGR, Sharpe, MDD, hit ratio, obchodů/den), grid/heatmapa přes filtry, „OOS odloženo — nespotřebováno".

---

## ✅ ČEKÁ NA POTVRZENÍ
Potvrď/oprav body 1–6 (hlavně: **bod 4 směr ATR filtru = PRO volatilitu?**, **bod 6 news default OFF + volitelně skip-NFP?**, a percentilové/threshold hodnoty v 2–4). Pak píšu kód.
