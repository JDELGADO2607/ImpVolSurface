import sys, json, tempfile, shutil, contextlib, io, time, inspect
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,pandas as pd
import src.heston.pipeline_phase4 as p
from src.heston.rates_curve import get_official_yield_curve
root=Path.cwd();base=root/'data/heston/phase4';orig=p.PHASE4_DIR
cfg=p.load_config();winner=json.loads((base/'heston_calibrated_parameters.json').read_text())
curve=get_official_yield_curve();ts=curve.to_quantlib_term_structure(dense_daily=True)
clean=pd.read_csv('data/heston/puts_selected_clean.csv');split=json.loads(Path('data/heston/data_split_manifest.json').read_text());train=clean[clean.contractSymbol.isin(split['train_symbols'])]
exact_poc=np.array([0.18613777847584,2.7254603668370714,0.2136796992000426,0.4817847258429695,-0.9498066630129804])
print('PARAMETER_DELTA_EXACT_POC',np.array(winner['calibrated_parameters_raw'])-exact_poc,flush=True)
for case in ('legitimate','price_payload_plus_one','missing_economic','invalid_parameter','wrong_partition_count'):
 with tempfile.TemporaryDirectory() as t:
  p.PHASE4_DIR=Path(t);shutil.copytree(base,p.PHASE4_DIR,dirs_exist_ok=True)
  part=pd.read_csv(base/'heston_pricing_summary_by_partition.csv');w3=pd.read_csv(base/'heston_worst3_mesh_controls.csv');w=json.loads(json.dumps(winner))
  if case=='price_payload_plus_one':
   f=p.PHASE4_DIR/'heston_pricing_full_puts.csv';d=pd.read_csv(f);d.loc[0,'prop_fine_price']+=1.;d.to_csv(f,index=False)
  elif case=='missing_economic':(p.PHASE4_DIR/'heston_representative_economic_controls.csv').unlink()
  elif case=='invalid_parameter':w['calibrated_parameters_raw'][0]=-1.
  elif case=='wrong_partition_count':part.loc[part.partition.eq('train'),'n_contracts']=59
  with contextlib.redirect_stdout(io.StringIO()):m=p.step10_build_manifest({},cfg,w,part,w3,time.time())
  print('ACTUAL_MANIFEST_GATE',case,m['verdict'],'outputs',len(m['output_files']),flush=True)
with tempfile.TemporaryDirectory() as t:
 p.PHASE4_DIR=Path(t)
 try:
  with contextlib.redirect_stdout(io.StringIO()):p.step3_assemble_local_refinements(train,ts,cfg)
 except Exception as e:print('CLEAN_EXTRACTION_STEP3',type(e).__name__,str(e),flush=True)
 # Force fresh valuation branch, without altering any financial data.
 w=json.loads(json.dumps(winner));w['selection_status']='WINNER_NEW_OPTIMUM'
 try:
  with contextlib.redirect_stdout(io.StringIO()):p.step5_full_pricing_evaluation(w,curve,ts)
 except Exception as e:print('FRESH_SOLVER_BRANCH',type(e).__name__,str(e),flush=True)
# Reuse path ignores changed parameters even at the public stage interface.
with tempfile.TemporaryDirectory() as t:
 p.PHASE4_DIR=Path(t);shutil.copytree(base,p.PHASE4_DIR,dirs_exist_ok=True)
 w=json.loads(json.dumps(winner));w['calibrated_parameters_raw'][0]=.5
 with contextlib.redirect_stdout(io.StringIO()):d,_,_=p.step5_full_pricing_evaluation(w,curve,ts)
 print('CHANGED_V0_RETURNS_OLD_PRICES',d.prop_fine_price.equals(pd.read_csv(base/'heston_pricing_full_puts.csv').prop_fine_price),flush=True)
p.PHASE4_DIR=orig
d=pd.read_csv(base/'heston_baseline_comparison.csv')
for c in ['price_heston_ql_fine','price_heston_prop_fine','price_flat_common_curve','price_flat_contract_rate','price_svi_historical_r3']:
 e=d[c]-d.lastPrice;print('BASELINE_METRICS',c,len(d),'MAE',abs(e).mean(),'RMSE',np.sqrt((e*e).mean()),flush=True)
sens=pd.read_csv(base/'heston_parameter_sensitivity.csv');r=sens[sens.param_shocked.eq('rho')]
print('RHO_SENSITIVITY',r[['scenario_id','rho','shock_val','delta_sse_vs_base']].to_json(orient='records'),flush=True)
print('SOURCE_SOLVER_SIGNATURE',inspect.signature(p.Heston2DSolver),inspect.signature(p.Grid2D),flush=True)
print('TRAIN_TENORS',train.expirationDate.nunique(),'HOLDOUT_TENORS',split['held_out_tenors'],flush=True)
print('OMITTED_OPTIMIZER_FILES',[n for n in ['refinement_A_res.json','refinement_B_res.json','refinement_C_res.json'] if not (base/n).exists()],flush=True)
print('DONE',flush=True)
