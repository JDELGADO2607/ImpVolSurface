import sys,json,tempfile,shutil,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import pandas as pd,numpy as np
import src.heston.pipeline_phase3 as s
import src.heston.pipeline_phase4 as p
root=Path.cwd();oldroot=s.root_dir
winner=json.loads(Path('data/heston/phase4/heston_calibrated_parameters.json').read_text());curve=p.get_official_yield_curve();ts=curve.to_quantlib_term_structure(dense_daily=True)
clean=pd.read_csv('data/heston/puts_selected_clean.csv');clean=clean[clean.contractSymbol.eq('NU261218P00012000')]
for case in ('legitimate','solver_source_changed','financial_input_changed'):
 with tempfile.TemporaryDirectory() as t:
  fake=Path(t)/'source';out=Path(t)/'out';out.mkdir()
  for _,(rel,_) in s.VERIFIED_SNAPSHOT_METADATA['inputs'].items():
   dest=fake/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(root/rel,dest)
  for _,(rel,_) in s.VERIFIED_SNAPSHOT_METADATA['pricing_sources'].items():
   dest=fake/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(root/rel,dest)
  if case=='solver_source_changed':
   dest=fake/'src/heston/solver_2d.py';code=dest.read_text();changed=code.replace('theta_adi: float = 1.0 / 3.0','theta_adi: float = 0.5',1);assert changed!=code;dest.write_text(changed)
  elif case=='financial_input_changed':
   dest=fake/'data/heston/puts_selected_clean.csv';d=pd.read_csv(dest);d.loc[0,'lastPrice']+=.01;d.to_csv(dest,index=False)
  s.root_dir=fake
  with contextlib.redirect_stdout(io.StringIO()):
   d,_,_=p.step5_full_pricing_evaluation(winner,curve,ts,out_puts_csv_path=out/'puts.csv',out_part_csv_path=out/'part.csv',out_tenor_csv_path=out/'tenor.csv',df_clean_override=clean)
  provenance=d.valuation_provenance.iloc[0]
  print('ACTUAL_DEPENDENCY_ROUTE',case,provenance,'finite',bool(np.isfinite(d.prop_fine_price).all()),flush=True)
  assert provenance==('PHASE3_VERIFIED_AUDITED' if case=='legitimate' else 'FRESH_SOLVER_2D_VALUATION')
s.root_dir=oldroot
print('DONE',flush=True)
