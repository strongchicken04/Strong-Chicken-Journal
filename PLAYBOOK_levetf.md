# PLAYBOOK — Leveraged/Inverse ETF EOD rebalancing flow (Projekt 2)

**Hypotéza:** mechanický end-of-day rebalancing flow 2x/3x lev/inverse ETF (TQQQ, SPXL, SSO, SQQQ…) zesiluje pohyb S&P v posledních 30–60 min RTH ve směru dosavadního denního pohybu; **a efekt SÍLÍ v čase úměrně růstu AUM** této skupiny fondů.
**Instrument:** ES (futures) + SPY. **In-sample:** 2021-01-01→2025-09-30. **OOS (rezervováno, NEPOUŽITO):** 2025-10-01→2026-07-11.

---

## ⛔ EXECUTIVE SUMMARY

> **Jádro hypotézy je FALZIFIKOVÁNO.** Slabý last-hour (posl. 60 min) intraday momentum efekt sice existuje (SPY 53,3 %, regresní R²=1,77 % — v akademickém pásmu), ALE **neroste s růstem AUM — naopak v čase slábne** (korelace roční síly s časem −0,7). Efekt je **volatilitně řízený** (korelace s roční vol +0,7), ne AUM-flow řízený: je to klasický intraday momentum silnější v high-vol režimech (vrchol 2022, bear market), který v nízkovol 2024–25 vymizel (agree <50 %, expectancy záporná).

**Hodnota:** hypotéza čistě zodpovězena. Efekt, který vypadal slibně, je jen převlečená volatilitní závislost, ne nový AUM-driven jev — a je slabý a slábnoucí.

---

## 1. Co bylo testováno

| Fáze | Test | Výsledek | Verdikt |
|---|---|---|---|
| 0 | Dostupnost AUM/shares dat pro ETF v QC | shares_outstanding/market_cap **0/10 naplněné** (Morningstar = firmy, ne fondy) | ❌ AUM proxy nedostupný → fallback subperiody |
| A | EOD momentum dataset (ES+SPY, cutoffy 15:00/15:30) | 1173/1168 dní; overall agree60 51,8 %/53,3 %, agree30 ~49–51 % | dataset OK |
| B1/B2 | Směrová shoda vs 50 % | SPY K=60 **53,3 % signif** (p=0,028); ES ns; K=30 obojí ns | slabý efekt jen K=60 |
| B3 | Regrese R² vs literatura | SPY R²=**1,77 %** (Gao et al 1,6–2,6 %) | ✅ metoda validní |
| B4 | Expectancy (vstup ve směru dne, drž do close) | K=60 **+0,7 až +1,9 bps** po nákladech (fixní exit → symetrie) | marginálně kladná (IS průměr) |
| B5 | Conditioning na velikost pohybu | velký/střední pohyb ~55 %, malý ~48 % (SPY large vs small p=0,06) | hraniční podpora vol-mechanismu |
| C1 | Per-year + early vs late | 2022 vrchol 58 %, pokles na <50 % v 2024–25; Fisher ES p=0,035 | efekt SLÁBNE |
| C2/C3 | **H_AUM vs H_vol** | corr(agree, čas) **−0,7**; corr(agree, vol) **+0,7** | **H_AUM vyvráceno, H_vol podpořeno** |
| D | Funnel na nejnovější období | neplatné (premisa „sílí" falzifikována) | — |
| E | OOS validace | **nespuštěno** (nic k validaci; hypotéza falzifikována IS) | gated, nedotčeno |

## 2. Tabulka setupu (formát playbook)

| Setup | Trigger | Vstup | Exit / risk | Win rate IS (celé) | Win rate 2021–23 | Win rate 2024–25 | OOS | Expectancy |
|---|---|---|---|---|---|---|---|---|
| Last-hour momentum (K=60) | v 15:00 znaménko r(9:30→15:00) | ve směru dne | drž do 16:00 close | SPY 53,3 % / ES 51,8 % | ~55 % (exp +2 bps) | ~49 % (exp −1 bps) | — (neprovedeno) | kladná jen v ranějším/high-vol období |
| Last-30-min (K=30) | v 15:30 | ve směru dne | drž do close | ~50 % | — | — | — | ~0 / záporná |

## 3. Metodické lekce

1. **Sladit definici okna s mechanismem.** Prompt uváděl „T-60 (14:00)" — ale 14:00 je 120 min před close. Hypotéza = posl. 30–60 min → správné cutoffy 15:00/15:30. Vždy zkontroluj, že měřicí okno odpovídá tvrzenému mechanismu (jinak testuješ něco jiného).
2. **Time-trend vs confounder (KLÍČOVÉ).** Zdánlivý „efekt v čase" může být řízený jinou proměnnou. Korelovat sílu efektu s OBĚMA kandidátními drivery (čas/AUM i volatilita). Zde efekt trackoval vol (+0,7), ne čas (−0,7) → „AUM příběh" byl iluze; šlo o vol-závislost.
3. **Fixní časový exit vs pohyblivý cíl.** Na rozdíl od projektu 1 (VWAP pohyblivý cíl → vysoký win rate, záporná expectancy) tu fixní exit na close dává symetrii avg_win≈avg_loss, takže 53 % win rate = reálně marginálně kladná expectancy. Typ exitu zásadně mění vztah win-rate↔expectancy.
4. **Kladná IS expectancy může být artefakt období.** +1,9 bps IS průměr byl tažený 2021–23; recentní období záporné. Vždy rozděl expectancy v čase, nespoléhej na celkový průměr.
5. **AUM data fondů nejsou v QC/Morningstar.** Fundamentals pokrývá firmy, ne ETF (0/10 populated). Bez fabrikace → poctivý fallback na subperiody. Externí AUM zdroj by vyžadoval placenou databázi / povolení domény.
6. **Sanity check vs literatura.** R²=1,77 % sedící na Gao et al (1,6–2,6 %) potvrzuje, že pipeline měří správnou věc — důležité před vyvozováním závěrů.

## 4. Infrastrukturní poznámky

- Stejný QC Free hybrid pipeline jako projekt 1 (push+compile headless, uživatel klikne Backtest, čtení výsledků přes read API).
- Fáze B/C/D čistě lokální (pandas/scipy) na datasetu z Fáze A → 0 kliků, rychlá iterace.
- Minutová data SPY/ES/ETF dostupná; AUM/shares data ne.

## 5. Návrhy do budoucna

- **Vol-conditional momentum** (cesta B): obchodovat last-hour momentum jen na high-vol / velký-pohyb dnech (B5 + H_vol). Reálný, ale slabý a data-driven → vyšší riziko přeučení; nutná striktní OOS validace.
- **Single-stock / sektorové leveraged ETF** (SOXL, NVDL…) — koncentrovanější flow, možná silnější a měřitelnější signál než široký S&P.
- **Přímá AUM data** z placeného zdroje (issuer/ETF databáze) → umožnilo by přímý test flow ∝ AUM×return místo hrubých subperiod.
- **OOS jako tečka:** okno 2025–26 (nejnovější, nejvyšší AUM) je stále nedotčené; jednorázově použitelné k potvrzení, že efekt je i tam slabý/vol-závislý (potvrzení falzifikace), pokud bude zájem.

## 6. Reprodukovatelnost

- Log: `results/RESULTS.md` (sekce PROJEKT 2). Datasety: `data/cache/eod_{es,spy}.csv`.
- Kód: `research/levetf_phase{0,A}/` (extrakce), `research/levetf_phase{B,C}/analyze.py` (lokální statistika).
- Mezivýsledky: `results/levetf_phase{B,C}.csv`.
- **OOS okno (2025-10-01→2026-07-11) NEPOUŽITO.**
