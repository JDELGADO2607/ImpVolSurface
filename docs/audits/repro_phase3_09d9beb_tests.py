import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pathlib import Path
import hashlib,subprocess,json
files=[p for d in ('data','docs','results') for p in Path(d).rglob('*') if p.is_file()]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
r=subprocess.run(['python','-m','pytest','tests/test_heston_phase0.py','tests/test_heston_phase1.py','tests/test_heston_phase2.py','tests/test_heston_phase3.py','-q'],capture_output=True,text=True)
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
Path('audit_tests.log').write_text(r.stdout+r.stderr+'\nHASH_CHANGES '+json.dumps([p for p in before if before[p]!=after[p]]))
print(r.returncode,r.stdout[-500:]);print('HASH_CHANGES',[p for p in before if before[p]!=after[p]])
