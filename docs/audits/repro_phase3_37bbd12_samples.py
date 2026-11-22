import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import numpy as np,pandas as pd,QuantLib as ql,json,math
from src.heston.solver_2d import Heston2DSolver
from src.heston.heston_model import HestonParams,HestonOptionPricer
from src.heston.rates_curve import get_official_yield_curve
m=json.loads(Path('data/heston/phase1/phase1_execution_manifest.json').read_text());p=HestonParams(**{k:m['best_model_parameters'][k] for k in ('v0','kappa','theta','xi','rho')});s=Heston2DSolver();c=get_official_yield_curve();pr=HestonOptionPricer()
def ref(K,days,params,am=True,fac=700,x=280,v=140,order=192):
 proc=ql.HestonProcess(pr.ts_handle,pr.div_handle,pr.spot_handle,params.v0,params.kappa,params.theta,params.xi,params.rho);model=ql.HestonModel(proc);exp=pr.eval_date+int(days)
 opt=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,float(K)),ql.AmericanExercise(pr.eval_date,exp) if am else ql.EuropeanExercise(exp));opt.setPricingEngine(ql.FdHestonVanillaEngine(model,max(120,round(fac*days/365)),x,v) if am else ql.AnalyticHestonEngine(model,order));return opt.NPV()
a=pd.read_csv('data/heston/phase3/market_97_puts_validation.csv');idx=list(dict.fromkeys(list(a.abs_err_fine_usd.nlargest(3).index)+list(np.random.default_rng(260721).choice(len(a),5,replace=False))))
rows=[]
for i in idx:
 r=a.iloc[i];T=float(r.tau_years);fine=s.price(r.strike,T,p,c,n_s=240,n_v=120,m_t=max(100,round(600*T))).price;default=s.price(r.strike,T,p,c).price;q=ref(r.strike,int(r.tau_days),p)
 row=dict(symbol=r.contractSymbol,replay_fine=fine-r.proprietary_fine_usd,replay_default=default-r.proprietary_default_usd,replay_reference=q-r.ql_refined_700_usd,fine_error=fine-q,default_error=default-q);rows.append(row);print('MARKET_SAMPLE',row,flush=True)
pd.DataFrame(rows).to_csv('audit_market_sample.csv',index=False)
b=pd.read_csv('data/heston/phase3/hypothetical_regimes_108.csv');samples=[]
for rid,g in b.groupby('regime_id'):
 samples.extend(list(dict.fromkeys([g.abs_error_usd.idxmax(),g.sample(1,random_state=743).index[0]])))
for i in samples:
 r=b.loc[i];pp=HestonParams(r.v0,r.kappa,r.theta,r.xi,r.rho);am=r.contract_style=='American';T=float(r.tau_years);fine=s.price(r.strike,T,pp,c,is_american=am,n_s=240,n_v=120,m_t=max(100,round(600*T))).price;q=ref(r.strike,round(365*T),pp,am)
 print('REGIME_SAMPLE',r.regime_id,r.contract_style,r.strike,365*T,'price_replay',fine-r.proprietary_fine_usd,'ref_replay192_vs_saved',q-r.ql_reference_usd,'error',fine-q,flush=True)
# The submitted validator marks v0=0 as QuantLib unsupported without attempting it.
for v0 in (0.,.0001):
 pp=HestonParams(v0,p.kappa,p.theta,p.xi,p.rho)
 try:q=ref(12.33,31,pp);print('QL_V0_SUPPORTED',v0,q,flush=True)
 except Exception as e:print('QL_V0_ACTUAL_EXCEPTION',v0,repr(e),flush=True);q=float('nan')
 for ns,nv,fac in ((160,80,300),(240,120,600),(320,160,900)):
  own=s.price(12.33,31/365,pp,c,n_s=ns,n_v=nv,m_t=max(100,round(fac*31/365))).price;print('V0_BOUNDARY_GRID',v0,ns,nv,own,'ref_delta',own-q,flush=True)
print('DONE',flush=True)
