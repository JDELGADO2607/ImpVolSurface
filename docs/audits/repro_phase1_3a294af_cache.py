import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import tempfile,shutil,json
import pandas as pd,numpy as np
from src.heston.heston_model import HestonOptionPricer
from src.heston.pipeline_phase1 import validate_and_load_multistart_cache
m=json.loads(Path('data/heston/phase1/phase1_execution_manifest.json').read_text())
train=pd.read_csv('data/heston/data_split_train.csv');pr=HestonOptionPricer()
with tempfile.TemporaryDirectory() as t:
 out=Path(t); shutil.copy('data/heston/phase1/phase1_execution_manifest.json',out)
 ms=pd.read_csv('data/heston/phase1/heston_multistart_results.csv')
 mask=ms.start_index.eq(3);ms.loc[mask,'status']=2;ms.loc[mask,'success']=False;ms.loc[mask,'termination_type']='ABNORMAL_TERMINATION';ms.loc[mask,'final_sse']=0.;ms.loc[mask,'final_rmse']=0.
 ms.to_csv(out/'heston_multistart_results.csv',index=False)
 print('PROBE: status2 candidate3 with forged SSE=0 and consistent RMSE=0; all inputs hashes unchanged',flush=True)
 p,rows,disp=validate_and_load_multistart_cache(out,m['input_hashes'],train,pr.ts_handle,pr.eval_date)
 print('INVALID_CACHE_ACCEPTED',disp['best_start_index'],'selected_sse',disp['best_train_sse'],'parameters',p.to_dict(),flush=True)
 print('ACTUAL_FINE_SSE_SELECTED',rows.loc[rows.start_index.eq(3),'fine_grid_sse'].iloc[0],flush=True)
 print('BEST_FINE_START',rows.sort_values('fine_grid_sse').iloc[0].start_index,flush=True)
 assert disp['best_start_index']==3,'counterexample changed'
 print('DEMONSTRATED',flush=True)

from src.heston.calibration import HestonCalibrator
coarse=HestonCalibrator(train,pr.ts_handle).evaluate_sse(p.to_array())
print('ACTUAL_COARSE_SSE_SELECTED',coarse,flush=True)
assert coarse>0.5
