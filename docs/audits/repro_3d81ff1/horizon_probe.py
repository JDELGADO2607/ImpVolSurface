"""Search the documented horizon independently of the production boolean."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from oracles import european_call, strike_diagnostics
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from src.surface import VolatilitySurface
from src.market_data import SPOT_PRICE, get_discount_factor, get_forward_price
s=VolatilitySurface(pd.read_csv(root/"outputs/tables/options_with_iv.csv"))
tenors=[t for t in s.tenors if t*365 >= 9.99999 and t<=s.tau_max_prod]
for n in (301,911):
    rows=[]
    for a,b in zip(tenors[:-1],tenors[1:]):
        for lam in (0.,.173,.371,.713,.853,1.):
            t=(1-lam)*a+lam*b
            support=s.surface_iv(0.,t)
            low,high=(support[x] for x in ("slice_support_K_min","slice_support_K_max"))
            u=np.linspace(.0001,.9999,n)
            strikes=low+(high-low)*(u+.07*np.sin(2*np.pi*u))
            data=[s.surface_iv(k,t,policy="strict") for k in np.log(strikes/get_forward_price(t))]
            px=european_call(SPOT_PRICE,strikes,get_discount_factor(t),1.,[d["w"] for d in data])
            slopes,curves=strike_diagnostics(strikes,px)
            for i in np.flatnonzero(curves < -1e-4):
                if not all(v["is_production_ready"] for v in data[i:i+3]):
                    continue
                rows.append((float(curves[i]),t*365,strikes[i:i+3].tolist(),px[i:i+3].tolist()))
    print("DOCUMENTED_HORIZON",n,len(rows),sorted(rows)[:8],flush=True)
