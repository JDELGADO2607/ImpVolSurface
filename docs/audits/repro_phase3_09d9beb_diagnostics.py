import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import hashlib,json,os
import numpy as np,pandas as pd
from src.heston.pipeline_phase3 import run_economic_arbitrage_checks,run_rates_curve_integration_check,VERIFIED_SNAPSHOT_METADATA
from src.heston.rates_curve import get_official_yield_curve
from src.heston.heston_model import HestonOptionPricer
base=Path('data/heston/phase3');m=json.loads((base/'phase3_execution_manifest.json').read_text())
names=['market_97_puts_validation.csv','market_97_summary_by_tenor.csv','market_97_summary_by_partition.csv','market_worst3_refinement.csv','hypothetical_regimes_108.csv','regimes_mesh_refinement.csv','continuity_edge_cases.csv']
for n in names:print('SNAPSHOT_PRICE_HASH',n,hashlib.sha256((base/n).read_bytes()).hexdigest()==VERIFIED_SNAPSHOT_METADATA['tables'][n],flush=True)
print('OUTPUT_HASHES',all(hashlib.sha256((base/n).read_bytes()).hexdigest()==v for n,v in m['output_files'].items()),flush=True)
paths={'puts_selected_clean':'data/heston/puts_selected_clean.csv','options_clean':'outputs/tables/options_clean.csv','treasury_cmt_raw':'data/heston/treasury_cmt_2026_11_17_raw.json','rates_treasury_manifest':'data/heston/rates_treasury_manifest.json','data_split_manifest':'data/heston/data_split_manifest.json','phase0_manifest':'data/heston/phase0_execution_manifest.json','phase1_manifest':'data/heston/phase1/phase1_execution_manifest.json'}
for k,v in m['input_hashes'].items():print('INPUT_HASH',k,hashlib.sha256(Path(paths[k]).read_bytes()).hexdigest()==v,flush=True)
for key,v in m['source_hashes'].items():
 name=key.removesuffix('_py')+'.py';raw=(Path('src/heston')/name).read_bytes();lf=raw.replace(b'\r\n',b'\n');crlf=lf.replace(b'\n',b'\r\n')
 print('SOURCE_HASH',name,'exact',hashlib.sha256(raw).hexdigest()==v,'lf_match',hashlib.sha256(lf).hexdigest()==v,'crlf_match',hashlib.sha256(crlf).hexdigest()==v,flush=True)
e=run_economic_arbitrage_checks();prev=pd.read_csv(base/'economic_arbitrage_checks.csv');print('CALENDAR_REPLAY_MAX',np.nanmax(abs(e.calendar_raw_diff-prev.calendar_raw_diff)),flush=True);print('CALENDAR_COUNT',e.calendar_raw_diff.notna().sum(),'RAW_NEGATIVE',(e.calendar_raw_diff<0).sum(),'TOL_VIOLATIONS',sum(e.calendar_violation>0),flush=True)
r=run_rates_curve_integration_check();rp=pd.read_csv(base/'rates_curve_integration_check.csv');print('RATES_REPLAY_MAX',max(abs(r.discrepancy-rp.discrepancy)),flush=True)
c=get_official_yield_curve();pr=HestonOptionPricer();ts=np.linspace(.001,3,10000);print('QL_CONTINUOUS_D_MAX',max(abs(pr.ts_handle.discount(float(t))-c.get_discount_factor(float(t))) for t in ts),flush=True)
l=pd.read_csv(base/'analytical_limits_validation.csv');z=l[l.parameter_v0.eq(0.)];print('V0_ZERO_ROWS',z[['abs_err_usd','max_abs_err_usd','status_target_002','ql_status','ql_exception']].to_dict('records'),flush=True)
print('SCIPY_METADATA',m['execution_provenance']['scipy_version'],flush=True)
print('DONE',flush=True)
