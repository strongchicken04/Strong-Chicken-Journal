"""A3 — kalendář makro událostí (FOMC / NFP / CPI) 2021–2026.

Výstup: data/cache/a3_calendar.csv  (date, event, approx)

Stav přesnosti:
  - FOMC: EXAKTNÍ rozhodovací dny (2. den zasedání), high-confidence.
  - NFP:  APROXIMACE = první pátek v měsíci (občas 2. pátek kvůli svátkům).
  - CPI:  ZATÍM VYNECHÁNO — bez spolehlivého rozvrhu bych data vymýšlel.
          Doplní se z autoritativního zdroje (BLS) před rozhodovacím
          použitím B7. B7 poběží zatím na FOMC + NFP.
"""
import os
import pandas as pd
from datetime import date, timedelta

# --- FOMC rozhodovací dny (2. den zasedání), 2021–2026 ---
FOMC = [
    # 2021
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16",
    "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
    "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (plán; spadá do OOS okna)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
]


def first_fridays(y0=2021, y1=2026):
    out = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            d = date(y, m, 1)
            # posun na první pátek (weekday 4)
            d += timedelta(days=(4 - d.weekday()) % 7)
            out.append(d.isoformat())
    return out


def build():
    rows = []
    for d in FOMC:
        rows.append({"date": d, "event": "FOMC", "approx": 0})
    for d in first_fridays():
        rows.append({"date": d, "event": "NFP", "approx": 1})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= "2026-07-11"].sort_values(["date", "event"]).reset_index(drop=True)
    os.makedirs("data/cache", exist_ok=True)
    df.to_csv("data/cache/a3_calendar.csv", index=False)
    print(f"A3 kalendář: {len(df)} událostí "
          f"(FOMC={int((df.event=='FOMC').sum())}, NFP={int((df.event=='NFP').sum())})")
    print("CPI: zatím vynecháno (viz docstring).")
    print(df.head(8).to_string(index=False))
    return df


if __name__ == "__main__":
    build()
