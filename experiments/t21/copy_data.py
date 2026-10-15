"""Copy stopped T20 fixture volumes read-only; preserve file hashes for rechecking."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

def hashes(root):
    result = {}
    for size in ('2', '400', '1600'):
        for path in sorted((root / size).rglob('*')):
            if path.is_file():
                with path.open('rb') as stream:
                    result[str(path.relative_to(root))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return result

source, destination, report = map(Path, sys.argv[2:])
if sys.argv[1] == 'copy':
    before = hashes(source)
    assert before and not any(destination.iterdir()), 'source must exist and destination must be empty'
    for size in ('2', '400', '1600'):
        shutil.copytree(source / size, destination / size)
    assert hashes(source) == hashes(destination) == before
    with report.open('x') as stream:
        json.dump(before, stream, indent=2)
    print(f'Copied and verified {len(before)} files; original mounted read-only.')
elif sys.argv[1] == 'check-source':
    expected = json.loads(report.read_text())
    assert hashes(source) == expected, 'original T20 volume changed'
    print(f'Original T20 volume unchanged: {len(expected)} hashes verified.')
else:
    raise ValueError('expected copy or check-source')
