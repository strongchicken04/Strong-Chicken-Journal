# PLAYBOOK v2 — Projekt 2b: přeformulovaný test leveraged-ETF flow mechanismu

**Navazuje na:** `PLAYBOOK_levetf.md` (Projekt 2 — AUM hypotéza falzifikována v „agree-rate × čas" formě).
**Přeformulace:** mechanismus predikuje `Flow ≈ AUM × L(L−1) × r` — tedy **signed, velikostně-škálující** vztah mezi returnem dne do cutoffu a returnem poslední hodiny; Projekt 2 testoval AUM/čas izolovaně, což mechanismus nepredikuje.
**In-sample:** 2021-01-01 → 2025-09-30 (SPY primární, ES sekundární). **OOS (2025-10-01 → 2026-07-11): v době psaní tohoto dokumentu NEDOTČENO.**

---

## EXECUTIVE SUMMARY

> **Flow-atribuce: NEPODLOŽENÁ (uzavřeno).** Signed momentum vztah `last60 ~ pre60` je reálný, přežije vol-kontrolu a koncentruje se na velké pohyby — což je s flow mechanismem *konzistentní* — ale (a) **timing jde proti**: efekt je silnější 15:00–15:30 a slábne ke close (mechanický EOD rebalance by měl ke close zesilovat), (b) **AUM vážení nešlo čistě otestovat**: historická AUM/shares data nejsou volně dostupná a AUM růst je ~monotónní s časem, tedy neoddělitelný od časového trendu, který už Projekt 2 zamítl. Per konzervativní bias se flow-specifická atribuce netvrdí.
>
> **Vedlejší reálný nález (in-sample):** size-weighted momentum na velko-pohybových dnech — β sig. po vol-normalizaci, cost-adjusted expectancy **+4,3 bps net** na large-move dnech (SPY), kladná i v recentním období. Tento nález NEZÁVISÍ na flow vysvětlení a je kandidát na jednorázovou OOS validaci (Fáze E).

---

## 1. Grounding (přesné definice z Projektu 2, apples-to-apples)

- Cutoff **15:00 ET**; `r_pre60` = return 9:30 open → 15:00 (bps); `r_last60` = return 15:00 → 16:00 (bps). Disjunktní okna.
- Projekt 2 „+0,7/−0,7": korelace **roční agree60 rate** (nevážený sign-count) s roční ATR% (+0,7) a s rok-indexem (−0,7). AUM proměnná nikdy neexistovala (QC fundamentals: 0/10 populated) — „H_AUM" byl jen časový trend.

## 2. Krok 1 — signed × velikost test (in-sample, lokální)

| test | SPY (N=1168) | ES (N=1173) |
|---|---|---|
| signed β `last60~pre60` | +0,063, p=5e-6, R²=1,77 % | +0,043, p=0,001, R²=0,87 % |
| **vol-normalizovaná β** (5a) | **+0,049, p=6e-4 → PŘEŽIJE** | **+0,040, p=0,005 → PŘEŽIJE** |
| interakce pre60×vol (5b) | +0,038, p=0,019 (base ns) | +0,018, p=0,247 |
| β jen hi-vol tercina (5c) | +0,080, p=0,001 (lo/mid ns) | +0,056, p=0,014 (lo/mid ns) |
| β jen large-\|pre60\| tercina (5d) | +0,069, p=0,0003 (small/med ns) | +0,047, p=0,006 |
| β 2024–25 (6) | +0,110, p<1e-7, R²=6,5 % | +0,071, p=0,0002 |

**Size-conditioned expectancy (net po 1,2 bps):** small −0,77 / med −0,30 / **large +4,34** (SPY); large & 2021–23 +5,03; large & 2024–25 +2,65. ES obdobně slabší (large +2,90; large & 24–25 +0,11).

**Klíčový reversal vs Projekt 2:** size-weighted β v čase ROSTE (0,02→0,11), zatímco agree60 klesal — nevážený sign-count ředil efekt malými no-flow dny. Lekce: **testuj ve formě, kterou mechanismus predikuje** (signed × size), ne v pohodlné binární formě.

## 3. Krok 1b — flow-timing test (large-move dny)

| sub-okno | SPY β / net exp | ES β / net exp |
|---|---|---|
| 15:00→15:30 (early) | +0,044 (t=4,0) / **+2,82 bps** | +0,042 (t=3,9) / +2,67 |
| 15:30→16:00 (u close) | +0,033 (t=2,8) / +0,35 | +0,013 (**ns**) / −0,95 |

Efekt **slábne ke close** → proti mechanickému „rebalance u close"; slučitelné nanejvýš s anticipací flow. Bez AUM dat nerozhodnutelné → per konzervativní bias NEatribuováno flow.

## 4. Krok 2 — AUM vážení: proč nešel dokončit

- QC fundamentals AUM/shares pro ETF: **0/10 populated** (ověřeno během v Projektu 2).
- `stockanalysis.com` (povolená doména): jen **aktuální** AUM snapshot (SSO $7,5B; UPRO $5,1B; SPXL $6,2B; SDS $0,44B; SPXU $0,52B; SPXS $0,41B; SH $1,1B → K≈99), **žádná historická řada**.
- I s hrubou roční AUM: růst je ~monotónní ⇒ K_t ≈ časový trend ⇒ confounded s časem (už testováno). Rozlišení by vyžadovalo ne-monotónní variaci (creations/redemptions) = placená data.
- Sanity check vzorce: L(L−1) > 0 pro všechny fondy vč. SH (L=−1 → 2), = 0 pro L=1. ✓ (implementace připravena, netestována na datech).

## 5. Verdikt dle předregistrovaného kritéria

- *Podpořeno* vyžadovalo: signed vztah přeživší vol-kontrolu **a ideálně posílený AUM vážením**. První splněno, druhé **nešlo otestovat** → **flow-atribuce NEPODLOŽENÁ** (ne vyvrácená — nerozhodnutelná volnými daty, timing ukazuje proti).
- Rámec „leveraged ETF" si zatím **nevydělal na své místo**: pozorovaný jev je zatím nerozlišitelný od obecného intraday momenta na velkých dnech (známého z literatury).

## 6. Co zbývá reálného: kandidát na OOS

**Mechanické pravidlo (bez kauzálního nároku):** na dnech s |r_pre60| ≥ in-sample large-práh vstup v 15:00 ve směru sign(r_pre60), exit 16:00 close. IS: net +4,3 bps/trade (SPY, n=390), kladné i 2024–25 (+2,5). Jediný čistý test = jednorázová OOS validace (Fáze E, gated, frozen spec — viz `phase_e_frozen_spec.md`).

**Doporučení (jedna věta):** Uzavřít flow-atribuci, size-weighted momentum pravidlo validovat přesně jednou na OOS okně dle zamrazené specifikace a podle výsledku buď zahodit, nebo teprve pak řešit ES překlad.

## 7. Reprodukovatelnost

Log: `results/RESULTS.md` (sekce PROJEKT 2b). Kód: `research/levetf_phase2b/step1.py`. Data: `data/cache/eod_{spy,es}.csv`. AUM snapshot probe: chat log 2026-07-14.
