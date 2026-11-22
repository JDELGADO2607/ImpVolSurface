import hashlib,json,zipfile
from pathlib import Path
roots={'data','docs','results','outputs','figures'}
with zipfile.ZipFile('source.zip') as z:
    expected={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/') and n.split('/')[0] in roots}
actual={p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in Path(root).rglob('*') if p.is_file()}
changed=[n for n in expected if actual.get(n)!=expected[n]]
added=sorted(set(actual)-set(expected))
print('ARCHIVE_OFFICIAL_HASH_CHECK',json.dumps({'versioned_files':len(expected),'changed_or_missing':changed,'added':added}))
assert not changed and not added
