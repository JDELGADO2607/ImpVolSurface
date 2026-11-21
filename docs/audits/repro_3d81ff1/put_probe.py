"""Independent put limits, strike slopes, and refinement on irregular grids."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from oracles import american_put_crr, strike_diagnostics
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from src.surface import VolatilitySurface
from src.market_data import SPOT_PRICE as S, get_forward_price, get_zero_rate
from src.pricing_american_fd import fd_american_price
s=VolatilitySurface(pd.read_csv(root/"outputs/tables/options_with_iv.csv"))
prod=[t for t in s.tenors if 9.99999 <= t*365 <= 430.000001]
days=sorted(set([*(t*365 for t in prod), *(365*(a+.417*(b-a)) for a,b in zip(prod[:-1],prod[1:])),5.597,21.991,290.476]))
for steps in (480,1200):
    witnesses=[]
    min_slope=0
    max_slope=0
    tested=0
    for d in days:
        t=d/365
        x=s.surface_iv(0.,t)
        low,high=[x[key] for key in ("slice_support_K_min","slice_support_K_max")]
        u=np.linspace(.01,.99,65)
        K=low+(high-low)*(u+.04*np.sin(2*np.pi*u))
        rs=[s.surface_iv(k,t,policy="strict") for k in np.log(K/get_forward_price(t))]
        assert all(v["is_production_ready"] for v in rs)
        r=get_zero_rate(t)
        v=np.array([american_put_crr(S,k,t,r,0.,row["iv"],steps) for k,row in zip(K,rs)])
        assert np.all(np.isfinite(v)) and np.all(v >= np.maximum(K-S,0)-1e-10) and np.all(v <= K+1e-10)
        slopes,c= strike_diagnostics(K,v)
        min_slope=min(min_slope,min(slopes))
        max_slope=max(max_slope,max(slopes))
        tested+=len(K)
        for i in np.flatnonzero(c < -.1):
            witnesses.append((float(c[i]),d,K[i:i+3].tolist()))
    print("PUT_GRID",steps,tested,min_slope,max_slope,len(witnesses),sorted(witnesses)[:5],flush=True)
for d,K in [(21.991,[10.186427622473634,10.19388197094192,10.201335550009258]),
            (290.476,[9.6643924184249,9.68368564131791,9.702976030537455])]:
    t=d/365
    r=get_zero_rate(t)
    iv=[s.surface_iv(k,t)["iv"] for k in np.log(np.array(K)/get_forward_price(t))]
    vals=[("EDP",[fd_american_price("P",S,k,t,r,v) for k,v in zip(K,iv)])]
    vals.extend((f"CRR {n}",[american_put_crr(S,k,t,r,0.,v,n) for k,v in zip(K,iv)]) for n in (1000,2000,4000))
    for name,px in vals:
        print("PUT_WITNESS",d,K,name,px,strike_diagnostics(np.array(K),px),flush=True)
