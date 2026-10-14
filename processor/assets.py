"""Explicit setup and offline verification; no downloads from conversion code."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).parent


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(models):
    for entry in json.loads((ROOT / 'models.lock.json').read_text())['files']:
        path = Path(models) / entry['path']
        if not path.is_file() or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError(f"Missing or changed model: {entry['path']}; run explicit setup")
    for path, expected in json.loads((ROOT / 'runtime.lock.json').read_text())['files'].items():
        if digest(path) != expected:
            raise ValueError(f'Changed OCR runtime/data: {path}')
    for line in (ROOT / 'requirements.lock').read_text().splitlines():
        name, version = line.split('==')
        if importlib.metadata.version(name) != version:
            raise ValueError(f'Changed package: {name}')


def profile():
    # Includes code as well as data/settings. A code edit gets a new revision.
    names = ['pdf.py', 'assets.py', 'settings.json', 'models.lock.json',
             'runtime.lock.json', 'requirements.lock']
    # Normalize checkout line endings; binary model hashes always use raw bytes.
    return hashlib.sha256(json.dumps({n: hashlib.sha256((ROOT / n).read_text().encode()).hexdigest() for n in names},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def download(models):
    root = Path(models)
    for entry in json.loads((ROOT / 'models.lock.json').read_text())['files']:
        path = root / entry['path']
        if path.is_file() and digest(path) == entry['sha256']:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.download')
        url = f"https://huggingface.co/{entry['repo']}/resolve/{entry['revision']}/{entry['file']}"
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open('wb') as target:
            total = 0
            while data := source.read(1024 * 1024):
                total += len(data)
                if total > entry['bytes']:
                    raise ValueError('Download larger than locked artifact')
                target.write(data)
        if temporary.stat().st_size != entry['bytes'] or digest(temporary) != entry['sha256']:
            raise ValueError(f"Artifact checksum mismatch: {entry['path']}")
        temporary.replace(path)
        print(entry['path'], flush=True)
    verify(root)
    print('Verified profile', profile())


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('download', 'verify'):
        raise SystemExit('usage: python -m processor.assets download|verify MODELS')
    if sys.argv[1] == 'download':
        download(sys.argv[2])
    else:
        verify(sys.argv[2])
        print(profile())
