import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import tempfile,contextlib,io
import pandas as pd
import src.heston.pipeline_phase3 as pipe
base=Path('data/heston/phase3')
load=lambda n:pd.read_csv(base/n)
a=load('market_97_puts_validation.csv');b=load('market_97_summary_by_tenor.csv');c=load('market_97_summary_by_partition.csv');bad=load('market_worst3_refinement.csv');bad.loc[0,'abs_err_extrafine_vs_ql1000']=1.;bad.loc[0,'status_extrafine_target']='FAIL'
pipe.run_market_97_validation=lambda:(a,b,c,bad)
pipe.run_hypothetical_regimes_108=lambda:(load('hypothetical_regimes_108.csv'),load('regimes_mesh_refinement.csv'))
pipe.run_analytical_limits_validation=lambda:load('analytical_limits_validation.csv')
pipe.run_continuity_and_edge_cases=lambda:load('continuity_edge_cases.csv')
pipe.run_economic_arbitrage_checks=lambda:load('economic_arbitrage_checks.csv')
pipe.run_rates_curve_integration_check=lambda:load('rates_curve_integration_check.csv')
with tempfile.TemporaryDirectory() as t,contextlib.redirect_stdout(io.StringIO()):result=pipe.run_phase3_pipeline(Path(t))
print('NEGATIVE_AGGREGATOR_WORST_INPUT',bad.loc[0,['abs_err_extrafine_vs_ql1000','status_extrafine_target']].to_dict())
print('NEGATIVE_AGGREGATOR_SUMMARY',result['validation_summary']['worst_3_refinement_status'])
