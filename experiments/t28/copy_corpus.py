"""Run in Docker with original T27 storage read-only and fresh T28 destination."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    if not args.run.replace('-', '').isalnum():
        raise ValueError('simple fresh run name required')
    target = Path('/destination')/args.run
    if target.exists(): raise ValueError('preserve existing destination')
    result = {}
    for suite in ('t14', 't11'):
        source = Path('/original/paired-v1')/suite
        before = hashes(source)
        if not before: raise ValueError('missing baseline corpus')
        shutil.copytree(source, target/suite)
        after = hashes(target/suite)
        if before != after or hashes(source) != before:
            raise ValueError('copy verification failed')
        result[suite] = {'source': str(source), 'destination': str(target/suite), 'files': before}
    with (Path('/out')/(args.run+'-corpus-copy.json')).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print('Verified copied corpora:', {k: len(v['files']) for k, v in result.items()})


if __name__ == '__main__': main()
