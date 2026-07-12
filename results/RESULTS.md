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
| _(čeká na běh backtestu)_ | | | | | | | | |

