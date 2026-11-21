import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import json,hashlib,time
from pathlib import Path
import numpy as np,pandas as pd,QuantLib as ql
from src.heston.heston_model import HestonParams,HestonOptionPricer
from src.heston.calibration import HestonCalibrator
m=json.loads(Path('data/heston/phase1/phase1_execution_manifest.json').read_text())
p=HestonParams(**{k:m['best_model_parameters'][k] for k in ('v0','kappa','theta','xi','rho')})
pr=HestonOptionPricer(); date=pr.eval_date
proc=ql.HestonProcess(pr.ts_handle,pr.div_handle,pr.spot_handle,p.v0,p.kappa,p.theta,p.xi,p.rho)
model=ql.HestonModel(proc)
def raw(K,exp,fac=300,x=160,v=80,minimum=60,am=True):
 t=ql.Actual365Fixed().yearFraction(date,exp)
 opt=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,float(K)),ql.AmericanExercise(date,exp) if am else ql.EuropeanExercise(exp))
 opt.setPricingEngine(ql.FdHestonVanillaEngine(model,max(minimum,round(fac*t)),x,v))
 return opt.NPV()
f=pd.read_csv('data/heston/phase1/heston_pricing_full_puts.csv'); records=[]
for row in f.itertuples():
 exp=pr._parse_exp_date(row.expirationDate)
 vals=[raw(row.strike,exp),raw(row.strike,exp,500,160,80,100),raw(row.strike,exp,300,240,120),raw(row.strike,exp,500,240,120,100)]
 records.append(dict(symbol=row.contractSymbol,split=row.dataset_split,K=row.strike,day=row.tau_days,observed=row.lastPrice,published=row.heston_price_am,production=vals[0],temporal=vals[1],spatial=vals[2],ultra=vals[3]))
out=pd.DataFrame(records);out.to_csv('audit_reprice.csv',index=False)
print('REPLAY_MAX',abs(out.production-out.published).max(),flush=True)
for key in ('temporal','spatial','ultra'): print('GRID_MAX',key,abs(out[key]-out.production).max(),flush=True)
for split,g in out.groupby('split'):
 e=g.production-g.observed; print('METRICS',split,len(g),e.abs().mean(),np.sqrt(np.mean(e*e)),flush=True)
for row in out.loc[(out.ultra-out.production).abs().nlargest(3).index].itertuples():
 exp=date+int(row.day); finest=raw(row.K,exp,900,320,160,180)
 print('FINER',row.symbol,'prod',row.production,'ultra',row.ultra,'900x320x160',finest,'delta',finest-row.production,flush=True)
print('RAW_BOUNDS',min(out.production-np.maximum(out.K-12.33,0)),min(out.K-out.production),flush=True)
ms=pd.read_csv('data/heston/phase1/heston_multistart_results.csv'); train=pd.read_csv('data/heston/data_split_train.csv')
cal=HestonCalibrator(train,pr.ts_handle,grid_t_factor=200,grid_x=200,grid_v=100)
for row in ms.itertuples():
 a=np.array([row.v0,row.kappa,row.theta,row.xi,row.rho]); print('FINE_SSE',row.start_index,cal.evaluate_sse(a),flush=True)
for file,h in m['input_hashes'].items(): print('HASH',file,hashlib.sha256((Path('data/heston')/file).read_bytes()).hexdigest()==h,flush=True)
# Independently recompute all nonuniform convexity/monotonicity checks.
for exp,g in f.groupby('expirationDate'):
 g=g.sort_values('strike'); k=g.strike.to_numpy(); y=g.heston_price_am.to_numpy(); slopes=np.diff(y)/np.diff(k)
 print('STRIKE',exp,'n',len(k),'min_slope',slopes.min(),'min_slope_increment',np.diff(slopes).min() if len(k)>2 else None,flush=True)
print('TEMPORAL_MIN',min(np.diff(g.sort_values('tau_days').heston_price_am).min() for _,g in f.groupby('strike') if len(g)>1),flush=True)
# New points not chosen by implementer, including historical failures.
for K,day in ((14.75,31),(14.75,37),(14.75,27),(20.42,612),(5.,430),(10.,31),(12.,1),(12.,2),(12.,800)):
 print('NEW_POINT',K,day,raw(K,date+day),raw(K,date+day,600,240,120,120),flush=True)
print('DONE',flush=True)
