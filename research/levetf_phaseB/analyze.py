import sys, os
sys.path.insert(0, "research/common")
import pandas as pd, numpy as np
from scipy import stats
from stats import Proportion, fisher_exact, wilson_ci

COST_BPS = {"opt": 0.4, "cons": 1.2}   # ES round-turn v bps (0.2-0.6 pt x 2 bps/pt)

out=[]
for sym in ["ES","SPY"]:
    d = pd.read_csv(f"data/cache/eod_{sym.lower()}.csv", parse_dates=["date"])
    print(f"\n===== {sym} (n={len(d)}) =====")
    for K,pre,last,agree in [(60,"r_pre60","r_last60","agree60"),(30,"r_pre30","r_last30","agree30")]:
        n=len(d); k=int(d[agree].sum()); p=Proportion(n,k)
        pv=stats.binomtest(k,n,0.5).pvalue
        x=d[pre].values; y=d[last].values
        lr=stats.linregress(x,y); r2=lr.rvalue**2
        pnl = np.sign(d[pre]) * d[last]
        exp=pnl.mean(); wins=pnl[pnl>0]; losses=pnl[pnl<0]
        aw=wins.mean() if len(wins) else 0; al=losses.mean() if len(losses) else 0
        print(f" B1/B2 K={K}: agree={100*p.rate:.1f}% CI[{100*p.ci95[0]:.1f},{100*p.ci95[1]:.1f}] n={n} | vs50 p={pv:.4f} {'SIGNIF' if pv<0.05 else 'ns'}")
        print(f"   B3 regrese: slope={lr.slope:.4f} R2={100*r2:.3f}% p={lr.pvalue:.2e}")
        print(f"   B4 expectancy: {exp:+.2f} bps/trade | avg_win={aw:.1f} avg_loss={al:.1f} | net_opt={exp-COST_BPS['opt']:+.2f} net_cons={exp-COST_BPS['cons']:+.2f} bps")
        out.append(dict(sym=sym,test=f"K{K}",n=n,agree=round(100*p.rate,1),ci_lo=round(100*p.ci95[0],1),ci_hi=round(100*p.ci95[1],1),
                        vs50_p=round(pv,4),R2=round(100*r2,3),slope=round(lr.slope,4),exp_bps=round(exp,2),
                        net_opt=round(exp-COST_BPS['opt'],2),net_cons=round(exp-COST_BPS['cons'],2)))
    d["move_norm"]=d.r_pre60.abs()/(d.atr_pct*100)
    d["mb"]=pd.qcut(d.move_norm,3,labels=["small","med","large"])
    print(" B5 conditioning na velikost pohybu (agree60):")
    for b in ["small","med","large"]:
        s=d[d.mb==b]; p=Proportion(len(s),int(s.agree60.sum()))
        print(f"   {b:5s}: agree={100*p.rate:.1f}% CI[{100*p.ci95[0]:.1f},{100*p.ci95[1]:.1f}] n={len(s)}")
        out.append(dict(sym=sym,test=f"B5_{b}",n=len(s),agree=round(100*p.rate,1),ci_lo=round(100*p.ci95[0],1),ci_hi=round(100*p.ci95[1],1)))
    sm=d[d.mb=="small"]; lg=d[d.mb=="large"]
    fp=fisher_exact(int(lg.agree60.sum()),len(lg),int(sm.agree60.sum()),len(sm))
    print(f"   large vs small Fisher p={fp:.4f}")
    out.append(dict(sym=sym,test="B5_large_vs_small_fisherp",vs50_p=round(fp,4)))
pd.DataFrame(out).to_csv("results/levetf_phaseB.csv",index=False)
print("\nuloženo results/levetf_phaseB.csv")
