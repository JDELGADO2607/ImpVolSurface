"""Exercise the actual stress capital path with counterfactual portfolio legs."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import pandas as pd
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
import src.stress_testing as st
from src.surface import VolatilitySurface
ivpath=root/"outputs/tables/options_with_iv.csv"
data=pd.read_csv(ivpath)
base=pd.read_csv(root/"outputs/tables/hypothetical_portfolio.csv")
s=VolatilitySurface(data)
summary={"hedge_shares":int(base.loc[base.type.eq("STOCK"),"quantity"].iloc[0]),
         "total_options_value_mod":float(base.loc[base.type.isin(["C","P"]),"surface_value_usd"].sum()),
         "total_options_value_mkt":float(base.loc[base.type.isin(["C","P"]),"market_value_usd"].sum())}
scenarios={name:value for name,value in st.SCENARIOS.items() if name in ("S0_Null_Shock","S1_Theta_Roll")}
if len(scenarios)<2:
    scenarios=dict(list(st.SCENARIOS.items())[:2])
for label,sym,col,value in [
    ("base",None,None,None),("premium","NU261218C00014000","obs_price",.16),
    ("quantity","NU270115P00011000","quantity",-5),
    ("replace","NU261218C00014000","contractSymbol","NU261218C00013000")]:
    port=base.copy()
    if sym:
        port.loc[port.contractSymbol.eq(sym),col]=value
        if label=="replace":
            port.loc[port.contractSymbol.eq(value),"obs_price"]=float(data.loc[data.contractSymbol.eq(value),"lastPrice"].iloc[0])
    with TemporaryDirectory() as d, patch.object(st,"build_hypothetical_portfolio",return_value=(port,summary)),          patch.object(st,"VolatilitySurface",return_value=s), patch.object(st,"SCENARIOS",scenarios):
        frame,legs=st.run_stress_testing(str(ivpath),d,d)
    print("STRESS_CONTROL",label,frame.economic_margin_capital.unique().tolist(),
          sorted(legs.contractSymbol.unique()),frame.total_port_pnl_stress_mod.tolist(),flush=True)
