"""Sdílené statistické utility pro celý výzkum (Fáze 0–E).

Globální pravidlo 3: u každého win rate uvádět n a Wilson score 95% CI;
pro porovnání dvou skupin Fisherův exact test.
Globální pravidlo 4: n < 30 je jen orientační.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from scipy import stats

MIN_SAMPLE = 30  # pravidlo 4: pod tímto je výsledek jen orientační


@dataclass
class Proportion:
    n: int
    k: int  # počet úspěchů (např. inside, nebo win)

    @property
    def rate(self) -> float:
        return self.k / self.n if self.n else float("nan")

    @property
    def ci95(self) -> tuple[float, float]:
        return wilson_ci(self.k, self.n, 0.95)

    @property
    def reliable(self) -> bool:
        return self.n >= MIN_SAMPLE

    def fmt(self, pct: bool = True) -> str:
        lo, hi = self.ci95
        if pct:
            base = f"{100*self.rate:.2f}% [{100*lo:.2f}%, {100*hi:.2f}%] (n={self.n})"
        else:
            base = f"{self.rate:.4f} [{lo:.4f}, {hi:.4f}] (n={self.n})"
        if not self.reliable:
            base += " ⚠️<30"
        return base


def wilson_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval pro binomický podíl. Vrací (low, high) jako podíly."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def fisher_exact(k1: int, n1: int, k2: int, n2: int,
                 alternative: str = "two-sided") -> float:
    """Fisherův exact test pro 2x2 tabulku: skupina1 (k1 úspěchů z n1) vs
    skupina2 (k2 z n2). Vrací p-hodnotu. Vhodné i pro malé vzorky."""
    table = [[k1, n1 - k1], [k2, n2 - k2]]
    _, p = stats.fisher_exact(table, alternative=alternative)
    return p


def ci_overlap(ci_a: tuple[float, float], ci_b: tuple[float, float]) -> bool:
    """True pokud se dvě CI překrývají (pro řazení dle významnosti ve Fázi D)."""
    lo_a, hi_a = ci_a
    lo_b, hi_b = ci_b
    return not (hi_a < lo_b or hi_b < lo_a)


if __name__ == "__main__":
    # rychlý self-test proti referenci: SPY 81,53 % inside při n~?
    p = Proportion(n=1000, k=815)
    print("demo:", p.fmt())
    print("wilson(815,1000):", wilson_ci(815, 1000))
    print("fisher(815/1000 vs 522/1000):", fisher_exact(815, 1000, 522, 1000))
