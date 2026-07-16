# PLAYBOOK — Projekt 4: Opening Range Breakout (15min, ATR SL/TP)

**Instrument:** ES (E-mini S&P 500) primární + NQ (E-mini Nasdaq-100) robustness, kontinuální kontrakt
**Prostředí:** QuantConnect / LEAN, headless cloud backtest jako compute engine (žádné reálné ordery, simulace NAV)
**In-sample:** 2018-01-02 → 2025-09-30 · **OOS (2025-10-01 → 2026-07-11): ROZHODNUTÍ ODLOŽENO — NESPOTŘEBOVÁNO**
**Zamrazená specifikace:** `orb_frozen_assumptions.md` (potvrzeno uživatelem před psaním kódu)
**Datum:** 2026-07 · Research anchor: Zarattini/Barbon & Aziz ORB studie · projekt QC 34184379, backtestId `095398965b38ac76d201a072dd2c1dcd`

---

## ⛔ EXECUTIVE SUMMARY

> **Opening Range Breakout s konfigurací SL = 2×ATR, TP = 1×ATR nemá na ES ani NQ (2018–2025) kladnou expectancy — všechny čtyři varianty ztrácejí, s CAGR −4,4 % až −6,0 % a záporným Sharpe.** Příčina je přesně ta, na kterou jsem upozornil v Kroku 0: RR 2:1 v neprospěch vyžaduje **hit rate > 66,7 %**, a strategie dodává binární win rate (TP-of-decided) **statisticky nerozeznatelný od právě těch 66,7 %** (Wilson CI všech čtyř variant straddluje 66,7 %). „Sedět na breakeven" před náklady + EOD výstupy = **ztrácet po nich**. Directional edge breakout-continuation na 15-min ES/NQ je tedy prakticky nulový nad rámec toho, co si vynucuje geometrie 2:1.
>
> **News filtr (deterministický 10:00-ET kalendář) situaci nezachrání:** ES marginálně zlepší (CAGR −6,0 → −5,1 %), NQ zhorší (−4,4 → −5,2 %) — **nekonzistentní znaménko napříč instrumenty = šum, ne reálný efekt.** Filtr odebere ~23 % obchodů, aniž by systematicky zvedl edge.
>
> **Hodnotný negativní výsledek, vyvrácený v IS fázi — OOS okno zůstává nedotčené.**

![ORB equity](results/figures/orb_equity.png)

---

## 1. Výsledky (IS 2018-01-02 → 2025-09-30, net_cons 1,2 bps)

| varianta | final NAV (z 100k) | CAGR | Sharpe | MDD | n obchodů | obch./den | net-win % | TP % | **TP-of-decided %** | EOD exits | mean R (gross) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **ES bez filtru** | 61 801 | **−6,0 %** | −1,01 | −39,0 % | 1963 | 1,01 | 62,3 | 59,2 | **66,6** | 217 | −0,034 |
| ES + news filtr | 66 696 | −5,1 % | −0,96 | −34,6 % | 1513 | 0,78 | 61,9 | 58,6 | **66,2** | 173 | −0,041 |
| **NQ bez filtru** | 70 725 | **−4,4 %** | −0,58 | −31,3 % | 1929 | 0,99 | 63,9 | 60,2 | **68,5** | 235 | −0,007 |
| NQ + news filtr | 65 920 | −5,2 % | −0,80 | −35,2 % | 1488 | 0,76 | 63,2 | 59,7 | **67,6** | 173 | −0,020 |

- **net-win %** = podíl obchodů s kladným net P&L; **TP %** = podíl obchodů ukončených na TP; **TP-of-decided %** = TP/(TP+SL), tj. binární win rate ve framingu, na který se vztahuje 66,7% breakeven práh (EOD výstupy vyloučené).
- **obchodů/den ~1,0** (bez filtru) — v souladu s „max 1 obchod/den" (mírně pod 1, protože OR se ne vždy prorazí).

## 2. Hit ratio vs. 66,7 % breakeven práh (jádro verdiktu)

RR 2:1 v neprospěch (win = +0,5R, loss = −1,0R) ⇒ breakeven binární win rate = **66,7 %**. Wilson 95% CI na TP-of-decided:

| varianta | TP-of-decided | Wilson 95% CI | vůči 66,7 % |
|---|---|---|---|
| ES bez filtru | 66,6 % (n=1746) | [64,4; 68,8] | **straddluje** |
| ES + filtr | 66,2 % (n=1340) | [63,6; 68,7] | **straddluje** |
| NQ bez filtru | 68,5 % (n=1694) | [66,3; 70,7] | **straddluje** (dolní mez 66,3 < 66,7) |
| NQ + filtr | 67,6 % (n=1315) | [65,0; 70,1] | **straddluje** |

**Ani jedna varianta není statisticky nad 66,7 %.** Nejlepší (NQ base 68,5 %) má dolní mez CI pod prahem. Directional edge continuation je tedy **nerozeznatelný od přesného breakeven** — a to je *před* dvěma tahači dolů:
1. **EOD výstupy** (~12 % obchodů, 217–235 ks): obchody, které do 16:00 netrefí TP ani SL, se zavřou na close — v průměru mírně ztrátové, mimo binární framing.
2. **Náklady** (1,2 bps round-turn × ~1900 obchodů): samotné náklady ukrojí řádově ~20 % NAV za období.

Výsledek: gross mean R lehce záporné (NQ base −0,007 = prakticky flat gross), po nákladech + EOD jasně záporná NAV.

## 3. Per-year net P&L ($, start 100k) — stabilně špatné, ne režimové

| rok | ES base | ES filt | NQ base | NQ filt |
|---|---|---|---|---|
| 2018 | −8 001 | −6 318 | −14 208 | −10 848 |
| 2019 | −8 501 | −8 376 | −535 | −2 452 |
| 2020 | −6 074 | −6 562 | −4 724 | −10 683 |
| 2021 | −1 362 | −2 195 | +1 384 | +3 504 |
| 2022 | −1 580 | −2 105 | −1 917 | −3 934 |
| 2023 | +817 | +1 281 | −1 936 | −103 |
| 2024 | −5 392 | −5 368 | +802 | −4 467 |
| 2025 | −3 597 | +297 | −3 992 | −1 110 |
| **ziskové roky** | **1/8** | 2/8 | 2/8 | 1/8 |

Žádná varianta nemá víc než 2 ziskové roky z 8. Není to „edge, který zmizel v jednom režimu" — je to **konzistentně ztrátové napříč lety** (2018–2020 obzvlášť, ale i jinde). Ojedinělé kladné roky (NQ 2021) nevytvářejí trend.

## 4. News filtr — verdikt: nepomáhá

- Odebere 451 (ES) / 445 (NQ) obchodů (~23 % — sedí na 23,6 % news dní v kalendáři).
- **ES:** CAGR −6,0 → −5,1 % (marginální zlepšení). **NQ:** −4,4 → −5,2 % (zhoršení).
- **Nekonzistentní znaménko napříč dvěma instrumenty ⇒ není to reálný efekt, jen redukce vzorku + šum.** Filtr byl testován jako refinement, ne jako load-bearing komponenta — a jako refinement selhává. (Pozn.: kalendář je deterministický subset 10:00-ET releasů — ISM Mfg/Svc + CB Consumer Confidence + UoM prelim/final; i kdyby úplnější kalendář filtr mírně vylepšil, nezmění to záporný základ strategie.)

## 5. Verdikt dle Kroku 0

- **Podpořeno** vyžadovalo: net_cons expectancy kladná, hit ratio prokazatelně nad 66,7 %. **Nesplněno** — NAV záporná u všech variant, hit ratio statisticky na breakeven.
- **Design condition z Kroku 0 se naplnila přesně:** „hit ratio pod 67 % s touhle konfigurací = automaticky ztrátová i před náklady." Strategie dodala ~66–68 % (na breakeven), tedy po EOD výstupech a nákladech ztrátovou. **Nejde o překvapení — jde o potvrzení předem identifikované náročné podmínky.**

## 6. Co by případně mohlo pomoct (budoucí směry, mimo tuto zamrazenou spec)

Tohle NEjsou úpravy k „doladění" současné strategie (to by byl overfitting na IS) — jsou to jiné hypotézy, které by si vyžádaly vlastní frozen spec:
- **Symetrické nebo příznivé RR** (TP ≥ SL): breakeven pak padá na ≤ 50 %, což je dosažitelnější — ale otázka je, jestli continuation dojede dost daleko (širší TP = nižší hit rate). Trade-off, ne free lunch.
- **Filtr kvality breakoutu** (objem/volatilita OR, šířka OR vs ATR): obchodovat jen „čisté" průrazy, ne každý.
- **Jiný TP/exit management** než fixní ATR násobek (trailing, R-multiple scale-out) — ale pozor na lekci z Projektu 3 TP-gridu (fixní TP ničí trend edge).
- **Jiný opening-range interval** (5min, 30min, 60min) — Zarattini ORB studie typicky používají 5-min OR na akciích/ETF, ne 15-min na futures.

## 7. OOS status

**OOS okno 2025-10-01 → 2026-07-11: ROZHODNUTÍ ODLOŽENO — NESPOTŘEBOVÁNO.** Protože žádná varianta nemá kladnou IS expectancy, kterou by šlo validovat, **není co na OOS testovat** — okno zůstává nedotčené (stejně jako u Projektu 1). Případný budoucí (jiný) ORB design by potřeboval vlastní frozen spec a teprve pak, s dostatečnou IS oporou, gated jednorázový OOS. Okno navíc už bylo spotřebováno 2× (Projekt 2b Fáze E, Projekt 3 R3), takže laťka pro jeho třetí použití je vysoká.

## 8. Reprodukovatelnost

- Log: `results/RESULTS.md` (sekce PROJEKT 4). Kód: `research/orb/main.py` (compile engine, 4 simy). Config: `research/orb/config.json` (cloud-id 34184379).
- Zamrazená spec: `orb_frozen_assumptions.md`. News kalendář: `data/cache/econ_calendar_1000et.csv` (460 dní, deterministicky generovaný, embedovaný v algoritmu).
- Metriky: `results/orb_is.json`. NAV série: `data/cache/orb_nav.csv`. Figura: `results/figures/orb_equity.png`.

**Metodická poznámka:** Krok-0 design note (RR 2:1 → potřeba >67 %) fungoval jako **falzifikovatelná předpověď před během** — a data ji potvrdila. Přesně proto se náročná podmínka pojmenovává předem: výsledek pak není „zklamání", ale čisté ověření hypotézy.

---

## Varianta B (explorativní) — fixní TP 10 bodů, SL = opačná strana OR

**Změna vůči zamrazené spec:** TP = entry ± 10 bodů (fixní), SL = opačná strana 30-min OR (long → OR_low, short → OR_high). Riziko = |entry − opačná strana OR| (mění se se šířkou range). Vše ostatní stejné. Explorativní IS-only, OOS nedotčeno. backtestId `9d05d4329fbbe1c84359695aded49e17`.

| varianta | final NAV (100k) | CAGR | Sharpe | MDD | n | **win %** | TP-of-decided % [CI95] | EOD | mean R |
|---|---|---|---|---|---|---|---|---|---|
| ES bez filtru | 79 194 | **−3,0 %** | −0,56 | −24,6 % | 1963 | 63,2 | 68,3 | 295 | −0,020 |
| ES + filtr | 82 954 | −2,4 % | −0,51 | −22,8 % | 1513 | 62,8 | 68,4 | 239 | −0,022 |
| NQ bez filtru | 75 698 | **−3,5 %** | −1,04 | −25,7 % | 1929 | **87,9** | **91,2** | 80 | −0,013 |
| NQ + filtr | 73 790 | −3,9 % | −1,23 | −27,2 % | 1488 | 87,0 | 90,8 | 69 | −0,023 |

**VERDIKT: pořád ztrátové na všech čtyřech — ale méně než varianta A** (A: ES −6,0 % / NQ −4,4 %; B: ES −3,0 % / NQ −3,5 %). Fixní 10-bodový TP se trefuje častěji → mělčí ztráta, ale ne kladná expectancy.

**NQ = učebnicové „picking pennies" (predikce z Kroku potvrzená přesně):** 10 bodů na NQ (~5 bps) se trefí skoro vždy → **win rate 87,9 %, TP-of-decided 91,2 %** — a přesto **−3,5 % CAGR**. Jen 162 SL z 1929 obchodů, ale ty stopy jsou na opačné straně celé NQ range (desítky bodů, ~30–50 bps) → jedna ztráta smaže ~6–10 výher. Mean R gross −0,013. Nejhorší Sharpe ze všech (−1,04) — vysoký win rate = vysoká, ale záporná jistota. **Toto je nejčistší ukázka lekce „win rate ≠ ziskovost" z celého výzkumu** (vedle VWAP TP-gridu, který ukázal opačný pól: nízký win rate + kladná expectancy).

**ES:** win 63 %, TP-of-decided 68,3 % (nad 66,7 %, ale to je breakeven jen pro RR 2:1 — tady je RR proměnlivé). Riziko = plná šířka OR (~15–30 bodů) proti fixnímu 10-bodovému zisku → na širokorozsahových dnech nepříznivé; mean R −0,020 → net záporné.

**News filtr:** opět ES marginálně zlepší (−3,0 → −2,4 %), NQ zhorší (−3,5 → −3,9 %) — **nekonzistentní znaménko = šum** (stejně jako u varianty A).

**Per-year:** 2–4 ziskové roky z 8 (o něco lepší než A, ale žádná varianta ne většinově kladná; 2019/2020/2024 stabilně ztrátové napříč instrumenty).

**Souhrn Projekt 4:** Ani ATR-based (varianta A), ani fixní-TP/range-SL (varianta B) konfigurace 15-min ORB nemá na ES/NQ 2018–2025 kladnou net expectancy. Dvě protilehlé RR geometrie (A: RR 2:1 v neprospěch, nízký win; B: malý fixní TP, vysoký win) skončily obě záporně — směrový edge continuation po 15-min OR průrazu je na těchto indexových futures prakticky nulový. **OOS zůstává nedotčené.** Data varianty B: `results/orb_b_is.json`, `data/cache/orb_b_nav.csv`, figura `results/figures/orb_b_equity.png`.

### Varianta B — průměrná velikost stopu (uzavírající datapoint)

Stop = opačná strana 30-min OR; průměr přes všechny obchody (bt `71be46272e93e3d2147c0da04e84f1c6`):

| varianta | prům. stop (body) | prům. stop (%) | TP 10b / stop | efektivní RR | breakeven WR | actual TP-of-dec |
|---|---|---|---|---|---|---|
| ES base | 24,31 | 0,551 % | 41,1 % | ~1:2,4 | 70,6 % | 68,3 % → pod |
| ES filt | 24,13 | 0,548 % | 41,4 % | ~1:2,4 | 70,6 % | 68,4 % → pod |
| NQ base | 120,77 | 0,820 % | 8,3 % | ~1:12 | 92,3 % | 91,2 % → pod |
| NQ filt | 119,74 | 0,816 % | 8,4 % | ~1:12 | 92,3 % | 90,8 % → pod |

**Mechanismus záporné expectancy exaktně:** fixní 10-bodový TP je jen **8 % (NQ) resp. 41 % (ES)** průměrné vzdálenosti stopu → efektivní RR silně v neprospěch → breakeven win rate 92 % (NQ) / 71 % (ES). Skutečná úspěšnost je u obou **těsně pod** svým breakevenem → obě ztrácejí. NQ má širší relativní OR (0,82 % vs ES 0,55 %), tedy ještě horší poměr TP/stop → nejvyšší win rate a zároveň nejhorší Sharpe. **Toto je numericky uzavřené vysvětlení picking-pennies charakteru varianty B.**
