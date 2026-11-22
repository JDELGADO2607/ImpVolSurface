import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import numpy as np,pandas as pd,math,json,hashlib
from src.heston.rates_curve import get_official_yield_curve
c=get_official_yield_curve();d=pd.read_csv('data/heston/phase3/economic_arbitrage_checks.csv')
comparisons=[]
for K,g in d.groupby('strike'):
 g=g.sort_values('maturity_years');diff=np.diff(g.price_american);eps=g.empirical_truncation_eps.to_numpy();tol=eps[1:]+eps[:-1]
 for i,z in enumerate(diff):comparisons.append((K,g.iloc[i].tenor_label,g.iloc[i+1].tenor_label,z,tol[i]))
print('CALENDAR_PAIR_COUNT',len(comparisons));print('CALENDAR_MIN',min(comparisons,key=lambda x:x[3]));print('CALENDAR_NEGATIVE_RAW',[x for x in comparisons if x[3]<0]);print('CALENDAR_VIOLATIONS_BEYOND_EMPIRICAL', [x for x in comparisons if x[3]<-x[4]])
print('UPPER_BOUND_WORST',float((d.price_american-d.strike).max()));print('FINITENESS',np.isfinite(d[['price_american','price_european']]).all().all())
a=pd.read_csv('data/heston/phase3/market_97_puts_validation.csv');default_error=a.proprietary_default_usd-a.ql_refined_700_usd;print('DEFAULT_MARKET_MAX',default_error.abs().max(),'DEFAULT_MARKET_MAE',default_error.abs().mean());print('COVERAGE',len(a),a.contractSymbol.nunique())
b=pd.read_csv('data/heston/phase3/hypothetical_regimes_108.csv');print('REGIME_COUNTS',b.groupby(['regime_id','contract_style']).size().to_dict())
for day in (31,94,212,430,794):
 T=day/365
 for factor,minimum in ((300,60),(600,100),(900,160)):
  N=max(minimum,round(factor*T));dt=T/N;times=T-(np.arange(N)+.5)*dt;rs=np.array([c.get_instantaneous_forward_rate(float(t)) for t in times]);disc=math.exp(-sum(rs)*dt);print('ACTUAL_STEP_DISCOUNT',day,N,'D_error',disc-c.get_discount_factor(T))
pr=pd.read_csv('data/heston/phase3/market_worst3_refinement.csv')
for r in pr.itertuples():print('WORST3_OWN_SEQUENCE',r.contractSymbol,r.price_default,r.price_fine,r.price_extrafine_320x160_m900,'ERROR_FIXED_QL1000',r.price_default-r.ql_ultra_1000,r.price_fine-r.ql_ultra_1000,r.price_extrafine_320x160_m900-r.ql_ultra_1000)
m=json.loads(Path('data/heston/phase3/phase3_execution_manifest.json').read_text());print('HASHES',[(n,hashlib.sha256((Path('data/heston/phase3')/n).read_bytes()).hexdigest()==h) for n,h in m['output_files'].items()]);print('MANIFEST_HAS_INPUT_HASHES','input_hashes' in m,'MANIFEST_HAS_CODE_ID',any(k in m for k in ('code_sha','source_sha','source_hashes','commit','sha')))

e=pd.read_csv('data/heston/phase3/economic_arbitrage_checks.csv');r=e.query('strike==17 and tenor_label=="794d"').iloc[0];edge=pd.read_csv('data/heston/phase3/continuity_edge_cases.csv').query('test_case=="Deep_ITM_Jan2029"').iloc[0]
print('EMPIRICAL_EPS_VS_REFINED_REFERENCE',r.empirical_truncation_eps,abs(r.price_american-edge.ql_reference_usd),abs(r.price_american-edge.ql_reference_usd)/r.empirical_truncation_eps)
