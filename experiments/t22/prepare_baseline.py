"""Create a fresh baseline build context without changing the working checkout."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root=Path(sys.argv[1])
root.mkdir(parents=True,exist_ok=False)
archive=zipfile.ZipFile(io.BytesIO(subprocess.check_output(['git','archive','--format=zip','c7427f3'])))
for name in archive.namelist():
    if name.startswith('src/') or name in ['Cargo.toml','Cargo.lock','LICENSE','.dockerignore']:
        archive.extract(name,root)
for name in ['examples/filter_profile.rs','docker/filter-profile.Dockerfile']:
    target=root/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(name,target)
with (root/'.dockerignore').open('a') as stream:stream.write('\n!docker/filter-profile.Dockerfile\n')
manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
(root/'source-hashes.json').write_text(json.dumps(manifest,indent=2))
print('Created T21 baseline context with the current identical profiler:',root)
