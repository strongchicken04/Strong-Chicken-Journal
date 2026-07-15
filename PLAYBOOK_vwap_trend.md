# PLAYBOOK — Projekt 3: VWAP Trend Trading (R1 replikace + R2 překlad SPY/ES)

**Zdroj:** Zarattini & Aziz, *"VWAP: The Holy Grail for Day Trading Systems"*, SSRN 4631351.
**Rodina:** trend-following od session VWAP (nová — mean-reversion a lev-ETF-flow uzavřeny, viz předchozí playbooky).
**Rozsah tohoto dokumentu:** POUZE R1+R2. R3 (fresh OOS) a R4 (risk mgmt) čekají na rozhodnutí uživatele.

---

## EXECUTIVE SUMMARY

> **R1 (replikace QQQ/TQQQ): PASS** — implementace ověřena, QQQ sedí na paper čísla prakticky přesně (CAGR 40,8 % vs 43 %, Sharpe 2,0 vs 2,1, hit 17,4 % vs ~17 %).
> **R2 (překlad na SPY/ES s reálnými costs): NEPŘEKLÁDÁ SE.** Edge je (a) **indexově specifický** — gross CAGR na SPY/ES jen 9,8–12,0 % vs 40,6 % na QQQ, dokonce **pod buy-and-hold** (14,3 %); (b) **extrémně cost-sensitivní** — ~17,5 obchodu/den × 0,4–1,2 bps = 7–21 bps/den drag → net CAGR **−6 až −36 %** na SPY/ES. Per-trade gross edge na SPY (~0,2 bps) je pod i optimistickými náklady.

---

## 1. Zamrazená pravidla (implementováno přesně dle paperu)

Session VWAP (RTH only, HLC/3×V, denní reset); vstup na close 1. minutové svíčky (9:31) vs VWAP → pozice na open další svíčky; reverzace jen když svíčka **zavře** na opačné straně VWAP (intra-bar průnik nespouští); EOD flat na close 16:00; 100 % kapitálu, frakční shares, plný reinvest.

## 2. R1 — replikace (QQQ/TQQQ, 2018-01-02→2023-09-28, paper costs)

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

**Verdikt: PASS.** QQQ replikováno ve všech metrikách. TQQQ: per-trade struktura replikována; kompounding gap = 0,71 bps/obchod, kvantitativně vysvětlen fee-per-share na split-adjusted cenách (QC adjusted $8–40 → 0,25–1,25 bps/RT; paper unadjusted $40–90 → 0,1–0,25 bps/RT) — datový artefakt, ne chyba pravidel (u QQQ, px ~$250, fee=0,04 bps, proto sedí).

## 3. R2 — překlad na SPY/ES s reálnými costs (2018-01-02→2025-09-30)

**Explicitní rozhodnutí (žádné tiché defaulty):**
1. **ES session:** VWAP i obchodování ukotveny na RTH 9:30–16:00 ET (vědomé rozhodnutí; ES obchoduje ~24 h). Kontinuální kontrakt (OpenInterest mapping, BackwardsRatio), notional 1× NAV, bez páky.
2. **Costs:** zavedený model z Fáze E — **0,4 bps (opt) / 1,2 bps (cons) round-turn**, aplikováno lokálně na denní gross returny × počet obchodů.
3. **Okno:** končí 2025-09-30. **Vyhrazené okno 2025-10-01→2026-07-11 NEDOTČENO** (rezerva pro případný R3). Pozn.: okno bylo jednou použito Fází E Projektu 2b (jiná signálová rodina, jeden pohled na last-hour outcome) — pro VWAP trend rodinu je prakticky čisté, ale v R3 dokumentaci to přiznat.

**Výsledky (~17,5 obchodu/den, hit 16–17 %, G:L 5,2–5,6 — struktura jako QQQ):**

| scénář | SPY CAGR | SPY Sharpe | SPY MDD | ES CAGR | ES Sharpe | ES MDD |
|---|---|---|---|---|---|---|
| GROSS (bez costs) | +9,8 % | +0,76 | 16,0 % | +12,0 % | +0,91 | 15,9 % |
| net_opt (0,4 bps/RT) | **−8,0 %** | −0,54 | 52,5 % | **−6,1 %** | −0,39 | 43,0 % |
| net_cons (1,2 bps/RT) | **−35,5 %** | −2,91 | 96,7 % | **−34,1 %** | −2,78 | 96,1 % |
| **B&H benchmark** | **+14,3 %** | **+0,65** | **33,7 %** | — | — | — |

**Kontext — i QQQ (paperový vlajkový výsledek) s realistickými costs:** net_opt CAGR +19,4 % (Sharpe 1,07 — pořád zajímavé), net_cons **−14,0 %** (mrtvé). Paperův cost model ($0,0005/akcii + nulový slippage ≈ 0,04 bps/RT na QQQ) je de facto frictionless assumption.

## 4. Závěr R2 (fakticky, bez ladění)

1. **Strategie se na SPY/ES nepřekládá:** gross edge je 4× slabší než na QQQ (intraday trend persistence je vlastnost NDX, ne obecná), gross výkon je pod buy-and-hold, a net výkon je při jakýchkoliv realistických nákladech záporný.
2. **Cost sensitivity je určující vlastnost celé strategie:** ~22–34k obchodů → každých 0,1 bps/RT nákladů = ~4,4 %/rok drag. Paper výsledek je replikovatelný, ale žije a umírá s předpokladem nulového slippage.
3. Guardrail dodržen: žádné ladění parametrů, vyhrazené okno nedotčeno.

## 5. R4 (NQ) + R3 (one-shot OOS) — dodatek

**R4 (in-sample ladění, NQ):** baseline 16,2 obch./den net_cons −17,8 % → hysterezní pásmo 20 bps: **2,5 obch./den, net_cons +9,5 %** (kladné v obou érách) → + vol-target 15 % (EWMA20, cap 1×): **+9,6 % CAGR, Sharpe 0,74, MDD 12,2 %**. Anatomie: whipsawy <15 min (77 % obchodů) = −700 % gross; top 1 % obchodů nese 2–3,6× celkový zisk.

**R3 (jednorázový OOS, frozen spec `r3_frozen_spec.md`, potvrzeno uživatelem):** platforma zkrátila okno na 140/197 dní (NQ continuous mapping končí 2026-04-16). Výsledek: gross +1,87 %, net_opt+VT15 +1,11 %, **net_cons+VT15 −1,33 %** → **VERDIKT: NEJEDNOZNAČNÉ** dle předregistrovaného kritéria (zóna −5 až 0 %). Mechanika drží (2,32 obch./den, hit 35,8 % ≈ IS), ale gross edge bodově výrazně pod IS. Okno spotřebováno; doporučení: rozhodnutí o nasazení jen přes paper-trading / budoucí data, ne další testy na tomto okně.

## 6. — KONEC — (R3 proběhlo; další krok = rozhodnutí uživatele o paper-tradingu)

Bez dalšího promptu se nepokračuje. Poznámky pro rozhodování (jen fakta, ne doporučení k ladění): QQQ@net_opt Sharpe 1,07 naznačuje, že rodina není univerzálně mrtvá — je QQQ-specifická a cost-hraniční; SPY/ES větev je na základě R2 netradeable.

## 6. Reprodukovatelnost

Kód: `research/vwap_trend/main.py` (MODE R1/R2). Výsledky: `results/vwap_r1.csv`, `results/vwap_r2.csv`, RESULTS.md sekce PROJEKT 3. Backtesty: R1 `c6bd24a4...`, R2 `e5319635...` (projekt 34170904).

---

## Diagnostika D1 — dekompozice a rok-po-roce rozklad (jen diagnóza, žádný redeploy)

Jeden diagnostický běh (backtest 567b6895), 2018-01-03→2026-04-17. Řádek **OOS\*** = spotřebovaný OOS segment 2025-10→2026-04, POUZE diagnosticky, ne nový test. Řádek 2025 = leden–září (IS). Net = net_cons (1,2 bps); VT = kontinuální EWMA20 (diagnostická varianta; oficiální R3 OOS číslo −1,33 % používalo cold-start, drobný rozdíl je očekávaný). Hit ratio řádku 2025 zahrnuje z logu celý kalendářní rok (caveat).

| rok | NQ vol | RAW gross | RAW net/Sharpe | B20 net/Sharpe (t/d) | +VT net/Sharpe | Δpásmo | ΔVT |
|---|---|---|---|---|---|---|---|
| 2018 | 20,1 % | +49,4 % | −10,0 %/−0,47 | +23,9 %/+1,22 (2,5) | +17,0 %/+1,15 | +33,8 | −6,9 |
| 2019 | 11,9 % | +10,9 % | −33,6 %/−2,97 | −3,8 %/−0,29 (1,8) | −3,8 %/−0,33 | +29,8 | −0,1 |
| 2020 | 23,3 % | +89,2 % | +14,5 %/+0,75 | +13,7 %/+0,66 (3,1) | +18,9 %/+1,22 | −0,8 | +5,2 |
| 2021 | 14,5 % | +49,4 % | −8,9 %/−0,54 | +22,9 %/+1,66 (2,1) | +21,4 %/+1,61 | +31,9 | −1,5 |
| 2022 | 26,8 % | +66,4 % | +2,2 %/+0,21 | +14,4 %/+0,65 (3,7) | +13,0 %/+0,84 | +12,2 | −1,4 |
| 2023 | 15,2 % | +13,0 % | −33,9 %/−2,46 | +0,7 %/+0,12 (2,4) | +1,3 %/+0,16 | +34,6 | +0,6 |
| 2024 | 13,9 % | +23,6 % | −26,3 %/−1,84 | +19,2 %/+1,37 (2,0) | +19,1 %/+1,48 | +45,5 | −0,1 |
| 2025 (I–IX) | 21,4 % | **+5,1 %** | −27,7 %/−2,30 | −11,4 %/−0,84 (2,5) | −7,8 %/−0,78 | +16,4 | +3,6 |
| **OOS\*** | 15,7 % | **+4,9 %** | −19,4 %/−2,49 | −2,5 %/−0,25 (2,3) | −1,9 %/−0,18 | +16,9 | +0,6 |

### Marginální příspěvky v čase

- **Pásmo (cost-mitigation):** velké a kladné v 8/9 segmentů (+12 až +46 pp/rok), bez časového trendu — jediná výjimka 2020 (−0,8), kdy extrémní trendový rok nesl i raw variantu a pásmo nic zachraňovat nemuselo. **Mechanismus pásma nedegraduje** — jeho příspěvek je stabilní, protože řeší náklady, ne alfu.
- **VT:** na returnu malý a smíšený (−6,9 až +5,2), ale to není jeho práce — Sharpe/de-risking zlepšuje přesně tam, kde má (vysokovol roky: 2020 0,66→1,22; 2022 0,65→0,84; 2025 −0,84→−0,78). **Žádné známky, že by EWMA20 v čase zaostávala víc** — příspěvek nese vol-režim, ne kalendář.

### Klíčová otázka: sleduje edge čas, nebo volatilitu?

Na ročním RAW gross edge (jádro efektu): **corr(edge, čas) = −0,44; corr(edge, vol) = +0,62** (n=8, oba slabé vzorky).

- **Pro vol-režim mluví:** 2019 (nejnižší vol 11,9 %) = nejslabší IS edge +10,9 %; 2020/2022 (vol 23–27 %) = nejsilnější edge +89/+66 %; 2023–24 (nízká vol) = slabé. Stejný vzorec jako u Projektu 2b (tam corr s vol +0,7, s časem −0,7).
- **Proti čistému vol-režimu mluví poslední dva segmenty:** 2025 (I–IX) má vol **21,4 %** — srovnatelnou s 2018 (20,1 % → edge +49 %) a 2020 (23,3 % → +89 %) — ale edge jen **+5,1 %**; OOS segment podobně (+4,9 % při 15,7 %). Poslední ~19 měsíců dodává **výrazně míň edge, než by vol-vztah z 2018–2024 predikoval** — to je otisk, který by zanechal crowding/adaptace trhu nastupující v posledních letech.

**Poctivý závěr:** data se nejvíc podobají **kombinaci** — bazální vol-režimová závislost (jako u 2b), na kterou se v 2025+ vrství dodatečný pokles nevysvětlený volatilitou. S 8–9 ročními body to nelze rozhodnout tvrdě; vol-hypotéza vysvětluje 2018–2024 dobře a selhává právě na nejnovějším období, což je zároveň období s nejmenším vzorkem.

**Co sledovat dál (jedna věta):** v paper-tradingu / příštím čistém OOS okně sledovat primárně **poměr realizovaného edge k realizované volatilitě** (edge/vol ratio, ne edge samotný) — pokud zůstane hluboko pod úrovní 2018–2024 i v dalším vysokovol období, převáží výklad crowding/decay a strategie se uzavře.
