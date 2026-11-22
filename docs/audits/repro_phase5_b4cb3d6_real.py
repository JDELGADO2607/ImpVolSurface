import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,pandas as pd,QuantLib as ql
from scipy.stats import norm
from src.heston.rates_curve import get_official_yield_curve
from src.heston.equivalent_iv import fd_american_price_curve,price_heston_european_call,invert_american_put_iv
from src.heston.heston_model import HestonParams
b=Path('data/heston/phase5');puts=pd.read_csv(b/'heston_iv_surface_97_puts.csv');calls=pd.read_csv(b/'heston_iv_surface_142_calls.csv');curve=get_official_yield_curve()
print('STATUS_PUTS',puts.status_heston_inversion.value_counts().to_dict(),flush=True);print('STATUS_CALLS',calls.status_heston_call.value_counts().to_dict(),flush=True)
for name,d,c in [('put',puts,'residual_heston_1d_usd'),('call',calls,'residual_heston_call_usd')]:print('MAX_ROOT_RESIDUAL',name,float(abs(d[c]).max()),flush=True)
for typ,d,px in [('puts',puts,'heston_price'),('calls',calls,'heston_call_price')]:
 e=d[px]-d.market_last_price;print('REAL_METRICS',typ,len(d),'MAE',abs(e).mean(),'RMSE',np.sqrt((e*e).mean()),flush=True)
sample=puts[puts.status_heston_inversion.eq('CONVERGED') & puts.tau_days.isin([31,59]) & puts.strike.isin([11.,12.,13.,14.,15.])]
short=puts[puts.status_heston_inversion.eq('CONVERGED') & puts.tau_days.eq(3)]
sample=pd.concat([sample,short]).drop_duplicates('contractSymbol')
date=ql.Date(17,11,2026);ql.Settings.instance().evaluationDate=date;ts=curve.to_quantlib_term_structure(dense_daily=True);div=ql.YieldTermStructureHandle(ql.FlatForward(date,0.,ql.Actual365Fixed()));spot=ql.QuoteHandle(ql.SimpleQuote(12.33))
rows=[]
for _,r in sample.iterrows():
 sig=float(r.iv_heston_equivalent);K=float(r.strike);days=int(r.tau_days);T=float(r.tau_years)
 process=ql.BlackScholesMertonProcess(spot,div,ts,ql.BlackVolTermStructureHandle(ql.BlackConstantVol(date,ql.NullCalendar(),sig,ql.Actual365Fixed())))
 opt=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,K),ql.AmericanExercise(date,date+days));opt.setPricingEngine(ql.FdBlackScholesVanillaEngine(process,700,700));ref=opt.NPV()
 fine=fd_american_price_curve('P',12.33,K,T,curve,sig,M=900,N=600)
 row={'symbol':r.contractSymbol,'K':K,'days':days,'iv':sig,'target':r.heston_price,'ql700':ref,'fd900':fine,'error_ql':ref-r.heston_price,'error_fine':fine-r.heston_price};rows.append(row);print('REAL_PUT_CHECK',row,flush=True)
pd.DataFrame(rows).to_csv('audit_phase5_real_prices.csv',index=False)
# Independent closed-form reconstruction of calls with the original continuous discount curve.
valid=calls[calls.status_heston_call.eq('CONVERGED')];errors=[]
for _,r in valid.iterrows():
 T=float(r.tau_years);sig=float(r.iv_heston_bs);K=float(r.strike);D=curve.get_discount_factor(T);sd=sig*np.sqrt(T);d1=(np.log(12.33/(K*D))+.5*sig*sig*T)/sd;price=12.33*norm.cdf(d1)-K*D*norm.cdf(d1-sd);errors.append(price-r.heston_call_price)
print('INDEPENDENT_BS_CALL_RESIDUAL_MAX',max(abs(np.array(errors))),flush=True)
print('DONE',flush=True)
# Additional real-data controls reported in the accompanying audit.
vec=json.loads(Path('data/heston/phase4/heston_calibrated_parameters.json').read_text())['calibrated_parameters_raw']
model=ql.HestonModel(ql.HestonProcess(ts,div,spot,*vec));engine=ql.AnalyticHestonEngine(model,192);diffs=[]
for _,r in calls.iterrows():
 opt=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call,float(r.strike)),ql.EuropeanExercise(date+int(r.tau_days)));opt.setPricingEngine(engine);diffs.append(opt.NPV()-r.heston_call_price)
print('COMMON_CURVE_QL192_CALL_DIFFERENCE_MAX',float(max(abs(np.array(diffs)))),flush=True)
r=puts[puts.contractSymbol.eq('NU261120P00012500')].iloc[0]
print('REAL_3D_IV_REFINEMENT',r.iv_heston_equivalent,invert_american_put_iv(float(r.heston_price),12.33,12.5,3/365,curve,M=900,N=600),flush=True)
