"""FÁZE D — funnel na C1 VWAP reverzi. Lokální analýza cross-tabu z logu.
C1 base -> +C3 timing (blok/regime) -> +C4 overnight, upper/lower zvlášť."""
import re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import pandas as pd, numpy as np
from stats import Proportion, fisher_exact

log = open("/tmp/claude-0/-home-user-Strong-Chicken-Journal/9ee1f942-bbd3-5dcd-beb3-ee96acbd0a44/scratchpad/phaseD_log.txt").read().splitlines()
rows = []
for l in log:
    m = re.search(r'###D### b=(\d) s=(\w+) blk=(\d+) ot=(\d+) n=(\d+) rev=(\d+)', l)
    if m:
        rows.append(dict(band=int(m[1]), side=m[2], block=int(m[3]), ot=int(m[4]),
                         n=int(m[5]), rev=int(m[6])))
df = pd.DataFrame(rows)
df.to_csv("results/phaseD_cells.csv", index=False)
print("cells:", len(df), "| total events:", df.n.sum())

REGIME = {**{b: "morning(10-12)" for b in [1,2,3,4]},
          **{b: "lull(12-14)" for b in [5,6,7,8]},
          **{b: "afternoon(14-16)" for b in [9,10,11,12]}}
df["regime"] = df.block.map(REGIME)

def agg(sub):
    n = int(sub.n.sum()); rev = int(sub.rev.sum())
    return Proportion(n, rev)

def line(label, p, base=None, comp=None):
    s = f"  {label:28s} {p.fmt()}"
    if base is not None and base.n:
        s += f"  Δ={100*(p.rate-base.rate):+.1f}pp"
    if comp is not None and comp.n and p.n:
        s += f"  Fisher_p={fisher_exact(p.k,p.n,comp.k,comp.n):.4f}"
    return s

OUT = []
def emit(s): print(s); OUT.append(s)

emit("\n===== FÁZE D FUNNEL — C1 ±1 VWAP reverze (ES) =====")
b1 = df[df.band == 1]
# LEVEL 1: base per side
emit("\n--- Level 1: C1 base (±1) ---")
base = {}
for side in ["upper", "lower"]:
    p = agg(b1[b1.side == side]); base[side] = p
    emit(line(f"{side}", p))
emit(line("upper vs lower (Fisher)", base["upper"], comp=base["lower"]))

# LEVEL 2: + C3 timing (regime), per side
emit("\n--- Level 2: +C3 timing (regime), upper/lower zvlášť ---")
l2 = {}
for side in ["upper", "lower"]:
    emit(f" [{side}] base={100*base[side].rate:.1f}%")
    for reg in ["morning(10-12)", "lull(12-14)", "afternoon(14-16)"]:
        sub = b1[(b1.side == side) & (b1.regime == reg)]
        rest = b1[(b1.side == side) & (b1.regime != reg)]
        p = agg(sub); l2[(side, reg)] = p
        flag = "  ⚠️n<40" if p.n < 40 else ""
        emit(line(reg, p, base=base[side], comp=agg(rest)) + flag)

# per-block detail (kvůli přesnému timing profilu)
emit("\n--- Level 2b: per-block win rate (±1) ---")
for side in ["upper", "lower"]:
    parts = []
    for blk in range(1, 13):
        sub = b1[(b1.side == side) & (b1.block == blk)]
        p = agg(sub)
        parts.append(f"blk{blk}:{100*p.rate:.0f}%(n{p.n})")
    emit(f" [{side}] " + " ".join(parts))

# LEVEL 3: + C4 overnight, within best-looking regime per side
emit("\n--- Level 3: +C4 overnight tercina (v rámci regime) ---")
for side in ["upper", "lower"]:
    for reg in ["morning(10-12)", "lull(12-14)", "afternoon(14-16)"]:
        base_reg = l2[(side, reg)]
        cells = []
        for ot in [0, 1, 2]:
            sub = b1[(b1.side == side) & (b1.regime == reg) & (b1.ot == ot)]
            p = agg(sub)
            cells.append((ot, p))
        # jen pokud aspoň jedna buňka >=40
        emit(f" [{side} / {reg}] base={100*base_reg.rate:.1f}%(n{base_reg.n}):")
        for ot, p in cells:
            lbl = {0:"on_small",1:"on_med",2:"on_large"}[ot]
            flag = "  ⚠️n<40" if p.n < 40 else ("  ⚠️n<30" if p.n<30 else "")
            emit(line(f"   {lbl}", p, base=base_reg) + flag)

open("results/phaseD_funnel.txt", "w").write("\n".join(OUT))
print("\nuloženo results/phaseD_funnel.txt + results/phaseD_cells.csv")
