import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import tempfile,shutil,io,contextlib
from pathlib import Path
import pandas as pd
import src.heston.pipeline_phase1 as pipe
class StopProbe(Exception): pass
class FakePricer:
 def __init__(self,*a,**kw): pass
 def price_american(self,K,exp,params,**kw):
  print('CACHE_ACCEPTED_PARAMETERS',params.to_dict())
  raise StopProbe('Pricing reached without rejecting stale or invalid cache')
pipe.HestonOptionPricer=FakePricer
for case in ('changed_train_only','negative_sse_only'):
 with tempfile.TemporaryDirectory() as t:
  data=Path(t)/'data'; shutil.copytree('data/heston',data); out=data/'phase1'
  if case=='changed_train_only':
   train=pd.read_csv(data/'data_split_train.csv'); train.loc[0,'lastPrice']+=.01; train.to_csv(data/'data_split_train.csv',index=False)
  else:
   ms=pd.read_csv(out/'heston_multistart_results.csv'); ms.loc[ms.start_index.eq(3),'final_sse']=-1.; ms.to_csv(out/'heston_multistart_results.csv',index=False)
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf):
   try: pipe.run_phase1_pipeline(str(data),str(out))
   except StopProbe as e: print('PROBE_RESULT',str(e))
  print('NEGATIVE_CASE',case); print(buf.getvalue())
