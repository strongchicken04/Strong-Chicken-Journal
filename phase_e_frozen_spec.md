# FÁZE E — ZAMRAZENÁ SPECIFIKACE (Krok 0)

> **Status:** čeká na výslovné potvrzení této specifikace uživatelem.
> Na OUTCOME data OOS okna (return 15:00→16:00) NEBYLO SÁHNUTO. Jediné, co
> bylo z OOS spočítáno, je N (filtr velikosti pohybu do cutoffu) — což
> neprozrazuje nic o outcome. Skutečný Krok 1 (outcome test) proběhne až
> po potvrzení této specifikace, přesně jednou.

---

## 1. Zamrazené definice (přesně z in-sample Projektu 2b, apples-to-apples)

- **Instrument:** SPY (stejný jako celá in-sample práce). *Překlad na ES je mimo rozsah této fáze.*
- **Cutoff:** 15:00 ET.
- **`day_return_to_cutoff` (= r_pre60):** return od 9:30 open do 15:00 close, v bps: `(P_15:00 / P_9:30_open − 1) × 10000`.
- **`last60_return` (= r_last60):** return od 15:00 do 16:00 close, v bps: `(P_16:00 / P_15:00 − 1) × 10000`. *(outcome — v Kroku 0 nečteno)*
- **„Velko-pohybový den":** `|r_pre60| ≥ 62,1987 bps`. Tento práh je **in-sample 2/3 kvantil** `|r_pre60|` (horní tercil, na kterém Krok 1 odhalil signifikantní size-weighted β). **Zamrazeno jako fixní bps hodnota** — na OOS se NEpřepočítávají terciny (to by byl data-dependent leak).

**Statistický základ (in-sample), který pravidlo ospravedlňuje (NEmění se):**
signed regrese `r_last60 ~ r_pre60`: β=+0,063, p=5e-6; **přežije vol-normalizaci** (β=+0,049, p=6e-4); signifikance koncentrovaná v horním tercilu `|r_pre60|` (β=+0,069, p=0,0003).

## 2. Zamrazené mechanické obchodní pravidlo

Pro každý OOS obchodní den:
1. V 15:00 spočítej `r_pre60`.
2. **Podmínka vstupu:** pokud `|r_pre60| ≥ 62,1987 bps` → obchoduj; jinak nic (žádný obchod).
3. **Směr:** `sign(r_pre60)` — long když trh do 15:00 vzrostl, short když klesl.
4. **Vstup:** v 15:00 (na close 15:00 baru).
5. **Velikost pozice:** konstantní 1 jednotka notional na obchod (žádné vol-scaling, žádný Kelly). Expectancy se měří v bps notional na obchod.
6. **Výstup:** 16:00 close (fixní čas, žádný pohyblivý cíl, žádný stop — v souladu s in-sample specifikací; symetrický win/loss framing).
7. **P&L na obchod (bps):** `sign(r_pre60) × r_last60`.

**Cost model (stejný jako in-sample):** round-turn `0,4 bps` (optimistický) / `1,2 bps` (konzervativní). Net expectancy = gross − cost.

## 3. N v OOS okně (2025-10-01 → 2026-07-11) — outcome-blind

- OOS obchodních dní (validní open+15:00): **134**
- **N (velko-pohybové dny, |r_pre60| ≥ 62,20 bps): 46** (≈ 34 %, sedí na in-sample 1/3 tercil)
- N = 46 je **nad hranicí ~15–20** → test má rozumnou (ne obří) sílu. Striktní p<0,05 nebude spolehlivé; rozhoduje kombinované kritérium níže.

## 4. In-sample reference (pro srovnání magnitudy — NEmění se)

| skupina | n | win rate | net_cons expectancy |
|---|---|---|---|
| SPY large-move (celé IS) | 390 | 57,4 % | **+4,30 bps** |
| SPY large-move & 2024–25 | 113 | — | +2,52 bps |

## 5. Pass/fail kritérium (STANOVENO TEĎ, před Krokem 1)

- **Podpořeno:** stejné znaménko jako in-sample (kladná expectancy směrem sign(r_pre60)), net_cons expectancy kladná (nebo jasně ne záporná), magnitude v rozumném řádu vůči IS (~+1 až +8 bps net — ne řádově jiná).
- **Nepodpořeno:** opačné znaménko, jasně záporná net_cons expectancy, nebo magnitude, co s IS prakticky nesouvisí.
- **Nejednoznačné (přijatelný výsledek):** N/rozptyl tak, že ani znaménko není spolehlivě čitelné → napsat přesně takto, neinterpretovat silněji.

## 6. Protokol jednorázovosti

- Krok 1 aplikuje pravidlo z §2 mechanicky na celé OOS okno **přesně jednou**.
- Reportuje: win rate + Wilson CI, gross/net expectancy, per-trade Sharpe (mean/std), směrová konzistence s IS.
- **Žádné iterování.** Ať výsledek vyjde jakkoliv, je to odpověď — ne signál měnit práh/okno/cokoliv a spouštět znovu.
- Outcome OOS okna se po Kroku 1 považuje za spotřebovaný.
