import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import json,math
import numpy as np,pandas as pd,QuantLib as ql
from scipy.stats import norm
from scipy.interpolate import RegularGridInterpolator
from src.heston.solver_2d import Heston2DSolver
from src.heston.heston_model import HestonParams,HestonOptionPricer
from src.heston.rates_curve import get_official_yield_curve
m=json.loads(Path('data/heston/phase1/phase1_execution_manifest.json').read_text());p=HestonParams(**{k:m['best_model_parameters'][k] for k in ('v0','kappa','theta','xi','rho')})
curve=get_official_yield_curve(); sol=Heston2DSolver();pr=HestonOptionPricer()
proc=ql.HestonProcess(pr.ts_handle,pr.div_handle,pr.spot_handle,p.v0,p.kappa,p.theta,p.xi,p.rho); model=ql.HestonModel(proc)
def qprice(K,day,am):
 exp=pr.eval_date+day;o=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,K),ql.AmericanExercise(pr.eval_date,exp) if am else ql.EuropeanExercise(exp));o.setPricingEngine(ql.FdHestonVanillaEngine(model,max(120,round(700*day/365)),280,140) if am else ql.AnalyticHestonEngine(model,192));return o.NPV()
rows=[]
for row in pd.read_csv('data/heston/phase2/smoke_test_results.csv').itertuples():
 am=row.contract=='American';day=int(round(row.maturity_years*365));r=sol.price(row.strike,row.maturity_years,p,curve,is_american=am,n_s=160,n_v=80,m_t=100);ref=qprice(row.strike,day,am)
 rows.append(dict(case=row.case_id,price=r.price,export=row.proprietary_solver_usd,replay_delta=r.price-row.proprietary_solver_usd,reference_fine=ref,error=r.price-ref))
print('SMOKE_REPLAY_MAX',max(abs(x['replay_delta']) for x in rows),flush=True); print('SMOKE_FINE_ERROR_MAX',max(abs(x['error']) for x in rows),flush=True);pd.DataFrame(rows).to_csv('audit_smoke.csv',index=False)
for K,day in ((14.75,31),(14.75,37),(20.42,612),(5.,430),(10.,31),(17.,794),(20.,3),(30.,31)):
 r=sol.price(K,day/365,p,curve,is_american=True,m_t=max(100,round(300*day/365)))
 ref=qprice(K,day,True)
 print('EXTRA',K,day,'price',r.price,'ref',ref,'err',r.price-ref,'intrinsic_gap',r.price-max(K-12.33,0),'comp',r.max_complementarity_residual,flush=True)
# Test nodes where interpolation must preserve a constant exercise value.
r=sol.price(20.,31/365,p,curve,is_american=True,m_t=100)
inter=RegularGridInterpolator((r.grid_s,r.grid_v),r.grid_v_surface,method='cubic')
spots=np.linspace(5,15,401);pts=np.column_stack((spots,np.full(len(spots),p.v0)));prices=inter(pts);gap=prices-np.maximum(20-spots,0)
i=int(np.argmin(gap));print('CUBIC_FLOOR_WORST','spot',spots[i],'gap',gap[i],'price',prices[i],flush=True)
# Public API advertises calls, but imposes upper spot boundary=0.
r=sol.price(12.33,31/365,p,.05,spot=90.,option_type='C',is_american=False,m_t=100)
print('CALL_INTERFACE',r.price,'economic_lower',90.-12.33*math.exp(-.05*31/365),flush=True)
# European S=0 residual boundary is observable independently of extraction price.
r=sol.price(12.33,1.,p,.05,is_american=False,m_t=20)
print('EU_S_ZERO','actual_min',r.grid_v_surface[0].min(),'actual_max',r.grid_v_surface[0].max(),'exact',12.33*math.exp(-.05),flush=True)
# Constant variance exactly xi=0 and v0=theta, not epsilon proxy.
b=HestonParams(.2,2.,.2,0.,0.)
for am in (False,True):
 r=sol.price(12.33,94/365,b,.05,is_american=am,m_t=200)
 print('XI_ZERO',am,r.price,flush=True)
print('DONE',flush=True)
