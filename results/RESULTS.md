# RESULTS — S&P 500 / ES kvantitativní výzkum (QuantConnect / LEAN)

Průběžný append-only log všech testů. Nový výsledek se vždy **přidává** jako nový
řádek, soubor se nikdy nepřepisuje od začátku.

**Režim spouštění:** `lean cloud backtest` jako výpočetní engine (jen `History()`
+ statistika + log, žádné objednávky/slippage/marže před Fází E).

**Globální nastavení:**
- In-sample okno: **2021-01-01 → 2025-09-30**
- OOS okno (rezervováno, jen Fáze E): **2025-10-01 → 2026-07-11** (~9,5 měsíce)
- Statistika: Wilson score 95% CI u každého win rate; Fisher exact pro 2 skupiny;
  n < 30 jen orientační.

Základní sada sloupců (napříč fázemi): `fáze/sekce | proměnná/test |
podskupina/kombinace | n | win rate | 95% CI (Wilson) | Δ vs. baseline |
p-hodnota (Fisher) | poznámka`.

---

## FÁZE 0 — Baseline statistika

**Test:** podíl dní, kdy close první 15min RTH svíčky (9:30–9:45 ET) leží uvnitř
vs. mimo kompletní 7denní High/Low pásmo předchozích 7 obchodních dnů (bez
dnešního dne). Pásmo = RTH-only (9:30–16:00) H/L u obou instrumentů (kontrolované
srovnání). Referenční hodnota z dosavadního výzkumu (SPY): **~81,53 % inside**.

| fáze/sekce | instrument | test | n | inside % (win rate) | 95% CI (Wilson) | outside % | Δ vs. ref 81,53 % | poznámka |
|---|---|---|---|---|---|---|---|---|
| 0 | SPY | close 1. 15min svíčky uvnitř 7d pásma | 1184 | **81,67 %** | [79,37 %, 83,77 %] | 18,33 % | +0,14 pp | ✅ potvrzuje referenci; bars_seen=463 050 (≈390/den, plné RTH) |
| 0 | ES | close 1. 15min svíčky uvnitř 7d pásma (RTH-only band) | 1217 | **82,42 %** | [80,18 %, 84,45 %] | 17,58 % | +0,89 pp | Fisher SPY vs ES p=0,67 → **žádný signif. rozdíl**; bars_seen=541 995 |

**Backtest:** projekt 34054490 „research/phase0_setup", backtestId `84de1a1bc4e6035d287fa957bfdca327`, in-sample 2021-01-01→2025-09-30. Kanál výsledků: runtime statistics (přes API). Wilson CI + Fisher spočítány lokálně.

**Zjištění Fáze 0:**
1. SPY replikace ~81,53 % **potvrzena** (81,67 %, CI [79,37 %, 83,77 %]).
2. ES (82,42 %) je statisticky **nerozlišitelné** od SPY (Fisher p=0,67) — při RTH-only definici pásma overnight/Globex charakter ranního otevření vůči 7d pásmu **nemění**.
3. ⚠️ **K prošetření před Fází A/B5:** ES `bars_seen`≈542k ⇒ ~445 barů/den, což je jen o málo víc než RTH (~390). Očekával bych u 24h ES násobně víc → nutno ověřit pokrytí **overnight** minutových dat kontinuálního kontraktu (RTH-závislá statistika Fáze 0 tím ale zasažená NENÍ). **VYŘEŠENO ve Fázi A:** default futures session je jen 9:30–17:00; s `extended_market_hours=True` `bars_seen` skočilo na **1 683 585** (~1380/den) → overnight/Globex data OK.

**Per-year rozpad (stabilita napříč roky):** SPY inside% 2021–2025 = 80,8 / 82,1 / 80,8 / 83,3 / 81,2 %; ES = 81,3 / 80,6 / 83,7 / 84,6 / 81,8 %. Baseline je napříč roky stabilní.

---

## FÁZE A — Sdílené datasety (extrakce)

**Kanál:** chart série (8 sérií, kategoriální zabalené do 1 int), rekonstrukce lokálně → `data/cache/`. Projekt 34056893, 2 běhy (SPY, ES). In-sample 2021-01-01→2025-09-30.

**Počty řádků (po warmup 14–15 dní na ATR14+POC):**

| dataset | instrument | rows | long | short | soubor |
|---|---|---|---|---|---|
| A1 breakout | SPY | 215 | 156 | 59 | `data/cache/a1_spy.csv` |
| A1 breakout | ES | 205 | 144 | 61 | `data/cache/a1_es.csv` |
| A2 range-bound | SPY | 953 | — | — | `data/cache/a2_spy.csv` |
| A2 range-bound | ES | 968 | — | — | `data/cache/a2_es.csv` |
| A1 combined | oba | 420 | 300 | 120 | `data/cache/a1_all.csv` |
| A2 combined | oba | 1921 | — | — | `data/cache/a2_all.csv` |
| A3 kalendář | — | 111 (44 FOMC + 67 NFP) | — | — | `data/cache/a3_calendar.csv` |

**A1 sloupce:** instrument, direction(±1), inside_day, b5_origin(2=overnight/gap-driven,1=RTH-fresh), rev10/20/30/40 (2=win/1=tie/0=loss), dist_atr, vol_ratio, prevday_body, poc_dist_atr, on_ret_pct. **A2 sloupce:** realized_range_atr, rth_ret_pct, on_ret_pct.

**Naivní mean-reversion grid (vstup 9:45 proti směru breakoutu, symetrická ±X-bodová bariéra, exit 16:00):**

| instrument | práh | n | raw win rate | 95% CI (Wilson) | excl-tie | ties |
|---|---|---|---|---|---|---|
| SPY | 10 ES-pt ($1) | 215 | 51,63 % | [44,98 %, 58,22 %] | 52,86 % | 5 |
| SPY | 20 ES-pt ($2) | 215 | 44,65 % | [38,16 %, 51,33 %] | 55,17 % | 41 |
| SPY | 30 ES-pt ($3) | 215 | 31,63 % | [25,78 %, 38,12 %] | 57,63 % | 97 |
| SPY | 40 ES-pt ($4) | 215 | 23,26 % | [18,11 %, 29,34 %] | 62,50 % | 135 |
| ES | 10 pt | 205 | 49,76 % | [42,98 %, 56,54 %] | 50,25 % | 2 |
| ES | 20 pt | 205 | 44,88 % | [38,23 %, 51,72 %] | 51,98 % | 28 |
| ES | 30 pt | 205 | 35,12 % | [28,92 %, 41,88 %] | 53,73 % | 71 |
| ES | 40 pt | 205 | 24,88 % | [19,46 %, 31,22 %] | 57,95 % | 117 |

**Zjištění Fáze A:**
1. ✅ Extrakce funguje, counts sedí na Fázi 0.
2. ✅ ES overnight data potvrzena (extended hours).
3. ⚠️ **Baseline 52,21 % je citlivá na definici** naivní reverze. Nejlíp sedí na malý práh: SPY 10pt raw=51,63 %, ES 20pt excl-tie=51,98 %. Symetrická 30bodová bariéra generuje hodně „ties" (cena se do 16:00 netrefí ani jedním směrem) → raw padá. **Nutno potvrdit přesnou definici** (bariéra vs. exit-na-close, jak počítat ties, který instrument) jako outcome proměnnou pro Fázi B.


---

## FAZE B - Breakout promenne (jednotlive, A1)

Primarni instrument **ES** (obchodovany), SPY = korelovany robustness check (NEpoolovano - stejny den ~ stejna udalost). Testy pro 3 outcome definice (sensitivity). `*` = Fisher p<0,05 vs. zbytek.

**Overall baselines (breakout):**

- ES: rev30_excl=53.73% | rev30_raw=35.12% | rev10_raw=49.76%
- SPY: rev30_excl=57.63% | rev30_raw=31.63% | rev10_raw=51.63%

**ES | outcome = rev30_excl (podmineno na +-30 pohyb; reverze vs. pokracovani):**

| promenna | bucket | n | win rate | 95% CI (Wilson) | delta vs base | Fisher p |
|---|---|---|---|---|---|---|
| B1_direction | long | 79 | 55.7% | [44.73, 66.13] | +1.96pp | 0.6019 |
| B1_direction | short | 55 | 50.91% | [38.08, 63.62] | -2.82pp | 0.6019 |
| B2_dist_atr | small | 38 | 52.63% | [37.26, 67.52] | -1.1pp | 1.0 |
| B2_dist_atr | med | 46 | 54.35% | [40.18, 67.85] | +0.62pp | 1.0 |
| B2_dist_atr | large | 50 | 54.0% | [40.4, 67.03] | +0.27pp | 1.0 |
| B3_vol_ratio | vol>1.0 | 89 | 57.3% | [46.94, 67.07] | +3.57pp | 0.2742 |
| B3_vol_ratio | vol<=1.0 | 45 | 46.67% | [32.94, 60.92] | -7.06pp | 0.2742 |
| B5_origin | overnight/gap(2) | 106 | 50.94% | [41.56, 60.26] | -2.79pp | 0.2868 |
| B5_origin | rth_fresh(1) | 28 | 64.29% | [45.83, 79.29] | +10.55pp | 0.2868 [!]n<30 |
| B6_poc_dist_atr | poc_low | 59 | 49.15% | [36.84, 61.56] | -4.58pp | 0.3855 |
| B6_poc_dist_atr | poc_mid | 37 | 59.46% | [43.49, 73.65] | +5.73pp | 0.4438 |
| B6_poc_dist_atr | poc_high | 38 | 55.26% | [39.71, 69.85] | +1.53pp | 0.8498 |
| B8_prevday_body | body_neg | 59 | 50.85% | [38.44, 63.16] | -2.88pp | 0.6027 |
| B8_prevday_body | body_mid | 39 | 51.28% | [36.2, 66.13] | -2.45pp | 0.8489 |
| B8_prevday_body | body_pos | 36 | 61.11% | [44.86, 75.22] | +7.38pp | 0.3332 |
| B8_inside_day | inside_day | 9 | 66.67% | [35.42, 87.94] | +12.94pp | 0.5042 [!]n<30 |
| B8_inside_day | not_inside | 125 | 52.8% | [44.1, 61.34] | -0.93pp | 0.5042 |
| B7_calendar | event | 12 | 41.67% | [19.33, 68.05] | -12.06pp | 0.5458 [!]n<30 |
| B7_calendar | non_event | 122 | 54.92% | [46.07, 63.46] | +1.19pp | 0.5458 |

**Klicove signifikantni efekty - jen u `rev30_raw` (tie=loss), konzistentni ES+SPY:**

| instrument | promenna | bucket | n | win rate | delta vs base | Fisher p |
|---|---|---|---|---|---|---|
| ES | B1_direction | long | 144 | 30.56% | -4.57pp | 0.0389* |
| ES | B1_direction | short | 61 | 45.9% | +10.78pp | 0.0389* |
| ES | B3_vol_ratio | vol>1.0 | 110 | 46.36% | +11.24pp | 0.0004* |
| ES | B3_vol_ratio | vol<=1.0 | 95 | 22.11% | -13.02pp | 0.0004* |
| SPY | B1_direction | long | 156 | 26.28% | -5.35pp | 0.0084* |
| SPY | B1_direction | short | 59 | 45.76% | +14.13pp | 0.0084* |
| SPY | B3_vol_ratio | vol>1.0 | 110 | 40.91% | +9.28pp | 0.0033* |
| SPY | B3_vol_ratio | vol<=1.0 | 105 | 21.9% | -9.72pp | 0.0033* |

**Zjisteni Faze B:**
1. Outcome **rev30_excl** (reverze vs. pokracovani, podmineno na pohyb): ZADNA jednotliva promenna neni signifikantni (vsechna p>0,27) - single-variable reverzni edge tu neni.
2. Outcome **rev30_raw** (tie=loss): **objem>1,0** (p=0,0004/0,0033) a **short breakout** (p=0,039/0,008) silne a konzistentni ES+SPY - ale predikuji spis JESTLI vubec dojde k +-30 pohybu (volatilita), ne smer reverze.
3. Ostatni signif. vysledky (rev10 inside_day n=12, B5 origin, body_mid) jsou bud male n nebo nekonzistentni -> pravdepodobne sum.
4. **Multiple-testing caveat:** ~114 testu -> ~5-6 falesnych p<0,05 ocekavano. Prezivaji jen vol_ratio (velmi silne) a smer.

_Detailni tabulka vsech kombinaci: `results/phaseB_raw.csv`._


---

## FAZE C - Range-bound promenne (A2 / in-algo ES)

ES, range-bound dny (996), in-sample. C1/C2/C3 in-algo (agregaty pres log), C4 lokalne z A2.

### C1 - VWAP mean-reversion (HLAVNI SETUP)

Event = close protne VWAP +-k*std (od 10:00). Win = navrat k VWAP pred 16:00 (bez stopu; VWAP je pohyblivy cil). TTR = time-to-revert.

| band | strana | n | win rate (navrat k VWAP) | 95% CI (Wilson) | median TTR | IQR |
|---|---|---|---|---|---|---|
| +-1 | upper | 1944 | **76.13%** | [74.19, 77.97] | 28 min | [8,68] |
| +-1 | lower | 1878 | **81.9%** | [80.09, 83.57] | 22 min | [8,62] |
| +-2 | upper | 967 | **65.77%** | [62.72, 68.69] | 42 min | [18,98] |
| +-2 | lower | 946 | **73.78%** | [70.89, 76.49] | 48 min | [18,98] |

Srovnani (Fisher): upper vs lower p<0,001 (obe pasma); +-1 vs +-2 upper p=5,2e-09.

### C2 - Initial Balance extension

IB = high/low 9:30-10:30. Po 10:30 prvni pruraz.

- % dni s IB extension: **99,6 %** (992/996) - trivialni (cena skoro vzdy prekroci prvni hodinu).
- Smer prvni extension: up=521 / down=471 (vyvazene). Prumerna prvni extension = **0,371 ATR**.
- Trend-following vstup na 1. IB pruraz (TP=SL=1x ATR, exit 16:00): win=56 loss=50 **tie=886** (rozliseno jen 106/992). Z rozlisenych 52,8 % - coin flip. **Zadny trend edge** (range-bound dny netrenduji, 1 ATR se casto netrefi).

### C3 - Intradenni sezonnost (avg 30min range, ES body)

| blok | 0930 | 1000 | 1030 | 1100 | 1130 | 1200 | 1230 | 1300 | 1330 | 1400 | 1430 | 1500 | 1530 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| avg range | 3.77 | 3.67 | 3.13 | 2.79 | 2.56 | 2.38 | **2.25** | 2.41 | 2.33 | 2.65 | 2.61 | 2.70 | 3.14 |

**POTVRZENO:** U-tvar - vysoka vol na open (3,77), midday minimum 12:00-13:30 (nejniz 12:30=2,25), narust po 14:00 (2,65+) a do close (15:30=3,14).

### C4 - Overnight drift jako kontext (lokalne z A2)

- Pearson r(|overnight%|, RTH range/ATR): ES 0,103 (p=1,3e-03), SPY 0,101 (p=1,8e-03). Spearman rho ES 0,137 / SPY 0,128.
- Terciny |overnight|: RTH range/ATR small->large: ES 0,90->1,00, SPY 0,87->0,97. Mann-Whitney small vs large p<1e-4.
- **Slaby ale signifikantni**: vetsi overnight pohyb -> mirne vetsi RTH range (r~0,1 => ~1% variance). Jako filtr marginalni.

**Zjisteni Faze C:**
1. **C1 VWAP reverze je silny edge**: +-1 pasmo -> navrat k VWAP 76-82 %, median ~22-28 min, n~1900/strana. To je jadro strategie.
2. **Asymetrie**: dolni pasmo (dipy) reverduje vic nez horni (76 vs 82 % na +-1; 66 vs 74 % na +-2) - buy-the-dip bias v uptrendu 2021-2025.
3. **+-1 > +-2**: jednou na +-2 vyssi sance na pokracovani/trend (66-74 % vs 76-82 %).
4. C2 IB trend-following bez edge (range-bound dny netrenduji). C3 midday lull potvrzen. C4 overnight kontext slaby.
5. **Caveat C1**: win = dosazeni VWAP do close BEZ stopu; realny trade se stopem bude mit nizsi win rate. Eventy v ramci dne jsou korelovane.

_Log: phaseC_log.txt; C4: results/phaseC_c4.csv._


---

## FAZE D - Funnel na C1 VWAP reverzi (ES, range-bound)

Dle rozhodnuti: breakout strana (B) ZAHOZENA z funnelu. Zaklad = C1 +-1 VWAP reverze, upper/lower zvlast, +C3 timing overlay, +C4 overnight kontext. 5735 eventu, 996 dni.

### Level 1 - C1 base (+-1)

| strana | n | win rate | 95% CI (Wilson) | pozn |
|---|---|---|---|---|
| upper | 1944 | 76,13 % | [74,19, 77,97] | |
| lower | 1878 | 81,90 % | [80,09, 83,57] | upper vs lower Fisher p<0,0001 |

### Level 2 - +C3 timing (regime startu eventu)

| strana | regime | n | win rate | 95% CI | Δ vs base | Fisher p vs rest |
|---|---|---|---|---|---|---|
| upper | morning(10-12) | 1316 | **85.56 %** | [83.56, 87.36] | +9.4 pp | <0.0001 |
| upper | lull(12-14) | 301 | **68.77 %** | [63.33, 73.74] | -7.4 pp | 0.0015 |
| upper | afternoon(14-16) | 316 | **46.52 %** | [41.09, 52.03] | -29.6 pp | <0.0001 |
| lower | morning(10-12) | 1245 | **93.17 %** | [91.63, 94.45] | +11.3 pp | <0.0001 |
| lower | lull(12-14) | 338 | **73.37 %** | [68.42, 77.8] | -8.5 pp | <0.0001 |
| lower | afternoon(14-16) | 288 | **45.14 %** | [39.49, 50.91] | -36.8 pp | <0.0001 |

**Per-block (+-1) win rate:**
- upper: blk1(10:00) 88% → blk8(13:30) 66% → blk12(15:30) 29% (monotonni pokles, n810→85)
- lower: blk1 94% → blk8 71% → blk12 21%

### ⚠️ KLICOVY CONFOUND (time-to-close)
Win = navrat k VWAP DO 16:00. Event v 10:00 ma ~6h na navrat, event v 15:30 jen 30 min. Monotonni per-block pokles => timing efekt je ZCASTI artefakt definice, ne cista lepsi reverze rano. Median TTR ~22-28 min => eventy startujici do ~14:30 (blk<=9, >=90 min do close) jsou relativne fair; blk 10-12 (14:30+) jsou casove utnute. I v ramci fair blocku 1-9 je ale realny gradient rano>lull (rano nizsi vol + korekce opening imbalances). **Nutno reseit ve Fazi E time-boxovanou reverzi (revert do X min) nebo realistickym stopem.**

### Level 3 - +C4 overnight tercina (v ramci regime)

Prehled Δ vs regime base (vsechny bunky n>=82):
- Vetsina Δ jen ±1-3 pp v sumu => overnight NEPRIDAVA konzistentni hodnotu (potvrzuje ocekavani).
- Jediny naznak: lower/lull/on_large 61,96 % vs base 73,37 % (Δ-11,4 pp, n=92) a lower/lull/on_small 80,15 % (Δ+6,8 pp) => velky overnight moze zhorsit reverzi v midday lull; ale single-cell, multiple comparisons -> spis sum.

**Zjisteni Faze D (funnel):**
1. **Nejsilnejsi funnel: C1 +-1 reverze v RANNIM okne (10:00-12:00)** - lower 93,2 % (n1245), upper 85,6 % (n1316). Velke n, tesne CI.
2. **C3 timing je dominantni filtr**, ale zcasti confounded time-to-close (viz caveat). Realny gradient rano>lull>afternoon existuje i po kontrole, ale magnituda je nadhodnocena.
3. **C4 overnight nepridava** konzistentni hodnotu -> z finalni sady vypustit (nanejvys jako weak exclusion 'velky overnight' v lull).
4. **Asymetrie lower>upper** zachovana napric regimy.
5. n zustava zdrave (>280 na regime, >1000 na rannim okne) - zadna vetev pod 40.

**Kandidatni finalni setupy pro Fazi E (OOS):**
- **Setup L**: lower +-1 VWAP reverze, start 10:00-12:00, exit navrat k VWAP. IS win rate 93,2 % (n1245).
- **Setup U**: upper +-1 VWAP reverze, start 10:00-12:00. IS win rate 85,6 % (n1316).
- Caveat: IS win rate je BEZ stopu (navrat do close). Ve Fazi E nutne prepocitat s realistickym stopem (1-1.5x ATR) a time-boxem => ocekavany pokles win rate.

_Detail: results/phaseD_cells.csv, results/phaseD_funnel.txt._


---

## FAZE E — DESIGN (IN-SAMPLE, stop/time-box/naklady/expectancy)

In-sample sim (2021-01-01→2025-09-30), ES, C1 +-1 VWAP reverze v rannim okne 10:00-12:00. 2561 eventu. avg denni ATR14=68,9 b; **avg zisk reverze (entry->VWAP)=3,09 b**. NENI OOS.

### #1 Stop-loss sensitivity (win rate, time-box=close)

| stop | upper wr (n=1316) | lower wr (n=1245) |
|---|---|---|
| 0,5x ATR | 85,0 % | 88,0 % |
| 1,0x ATR | 88,1 % | 94,1 % |
| 1,5x ATR | 88,3 % | 95,0 % |
| 2,0x ATR | 88,3 % | 95,0 % |
| no-stop | 88,3 % | 95,0 % |

**Pozor:** ATR je SPATNE meritko pro stop tohoto setupu. Edge=~3 b, ale 1xATR=~69 b. Stopy >=1x ATR se skoro nikdy netrefi (win rate se nemeni), 0,5x ATR (~34 b) urizne jen par procent. Stop v ATR je ~10-20x sirsi nez zachyceny pohyb.

### #2 Time-box (% vsech +-1 eventu zreverzovanych do T, cely den)

| strana | <=60m | <=90m | <=120m | close |
|---|---|---|---|---|
| upper | 55,1 % | 62,4 % | 66,8 % | 76,1 % |
| lower | 61,0 % | 67,8 % | 72,2 % | 81,9 % |

### #3 Naklady ES/MES (odhad, rozsah v BODECH round-turn)

- ES ($50/bod): komise $2,5-5 + slippage 0,5-2 ticky => **~0,18 b (optim) az 0,60 b (konzerv)**.
- MES ($5/bod): komise $1-1,5 + slippage 1-2 ticky => **~0,45-0,80 b** (v bodech DRAZ nez ES).

### EXPECTANCY (body/trade) — combined upper+lower, morning

| kombinace | n | win rate | gross | net konzerv (-0,6) | net optim (-0,18) |
|---|---|---|---|---|---|
| stop 1x, tbox 90m | 2561 | 78,4 % | **-0,22 b** | -0,82 b | -0,40 b |
| stop 1x, tbox close | 2561 | 91,0 % | -0,73 b | -1,33 b | -0,91 b |
| no-stop, tbox 90m | 2561 | 78,4 % | -0,20 b | -0,80 b | -0,38 b |
| lower only, tbox 60-90m (nejlepsi bunka) | 1245 | ~90 % | -0,02 b | -0,62 b | -0,20 b |

### ⛔ VERDIKT FAZE E DESIGN

**Setup C1 +-1 VWAP mean-reversion ma NULOVOU az ZAPORNOU gross expectancy in-sample, ZAPORNOU po nakladech, napric CELYM gridem stop x time-box.**
- Pricina: prumerny zisk reverze +3 b, ale nezreverzovane dny (5-15 %) = zavreni prumerne -35 b. Vysoky win rate (85-95 %) je ILUZE ziskovosti — vzacne velke ztraty (trendove dny) prebiji spoustu malych zisku.
- Kratsi time-box (60-90m) urizne trendovy ocas a zmirni ztratu (close->90m: -0,73->-0,22 b), ale nezachrani.
- ES/kontrakt konzerv: ~-41 $/trade; MES ~-1 az -4 $/trade. Zadna varianta parametru neni kladna.
- **Konzervativni vs agresivni naklady:** rozdil ~0,42 b/trade (ES), ale obe varianty jsou zaporne — vysledek NENI citlivy na predpoklad nakladu, je zaporny tak jako tak.

**Dusledek pro OOS:** spoustet gated OOS na setupu se zapornou IS expectancy nema smysl (neni co validovat). Doporuceni: bud (a) prijmout jako dokumentovany NEGATIVNI vysledek, nebo (b) reformulovat setup in-sample (napr. +-2 entry pro vetsi cil, fixni R:R misto pohybliveho VWAP, trend/volatility filtr na vyrazeni trendovych dni) a teprve pak zvazit OOS. **OOS okno zustava nedotcene.**

_Log: phaseE_design_log.txt; projekt 34069923._


---

## FAZE E — REFORMULACE (IN-SAMPLE): fixni bariery + trend filtr

Test: fade na +-1 a +-2 VWAP pasmu (morning), FIXNI symetricke bariery B bodu misto pohybliveho VWAP cile. Symetricka bariera => win rate primo meri edge nad 50 %. Projekt 34070394. entries: b1=2561, b2=1278.

### First-passage win rate (symetricka bariera, no filter)

| entry/side | B(body) rozsah | win rate (excl timeout) |
|---|---|---|
| ±1 upper | 4–15 | 48,2–50,3 % |
| ±1 lower | 4–15 | 48,1–52,6 % |
| ±2 upper | 4–15 | 45,9–48,6 % |
| ±2 lower | 4–15 | 48,4–51,2 % |

**Win rate ~48–52 % napric VSIM = hod mincí.** Zadny smerovy edge na VWAP +-1 ani +-2 entry.
- Nejlepsi bunka: ±1 lower B=15, wr 52,6 %, Wilson CI [49,7 %, 55,5 %] => **zahrnuje 50 %, NEsignifikantni** (navic nejlepsi z 24+ bunek -> multiple testing -> sum).
- **Trend filtr (VWAP sklon) NEPOMAHA**: vylouceni with-trend nechava win rate ~48–51 %. Counter-trend only zabije vzorek (n<30).
- Expectancy po nakladech (0,4 b): zaporna vsude krome sumove ±1 lower B15.

### ⛔⛔ FINALNI VERDIKT VYZKUMU

**Ani jeden testovany setup nema obchodovatelny edge na ES/SPY v tomto frameworku (in-sample 2021–2025):**
1. **Breakout mean-reversion (Faze B):** zadna promenna nepredikuje SMER reverze (rev30_excl p>0,27). To, co bylo signif. (objem, smer), predikuje jen volatilitu.
2. **VWAP mean-reversion (Faze C/D/E):** vysoky 'reversion' win rate (76–93 %) byl ARTEFAKT asymetrickeho cile (maly pohyblivy VWAP cil). Se symetrickou bariérou win rate = ~50 % (coin flip). Fixni bariery, ±2 entry, trend filtr ani time-box to nezachrani. Gross i net expectancy zaporna/nulova.
3. **Time-of-day 'edge' (Faze D):** z velke casti confounded time-to-close, ne cisty signal.

**Zaver:** Naivni mean-reversion na 7d pasmu / VWAP pasmu na S&P futures NEMA v tomto obdobi kladnou expectancy po realistickych nakladech. Vysoke win rate byly klamave (asymetrie zisk/ztrata nebo pohyblivy cil). **Doporuceni: NEspoustet gated OOS** (neni pozitivni IS setup k validaci). OOS okno zustava NEDOTCENE. Hodnota vyzkumu = poctive vyvraceni domnele strategie pred nasazenim realneho kapitalu.

_Log: phaseE_reform_log.txt._


---
---

# PROJEKT 2 — Leveraged/Inverse ETF EOD rebalancing flow → intraday momentum

**Hypotéza:** mechanický end-of-day rebalancing flow 2x/3x lev/inverse ETF zesiluje pohyb S&P v posledních 30–60 min RTH ve směru dosavadního denního pohybu; a efekt SÍLÍ v čase úměrně růstu AUM téhle skupiny fondů.

**Prostředí:** stejné (QC Free hybrid). **In-sample:** 2021-01-01→2025-09-30. **OOS (rezervováno):** 2025-10-01→2026-07-11.

## FÁZE 0 — dostupnost dat

| položka | stav |
|---|---|
| Minutová data SPY / ES | ✅ přes cloud backtest (jako projekt 1) |
| Minutová data 10 lev/inverse ETF (TQQQ,SPXL,SSO,SQQQ,SPXS,SDS,UPRO,SPXU,QLD,QID) | ✅ dostupná |
| Fundamental pole SharesOutstanding / MarketCap | ✅ existují v datasetu |
| **SharesOutstanding/MarketCap NAPLNĚNÉ pro ETF** | ❌ **0/10 populated** (Morningstar pokrývá firmy, ne fondy) |

**Důsledek:** kontinuální AUM proxy z QC **není dostupný**. Dle pravidla „nevymýšlet aproximaci" → fallback na **subperiod design po kalendářních letech** (konzervativní, bez fabrikace přesnosti). Test „efekt sílí v čase" se dělá porovnáním win rate mezi lety (Fisher). ETF data do datasetu nepotřebujeme — momentum test je čistě z SPY/ES intraday returnů; velikost flow proxujeme velikostí denního pohybu (B5).

**Milestone kontext (jen volný, NE fabrikovaná řada):** veřejně známý řádový růst skupiny lev/inverse ETF (~desítky mld 2021–22 → ~100+ mld 2023–24 → ~150–200 mld 2025–26). Primární subperiod = kalendářní roky (nejméně nafouknutelné); milníky jen jako interpretační rámec.

## FÁZE A — EOD momentum dataset

Cutoffy OPRAVENÉ dle hypotézy (posl. 30-60 min): K=60 → 15:00, K=30 → 15:30. Predictor/outcome disjunktní. In-sample. Projekt 34107242, 2 běhy.

| dataset | rows | agree60 overall | agree30 overall | soubor |
|---|---|---|---|---|
| ES | 1173 | 51,8 % | 49,2 % | `data/cache/eod_es.csv` |
| SPY | 1168 | 53,3 % | 50,9 % | `data/cache/eod_spy.csv` |

Sloupce: r_pre60/r_last60/r_pre30/r_last30 (bps), atr_pct, year, agree60/agree30.

**⚠️ Preliminární per-year agree60 (POZOR — směřuje PROTI hypotéze):**
- ES: 2021=51,9 / 2022=**57,6** / 2023=53,0 / 2024=47,4 / 2025=48,4
- SPY: 2021=53,8 / 2022=**58,4** / 2023=54,0 / 2024=49,8 / 2025=49,2

Efekt je NEJSILNĚJŠÍ v 2022 (vysoká vol, bear market) a KLESÁ do 2024-25 pod 50 %. To je **opak** hypotézy „sílí s růstem AUM". Konzistentní spíš s „momentum silnější ve vysokovolatilních / velký-pohyb obdobích" (B5), ne s růstem AUM v čase (C). Formální test ve Fázi B/C.

## FÁZE B — základní test efektu (celé in-sample, lokální analýza)

Vstup ve směru r_pre, drž do close. Náklady ES round-turn 0,4 (opt) / 1,2 (cons) bps.

| test | agree | 95% CI | vs 50% p | R² | expectancy | net_opt | net_cons |
|---|---|---|---|---|---|---|---|
| ES K=60 | 51,8 % | [49,0, 54,7] | 0,22 ns | 0,87 % | +1,90 bps | +1,50 | +0,70 |
| ES K=30 | 49,2 % | [46,3, 52,0] | 0,60 ns | 0,17 % | +0,16 | −0,24 | −1,04 |
| SPY K=60 | **53,3 %** | [50,4, 56,1] | **0,028 SIGNIF** | **1,77 %** | +2,29 bps | +1,89 | +1,09 |
| SPY K=30 | 50,9 % | [48,0, 53,7] | 0,58 ns | 0,95 % | +0,57 | +0,17 | −0,63 |

**B3 sanity:** SPY K=60 R²=1,77 % **sedí do akademického pásma 1,6–2,6 %** (Gao et al) → metoda validní; slabý intraday momentum efekt v regresním smyslu existuje.

**B5 conditioning na velikost pohybu (agree60):**

| bucket | ES | SPY |
|---|---|---|
| small | 47,6 % | 48,5 % |
| med | 55,0 % | 56,0 % |
| large | 52,9 % | 55,3 % |
| large vs small Fisher p | 0,15 ns | 0,062 (hraniční) |

Velký/střední pohyb → vyšší shoda (~55 %), malý pohyb → ~48 % (mírná reverze). Hraničně podporuje flow mechanismus.

**Zjištění Fáze B:**
1. **Slabý statický last-hour (K=60) momentum efekt existuje** (SPY 53,3 % signif., R² 1,77 % dle literatury), **marginálně kladná expectancy i po nákladech** (+0,7 až +1,9 bps) — na rozdíl od minulého projektu tu fixní exit na close nedělá asymetrii zisk/ztráta (avg_win≈avg_loss≈24 bps).
2. **Jen K=60, ne K=30** (posl. půlhodina ~50 %, žádný efekt).
3. **⚠️ Kladná IS expectancy je ale průměr přes období — a je tažená ranějším obdobím** (2021–23, hlavně 2022). Vzhledem k per-year poklesu <50 % v 2024–25 je recentní expectancy pravděpodobně záporná. Formální temporální test = Fáze C.
4. **Jádro hypotézy (sílí s AUM v čase) preliminárně VYVRÁCENO** — efekt slábne, ne sílí.

## FÁZE C — časová nestabilita (JÁDRO hypotézy)

**C1 per-year agree60 + expectancy (net_cons = po konzerv. nákladech 1,2 bps):**

| rok | ES agree | ES exp | ES net_cons | SPY agree | SPY exp | avg ATR% |
|---|---|---|---|---|---|---|
| 2021 | 51,9 % | +2,67 | +1,47 | 53,8 % | +3,22 | ~1,05 % |
| **2022** | **57,6 %** | +4,02 | +2,82 | **58,4 %** | +4,19 | **~2,0 %** |
| 2023 | 53,0 % | +3,06 | +1,86 | 54,0 % | +3,10 | ~1,15 % |
| 2024 | 47,4 % | −1,49 | −2,69 | 49,8 % | −1,45 | ~1,0 % |
| 2025 | 48,4 % | +1,08 | −0,12 | 49,2 % | +2,49 | ~1,4 % |

**Early (2021–23) vs Late (2024–25):**
- ES: 54,2 % vs 47,8 %, **Fisher p=0,035 (signif. POKLES)**; expectancy +3,26 → −0,40 bps
- SPY: 55,4 % vs 49,5 %, Fisher p=0,052 (hraniční); expectancy +3,51 → +0,23 bps

**🎯 C2/C3 — rozhodující test H_AUM vs H_vol** (AUM proxy nedostupný → místo korelace s AUM korelace roční shody s časem a s volatilitou):

| | ES | SPY |
|---|---|---|
| corr(roční agree, čas/rok) — H_AUM predikuje **+** | **−0,67** | **−0,76** |
| corr(roční agree, roční ATR%) — H_vol predikuje **+** | **+0,72** | **+0,64** |

- **H_AUM (sílí s časem/AUM): VYVRÁCENO** — shoda s časem koreluje **NEGATIVNĚ** (−0,67/−0,76). Efekt SLÁBL, zatímco AUM rostla.
- **H_vol (silnější ve vysokovolatilním období): PODPOŘENO** — shoda koreluje **pozitivně s roční volatilitou** (+0,72/+0,64). 2022 (bear, ATR 2 %) = nejvyšší shoda; nízkovol 2024 = nejnižší.

**C3 vzorky:** 2024 n~250, 2025 n~186, late 24-25 n~437 — všechny >30, závěr o poklesu je důvěryhodný.

**Zjištění Fáze C:**
1. **Jádro hypotézy je falzifikováno.** Efekt neroste s růstem AUM — naopak v čase slábne (korelace s časem −0,7).
2. **Zdánlivý efekt je volatilitně řízený**, ne AUM-flow řízený: klasický intraday momentum silnější v high-vol režimech (+0,7 korelace s vol), ne příběh leveraged-ETF-flow.
3. **Tradeable expectancy** byla kladná 2021–23 (vč. high-vol 2022), ~nula/záporná v nízkovol 2024–25.
4. **Důsledek pro D/E:** premisa „zaměř finální setup na nejnovější období" (z promptu, podmíněná potvrzením sílení) **neplatí** — nejnovější období je NEJSLABŠÍ. OOS (2025–26) závisí na vol v OOS okně, ne na AUM.

## FÁZE D — neplatná (rozhodnutí: cesta A)

Prompt podmiňuje Fázi D potvrzením „efekt sílí". Fáze C to VYVRÁTILA (efekt slábne, je vol-driven). Zvolena **cesta A** = uzavřít jako falzifikaci + PLAYBOOK. Funnel na „nejnovější období" nedává smysl (nejnovější = nejslabší). OOS ponecháno GATED (nespuštěno).

## PROJEKT 2b — přeformulovaný test (signed × velikost flow mechanismu)

**Přeformulace:** Projekt 2 testoval AUM/čas izolovaně (přes agree60 rate a rok-index). Mechanismus ale predikuje **signed, velikostně-škálující** vztah `last60 ~ day_return_to_cutoff`. Kritérium: podpořeno = β>0 sig, přežije vol-kontrolu, ≥0 cost-adj expectancy v nějakém režimu.

**Definice (apples-to-apples s Projektem 2):** cutoff 15:00; r_pre60=9:30→15:00; r_last60=15:00→16:00 (bps). Náklady konzerv. 1,2 bps round-turn.

### Krok 1 (lokální, in-sample)

| test | SPY | ES |
|---|---|---|
| [3] signed β (last60~pre60) | β=+0,063 t=4,58 **p=5e-6** R²=1,77 % | β=+0,043 t=3,21 **p=0,001** R²=0,87 % |
| [5a] **vol-NORMalizovaná** β | β=+0,049 t=3,43 **p=6e-4** | β=+0,040 t=2,84 **p=0,005** | 
| [5c] β jen v hi-vol tercině | β=+0,080 **p=0,001** (lo/mid ns) | β=+0,056 **p=0,014** (lo/mid ns) |
| [5d] β jen ve large-|pre60| tercině | β=+0,069 **p=0,0003** (small/med ns) | β=+0,047 **p=0,006** |
| [6] β 2024–25 | **β=+0,110 p=1e-8 R²=6,5 %** | β=+0,071 p=0,0002 R²=3,2 % |

**Size-conditioned expectancy (net po nákladech 1,2 bps):**

| bucket |pre60| | SPY winrate / net_cons | ES winrate / net_cons |
|---|---|---|
| small (avg 12 bps) | 47,9 % / −0,77 | 47,3 % / −0,32 |
| med (42 bps) | 54,2 % / −0,30 | 53,5 % / −0,49 |
| **large (113 bps)** | **57,6 % / +4,34** | **54,7 % / +2,90** |
| large & 2021–23 | 58,8 % / +5,03 | 56,3 % / +4,02 |
| large & 2024–25 | 54,5 % / +2,65 | 50,9 % / +0,11 |

**Zjištění Krok 1 — PASS (proti Projektu 2):**
1. **Signed β>0 signifikantní a PŘEŽIJE vol-normalizaci** (5a: p<0,01 obojí) → není to jen vol-clustering. Skutečný směrový vztah.
2. **Efekt je koncentrovaný na velké pohyby / high-vol** (5c, 5d: β sig jen v hi bucketech) — **přesně jak flow predikuje** (flow ∝ r).
3. **Na large-move dnech kladná cost-adj expectancy** (SPY +4,34 bps, ES +2,90 bps), a to i recentně (SPY +2,65; ES +0,11 marginální).
4. **⚠️ Reversal Projektu 2:** size-weighted β dokonce ROSTE v čase (2021 0,02 → 2024–25 0,11), zatímco Projekt 2 viděl pokles agree60. Vysvětlení: agree60 (nevážený sign-count) ředí efekt spoustou malých no-flow dní; β (size-weighted) chytá právě big-flow dny. **To znovuotevírá AUM hypotézu v její SPRÁVNÉ (signed×size) formě.**
5. **Caveaty:** (a) mechanismus zatím NEODLIŠEN od obecného „intraday momentum silnější na velkých dnech" (literatura) — to rozliší až Krok 2 (AUM vážení); (b) β_2024-25 R²6,5 % může být tažené pár extrémními dny (2025 vol spikes) — fragilní; (c) large-move = ~1/3 dní, in-sample, theory-driven conditioning (ne cherry-pick, mechanismus to předpovídá).

### Krok 1b — flow-timing test (dekompozice poslední hodiny, large-move dny)

Flow predikuje koncentraci efektu BLÍŽ ke close (rebalance jede v posl. minutách / MOC).

| sub-okno | SPY β / t / net_exp | ES β / t / net_exp |
|---|---|---|
| A: 15:00→15:30 (early) | +0,044 / 4,00 / **+2,82** | +0,042 / 3,87 / **+2,67** |
| B: 15:30→16:00 (late, u close) | +0,033 / 2,84 / +0,35 | +0,013 / **1,15 ns** / −0,95 |

**Efekt je SILNĚJŠÍ dřív (15:00–15:30) a SLÁBNE ke close** (ES v posl. 30 min nesignifikantní). To je:
- **Proti** mechanickému flow „executuje se u close" (ten by měl ke close zesilovat).
- **Možná konzistentní** s tím, že trh flow ANTICIPUJE/front-runuje (pohyb se odehraje dřív, v očekávání známého EOD flow).
→ Nejednoznačné pro flow-specificitu; přímý arbitr je až Krok 2 (AUM vážení).


## FÁZE E — jednorázová OOS validace (Projekt 2b) — VÝSLEDEK

Frozen spec potvrzena uživatelem před během (phase_e_frozen_spec.md). Jediný běh, backtestId ab5b1bc1d2dea28bafacc60674b0ddab.

| fáze/test | podskupina | n | win rate | 95% CI (Wilson) | gross exp | net_cons | verdikt |
|---|---|---|---|---|---|---|---|
| E OOS large-move momentum | OOS 2025-10→2026-07 | 46 | 43,5 % | [30,2 %, 57,8 %] | −0,85 bps | **−2,05 bps** | **NEPODPOŘENO** (IS ref: 57,4 %, +4,30 net) |

Opačné znaménko vůči IS, jasně záporná net expectancy → předregistrované „Nepodpořeno". CI zahrnuje 50 % → selhání replikace, ne prokázaná reverze. **OOS okno tímto SPOTŘEBOVÁNO** (jediný povolený pohled proběhl; žádné další testy na tomto okně nejsou validní).

---
---

# PROJEKT 3 — VWAP Trend Trading (Zarattini/Aziz SSRN 4631351)

Nová signálová rodina: trend-following od VWAP. R1 replikace + R2 překlad SPY/ES.

## R1 — replikace (QQQ/TQQQ, 2018-01-02→2023-09-28, paper costs $0,0005/share, no slippage)

| metrika | QQQ moje | QQQ paper | TQQQ moje | TQQQ paper |
|---|---|---|---|---|
| total return | 611,6 % | 671 % | 1 484 % | 8 242 % |
| CAGR | 40,8 % | 43 % | 61,9 % | 116 % |
| vol ann. | 17,7 % | 18 % | 52,9 % | 54 % |
| Sharpe | 2,0 | 2,1 | 1,2 | 1,7 |
| MDD | 8,8 % | 9,4 % | 40,9 % | 36,1 % |
| hit ratio | 17,4 % | ~17 % | 18,1 % | ~17 % |
| gain:loss | 5,5 | ~5,7 | 5,2 | ~5,5 |
| trades | 23 360 | ~21 967 | 23 504 | ~22 399 |

**Verdikt R1: PASS.** QQQ replikováno prakticky přesně (vše v toleranci zdroje dat). TQQQ: per-trade struktura (vol/hit/G:L/trades) replikována; kompounding gap = 0,71 bps/obchod, kvantitativně vysvětlen fee-per-share na split-adjusted cenách (QC adjusted $8–40 → 0,25–1,25 bps/RT vs paper unadjusted $40–90 → 0,1–0,25) — datový artefakt, ne chyba pravidel. Backtest c6bd24a4, projekt 34170904.

## R2 — překlad SPY/ES s reálnými costs (2018-01-02→2025-09-30, vyhrazené okno nedotčeno)

ES: RTH-only VWAP (vědomé rozhodnutí), kontinuální kontrakt, notional 1× NAV. Costs 0,4/1,2 bps RT lokálně. ~17,5 obchodů/den, hit 16–17 %, G:L 5,2–5,6.

| scénář | SPY CAGR / Sharpe / MDD | ES CAGR / Sharpe / MDD |
|---|---|---|
| GROSS | +9,8 % / +0,76 / 16,0 % | +12,0 % / +0,91 / 15,9 % |
| net_opt (0,4) | −8,0 % / −0,54 / 52,5 % | −6,1 % / −0,39 / 43,0 % |
| net_cons (1,2) | −35,5 % / −2,91 / 96,7 % | −34,1 % / −2,78 / 96,1 % |
| B&H benchmark | +14,3 % / +0,65 / 33,7 % | — |

Kontext: QQQ (R1) s realistickými costs: net_opt +19,4 % (Sharpe 1,07), net_cons −14,0 %.

**Verdikt R2: strategie se na SPY/ES NEPŘEKLÁDÁ** — gross pod B&H, net záporné při všech realistických nákladech. Edge je QQQ/NDX-specifický a extrémně cost-sensitivní. Backtest e5319635, detail `results/vwap_r2.csv`. **Konec fáze — čeká se na rozhodnutí o R3.**

## R4a — NQ baseline + anatomie P&L (2018-01-02→2025-09-30)

**NQ baseline (16,2 obchodů/den, hit 17,5 %, G:L 5,4):** GROSS CAGR **+36,1 %** (Sharpe 1,88, MDD 11,1 %) → NDX edge na futures POTVRZEN (QQQ ekvivalent 40,6 %). net_opt (0,4): +15,1 %/0,88; net_cons (1,2): **−17,8 %** → baseline na konzervativních nákladech mrtvá; redukce obchodů nutná.

**Anatomie (éra0=2018–21 / éra1=2022–25, gross):**
- **Délka držení (klíč):** obchody <15 min (~77 % všech) = kumulativně **−695 %/−766 %**; obchody ≥30 min = **+846 %/+865 %**. Whipsawy identifikovány u zdroje.
- **Koncentrace:** top 1 % obchodů = +339/+346 % vs total +159/+95 % → **99 % obchodů má záporný součet**; edge = vzácné dlouhé trendy. Filtr nesmí zmeškat trendové vstupy.
- **Hodina vstupu:** všechny hodiny gross kladné (ráno ~1,1 bps/obchod, midday ~0,6) → hodinový filtr je slabý nástroj.
- **Pořadí v dni:** i 10.+ obchod dne kladný součet (+71/+40 %) → tvrdý cap obchodů/den by odřízl významný kus gross → špatný nástroj.

**Závěr:** jediný filtr, který anatomie podporuje, je **konfirmační/hysterezní pásmo kolem VWAP** (zabíjí <15min whipsawy u zdroje, nechává trendové vstupy). Hodinové filtry a trade capy data nepodporují — vyřazeny. Backtest c707bbc8.

## R4b — hysterezní pásmo kolem VWAP (NQ, předregistrovaný grid b ∈ {2,5/5/10/20} bps)

Vstup i flip vyžadují close ZA VWAP±b; jinak pravidla beze změny. 2018-01-02→2025-09-30.

| band | tr/den | hit | GROSS CAGR/Sharpe | net_opt | net_cons CAGR/Sharpe/MDD | net_cons éra0/éra1 |
|---|---|---|---|---|---|---|
| 0 (baseline) | 16,2 | 17,5 % | +36,1 %/1,88 | +15,1 %/0,88 | **−17,8 %**/−0,96/80 % | — |
| 2,5 | 9,4 | 22,1 % | +28,9 %/1,56 | +16,9 %/0,98 | −3,8 %/−0,13/51 % | +3,8/−11,1 |
| 5 | 6,7 | 25,2 % | +22,3 %/1,22 | +14,0 %/0,82 | −0,9 %/+0,04/43 % | +5,2/−7,0 |
| 10 | 4,4 | 29,8 % | +20,1 %/1,12 | +14,8 %/0,86 | +4,9 %/+0,35/24 % | +9,8/−0,3 |
| **20** | **2,5** | **36,9 %** | +18,4 %/1,04 | +15,4 %/0,89 | **+9,5 %/+0,59/22,5 %** | **+13,3/+5,1** |

**Zjištění:** (1) net_opt je PLOCHÉ napříč gridem (~14–17 %) — pásmo mění gross edge za úsporu nákladů ~1:1; (2) net_cons monotónně roste s pásmem: −17,8 % → **+9,5 %**; (3) b=20: 2,5 obchodu/den (−85 % vs baseline), kladné v OBOU érách (předregistrované kritérium ✓); (4) b=10–20 tvoří plateau; b=20 je hrana gridu — trend je monotónní, ale grid se post-hoc NErozšiřuje (pre-registrace); (5) éra1 slabší než éra0 všude (edge v čase slábne) — poctivě flagováno.

## R4c — sizing (lokálně, na b=20 net_cons řadě)

| sizing | CAGR | vol | Sharpe | MDD | éra0/éra1 |
|---|---|---|---|---|---|
| plná pozice | +9,5 % | 17,5 % | 0,59 | 22,5 % | +13,3/+5,1 |
| **vol-target 15 % (EWMA20, cap 1×)** | **+9,6 %** | 13,2 % | **0,74** | **12,2 %** | +12,6/+6,0 |
| vol-target 10–12 % | +8,1–8,8 % | 10–12 % | 0,78–0,80 | 9,6–11,1 % | ~+10/+6 |

**Vol-targeting 15 % = free lunch:** stejné CAGR, poloviční MDD (22,5→12,2 %), Sharpe 0,59→0,74, éra1 mírně lepší. Plateau 10–15 % robustní. Denní loss-limit vyžaduje intradenní path (další běh) — lokálně neaproximováno.

**Kandidátní finální konfigurace pro R3 (one-shot OOS):** NQ, VWAP trend + hysterezní pásmo 20 bps, vol-target 15 % (cap 1×), costs 0,4/1,2 bps. IS: net_cons CAGR +9,6 %, Sharpe 0,74, MDD 12,2 %, ~2,5 obchodu/den, kladné v obou érách.

## R3 — jednorázová OOS validace (frozen spec potvrzena; JEDEN běh)

⚠️ **Platformní zkrácení okna:** QC free tier má mapping kontinuálního NQ jen do 2026-04-16 → backtest pokryl **140 ze ~197 obchodních dní** OOS (2025-10-02→2026-04-17, 71 %). Nezaviněno volbou parametrů; pravidlo běželo přesně dle frozen spec. BacktestId 0f336a6d.

| scénář (frozen pipeline) | total za 140 dní | Sharpe (ann.) | MDD | IS implikace za 140 dní |
|---|---|---|---|---|
| GROSS plná pozice | +1,87 % | +0,31 | 9,0 % | (IS gross +18,4 % p.a. → ~+9,7 %) |
| net_opt + VT15 | +1,11 % | +0,21 | 8,9 % | — |
| **net_cons + VT15 (PRIMÁRNÍ)** | **−1,33 %** | −0,11 | 9,9 % | ~+5,2 % |

Obchody: 324 (2,32/den — sedí na IS 2,5), hit 35,8 % (IS 36,9 % — struktura drží).

**VERDIKT (předregistrované kritérium): NEJEDNOZNAČNÉ.** Primární metrika −1,33 % je v zóně (−5 %, 0): není to „podpořeno" (vyžadovalo >0) ani „nepodpořeno" (vyžadovalo <−5 % nebo záporný gross — gross je +1,87 %). Přesně dle spec: interpretuje se TAKTO a ne silněji.

**Poctivé čtení bodových odhadů (bez statistické váhy, t≈±0,1):**
1. Gross edge OOS (+3,4 % p.a. ekviv.) je výrazně pod IS gross (+18,4 % p.a.) — bodový odhad směřuje ke slabšímu edge, ale 140 dní Sharpe~1 strategie má obří rozptyl; nelze odlišit od šumu.
2. Výsledek osciluje kolem nákladového předpokladu: net_opt kladný, net_cons záporný — strategie na tomhle okně žila v pásmu svých nákladů.
3. Mechanika drží (frekvence i hit ratio sedí na IS) — selhání není implementační.
4. Dle poznámky uživatele: i „podpořeno" by tu mělo malou důkazní sílu; „nejednoznačné" má ještě menší.

**Protokol:** jeden běh, žádné iterování, spec potvrzena předem. Okno 2025-10→2026-04 se považuje za SPOTŘEBOVANÉ i pro tuto rodinu. Segment 2026-04-17→07-11 zůstal nevyhodnocen kvůli platformnímu limitu dat (viz text) — případné doplnění by vyžadovalo změnu datového přístupu a rozhodnutí uživatele; default = uzavřeno jako nejednoznačné.


## Diagnostika D1 (Projekt 3) — shrnutí

Rok-po-roce dekompozice Raw / +pásmo / +VT na NQ (tabulka v PLAYBOOK_vwap_trend.md, data results/vwap_d1.csv, backtest 567b6895). Klíč: corr(raw edge, čas)=−0,44; corr(raw edge, vol)=+0,62 (n=8). Pásmo přispívá stabilně (+12 až +46 pp/rok, cost-mitigation nedegraduje); VT plní de-risk roli ve vysokovol letech. 2025+OOS segment dodávají edge hluboko pod vol-implikovanou úroveň (2025: vol 21,4 % ale edge +5,1 % vs 2018: vol 20,1 % → +49 %) → obraz = vol-režimová báze + od 2025 dodatečný pokles nevysvětlený volatilitou; 8–9 bodů nerozhodne. Metrika ke sledování dál: edge/vol ratio.


## Diagnostika D2 (Projekt 3) — shrnutí

MC bootstrap (10k, b=20+VT15 net_cons): IS CAGR +9,7 % [+1,2; +19,0], P(CAGR<0)=3,2 %. OOS segment: total −1,36 % [−16,1; +17,6], **P(>0)=44,8 %**, P(<−5 %)=35,5 % → R3 „nejednoznačné" empiricky potvrzeno (mincovní hod). 2D grid 5×5 (band×VT): jeden souvislý ostrov (15–16/25 buněk), (20,15) uvnitř na okraji (hrana b=15 pod ním); VT dimenze plochá, rozhoduje band; hřeben b=25 (Sharpe ~1,0) = kandidát pro příští čisté OOS, nic se teď nemění. Detail: results/vwap_d2_grid.csv, figures/d2_heatmap.png, PLAYBOOK sekce D2. Běh 8d579324.

---

## PROJEKT 3 — Diagnostika TP-grid (explorativní, IN-SAMPLE, „jen sranda")

Test nápadu uživatele „fixní TP = ½ stopu (RR 1:2)". Fixní TP = tp_mult×R, R=|entry−opačné pásmo|, na zamrazeném b=20 VWAP-trend pravidle, NQ IS 2018→2025-09-30, OOS nedotčeno, net_cons 1,2 bps. backtestId c194898cc17dcea9c33d7ce4daa77cd4.

| TP | hit% | trades | CAGR net_cons | Sharpe | MDD | final NAV |
|---|---|---|---|---|---|---|
| 0,25R | 79,6 | 11115 | −11,3 % | −1,29 | −62,9 % | 9915 |
| 0,5R | 66,3 | 8513 | −6,8 % | −0,60 | −47,5 % | 14532 |
| 1,0R | 51,3 | 6656 | −1,2 % | −0,04 | −37,5 % | 22773 |
| bez TP (baseline) | 36,4 | 5051 | +9,5 % | +0,59 | −22,4 % | 51043 |

VERDIKT: fixní TP monotónně ničí edge (čím těsnější, tím hůř). 0,5R obrátil +9,5 % → −6,8 %. Baseline reprodukuje D2 b=20 (+9,5 %, Sharpe 0,59) → sanity OK. Mechanismus: edge žije ve vzácných dlouhých trendech; fixní TP usekne pravý ocas → klamavě vysoký winrate (0,25R: 79,6 % hit / −11,3 % CAGR) — identická past jako Projekt 1. Dopad na nasazení: žádný (IS-only explorace, deploy zůstává b=20+VT15 bez TP; žádná varianta ani na OOS kandidátní seznam).

---

## PROJEKT 4 — Opening Range Breakout (15min, ATR SL/TP), IN-SAMPLE

Zamrazená spec `orb_frozen_assumptions.md` (potvrzeno). OR = high/low prvních dvou 15-min svíček (9:30–10:00 ET); vstup na open svíčky po prvním 15-min close mimo OR; SL=entry∓2×ATR(14,15-min), TP=entry±1×ATR; SL-first při ambiguitě; max 1 obchod/den; EOD flat 16:00; 1% risk cap ≤1× notional; net_cons 1,2 bps. ES+NQ × base/filt. IS 2018-01-02→2025-09-30, OOS nedotčeno. QC 34184379, bt 095398965b38ac76d201a072dd2c1dcd.

| varianta | final NAV (100k) | CAGR | Sharpe | MDD | n | TP-of-decided | vs 66,7% |
|---|---|---|---|---|---|---|---|
| ES base | 61801 | −6,0 % | −1,01 | −39,0 % | 1963 | 66,6 % [64,4;68,8] | straddle |
| ES filt | 66696 | −5,1 % | −0,96 | −34,6 % | 1513 | 66,2 % [63,6;68,7] | straddle |
| NQ base | 70725 | −4,4 % | −0,58 | −31,3 % | 1929 | 68,5 % [66,3;70,7] | straddle |
| NQ filt | 65920 | −5,2 % | −0,80 | −35,2 % | 1488 | 67,6 % [65,0;70,1] | straddle |

VERDIKT: NEPODPOŘENO. Všechny 4 varianty ztrácejí (CAGR −4,4 až −6,0 %, záporný Sharpe, 1–2 ziskové roky z 8). Binární win rate (TP-of-decided) statisticky nerozeznatelný od 66,7 % breakeven (RR 2:1) → directional edge nulový nad rámec geometrie; po EOD výstupech (~12 %) + nákladech záporná NAV. News filtr nekonzistentní (ES +, NQ −) = šum, nezachrání. Krok-0 design note (potřeba >67 %) potvrzena jako předběžná falzifikovatelná předpověď. OOS ODLOŽENO — NESPOTŘEBOVÁNO (není co validovat). Detail: PLAYBOOK_orb.md.

### PROJEKT 4 — varianta B (fixní TP 10b, SL = opačná strana OR), IS

bt 9d05d4329fbbe1c84359695aded49e17. TP=entry±10b fix, SL=opačná strana 30-min OR, riziko=|entry−OR opp|. Explorativní IS-only, OOS nedotčeno.

| var | finalNAV | CAGR | Sharpe | MDD | n | win% | TP-of-dec% |
|---|---|---|---|---|---|---|---|
| ES base | 79194 | −3,0 % | −0,56 | −24,6 % | 1963 | 63,2 | 68,3 |
| ES filt | 82954 | −2,4 % | −0,51 | −22,8 % | 1513 | 62,8 | 68,4 |
| NQ base | 75698 | −3,5 % | −1,04 | −25,7 % | 1929 | 87,9 | 91,2 |
| NQ filt | 73790 | −3,9 % | −1,23 | −27,2 % | 1488 | 87,0 | 90,8 |

VERDIKT: pořád ztrátové (všechny 4), ale mělčí než A. NQ = picking pennies: 87,9% win rate, přesto −3,5% (162 SL = plná range smaže ~6-10 výher). News filtr nekonzistentní (šum). Souhrn P4: ani A (ATR) ani B (fixní TP) nemá kladnou expectancy → 15-min ORB continuation edge na ES/NQ nulový. OOS nedotčeno. Detail: PLAYBOOK_orb.md.

### PROJEKT 4 — varianta C (ES grid: zkrácený stop × RR-based TP), IS

bt 4d7be54fd8da19a0b719ab3c33a714e0. SL=s×šířka_OR, TP=m×stop, grid 6×4, net R/obchod. Test příznivého RR (dosud netestováno).

RR trend (avg mean-net-R přes s): m=1→−0,076, m=1.5→−0,067, m=2→−0,049, m=3→−0,029. Širší TP monotónně líp (potvrzeno), ale jen k nule. Jen 3/24 buněk kladné (všechny m=3). Nejlepší s=0.6 m=3: mean +0,0139R, ale t=0,39 p=0,70 (= nula), sousedé záporní (ne ostrov), Sharpe +0,009. VERDIKT: žádný robustní edge; příznivé RR = z „ztrátové" na „~breakeven". Doporučení pokud nutno: s≈0,7 m=3, ale ~nula, NE na OOS. Souhrn P4: ORB continuation na ES/NQ nemá edge v žádné z 3 RR geometrií. OOS nedotčeno. Detail: PLAYBOOK_orb.md.

### PROJEKT 4b — pre-market ORB, 1-min breakout, 1:1 RR + filtry (NQ), IS

Spec orb_4b_frozen_assumptions.md. NQ extended hours, range 9:15-9:30, 1-min breakout, SL=opačná strana range, TP 1:1, filtry range%×RVOL×ATR (18 kombinací). QC 34193719, bt 28397134653b59965d07549cce9c720d. IS, OOS nedotčeno.

VERDIKT: NEPODPOŘENO. 0/18 kombinací kladná. Baseline TP-of-decided 51,3% [49,1;53,5] = straddluje 50% breakeven (hod mincí), mean net R −0,042. Nejlepší RVOL≥1,2: −0,006 R (t=−0,13, p=0,89 = nula, pořád záporné), rozpadá se u RVOL≥1,5 (−0,098). ATR-pro-vol filtr neutrální/škodlivý. Island check: fragilní hřeben, ne stabilní ostrov (optimizer's curse). Konzistentní s MNQ falsifikační studií + Projekt 4 A/B/C. Detail: PLAYBOOK_orb.md sekce Varianta 4b.
