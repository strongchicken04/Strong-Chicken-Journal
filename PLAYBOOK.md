# PLAYBOOK — Kvantitativní výzkum S&P 500 / ES mean-reversion strategií

**Instrument:** SPY (equity) + ES (E-mini S&P 500 futures, kontinuální kontrakt)
**Prostředí:** QuantConnect / LEAN, Research přes headless cloud backtest jako compute engine
**In-sample:** 2021-01-01 → 2025-09-30 · **OOS (rezervováno, NEDOTČENO):** 2025-10-01 → 2026-07-11
**Datum:** 2026-07

---

## ⛔ EXECUTIVE SUMMARY — hlavní závěr

> **Žádný z testovaných mean-reversion setupů nemá na S&P futures/ETF v období 2021–2025 kladnou expectancy po realistických nákladech.** Vysoké „win rate" (52–93 %), na kterých byla původní hypotéza postavená, se ukázaly jako **klamavé** — buď kvůli asymetrii zisk/ztráta, nebo kvůli pohyblivému cíli (VWAP). Se symetrickým rizikem/ziskem klesá edge na **~50 % (hod mincí)**.

Tohle je **hodnotný negativní výsledek**: strategie byla poctivě vyvrácena **v in-sample fázi, před nasazením kapitálu a bez spotřebování jednorázového OOS okna.**

---

## 1. Co bylo testováno a jak to dopadlo

| Fáze | Setup / hypotéza | Výsledek | Verdikt |
|---|---|---|---|
| **0** | Close 1. 15min svíčky uvnitř 7denního H/L pásma | SPY 81,67 %, ES 82,42 % (potvrzuje referenci 81,53 %) | ✅ statistika potvrzena, ale sama o sobě není edge |
| **B (breakout)** | Proměnné B1–B8 predikují úspěch reverze po průrazu pásma | Žádná proměnná nepredikuje **směr** reverze (rev30_excl, všechna Fisher p>0,27) | ❌ no edge |
| **B (breakout)** | Objem 1. svíčky, směr breakoutu | Signifikantní (p<0,01, konzistentní ES+SPY) **jen** u tie=loss definice | ⚠️ predikuje **volatilitu**, ne směr obchodu |
| **C1 (VWAP)** | Cena reverduje k VWAP po dotyku ±1/±2 pásma | Návrat k VWAP: ±1 = 76–82 %, ±2 = 66–74 % (n≈1900) | ⚠️ vysoký win rate, ale viz E |
| **C2 (IB)** | Initial Balance extension trend-following | 99,6 % dní prorazí IB, ale TF vstup bez edge (52,8 % z rozlišených) | ❌ no edge |
| **C3 (sezónnost)** | Nižší volatilita 12:00–13:30, nárůst po 14:00 | Potvrzeno (U-tvar, min 12:30 = 2,25 b, close 3,14 b) | ✅ efekt reálný (kontextový) |
| **C4 (overnight)** | Velikost overnight pohybu ↔ RTH range | Slabá signif. korelace (r≈0,10) | ⚠️ marginální |
| **D (funnel)** | C1 + timing (C3) + overnight (C4) | Ranní okno 10:00–12:00 „nejlepší" (85–93 %), ale **z velké části confounded time-to-close** | ⚠️ artefakt definice |
| **E design** | C1 + realistický stop (ATR) + time-box + náklady | Zisk reverze +3 b vs ocas −35 b → **záporná expectancy** napříč celým gridem | ❌ nefunguje |
| **E reform** | Fixní bodové bariéry + trend filtr + ±2 entry | Symetrická bariéra → **~48–52 % (coin flip)**; trend filtr nepomáhá | ❌ definitivně no edge |

---

## 2. Tabulka setupů (formát playbook)

| Setup | Trigger | Vstup | TP / SL / risk | Win rate IS | n IS | Win rate OOS | Poznámka |
|---|---|---|---|---|---|---|---|
| Breakout naivní reverze | 9:45 close mimo 7d pásmo | fade proti breakoutu | ±30 ES-b bariéra | 35 % raw / 54 % excl-tie | 205 (ES) | — (neprovedeno) | definičně citlivé; žádný filtr edge nezvedne |
| VWAP ±1 reverze (pohyblivý cíl) | dotyk vwap±1σ, morning | fade k VWAP | cíl=VWAP, bez stopu | 76–93 % | ~1200–1900 | — (neprovedeno) | win rate = artefakt malého cíle |
| VWAP ±1, ATR stop + time-box | dotyk vwap±1σ, morning | fade k VWAP | stop 0,5–2× ATR, box 60–120 min | 78–91 % | 2561 | — (neprovedeno) | **gross exp −0,02 až −0,73 b; net záporná** |
| VWAP ±1/±2, fixní symetrická bariéra | dotyk vwap±kσ, morning | fade | TP=SL= 4–15 b | **~48–52 %** | ~600–1300 | — (neprovedeno) | **hod mincí, žádný edge** |

**OOS sloupec je prázdný záměrně** — OOS okno se nespouštělo, protože žádný setup nemá kladnou in-sample expectancy, kterou by bylo možné validovat. Okno zůstává nedotčené pro budoucí (jiný) setup.

---

## 3. Metodické lekce (nejcennější část)

1. **Win rate ≠ ziskovost.** Setup s 90 % win rate může mít silně zápornou expectancy, pokud jsou výhry malé a prohry velké. Klíčová identita: `expectancy = win_rate × avg_win − loss_rate × avg_loss − náklady`. Vždy počítej **expectancy**, ne jen win rate. (VWAP reverze: 90 % × 3 b − 10 % × 35 b = záporné.)

2. **Pohyblivý cíl nadhodnocuje win rate.** Cílit na VWAP (který „utíká" k ceně) dává vysokou pravděpodobnost dosažení, ale mrňavý průměrný zisk (~3 b). **Test symetrickou fixní bariérou** je poctivé měřítko edge: pokud first-passage win rate ≈ 50 %, směrový edge neexistuje.

3. **Time-to-close confound.** „Reverze do konce dne" dává ranním eventům 6 h a odpoledním minuty → falešný „ranní edge". Vždy používej **time-box relativní k entry**, ne absolutní konec dne.

4. **Asymetrie ATR vs edge.** Denní ATR (~69 b ES) byl ~20× větší než zachycený reverzní pohyb (~3 b). ATR-násobek je špatné měřítko stopu pro micro-scalp edge. Škáluj stop k **přirozenému riziku setupu**, ne k dennímu ATR.

5. **Multiple testing.** ~114 testů ve Fázi B → ~5–6 falešně signifikantních p<0,05 očekáváno. „Nejlepší z N buněk" je téměř vždy nadhodnocená — kontroluj Wilson CI a konzistenci napříč instrumenty/definicemi.

6. **SPY a ES na stejný den ≈ stejná událost** → nepoolovat (pseudo-replikace, falešné n). SPY = korelovaný robustness check, ne nezávislý vzorek.

7. **Look-ahead disciplína.** Pásmo/ATR/POC/prev-day vždy jen z DOKONČENÝCH předchozích dnů; dnešní bar se přidá až po klasifikaci. OOS fyzicky oddělené datem řezu, ne filtrem za běhu.

---

## 4. Infrastrukturní poznámky (QC Free tier)

- **Spouštění:** Free účet blokuje backtest přes API/CLI → hybrid: kód se pushne + zkompiluje headless (zdarma), backtest spustí uživatel 1 klikem ve web IDE, výsledky se čtou přes read API.
- **Kanály exportu dat ven** (Free limity): runtime statistics (pár KV); charty (10 sérií × 4000 bodů); logy `backtests/read/log` (10 KB/backtest, stránkuje po 200). Object-store export = jen Institutional.
- **Strategie:** minutové featury/eventy počítat **v algoritmu**, ven posílat kompaktní agregáty; statistika (Wilson, Fisher, funnel, expectancy) pak lokálně v pandas/scipy → ověřená a rychle iterovatelná.
- **ES data:** default futures session = jen 9:30–17:00; pro overnight/Globex nutné `extended_market_hours=True`.

---

## 5. Předpoklady nákladů (ES/MES, odhad — ne živé sazby)

| | multiplikátor | komise round-turn | slippage RTH | **round-turn v bodech** |
|---|---|---|---|---|
| ES | $50/bod | $2,5–5 | 0,5–2 ticky | ~0,18 (optim) – 0,60 (konzerv) b |
| MES | $5/bod | $1–1,5 | 1–2 ticky | ~0,45 – 0,80 b (v bodech dráž než ES) |

Výsledky výzkumu **nejsou citlivé** na tento předpoklad — expectancy je záporná i při optimistických nákladech.

---

## 6. Co by bylo potřeba pro reálný edge (budoucí směry)

Tenhle výzkum vyčerpal naivní mean-reversion. Pokud se k tématu vracet, zkusit **jiné třídy signálu** (ne jen „cena je daleko → vrátí se"):

- **Order-flow / mikrostruktura** (delta, absorpce) — ne jen cena/objem v barech.
- **Multi-day / swing** místo intraday scalp (náklady jsou menší podíl většího pohybu).
- **Relativní hodnota / spready** (ES vs NQ, sektorová rotace) místo směrové reverze.
- **Vol-based** (IV vs RV, term structure) — S&P má bohaté opční/vol signály.
- Pokud trvat na intraday reverzi: **striktní režimový filtr** (obchodovat jen prokazatelně range dny), ale Fáze D ukázala, že „range-bound" klasifikace v 9:45 nestačí — dny se mění na trend.

---

## 7. Reprodukovatelnost

- Kompletní průběžný log všech testů: **`results/RESULTS.md`**.
- Datasety: `data/cache/` (A1 breakout, A2 range-bound, A3 kalendář).
- Kód per fáze: `research/phase{0,A,B,C,D,E_design,E_reform}/`.
- Syrové logy backtestů: `results/phase*_log.txt`.
- Statistické utility: `research/common/stats.py` (Wilson CI, Fisher exact), `qc_fetch.py` (čtení výsledků z QC API).
- **OOS okno (2025-10-01 → 2026-07-11) nebylo použito** — připraveno pro budoucí validaci jiného setupu.
