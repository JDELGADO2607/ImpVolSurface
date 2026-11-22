import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import tempfile,shutil,contextlib,io,json,hashlib
import numpy as np,pandas as pd
import src.heston.pipeline_phase3 as pipe
base=Path('data/heston/phase3').resolve()
load=lambda n:pd.read_csv(base/n)
# Keep expensive independent limits/diagnostics as their legitimate immutable fixtures; exercise real cache loader and real aggregation.
pipe.run_analytical_limits_validation=lambda:load('analytical_limits_validation.csv')
pipe.run_continuity_and_edge_cases=lambda **kw:load('continuity_edge_cases.csv')
pipe.run_economic_arbitrage_checks=lambda **kw:load('economic_arbitrage_checks.csv')
pipe.run_rates_curve_integration_check=lambda:load('rates_curve_integration_check.csv')
for scenario in ('legitimate','raw_price_changed','numeric_failure_label_PASS'):
 with tempfile.TemporaryDirectory() as t:
  cache=Path(t)/'cache';shutil.copytree(base,cache);out=Path(t)/'out';pipe.DATA_DIR=cache
  f=cache/'market_97_puts_validation.csv';df=pd.read_csv(f)
  if scenario=='raw_price_changed':df.loc[0,'proprietary_fine_usd']+=1.;df.to_csv(f,index=False)
  if scenario=='numeric_failure_label_PASS':df.loc[0,'abs_err_fine_usd']=1.;df.to_csv(f,index=False)
  with contextlib.redirect_stdout(io.StringIO()):m=pipe.run_phase3_pipeline(out)
  actual_hash=hashlib.sha256(f.read_bytes()).hexdigest();baseline=json.loads((cache/'phase3_execution_manifest.json').read_text())['output_files']['market_97_puts_validation.csv']
  print('CACHE_PROBE',scenario,'original_hash_matches',actual_hash==baseline,'overall',m['validation_summary']['overall_status'],'market_status',m['validation_summary']['market_97_status'],'market_max_err',m['validation_summary']['market_97_puts']['max_abs_err_usd'],'prices_source',m['execution_provenance']['prices_source_commit'],flush=True)
  if scenario=='raw_price_changed':print('ACTUAL_PRICE_ERROR_ROW0',float(df.loc[0,'proprietary_fine_usd']-df.loc[0,'ql_refined_700_usd']),flush=True)
print('DONE',flush=True)
