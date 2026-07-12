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

