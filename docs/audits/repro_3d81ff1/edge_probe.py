"""Locate the harmonization source and boundary failures for fixed test cases."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from oracles import european_call, american_put_crr, strike_diagnostics
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from src.surface import VolatilitySurface
from src.market_data import SPOT_PRICE as S, get_forward_price, get_discount_factor, get_zero_rate
from src.pricing_american_fd import fd_american_price
data=pd.read_csv(root/"outputs/tables/options_with_iv.csv")
s=VolatilitySurface(data)
for d in (10,17,24,31,37,59,430):
    t=min(s.tenors,key=lambda t:abs(t-d/365))
    u=s.tenors[s.tenors.index(t)-1]
    curr,prev=s.slices[t],s.slices[u]
    grid=np.linspace(min(curr["k_min"],-.4),max(curr["k_max"],.35),50)
    q=np.array([(t/u)**.22*s._evaluate_slice_w(u,k)-s._evaluate_raw_slice_w(t,k) for k in grid])
    k=grid[q.argmax()]
    print("LIFT",d,"prev",u*365,"k",k,"prev_support",[prev["k_min"],prev["k_max"]],
          "curr_support",[curr["k_min"],curr["k_max"]],"deficit",q.max(),"lift",curr["calendar_lift"],flush=True)

target=5.597
t=target/365
u=min(s.tenors)
v=s.slices[u]
clip=v["k_min"]-.03
K=get_forward_price(t)*np.exp(clip)
print("KINK",clip,K,flush=True)
for h in (.02,.005,.001,.00025):
    Ks=K+h*np.array([-1.,0.,1.15])
    rs=[s.surface_iv(float(np.log(k/get_forward_price(t))),t,policy="strict") for k in Ks]
    calls=european_call(S,Ks,get_discount_factor(t),1.,[r["w"] for r in rs])
    puts=[fd_american_price("P",S,k,t,get_zero_rate(t),r["iv"]) for k,r in zip(Ks,rs)]
    tree=[american_put_crr(S,k,t,get_zero_rate(t),0.,r["iv"],4000) for k,r in zip(Ks,rs)]
    print("EDGES",h,Ks.tolist(),[r["is_production_ready"] for r in rs],strike_diagnostics(Ks,calls),
          strike_diagnostics(Ks,puts),strike_diagnostics(Ks,tree),flush=True)

for d in (31,59):
    t=d/365
    K=np.linspace(11,15,901)
    rs=[s.surface_iv(float(np.log(x/get_forward_price(t))),t,policy="strict") for x in K]
    c=european_call(S,K,get_discount_factor(t),1.,[x["w"] for x in rs])
    slopes,curve=strike_diagnostics(K,c)
    print("NARROW_CORE",d,curve.min(),sum(curve < -1e-4),sum(x["is_production_ready"] for x in rs),flush=True)
