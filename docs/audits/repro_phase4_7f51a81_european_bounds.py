import sys,json,contextlib,io,tempfile,shutil,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import pandas as pd,numpy as np
import src.heston.pipeline_phase4 as p
b=p.PHASE4_DIR;cfg=p.load_config();w=json.loads((b/'heston_calibrated_parameters.json').read_text());load=lambda n:pd.read_csv(b/n)
curve=p.get_official_yield_curve();econ=load('heston_representative_economic_controls.csv')
lo=np.array([max(float(r.strike)*curve.get_discount_factor(float(r.tau_years))-12.33,0.) for _,r in econ.iterrows()]);up=np.array([float(r.strike)*curve.get_discount_factor(float(r.tau_years)) for _,r in econ.iterrows()])
print('LEGITIMATE_EUROPEAN_BOUNDS',bool(((econ.price_european>=lo-1e-4)&(econ.price_european<=up+1e-4)).all()),flush=True)
print('ORIGINAL_ITM_CONTROLS',econ.assign(discounted_lower_bound=lo).query('discounted_lower_bound>0')[['contract_id','price_european','discounted_lower_bound']].to_json(orient='records'),flush=True)
with tempfile.TemporaryDirectory() as t:
 p.PHASE4_DIR=Path(t);shutil.copytree(b,Path(t),dirs_exist_ok=True)
 econ['price_european']=0.;econ['early_exercise_premium']=econ.price_american
 with contextlib.redirect_stdout(io.StringIO()):m=p.step10_build_manifest({},cfg,w,load('heston_pricing_full_puts.csv'),load('heston_pricing_summary_by_partition.csv'),load('heston_worst3_mesh_controls.csv'),econ,time.time())
 print('ZERO_EUROPEAN_WITH_COHERENT_EEP',m['verdict'],'violated_lower_bounds',int((econ.price_european<lo-1e-4).sum()),'largest_shortfall',float(max(lo-econ.price_european)),flush=True)
 assert m['verdict']=='PASS' # Records the defect; this assertion must change when corrected.
p.PHASE4_DIR=b
