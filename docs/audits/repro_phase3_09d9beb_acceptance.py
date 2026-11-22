import sys, json, hashlib, contextlib, io, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import pandas as pd
import src.heston.pipeline_phase3 as p
base=Path('data/heston/phase3').resolve()
with tempfile.TemporaryDirectory() as t:
    with contextlib.redirect_stdout(io.StringIO()):
        m=p.run_phase3_pipeline(Path(t)/'out', data_dir=base)
    print('FULL_ISOLATED_REPLAY',json.dumps(m['validation_summary']),flush=True)
    assert m['validation_summary']['overall_status']=='PASSED'
    assert m['execution_provenance']['prices_source_commit']=='37bbd12d52819c765c64a950333962af9410073d'
# Retain actual loaders, economic builder and gate. Only costly unchanged reference stages use fixtures below.
p.run_analytical_limits_validation=lambda:pd.read_csv(base/'analytical_limits_validation.csv')
p.run_rates_curve_integration_check=lambda:pd.read_csv(base/'rates_curve_integration_check.csv')
for case in ('regime_paired','continuity_paired','economic_eps','missing_market'):
    with tempfile.TemporaryDirectory() as t:
        cache=Path(t)/'cache';shutil.copytree(base,cache)
        if case=='regime_paired':
            f=cache/'hypothetical_regimes_108.csv';d=pd.read_csv(f)
            cols=[c for c in d.columns if 'price' in c.lower() or 'usd' in c.lower()]
            # Byte-level change of a numeric payload is enough to invalidate the immutable snapshot.
            col=next(c for c in cols if pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().all())
            d.loc[0,col]+=1.;d.to_csv(f,index=False)
        elif case=='continuity_paired':
            f=cache/'continuity_edge_cases.csv';d=pd.read_csv(f);d.loc[0,'abs_error_usd']=0.;d.to_csv(f,index=False)
        elif case=='economic_eps':
            f=cache/'economic_arbitrage_checks.csv';d=pd.read_csv(f);d['empirical_truncation_eps']=10.;d.to_csv(f,index=False)
        else:
            (cache/'market_97_puts_validation.csv').unlink()
            # Missing provenance must abort in strict reuse, rather than approve an incomplete run.
            try:
                p.load_verified_snapshot_table('market_97_puts_validation.csv',data_dir=cache,strict=True)
            except (p.SnapshotIntegrityError,FileNotFoundError):
                print('ADDITIONAL_NEGATIVE',case,'REJECTED',flush=True);continue
            raise AssertionError(case)
        with contextlib.redirect_stdout(io.StringIO()):
            m=p.run_phase3_pipeline(Path(t)/'out',data_dir=cache)
        print('ADDITIONAL_NEGATIVE',case,m['validation_summary']['overall_status'],flush=True)
        assert m['validation_summary']['overall_status']=='FAILED'
print('ALL_CONTROLS_PASS',flush=True)
