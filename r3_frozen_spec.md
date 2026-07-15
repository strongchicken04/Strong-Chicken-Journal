# R3 — ZAMRAZENÁ SPECIFIKACE: one-shot OOS validace NQ VWAP trend strategie

> **Status:** čeká na výslovné potvrzení uživatele. Na OOS okno (2025-10-01 → 2026-07-11)
> nebylo touto strategií sáhnuto. Po potvrzení proběhne PŘESNĚ JEDEN běh; žádný parametr
> se po pohledu na výsledek nemění; žádné iterování. (Přiznání: okno vidělo jeden pohled
> jiné signálové rodiny — 2b Fáze E, last-hour momentum na 46 dnech; pro VWAP trend
> rodinu prakticky nekontaminující, ale uvádíme.)

## 1. Zamrazená pravidla strategie (z R4b, beze změny)

- **Instrument:** NQ (E-mini Nasdaq-100), kontinuální kontrakt: mapping OpenInterest,
  normalizace BackwardsRatio, depth 0, `extended_market_hours=False`.
- **Session/VWAP:** RTH 9:30–16:00 ET; session VWAP = Σ(HLC/3 × V)/Σ(V), denní reset,
  jen RTH minutové bary (první bar končí 9:31).
- **Hysterezní pásmo (FROZEN): b = 20 bps.** `up = VWAP×1,0020`, `dn = VWAP×0,9980`.
- **Vstup (z flat, včetně prvního vstupu dne):** close baru > up → long; close < dn → short.
  První bar dne, jehož close je za pásmem, spouští vstup (nemusí to být 9:31 bar).
- **Flip:** long a close < dn → přímý flip na short (ne na flat); short a close > up → flip long.
  Pouhý návrat k VWAP nebo intra-bar průnik NIC nespouští — jen close za pásmem.
- **Exekuce:** fill na open následujícího baru. **EOD:** vše flat na close 16:00 baru;
  half-day/gap → force close na close posledního dostupného baru dne. Žádné overnight.
- **Pozice:** 100 % NAV notional (frakčně) × vol-target koeficient (viz §3), plný reinvest.

## 2. Cost model NQ (VÝSLOVNĚ, frozen)

Model **0,4 bps (optimistický) / 1,2 bps (konzervativní) notional round-turn na obchod**
(zavedený model z Fáze E, beze změny). Aplikace: `net_daily = gross_daily − trades_daily × cost/10⁴`
na denní řadě (aditivně, stejně jako ve všech IS výpočtech R2–R4).

Sanity-check vůči realitě NQ (odhad, NENÍ součást modelu): komise retail ~$2,5–5 RT na
notional ~$450–520k → ~0,05–0,1 bps; slippage 0,5–2 ticky/side (tick 0,25 b) → ~0,1–0,4 bps
RT; realisticky celkem ~0,15–0,5 bps RT ⇒ **cons 1,2 bps je ~2–8× konzervativní** (záměrně,
preferovaný podhodnocující bias). Primární rozhodovací scénář = **net_cons (1,2)**.

## 3. Vol-targeting (VÝSLOVNĚ, frozen — přesná formule)

Aplikuje se **lokálně na denní net return řadu** (identicky s tím, jak vznikla IS reference):

1. Pro cost scénář c: `r_net(t) = r_gross(t) − n_trades(t)·c/10⁴`
2. Odhad volatility: `σ_ann(t) = EWMA_std(r_net; span=20).shift(1) × √252`
   — pandas `Series.ewm(span=20, adjust=True).std()` (bias-korigovaná), **shift(1)** =
   k dimenzování dne t se používá jen historie do t−1 (look-ahead-free).
3. Koeficient: **`lev(t) = min(1.0, 0.15 / σ_ann(t))`**; kde σ_ann není definována
   (první ~2 dny okna), `lev = 1.0`. EWMA startuje UVNITŘ OOS okna (self-contained,
   žádné IS dávky do odhadu).
4. Realizovaný denní return: `r_vt(t) = lev(t) × r_net(t)`. Cap 1,0 = nikdy víc než
   100 % NAV notional, žádná páka; koeficient jen de-riskuje vysokovolatilní období.
5. Interpretace pro obchodování: `lev(t)` = frakce NAV nasazená ten den jako notional
   (kontrakty = lev×NAV/(cena×multiplikátor), frakčně — bez celočíselného zaokrouhlení,
   stejně jako celá IS analýza; pozn. k živému nasazení: 1 MNQ ≈ $50k notional ⇒ prakticky
   vyžaduje NAV řádu ≥$50k, jinak lumpy sizing — netýká se této validace).

## 4. OOS protokol

- **Okno:** 2025-10-01 → 2026-07-11 (~197 obchodních dní; očekávám ~490 obchodů při
  IS frekvenci 2,5/den — odhad z IS, NEměřeno na OOS).
- **Běh:** jeden QC backtest (gross NAV + trades/den export), costs + VT lokálně dle §2–3.
  Žádný outcome-blind předkrok (strategie obchoduje ~denně, N není selektivní filtr).
- **Report (předregistrováno):** total return net_cons+VT15 (PRIMÁRNÍ), + varianty
  (gross, net_opt, plná pozice), trades/den, hit ratio, MDD, denní Sharpe, srovnání s IS.

## 5. IS reference (pro srovnání, NEmění se)

net_cons + VT15: **CAGR +9,6 %, Sharpe 0,74, MDD 12,2 %**, ~2,5 obch./den, hit 36,9 %;
éra1 (2022–25) net_cons +6,0 % p.a. → pro 9,4měsíční okno implikuje ~**+4,7 %**.

## 6. Pass/fail kritérium (STANOVENO TEĎ)

⚠️ **Přiznaná síla testu:** 9,4měsíčního okno u strategie s IS Sharpe 0,74 dává očekávané
t ≈ 0,74×√0,78 ≈ 0,65 — okno NEMŮŽE statisticky potvrdit signifikanci ani u reálného
edge. Kritérium je proto znaménko+magnitude, ne p-hodnota:

- **Podpořeno:** net_cons+VT15 total return za okno **> 0** (a gross edge kladný),
  magnitude řádově slučitelná s IS (mezi ~0 a ~+15 % za okno; ne řádově jiná).
- **Nepodpořeno:** net_cons+VT15 **< −5 %** za okno, nebo gross edge záporný
  (strategie prodělává už před náklady).
- **Nejednoznačné (přijatelný výsledek):** mezi −5 % a 0 — malé okno, malá síla; napsat
  přesně takto, neinterpretovat silněji. Rozhodnutí o nasazení by pak vyžadovalo delší
  paper-trading, ne další testy na tomto okně.

## 7. Jednorázovost

Jeden běh. Ať vyjde cokoliv, je to odpověď — žádná změna pásma, targetu, okna či nákladů
a opakování. Po běhu se OOS okno považuje za spotřebované i pro tuto rodinu.
