import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,pandas as pd,QuantLib as ql
from src.heston.rates_curve import get_official_yield_curve
b=Path('data/heston/phase6');d=pd.read_csv(b/'models_comparison_detailed.csv');p=pd.read_csv(b/'portfolio_greeks_and_valuation.csv');s=pd.read_csv(b/'portfolio_stress_scenarios.csv');legs=p[p.type.ne('STOCK')];detail=pd.read_csv(b/'portfolio_stress_leg_detail.csv')
for typ,g in d.groupby('type'):
 print('REAL_MODELS',typ,len(g),{c:float(abs(g[c]-g.market_last_price).mean()) for c in ['m1_eu_const_bs','m2_am_const_1d','m3_eu_heston','m4_am_heston']},flush=True)
puts=d[d.type.eq('PUT')];flat=abs(puts.m2_am_const_1d-puts.market_last_price).mean();h=abs(puts.m4_am_heston-puts.market_last_price).mean();print('PUT_MAE_REDUCTION_AM_FLAT_PCT',100*(1-h/flat),flush=True)
for col,unit in [('heston_value_usd','heston_price'),('market_value_usd','obs_price'),('position_delta','delta_per_unit'),('position_gamma','gamma_per_unit'),('position_sens_sigma0_1pp','sens_sigma0_1pp_per_unit'),('position_theta_daily','theta_daily_per_unit')]:
 err=abs(p[col]-p.quantity*p.multiplier*p[unit]).max();print('AGGREGATION_CHECK',col,float(err),float(legs[col].sum()),flush=True)
for _,r in s.iterrows():
 g=detail[detail.scenario_id.eq(r.scenario_id)];pnl=(g.leg_val_shock_usd-g.leg_val_base_usd).sum();print('STRESS_RECONCILE',r.scenario_id,float(pnl-r.options_pnl_reval_usd),float(r.options_pnl_reval_usd+r.hedge_pnl_usd-r.total_portfolio_pnl_reval_usd),flush=True)
curve=get_official_yield_curve();ref=ql.Date(17,11,2026);ql.Settings.instance().evaluationDate=ref;ts=curve.to_quantlib_term_structure(dense_daily=True);div=ql.YieldTermStructureHandle(ql.FlatForward(ref,0.,ql.Actual365Fixed()));vec=np.array(json.loads(Path('data/heston/phase4/heston_calibrated_parameters.json').read_text())['calibrated_parameters_raw']);S0=12.33;hs=.01*S0;sig0=math.sqrt(vec[0]);bump=.01
def price(kind,S,K,days,v):
 process=ql.HestonProcess(ts,div,ql.QuoteHandle(ql.SimpleQuote(S)),*map(float,v));model=ql.HestonModel(process);payoff=ql.PlainVanillaPayoff(ql.Option.Call if kind=='C' else ql.Option.Put,K)
 if kind=='C':exercise=ql.EuropeanExercise(ref+days);engine=ql.AnalyticHestonEngine(model,192)
 else:exercise=ql.AmericanExercise(ref,ref+days);engine=ql.FdHestonVanillaEngine(model,max(120,round(700*days/365)),280,140)
 opt=ql.VanillaOption(payoff,exercise);opt.setPricingEngine(engine);return opt.NPV()
rows=[]
for _,r in legs.iterrows():
 k=float(r.strike);days=int(r.tau_days);p0=price(r.type,S0,k,days,vec);up=price(r.type,S0+hs,k,days,vec);dn=price(r.type,S0-hs,k,days,vec);vup=vec.copy();vdown=vec.copy();vup[0]=(sig0+bump)**2;vdown[0]=(sig0-bump)**2
 delta=(up-dn)/(2*hs);gamma=(up-2*p0+dn)/hs**2;sens=(price(r.type,S0,k,days,vup)-price(r.type,S0,k,days,vdown))/2;theta=price(r.type,S0,k,days-1,vec)-p0
 row={'symbol':r.contractSymbol,'price_diff':p0-r.heston_price,'delta_ref':delta,'delta_diff':delta-r.delta_per_unit,'gamma_ref':gamma,'gamma_diff':gamma-r.gamma_per_unit,'sens_ref':sens,'sens_diff':sens-r.sens_sigma0_1pp_per_unit,'theta_ref':theta,'theta_diff':theta-r.theta_daily_per_unit};rows.append(row);print('REFERENCE_LEG',row,flush=True)
pd.DataFrame(rows).to_csv('audit_phase6_reference.csv',index=False)
net=sum(float(r.quantity)*100*(float(q['delta_ref'])) for (_,r),q in zip(legs.iterrows(),rows));print('REFERENCE_NET_DELTA',net,'PUBLISHED',float(legs.position_delta.sum()),'ROUND_HEDGE',-round(net),flush=True)
print('DONE',flush=True)
