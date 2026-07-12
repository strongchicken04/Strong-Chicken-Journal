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

