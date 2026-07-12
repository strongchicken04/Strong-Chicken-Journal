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
3. ⚠️ **K prošetření před Fází A/B5:** ES `bars_seen`≈542k ⇒ ~445 barů/den, což je jen o málo víc než RTH (~390). Očekával bych u 24h ES násobně víc → nutno ověřit pokrytí **overnight** minutových dat kontinuálního kontraktu (RTH-závislá statistika Fáze 0 tím ale zasažená NENÍ).

