"""Reproduce final-surface findings in the extracted revision; no output writes."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from oracles import american_put_crr, european_call, previous_audit_grids, strike_diagnostics

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from src.market_data import SPOT_PRICE as S, get_discount_factor, get_forward_price, get_zero_rate
from src.pricing_american_fd import fd_american_price
from src.surface import VolatilitySurface

data = pd.read_csv(root / "outputs/tables/options_with_iv.csv")
s = VolatilitySurface(data)

def at_strike(d, strikes, policy="allow"):
    t = d / 365
    return [s.surface_iv(float(np.log(k / get_forward_price(t))), t, policy=policy) for k in strikes]

def prices(day, grid):
    t = day / 365
    out = at_strike(day, grid)
    c = european_call(S, grid, get_discount_factor(t), 1., [v["w"] for v in out])
    slopes, curve = strike_diagnostics(grid, c)
    return out, c, slopes, curve

tenors = np.array(s.tenors) * 365
print("TENORS", tenors, "HORIZON", s.tau_max_prod * 365, flush=True)
for d, k in [(3,12.5),(27.5,14.75),(31,10),(430,5),(612,20.4166667),(794,15),(-1,12)]:
    for policy in ("allow","strict"):
        try:
            r=at_strike(d,[k],policy)[0]
            print("SUPPORT",d,k,policy,r,flush=True)
        except ValueError as e:
            print("REJECT",d,k,policy,e,flush=True)

for d, grid in previous_audit_grids():
    out,c,slopes,curve=prices(d,grid)
    j=np.argmin(curve)
    prod=[r["is_production_ready"] for r in out]
    print("B1",d,len(grid),grid[j+1],curve[j],sum(curve < -1e-4),sum(prod),flush=True)

def fmt_triplet(d, grid, curve):
    j=np.argmin(curve)
    return (float(curve[j]),d,grid[j:j+3].tolist())

for n in (151,409,1001):
    witness=[]
    production=[]
    max_call_slope=0.
    min_call_slope=0.
    for lo,hi in zip(tenors[:-2],tenors[1:-1]):
        for d in (lo, lo+(hi-lo)*.371, lo+(hi-lo)*.713, hi):
            t=d/365
            anchor=s.surface_iv(0.,t)
            a,b=anchor["slice_support_K_min"],anchor["slice_support_K_max"]
            u=np.linspace(.002,.998,n)
            grid=a+(b-a)*(u+.06*np.sin(2*np.pi*u))
            out,c,slopes,curve=prices(d,grid)
            assert np.all(np.isfinite(c)) and np.all(c >= np.maximum(S-grid*get_discount_factor(t),0)-1e-10) and np.all(c <= S + 1e-10)
            assert all(v["w"]>0 for v in out)
            max_call_slope=max(max_call_slope,float(np.max(slopes)))
            min_call_slope=min(min_call_slope,float(np.min(slopes)))
            for j in np.flatnonzero(curve < -1e-4):
                v=(float(curve[j]),float(d),grid[j:j+3].tolist(),c[j:j+3].tolist())
                witness.append(v)
                if all(row["is_production_ready"] for row in out[j:j+3]):
                    production.append(v)
    print("NEW_GRID",n,"violations",len(witness),"production",len(production),"worst",min(production, default=None),"slopes",min_call_slope,max_call_slope,flush=True)

for d in [3,10,17,24,31,37,59,430,794]:
    t=d/365
    for k in (0., .15, -.15):
        eps=2.0e-6
        a,b,c=[s.surface_iv(k,t+e) for e in [-eps,0,eps]]
        m=s.surface_iv(k,t+5e-7)
        print("REGULARITY",d,k,(b["w"]-a["w"])/eps,(c["w"]-b["w"])/eps,m["w"]-(t+5e-7)*m["iv"]**2,flush=True)

kgrid=np.linspace(-1.20,1.08,801)
time_witness=[]
for t in s.tenors:
    if t > s.tau_max_prod:
        continue
    for k in kgrid:
        x=s.surface_iv(k,t-1.1e-6)
        y=s.surface_iv(k,t)
        if y["w"] < x["w"]-1e-9:
            time_witness.append((y["w"]-x["w"],t*365,k,x["is_production_ready"],y["is_production_ready"]))
print("CALENDAR",len(time_witness),min(time_witness,default=None),"prod",min((w for w in time_witness if all(w[3:])),default=None),flush=True)

worst=[]
for strike in sorted(set(np.linspace(9.5,19.5,81))|{14.75}):
    prev=None
    for d in sorted(set(tenors[tenors <= 430.001]) | {27.5, 32.73, 76.3, 238.4}):
        t=d/365
        out=at_strike(d,[strike])[0]
        if not out["is_production_ready"]:
            prev=None
            continue
        v=american_put_crr(S,strike,t,get_zero_rate(t),0,out["iv"],480)
        if prev and v<prev[0]-0.0003:
            worst.append((v-prev[0],strike,prev[1],float(d)))
        prev=(v,float(d))
print("PUT_SCAN",len(worst),sorted(worst)[:10],flush=True)
for k,d1,d2 in [(14.75,31.,37.)]+[(x[1],x[2],x[3]) for x in sorted(worst)[:3]]:
    for d in (d1,d2):
        t=d/365
        out=at_strike(d,[k])[0]
        iv=out["iv"]
        print("PUT_CONFIRM",k,d,iv,fd_american_price("P",S,k,t,get_zero_rate(t),iv),
              [american_put_crr(S,k,t,get_zero_rate(t),0,iv,n) for n in (1000,2000,4000)],flush=True)

for d in (31.,59.):
    print("CORE",d,[(100*x["iv"], x["quality"]) for x in at_strike(d,range(11,16))],flush=True)
