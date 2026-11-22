import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import numpy as np,pandas as pd,QuantLib as ql
from src.heston.solver_2d import Heston2DSolver
from src.heston.heston_model import HestonParams,HestonOptionPricer
from src.heston.rates_curve import get_official_yield_curve
b=pd.read_csv('data/heston/phase3/hypothetical_regimes_108.csv');s=Heston2DSolver();c=get_official_yield_curve();pr=HestonOptionPricer()
for rid,g in b.query('contract_style=="European"').groupby('regime_id'):
 r=g.loc[g.abs_error_usd.idxmax()];p=HestonParams(r.v0,r.kappa,r.theta,r.xi,r.rho);model=ql.HestonModel(ql.HestonProcess(pr.ts_handle,pr.div_handle,pr.spot_handle,p.v0,p.kappa,p.theta,p.xi,p.rho));exp=pr.eval_date+round(365*r.tau_years);o=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,float(r.strike)),ql.EuropeanExercise(exp))
 vals=[]
 for order in (144,192):o.setPricingEngine(ql.AnalyticHestonEngine(model,order));vals.append(o.NPV())
 own=s.price(r.strike,r.tau_years,p,c,is_american=False,n_s=240,n_v=120,m_t=max(100,round(600*r.tau_years))).price
 print('EUROPEAN_REGIME',rid,'K',r.strike,'days',365*r.tau_years,'own_replay',own-r.proprietary_fine_usd,'ql192_replay',vals[1]-r.ql_reference_usd,'integration_delta',vals[1]-vals[0],'own_error',own-vals[1],flush=True)
print('DONE',flush=True)
