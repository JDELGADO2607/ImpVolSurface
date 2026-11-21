"""Audit probes for market inputs, HAR causality, and negative pipeline cases."""
import contextlib
import importlib
import io
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from market_oracles import CMT, har_sample, semiannual_par_cashflow_price

root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from src.market_data import TREASURY_PAR_CURVE, SPOT_PRICE, get_zero_rate, get_discount_factor, get_forward_price
from src.forecasts import fit_har_rv_walk_forward
import run_all

for t,y in TREASURY_PAR_CURVE:
    if t>=.5:
        print("PAR",t,y,CMT[t],get_zero_rate(t),semiannual_par_cashflow_price(t,y,get_discount_factor),semiannual_par_cashflow_price(t,CMT[t],get_discount_factor))
    elif y!=CMT[t]:
        print("PAR_INPUT_MISMATCH",t,y,CMT[t])
for d in (3,31,59,430,794):
    t=d/365
    print("MARKET",d,get_zero_rate(t),get_discount_factor(t),get_forward_price(t))

a,b=har_sample()
series=[]
for case,x in enumerate((a,b)):
    _,pred,_=fit_har_rv_walk_forward(x,test_window=55)
    series.append(pred)
    print("HAR",case,len(pred),pred.iloc[0][["date","pred_vol_har"]].to_dict())
origin=series[0].iloc[0]["date"]
c=a.copy(deep=True)
c.loc[c.index>origin,["log_ret","rv_daily"]]*=10
_,pred,_=fit_har_rv_walk_forward(c,test_window=55)
print("HAR_POST_ORIGIN",pred.iloc[0]["pred_vol_har"]-series[0].iloc[0]["pred_vol_har"])
try:
    fit_har_rv_walk_forward(a.iloc[:90],test_window=55)
except Exception as e:
    print("HAR_TOO_SHORT",type(e).__name__,str(e))

from hashlib import sha256
def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()
with TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    shutil.copytree(root/"outputs",tmp/"outputs")
    cwd=Path.cwd()
    os.chdir(tmp)
    try:
        f=Path("outputs/tables/options_with_iv.csv")
        original=f.read_bytes()
        frame=pd.read_csv(f)
        for case in ("absent_column","partial_null","absent_finite_only"):
            target=f
            if case=="absent_column":
                altered=frame.drop(columns="our_iv_decimal")
            elif case=="partial_null":
                altered=frame.copy()
                altered.loc[0,"our_iv_decimal"]=np.nan
            else:
                target=Path("outputs/tables/options_audit.csv")
                altered=pd.read_csv(target).drop(columns="strike")
            content=target.read_bytes()
            altered.to_csv(target,index=False)
            try:
                run_all._validate_table_file(target)
                print("CONTRACT",case,"ACCEPTED")
            except Exception as e:
                print("CONTRACT",case,"REJECTED",type(e).__name__,str(e))
            target.write_bytes(content)
        fake=SimpleNamespace(**{fn:lambda:None for fn in (
            "clean_and_audit_options","invert_clean_dataset","generate_surface_plots_and_tables",
            "run_model_comparison","build_hypothetical_portfolio","run_stress_testing","run_strategies_analysis")})
        real_import=importlib.import_module
        def test_pipeline():
            with patch("importlib.import_module",side_effect=lambda n,*a,**kw:fake if n.startswith("src.") else real_import(n,*a,**kw)):
                with contextlib.redirect_stdout(io.StringIO()):
                    return run_all.run_pipeline(raise_on_error=False,run_tests=False)
        print("STALE_STAGES",test_pipeline(),f.read_bytes()==original)
        fig=run_all.REQUIRED_FIGURES[0]
        fig.write_bytes(b"x")
        print("INVALID_PNG",test_pipeline())
        fig.unlink()
        try:
            print("MISSING_FIGURE",test_pipeline())
        except Exception as e:
            print("MISSING_FIGURE",type(e).__name__,str(e))
    finally:
        os.chdir(cwd)

p=pd.read_csv(root/"outputs/tables/hypothetical_portfolio.csv")
def capital(frame):
    opts=frame[frame.type.isin(["C","P"])]
    short=opts.quantity.lt(0)
    return (opts.quantity.abs()*opts.multiplier*(opts.obs_price+.20*SPOT_PRICE*short)).sum()+.50*SPOT_PRICE*frame.loc[frame.type.eq("STOCK"),"quantity"].abs().sum()
base=capital(p)
print("CAPITAL",base)
for sym,field,delta in [("NU261218C00014000","obs_price",.01),("NU270115P00011000","quantity",-1),("NU270115C00013000","obs_price",.01)]:
    x=p.copy()
    x.loc[x.contractSymbol.eq(sym),field]+=delta
    print("CAPITAL_PERTURB",sym,field,delta,capital(x)-base)
