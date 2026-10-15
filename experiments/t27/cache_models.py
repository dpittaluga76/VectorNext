"""Explicit offline copy into a fresh Linux test volume, checking every copied byte."""
import hashlib
import json
from pathlib import Path


def main():
    for name in ('/experiments/t02/models.26b.lock.json', '/experiments/t27/models.12b.lock.json'):
        spec = json.loads(Path(name).read_bytes())['models']['generator']
        artifact = next(f for f in spec['files'] if f['path'].endswith('.gguf'))
        relative = Path(spec['directory']) / artifact['path']
        destination = Path('/cache') / relative
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            with destination.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if destination.stat().st_size != artifact['size'] or actual != artifact['sha256']:
                raise ValueError('existing cache is corrupt; preserve it and use a new volume')
        else:
            partial = destination.with_suffix('.pending')
            checksum = hashlib.sha256()
            with (Path('/source')/relative).open('rb') as source, partial.open('xb') as output:
                while block := source.read(4 * 1024 * 1024):
                    checksum.update(block)
                    output.write(block)
            if partial.stat().st_size != artifact['size'] or checksum.hexdigest() != artifact['sha256']:
                raise ValueError('copied generation artifact failed verification')
            partial.replace(destination)
        print('VERIFIED', relative, artifact['sha256'], flush=True)


if __name__ == '__main__':
    main()
