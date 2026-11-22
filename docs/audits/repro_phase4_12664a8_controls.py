import sys,json,time,tempfile,shutil,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,pandas as pd
import src.heston.pipeline_phase4 as p
root=Path.cwd();data=root/'data/heston';base=data/'phase4';cfg=p.load_config();w=json.loads((base/'heston_calibrated_parameters.json').read_text());original=p.PHASE4_DIR
load=lambda n:pd.read_csv(base/n)
for case in ('legitimate','price_plus_one','price_nan','reference_nan','market_nan','default_inf','missing_economic','invalid_parameter','changed_summary_only','bad_raw_partition','mesh_raw_bad','all_local_failed'):
 with tempfile.TemporaryDirectory() as t:
  p.PHASE4_DIR=Path(t);shutil.copytree(base,p.PHASE4_DIR,dirs_exist_ok=True)
  puts=load('heston_pricing_full_puts.csv');part=load('heston_pricing_summary_by_partition.csv');mesh=load('heston_worst3_mesh_controls.csv');econ=load('heston_representative_economic_controls.csv');meta=json.loads(json.dumps(w))
  if case=='price_plus_one':puts.loc[0,'prop_fine_price']+=1.
  elif case=='price_nan':puts.loc[0,'prop_fine_price']=np.nan
  elif case=='reference_nan':puts.loc[0,'ql_fine_price']=np.nan
  elif case=='market_nan':puts.loc[0,'lastPrice']=np.nan
  elif case=='default_inf':puts.loc[0,'prop_default_price']=np.inf
  elif case=='missing_economic':(p.PHASE4_DIR/'heston_representative_economic_controls.csv').unlink()
  elif case=='invalid_parameter':meta['calibrated_parameters_raw'][0]=-1.
  elif case=='changed_summary_only':part.loc[part.partition.eq('train'),'n_contracts']=59
  elif case=='bad_raw_partition':puts.loc[0,'partition']='tenor_holdout'
  elif case=='mesh_raw_bad':mesh.loc[0,'abs_diff_ql_refinement_usd']=1.;mesh.loc[0,'ql_ultrafine_1000_usd']+=1.
  elif case=='all_local_failed':
   f=p.PHASE4_DIR/'heston_local_refinements.csv';d=pd.read_csv(f);d.loc[d.start_index.gt(0),['status','success']]=[2,False];d.to_csv(f,index=False)
  try:
   with contextlib.redirect_stdout(io.StringIO()):m=p.step10_build_manifest({},cfg,meta,puts,part,mesh,econ,time.time())
   print('REAL_GATE',case,m['verdict'],m['recalculated_raw_metrics'],flush=True)
  except Exception as e:print('REAL_GATE',case,'REJECTED',type(e).__name__,str(e),flush=True)
p.PHASE4_DIR=original
curve=p.get_official_yield_curve();ts=curve.to_quantlib_term_structure(dense_daily=True)
# One real contract exercises the production valuation stage; global gate coverage is tested separately above.
with tempfile.TemporaryDirectory() as t:
 fake=Path(t)/'heston';shutil.copytree(data,fake);p.DATA_DIR=fake;p.PHASE4_DIR=fake/'phase4'
 clean=pd.read_csv(fake/'puts_selected_clean.csv');clean=clean[clean.contractSymbol.eq('NU261218P00012000')];assert len(clean)==1;clean.to_csv(fake/'puts_selected_clean.csv',index=False)
 f=fake/'phase3/market_97_puts_validation.csv';snap=pd.read_csv(f);snap.loc[snap.contractSymbol.eq(clean.iloc[0].contractSymbol),'proprietary_fine_usd']=np.nan;snap.to_csv(f,index=False)
 with contextlib.redirect_stdout(io.StringIO()):out,part,ten=p.step5_full_pricing_evaluation(w,curve,ts)
 print('STEP5_INVALID_PHASE3_SNAPSHOT',out[['contractSymbol','prop_fine_price','status_discrepancy_gate_002']].to_json(orient='records'),'provenance',[(c,out[c].iloc[0]) for c in out if 'provenance' in c],flush=True)
 meta=json.loads(json.dumps(w));meta['calibrated_parameters_raw'][0]=.20;meta['selection_status']='WINNER_NEW_OPTIMUM'
 with contextlib.redirect_stdout(io.StringIO()):out,part,ten=p.step5_full_pricing_evaluation(meta,curve,ts);mesh=p.step6_worst3_mesh_controls(out,meta,curve,ts)
 print('FRESH_CHANGED_VECTOR_REAL_API',out[['prop_fine_price','ql_fine_price','abs_diff_prop_fine_vs_ql_fine_usd']].to_json(orient='records'),'EXTRAFINE',mesh[['abs_diff_ql_refinement_usd','abs_diff_prop_refinement_usd']].to_json(orient='records'),flush=True)
p.DATA_DIR=data;p.PHASE4_DIR=original
print('DONE',flush=True)
