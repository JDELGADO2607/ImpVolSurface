import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import tempfile,shutil,contextlib,io,json,hashlib
import numpy as np,pandas as pd
import src.heston.pipeline_phase3 as pipe
base=Path('data/heston/phase3').resolve();root=Path('.').resolve();load=lambda n:pd.read_csv(base/n)
# Keep independent expensive stages as legitimate fixtures; loaders, economic checks and aggregation remain real.
pipe.run_analytical_limits_validation=lambda:load('analytical_limits_validation.csv')
pipe.run_rates_curve_integration_check=lambda:load('rates_curve_integration_check.csv')
for scenario in ('legitimate','old_price_plus_one','old_error_one','paired_price_and_reference','economic_prices_replaced'):
 with tempfile.TemporaryDirectory() as t:
  cache=Path(t)/'cache';shutil.copytree(base,cache);out=Path(t)/'out'
  f=cache/'market_97_puts_validation.csv';d=pd.read_csv(f)
  if scenario=='old_price_plus_one':d.loc[0,'proprietary_fine_usd']+=1.;d.to_csv(f,index=False)
  elif scenario=='old_error_one':d.loc[0,'abs_err_fine_usd']=1.;d.to_csv(f,index=False)
  elif scenario=='paired_price_and_reference':
   d.loc[0,'proprietary_fine_usd']+=1.;d.loc[0,'ql_refined_700_usd']+=1.;d.to_csv(f,index=False)
  elif scenario=='economic_prices_replaced':
   feco=cache/'economic_arbitrage_checks.csv';e=pd.read_csv(feco);e['price_american']=np.maximum(e.strike-12.33,0.)+1e-12;e['price_european']=e.price_american;e.to_csv(feco,index=False)
  with contextlib.redirect_stdout(io.StringIO()):m=pipe.run_phase3_pipeline(out,data_dir=cache)
  print('GATE_CASE',scenario,'overall',m['validation_summary']['overall_status'],'source',m['execution_provenance']['prices_source_commit'],'market',m['validation_summary']['market_97_status'],'economic',m['validation_summary']['economic_arbitrage_status'],flush=True)
  if scenario=='paired_price_and_reference':
   try:pipe.run_market_97_validation(data_dir=cache,strict_verification=True)
   except pipe.SnapshotIntegrityError as exc:print('STRICT_TRUE_REJECTS',type(exc).__name__,flush=True)
with tempfile.TemporaryDirectory() as t:
 fake_root=Path(t)
 for k,(rel,h) in pipe.VERIFIED_SNAPSHOT_METADATA['inputs'].items():
  dest=fake_root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(root/rel,dest)
 
 for module_name in ('solver_2d.py','heston_model.py','rates_curve.py'):
  target=fake_root/'src/heston'/module_name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(root/'src/heston'/module_name,target)
 print('SOURCE_CONTROL_LEGITIMATE_ROOT',pipe.verify_snapshot_inputs_and_params(fake_root),flush=True)
 dest=fake_root/'src/heston/solver_2d.py';dest.parent.mkdir(parents=True,exist_ok=True);code=(root/'src/heston/solver_2d.py').read_text();changed=code.replace('theta_adi: float = 1.0 / 3.0','theta_adi: float = 0.5',1);assert changed!=code;dest.write_text(changed)
 ok,msg=pipe.verify_snapshot_inputs_and_params(fake_root)
 print('CHANGED_PRICING_SOURCE_VERIFICATION',ok,msg,'theta_ADI_changed_1_3_to_1_2',flush=True)
print('DONE',flush=True)
