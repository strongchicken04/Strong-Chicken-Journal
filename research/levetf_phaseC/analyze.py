import sys; sys.path.insert(0,"research/common")
import pandas as pd, numpy as np
from scipy import stats
from stats import Proportion, fisher_exact
COST={"opt":0.4,"cons":1.2}
out=[]
for sym in ["ES","SPY"]:
    d=pd.read_csv(f"data/cache/eod_{sym.lower()}.csv",parse_dates=["date"])
    print(f"\n===== {sym} — C1 per-year (K=60) =====")
    print(f"{'rok':6s}{'n':>5s}{'agree60':>9s}{'95% CI':>16s}{'exp_bps':>9s}{'net_cons':>9s}{'avg_atr%':>9s}{'avg|move|bps':>13s}")
    yr_stats={}
    for y,g in d.groupby("year"):
        n=len(g); k=int(g.agree60.sum()); p=Proportion(n,k)
        pnl=np.sign(g.r_pre60)*g.r_last60; exp=pnl.mean()
        atr=g.atr_pct.mean(); mv=g.r_pre60.abs().mean()
        yr_stats[int(y)]=dict(n=n,agree=100*p.rate,exp=exp,atr=atr,mv=mv)
        print(f"{int(y):<6d}{n:>5d}{100*p.rate:>8.1f}%  [{100*p.ci95[0]:>4.1f},{100*p.ci95[1]:>4.1f}]{exp:>+8.2f}{exp-COST['cons']:>+9.2f}{atr:>8.2f}%{mv:>12.1f}")
        out.append(dict(sym=sym,test=f"year{int(y)}",n=n,agree=round(100*p.rate,1),exp_bps=round(exp,2),avg_atr=round(atr,2),avg_move=round(mv,1)))
    # early vs late Fisher
    early=d[d.year.isin([2021,2022,2023])]; late=d[d.year.isin([2024,2025])]
    fe=fisher_exact(int(late.agree60.sum()),len(late),int(early.agree60.sum()),len(early))
    pe=Proportion(len(early),int(early.agree60.sum())); pl=Proportion(len(late),int(late.agree60.sum()))
    print(f"  EARLY 21-23: {100*pe.rate:.1f}% (n={len(early)}) vs LATE 24-25: {100*pl.rate:.1f}% (n={len(late)}) | Fisher p={fe:.4f}")
    # exp per group
    for name,gg in [("early21-23",early),("late24-25",late)]:
        pnl=np.sign(gg.r_pre60)*gg.r_last60
        print(f"    {name}: expectancy={pnl.mean():+.2f} bps net_cons={pnl.mean()-COST['cons']:+.2f}")
    out.append(dict(sym=sym,test="early_vs_late_fisherp",agree=round(100*pl.rate,1),exp_bps=round((np.sign(late.r_pre60)*late.r_last60).mean(),2),vs50=round(fe,4)))
    # C: koreluje rocni agree s rocni volatilitou (H_vol) nebo s casem (H_AUM)?
    yrs=sorted(yr_stats); ag=[yr_stats[y]['agree'] for y in yrs]
    atrs=[yr_stats[y]['atr'] for y in yrs]; tt=list(range(len(yrs)))
    print(f"  H_vol: corr(rocni agree, rocni ATR%) = {np.corrcoef(ag,atrs)[0,1]:+.2f}")
    print(f"  H_AUM: corr(rocni agree, cas/rok)     = {np.corrcoef(ag,tt)[0,1]:+.2f}")
pd.DataFrame(out).to_csv("results/levetf_phaseC.csv",index=False)
print("\nC3 vzorky: 2024 n~252, 2025 n~186 (obe >30). late 24-25 n~438.")
print("uloženo results/levetf_phaseC.csv")
