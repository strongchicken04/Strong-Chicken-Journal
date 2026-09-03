# PROJEKT 5 — VWAP/VP order-flow setup (reverse-engineering) — KROK 0

Reverse-engineering diskréčního ES setupu uživatele (má reálné prop payouty).

## Klíčový fakt (bod 5 uživatele)
**„Bez konfirmace volume/delta nejdu do tradu."** Vstupy jsou GATOVANÉ order flowem. Tenhle test měří strukturu BEZ toho gate = **kostra**. Očekávaně ~nula (Projekt 1 už holou VWAP ±1σ reverzi na ES ukázal jako coin-flip). Ta nula je NÁLEZ: lokalizuje, jestli edge je ve struktuře, nebo v tapu. Delta samotná jde ověřit jen z tickových dat (Kolej B, zatím neřešeno).

## Zamrazená pravidla (kostra)
- **Instrument:** ES, extended hours.
- **Session VWAP kotvený 18:00 ET** (00:00 Czech = Globex open), reset denně; ±1σ deviation band (HLC3×vol, stejná formule jako Projekt 3).
- **Developing volume profile od 18:00 ET:** POC, VAH, VAL (70% value area, biny 1 bod).
- **Úrovně (6):** VWAP, +1σ, −1σ, POC, VAH, VAL.
- **Okno:** vstupy jen 10:00–16:00 ET (16:00 Czech = 10:00 ET), **max 1 obchod/den** (první trigger za session).
- **Dvě varianty (testované ZVLÁŠŤ, potvrzeno „testuj oba"):**
  - **CONT:** 1-min close ZA ±1σ band → vstup ve směru průrazu.
  - **REV:** 1-min dotyk ±1σ band → vstup zpět k VWAP.
- **Cíl = nejbližší úroveň ve směru obchodu; STOP = fixní 1:1** (stejná vzdálenost opačně). Fill na open další 1-min svíčky.
- **EOD flat 16:00 ET.** Costs 0,4/1,2 bps, verdikt net_cons.
- **Metrika:** net R/obchod + hit rate vs 50 % breakeven (1:1) + per-year + equity curve.

## Co uživatel potvrdil
1. Stop fixní 1:1. ✓
2. Testovat oba vzorce (cont + rev). ✓
3. 6 úrovní = POC, VAH, VAL, VWAP, +1σ, −1σ. ✓
4. Drží minuty, ~1 trade/den. ✓
5. Bez delta konfirmace nevstupuje (→ kostra je test bez gate). ✓

## Disciplína
IS do 2025-09-30. **OOS 2025-10→2026-07 NEDOTČENO.** QC projekt 34197200.
