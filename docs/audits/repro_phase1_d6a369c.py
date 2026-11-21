import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd,QuantLib as ql
from src.heston.heston_model import HestonParams,HestonOptionPricer
from src.heston.rates_curve import get_official_yield_curve
from src.heston.calibration import HestonCalibrator
root=Path(".")
m=json.loads((root/"data/heston/phase1/phase1_execution_manifest.json").read_text())
params=HestonParams(**{k:m["best_model_parameters"][k] for k in ("v0","kappa","theta","xi","rho")})
curve=get_official_yield_curve(); ts=curve.to_quantlib_term_structure(dense_daily=True)
pr=HestonOptionPricer(ts)
proc=ql.HestonProcess(ts,pr.div_handle,pr.spot_handle,params.v0,params.kappa,params.theta,params.xi,params.rho)
model=ql.HestonModel(proc)
date=pr.eval_date
def raw(K,exp,nt=100,nx=100,nv=50,american=True,kind=ql.Option.Put):
 t=ql.Actual365Fixed().yearFraction(date,exp)
 exercise=ql.AmericanExercise(date,exp) if american else ql.EuropeanExercise(exp)
 opt=ql.VanillaOption(ql.PlainVanillaPayoff(kind,K),exercise)
 opt.setPricingEngine(ql.FdHestonVanillaEngine(model,max(50,round(nt*t)),nx,nv))
 return opt.NPV()
data=pd.read_csv("data/heston/phase1/heston_pricing_full_puts.csv")
rows=[]
for row in data.itertuples():
 exp=pr._parse_exp_date(row.expirationDate)
 p=raw(row.strike,exp)
 fine=raw(row.strike,exp,200,200,100)
 rows.append(dict(symbol=row.contractSymbol,K=row.strike,T=row.tau_days,split=row.dataset_split,observed=row.lastPrice,raw=p,published=row.heston_price_am,fine=fine,delta=fine-p,raw_intrinsic_gap=p-max(row.strike-12.33,0)))
out=pd.DataFrame(rows)
out.to_csv("audit_reprice.csv",index=False)
print("RAW_REPLAY_MAX",abs(out.raw-out.published).max(),flush=True)
print("FULL_GRID_EXCEEDS",sum(out.delta.abs()>.002),"MAX",out.delta.abs().max(),flush=True)
print(out.loc[out.delta.abs().nlargest(7).index].to_string(index=False),flush=True)
print("RAW_INTRINSIC_MIN",out.raw_intrinsic_gap.min(),flush=True)
for name,g in out.groupby("split"):
 e=g.fine-g.observed
 print("FINE_METRICS",name,len(e),e.abs().mean(),np.sqrt(np.mean(e*e)),flush=True)
for row in out.loc[out.delta.abs().nlargest(3).index].itertuples():
 original=data.loc[data.contractSymbol.eq(row.symbol)].iloc[0]; exp=pr._parse_exp_date(original.expirationDate)
 print("FINEST",row.symbol,raw(row.K,exp,400,320,160),"SPATIAL",raw(row.K,exp,200,320,160),"TEMPORAL",raw(row.K,exp,400,200,100),flush=True)
train=pd.read_csv("data/heston/data_split_train.csv")
cal=HestonCalibrator(train,ts)
ms=pd.read_csv("data/heston/phase1/heston_multistart_results.csv")
for row in ms.itertuples():
 x=np.array([row.v0,row.kappa,row.theta,row.xi,row.rho])
 print("SSE_REPLAY",row.start_index,row.final_sse,cal.evaluate_sse(x),flush=True)
daily=np.arange(1,795)/365
mid=np.linspace(.001,3,10000)
print("DISCOUNT_DAILY",max(abs(ts.discount(float(t))-curve.get_discount_factor(t)) for t in daily),flush=True)
print("DISCOUNT_CONTINUOUS",max(abs(ts.discount(float(t))-curve.get_discount_factor(t)) for t in mid),flush=True)
for f,h in m["input_hashes"].items():
 print("HASH",f,hashlib.sha256((Path("data/heston")/f).read_bytes()).hexdigest()==h)
for name in ("heston_pricing_train","heston_pricing_strike_holdout","heston_pricing_tenor_holdout","heston_calls_contrast"):
 df=pd.read_csv("data/heston/phase1/"+name+".csv")
 print("CSV_METRIC",name,len(df),df.abs_error_usd.mean(),np.sqrt(np.mean(df.error_usd**2)),flush=True)
# Similar objective does not prove similar extrapolated predictions.
subset=ms[ms.final_sse<=1.05*ms.final_sse.min()]
for K,day in ((12.,31),(17.,794),(30.,794)):
 exp=date+day
 prices=[pr.price_american(K,exp,HestonParams(row.v0,row.kappa,row.theta,row.xi,row.rho),spot_steps=120,vol_steps=60) for row in subset.itertuples()]
 print("NEAR_OPT_PREDICT",K,day,min(prices),max(prices),max(prices)-min(prices),flush=True)