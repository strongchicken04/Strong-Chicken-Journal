import sys; sys.path.insert(0,"research/common")
import pandas as pd, numpy as np
from scipy import stats
COST_BPS_CONS=1.2; COST_BPS_OPT=0.4

def ols(y, X):
    """X vcetne intercept sloupce. vrati beta, se, t, p, R2."""
    X=np.asarray(X,float); y=np.asarray(y,float)
    beta,_,_,_=np.linalg.lstsq(X,y,rcond=None)
    resid=y-X@beta; n,k=X.shape
    dof=n-k; s2=(resid@resid)/dof
    XtX_inv=np.linalg.inv(X.T@X)
    se=np.sqrt(np.diag(s2*XtX_inv))
    t=beta/se; p=2*(1-stats.t.cdf(np.abs(t),dof))
    ss_tot=((y-y.mean())**2).sum(); r2=1-(resid@resid)/ss_tot
    return beta,se,t,p,r2

for sym in ["SPY","ES"]:
    d=pd.read_csv(f"data/cache/eod_{sym.lower()}.csv",parse_dates=["date"])
    x=d.r_pre60.values; y=d.r_last60.values; vol=d.atr_pct.values
    print(f"\n########## {sym} (N={len(d)}) ##########")
    # (3) signed regrese last60 ~ pre60
    b,se,t,p,r2=ols(y, np.c_[np.ones(len(x)), x])
    print(f"[3] last60 ~ pre60:        beta={b[1]:+.5f}  t={t[1]:+.2f}  p={p[1]:.2e}  R2={100*r2:.3f}%")
    # (4) |last60| ~ vol (baseline magnitude)
    b4,_,t4,p4,r24=ols(np.abs(y), np.c_[np.ones(len(x)), vol])
    print(f"[4] |last60| ~ atr%:        beta={b4[1]:+.3f}  t={t4[1]:+.2f}  p={p4[1]:.2e}  R2={100*r24:.3f}%  (vol-clustering baseline)")
    # (5a) vol-normalized: (last60/vol) ~ (pre60/vol)
    yn=y/vol; xn=x/vol
    b5,se5,t5,p5,r25=ols(yn, np.c_[np.ones(len(x)), xn])
    print(f"[5a] vol-NORM last60 ~ pre60: beta={b5[1]:+.5f}  t={t5[1]:+.2f}  p={p5[1]:.2e}  R2={100*r25:.3f}%  <- prezije β vol-normalizaci?")
    # (5b) interakce: last60 ~ pre60 + pre60*vol + vol
    Xi=np.c_[np.ones(len(x)), x, x*vol, vol]
    bi,sei,ti,pi,r2i=ols(y, Xi)
    print(f"[5b] +interakce: pre60 base beta={bi[1]:+.5f} (t={ti[1]:+.2f} p={pi[1]:.3f}) | pre60xvol beta={bi[2]:+.5f} (t={ti[2]:+.2f} p={pi[2]:.3f})")
    # (5c) beta po vol tercinach
    d['volb']=pd.qcut(d.atr_pct,3,labels=['loVol','midVol','hiVol'])
    print("[5c] beta v vol-tercinach:")
    for vb in ['loVol','midVol','hiVol']:
        g=d[d.volb==vb]; bb,_,tt,pp,rr=ols(g.r_last60.values, np.c_[np.ones(len(g)), g.r_pre60.values])
        exp=(np.sign(g.r_pre60)*g.r_last60).mean()
        print(f"     {vb}: n={len(g)} beta={bb[1]:+.4f} t={tt[1]:+.2f} p={pp[1]:.3f} | exp={exp:+.2f}bps net_cons={exp-COST_BPS_CONS:+.2f}")
    # (5d) beta po |pre60| tercinach (skaluje s velikosti?)
    d['mb']=pd.qcut(d.r_pre60.abs(),3,labels=['small','med','large'])
    print("[5d] beta po |pre60| tercinach (flow predikuje ~konstantni beta):")
    for mb in ['small','med','large']:
        g=d[d.mb==mb]; bb,_,tt,pp,rr=ols(g.r_last60.values, np.c_[np.ones(len(g)), g.r_pre60.values])
        print(f"     {mb}: n={len(g)} beta={bb[1]:+.4f} t={tt[1]:+.2f} p={pp[1]:.3f}")
    # (6) regime: beta per obdobi
    print("[6] beta per obdobi:")
    for lbl,yrs in [('2021',[2021]),('2022',[2022]),('2023',[2023]),('2024-25',[2024,2025])]:
        g=d[d.year.isin(yrs)]; bb,_,tt,pp,rr=ols(g.r_last60.values, np.c_[np.ones(len(g)), g.r_pre60.values])
        exp=(np.sign(g.r_pre60)*g.r_last60).mean()
        print(f"     {lbl}: n={len(g)} beta={bb[1]:+.4f} t={tt[1]:+.2f} p={pp[1]:.3f} R2={100*rr:.2f}% | exp={exp:+.2f} net_cons={exp-COST_BPS_CONS:+.2f}")
