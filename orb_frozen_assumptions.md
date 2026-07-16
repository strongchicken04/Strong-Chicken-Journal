# PROJEKT 4 — Opening Range Breakout (15min, ATR SL/TP) — KROK 0: ZAMRAZENÉ PŘEDPOKLADY

> **Status:** čeká na výslovné potvrzení uživatelem. **Žádný backtest kód se nepíše, dokud tohle nepotvrdíš.**
> Tohle NENÍ nevratný OOS krok (jako Fáze E / R3) — smyslem je jen nezačít kódovat na špatně pochopeném zadání.
> Research anchor: Zarattini/Barbon & Aziz ORB studie; navazuje na plánovanou „Strategy 2: Opening Range Breakout" z Pine poznámek. **První skutečné rozpracování.**

---

## 0. Design note, kterého jsem si všiml (a musí ho report zohlednit)

**SL = 2×ATR, TP = 1×ATR ⇒ risk:reward 2:1 V NEPROSPĚCH.** V R-jednotkách (R = riziko = 2×ATR): každá **výhra = +0,5R**, každá **prohra = −1,0R** (před náklady). Breakeven hit rate:

`p × 0,5R = (1−p) × 1,0R  ⇒  1,5p = 1  ⇒  p = 66,7 %`

**Tahle konfigurace potřebuje hit rate > ~67 % (před náklady), ne > 50 %.** Hit ratio pod 67 % s tímhle nastavením = **automaticky ztrátová strategie i před náklady** — bez ohledu na to, jak „hezky" vypadá equity křivka na krátkém vzorku. Report u výsledků bude hit ratio explicitně srovnávat s tímhle 67% prahem (ne s 50 %). Není to nutně špatný design (pokud je continuation po potvrzeném breakoutu opravdu spolehlivý, tight TP dává smysl), ale je to **vědomá, náročná podmínka**.

---

## 1–5. Odpovědi na Krok-0 body (žádné tiché defaulty)

### 1. Instrument — **ES** (potvrzuji tvůj předpoklad)
- ES (E-mini S&P 500 futures), kontinuální kontrakt: `add_future(Futures.Indices.SP_500_E_MINI, resolution=Resolution.MINUTE, data_mapping_mode=DataMappingMode.OPEN_INTEREST, data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO, contract_depth_offset=0, extended_market_hours=False)`, `set_time_zone(TimeZones.NEW_YORK)`.
- **Poznámka/varování:** Projekt 3 zjistil, že trend-continuation edge se z NQ na ES **nepřeložil** (ES/SPY net záporné). ORB je taky momentum-continuation rodina. Neznamená to, že ORB na ES nefunguje (jiný setup, jiná mikrostruktura otevírání), ale **navrhuji jako robustness přidat NQ jako sekundární instrument** (stejná mechanika, jen jiný symbol) — apples-to-apples, ať vidíme, jestli je případný edge ES-specifický nebo obecný. Toto je návrh, ne změna zadání; hlavní instrument zůstává ES dle tebe.

### 2. ATR timeframe — **ATR(14) na 15-min chartu** (potvrzuji)
- ATR(14), Wilder, počítané na **15-min RTH svíčkách** (stejný chart, na kterém běží signální logika), NE denní ATR.
- Hodnota ATR použitá pro obchod = ATR(14) **k close signální svíčky** (poslední dokončená 15-min svíčka, která zavřela mimo range). Fixní pro celý obchod (SL/TP hladiny se během obchodu nemění). Look-ahead-free (jen dokončené svíčky).

### 3. TP mode — **ATR (1×ATR), „TP Fixed Ticks: 20" se IGNORUJE** (potvrzuji)
- Aktivní: `ATR TP Multiplier = 1` ⇒ TP = entry ± 1×ATR (ve směru obchodu).
- „TP Fixed Ticks: 20" je UI pole, které se při Mode=ATR **nepoužije**. Pokud bys chtěl fixních 20 ticků místo ATR TP, je to **jiná strategie** (fixní vs. proporční cíl) — řekni to explicitně a zamrazím jinak.

### 4. Fill timing — **vstup na OPEN další svíčky, SL/TP aktivní od vstupu** (návrh)
- **Signál:** 15-min svíčka ZAVŘE mimo OR range (close > OR_high → long; close < OR_low → short).
- **Vstup:** na **open NÁSLEDUJÍCÍ 15-min svíčky** (ne na close signální svíčky). Konzistentní s celým dosavadním výzkumem (Projekt 3: „fill on next bar's open") a look-ahead-free.
- **SL/TP hladiny:** spočítané z entry ceny a ATR k signálnímu close; **aktivní od okamžiku vstupu**, tj. kontrolují se na high/low téže vstupní svíčky (od jejího open) i všech následujících.
- **Intrabar fill:** TP = limit (fill na přesné TP ceně, když bar.high ≥ TP pro long / bar.low ≤ TP pro short); SL = stop (fill na SL ceně, slippage schovaná v cost modelu).
- **Ambiguita, když jedna svíčka protne SL i TP** (rozpětí ≥ 3×ATR kolem entry): **konzervativně předpokládám SL first** (pesimistické — aby se edge nenafoukl). Zaznamenám počet takových svíček zvlášť (mělo by být vzácné).

### 5. News filtr — zdroj a přesná definice (ROZHODNUTÍ POTŘEBUJI OD TEBE)
**Problém:** všechny živé economic-calendar zdroje jsou teď **blokované síťovou politikou** (ověřeno, HTTP 403 CONNECT denial):
- `nfs.faireconomy.media` (Forex Factory JSON mirror) → 403
- `www.forexfactory.com/calendar` → 403
- `api.stlouisfed.org` (FRED) → 403

Navíc FF JSON mirror dává jen **aktuální/blízký týden**, ne historii 2018–2025 (pro IS backtest nepoužitelné), a FRED dává release **datumy**, ne intradenní **časy**.

**Navrhované varianty (vyber jednu):**

- **A) [DOPORUČENO — funguje bez sítě, plně reprodukovatelné] Deterministický statický kalendář** pravidelných 10:00 ET US makro releasů, vygenerovaný z jejich známých plánovacích pravidel a commitnutý jako `data/cache/econ_calendar_1000et.csv`. „News day" = den s ≥1 takovým releasem naplánovaným na **≥10:00 ET**. Zahrnuté série (spolehlivě plánované, market-moving, 10:00 ET, pravidlově odvoditelné datum):
  - **ISM Manufacturing PMI** — 1. obchodní den v měsíci, 10:00
  - **ISM Services PMI** — 3. obchodní den v měsíci, 10:00
  - **CB Consumer Confidence** — poslední úterý v měsíci, 10:00
  - **UoM Consumer Sentiment** — prelim (2. pátek) + final (4./poslední pátek), 10:00
  - *(Omezení: JOLTS a home-sales série mají nepravidelná data, která nejdou čistě pravidlově odvodit — v této variantě NEJSOU zahrnuty. Jsou to méně předvídatelné releasy; ISM je zdaleka nejsilnější 10:00 event a ten pokryt je.)*
- **B) Přidáš do síťové politiky doménu s historickým kalendářem** (jako jsi přidal stockanalysis.com) → stáhnu reálný historický kalendář. Ale pozor: volně dostupná historie s intradenními časy je vzácná (FF nemá čistý bulk export historie); reálně bych stejně skončil u rekonstrukce z pravidel. **Nižší poměr přínos/práce než A.**
- **C) [METODICKY ČISTÉ] Core ORB nejdřív BEZ news filtru** (baseline), news filtr přidat až jako **sensitivity vrstvu** na vybraném zdroji. Výhoda: uvidíme, jestli filtr vůbec pomáhá a jestli edge nestojí a nepadá na filtru (neměl by — filtr má být refinement, ne load-bearing). Tohle bych stejně dělal i u varianty A.

**Můj default, pokud neřekneš jinak: A + C** — postavím core ORB, změřím baseline bez filtru, a pak přidám deterministický 10:00-ET filtr (varianta A) jako druhou vrstvu a porovnám. **Impact threshold:** high-impact 10:00-ET série výše. Pokud chceš i Medium-impact nebo i JOLTS/home sales, potřebuju variantu B (síť).

---

## 6. Další mechanika, kterou NEnechávám tiše (no silent defaults)

- **Opening range:** high & low prvních DVOU 15-min svíček po 9:30 ET → okno **9:30–10:00 ET** (svíčky 9:30–9:45 a 9:45–10:00). OR_high = max(high obou), OR_low = min(low obou). Fixní po zbytek dne.
- **První eligible signální svíčka:** 10:00–10:15 (zavírá 10:15). Dřív ne (OR se teprve dotváří).
- **Max 1 obchod/den:** jen **PRVNÍ** 15-min close mimo range spustí vstup. Po výstupu (SL/TP/EOD) se ten den už znovu nevstupuje. Když OR do konce dne nikdy neprorazí → žádný obchod ten den.
- **Směr:** long při close > OR_high; short při close < OR_low.
- **EOD flat:** pokud SL ani TP nedojde, pozice se zavře na **16:00 ET close** (market-on-close). Žádné držení přes noc.
- **Session:** jen RTH 9:30–16:00 ET, bez extended hours (konzistentní s Projektem 3).
- **Sizing:** primární metriky (hit rate, R-multiple expectancy) jsou **sizing-independent** — to je jádro. Pro equity křivku (CAGR/Sharpe/MDD): **fixed-fractional risk 1 % equity na obchod** (dollar risk = 0,01×equity, počet jednotek = risk$ / (2×ATR×point_value)), **cap notional ≤ 1× equity** (bez páky, konzistentní s VT projektem), bez intraday compoundingu (equity update po uzavření obchodu). Risk 1 % je explicitní volba, ne tichý default — řekni, když chceš jinak.
- **ATR seed:** ATR(14) potřebuje 14 dokončených 15-min svíček; warm-up přeskočí obchody, dokud není ATR platné (první ~den). Kontinuální přes dny (Wilder rolling).
- **Look-ahead disciplína:** OR, ATR i signál jen z DOKONČENÝCH svíček; vstup až na open další svíčky.

## 7. Náklady (konzistentní s Projekty 1–3)
- Round-turn **0,4 bps (optimistický) / 1,2 bps (konzervativní)**, aplikované per obchod (entry+exit), na výnos obchodu. Při ES ~5000 je 1,2 bps ≈ 0,6 bodu ≈ 2,4 ticku round-turn — realistické konzervativní pro 1-lot ES (sedí na odhad v `PLAYBOOK.md §5`). Primární verdikt dle **net_cons (1,2 bps)**.

## 8. Backtesting disciplína
- **IS vývoj/tuning:** data do **~2025-09-30** (stejná hranice jako Projekty 1–3).
- **OOS okno (2025-10-01 → 2026-07-11): ROZHODNUTÍ ODLOŽENO — NESPOTŘEBOVÁNO.** Okno už bylo použité 2× (Projekt 2b Fáze E, Projekt 3 R3); třetí použití pro filozoficky **podobnou** (breakout/momentum-continuation) rodinu by stálo na tenčím ledě než dřívější „jiná rodina" argument. **Nerozhoduje se teď.** Do doby, než bude IS hotové, může přibýt i nová fresh data. Žádný běh na OOS bez samostatné gated ceremonie s tvým výslovným souhlasem.

## 9. Metriky, které report vydá (IS)
CAGR, Sharpe, MDD, **hit ratio + Wilson CI**, **hit ratio vs. 67% breakeven práh** (explicitně), obchodů/den, průměrné R-multiple na obchod, gross/net_opt/net_cons expectancy, rozklad výher/proher (avg win +0,5R vs avg loss −1R kontrola), počet „ambiguous SL&TP v jedné svíčce" svíček, ES vs (volitelně) NQ. Výstup do **`PLAYBOOK_orb.md`** s jasně označeným „**OOS rozhodnutí odloženo — nespotřebováno**".

---

## ✅ ČEKÁ NA POTVRZENÍ
Potvrď body 1–4 (nebo oprav) a **hlavně rozhodni bod 5** (varianta A / B / C, impact threshold). Pak teprve píšu kód.
