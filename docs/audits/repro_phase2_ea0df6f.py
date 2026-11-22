import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from src.heston.solver_2d import Heston2DSolver,compute_temporal_consistency_defect
from src.heston.pipeline_phase2 import get_phase1_poc_params
from src.heston.rates_curve import get_official_yield_curve
s=Heston2DSolver();p=get_phase1_poc_params();c=get_official_yield_curve()
for typ in ('C','CALL','binary','X',''):
 for T in (0.,31/365):
  try:s.price(12.33,T,p,c,spot=90.,option_type=typ)
  except ValueError:print('UNSUPPORTED_REJECTED',repr(typ),T,flush=True)
  else:raise AssertionError('invalid contract accepted')
rows=[]
for row in pd.read_csv('data/heston/phase2/smoke_test_results.csv').itertuples():
 r=s.price(row.strike,row.maturity_years,p,c,is_american=row.contract=='American',n_s=160,n_v=80,m_t=100)
 assert r.theta is None;assert r.vega==r.d_price_d_v0;assert r.max_complementarity_residual==r.max_algebraic_complementarity_residual
 rows.append(dict(case=row.case_id,price=r.price,export=row.proprietary_solver_usd,delta=r.price-row.proprietary_solver_usd))
print('REPLAY_MAX',max(abs(x['delta']) for x in rows),flush=True)
pd.DataFrame(rows).to_csv('audit_replay.csv',index=False)
a=s.price(15.,31/365,p,c,option_type='P');b=s.price(15.,31/365,p,c,option_type='PUT');print('PUT_ALIAS_DELTA',abs(a.price-b.price),flush=True)
result=compute_temporal_consistency_defect();published=pd.read_csv('data/heston/phase2/temporal_consistency.csv')
print('TEMPORAL_CONTROL',result,flush=True)
print('TEMPORAL_TABLE_MAX',max(abs(result[i]['max_price_step_defect_core']-published.iloc[i].max_price_step_defect_core) for i in range(3)),flush=True)
m=json.loads(Path('data/heston/phase2/phase2_execution_manifest.json').read_text());print('ARTIFACT_HASHES',[(n,hashlib.sha256((Path('data/heston/phase2')/n).read_bytes()).hexdigest()==h) for n,h in m['output_files'].items()],flush=True)
print('DONE',flush=True)
