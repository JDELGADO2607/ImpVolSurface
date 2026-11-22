import hashlib,subprocess,json
from pathlib import Path
def hashes():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in ('data','docs','outputs','results','figures') for p in Path(d).rglob('*') if p.is_file()}
before=hashes()
r=subprocess.run(['python','-m','pytest',*[f'tests/test_heston_phase{i}.py' for i in range(5)],'-q'],capture_output=True,text=True)
after=hashes()
log=r.stdout+r.stderr+'\nHASH_CHANGES '+json.dumps([n for n in before.keys()|after.keys() if before.get(n)!=after.get(n)])
Path('audit_phase4_tests.log').write_text(log,encoding='utf-8');print(log,flush=True)
print('EXIT_CODE',r.returncode,flush=True)
