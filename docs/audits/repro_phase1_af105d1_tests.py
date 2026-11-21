from pathlib import Path
import hashlib,json,subprocess
files=[p for d in ('data','docs','results') for p in Path(d).rglob('*') if p.is_file()]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
r=subprocess.run(['python','-m','pytest','tests/test_heston_phase0.py','tests/test_heston_phase1.py','-q'],capture_output=True,text=True)
Path('audit_tests.log').write_text(r.stdout+r.stderr)
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
print('PYTEST',r.returncode,r.stdout[-1500:]); print('PRODUCTION_HASH_CHANGES',[p for p in before if before[p]!=after[p]])
