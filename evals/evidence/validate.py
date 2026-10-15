"""Read-only validation of the frozen T23 source/label contract."""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(root=Path('evals/evidence'), repository=Path('.')):
    root = Path(root)
    freeze = json.loads((root/'input-freeze.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        assert digest(repository/name) == expected, f'frozen input changed: {name}'
    sources = json.loads((root/'sources.json').read_text(encoding='utf-8'))['sources']
    requests = json.loads((root/'requests.json').read_text(encoding='utf-8'))
    gold = json.loads((root/'gold.json').read_text(encoding='utf-8'))
    blobs = {}
    for source in sources:
        data = (root/source['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == source['text_sha256']
        assert len(data) == source['text_bytes']
        assert source['id'] not in blobs
        blobs[source['id']] = data
    ids = [q['id'] for q in requests]
    assert len(ids) == len(set(ids)) == 24
    assert set(ids) == {q['id'] for q in gold['cases']}
    for q in requests:
        assert set(q) == {'id', 'question', 'hints'}
        assert q['question'].strip() and 1 <= len(q['hints']) <= 4
        assert all(h.strip() for h in q['hints'])
    for fact in gold['facts'].values():
        assert fact['supports']
        for support in fact['supports']:
            data = blobs[support['document_id']]
            assert hashlib.sha256(data).hexdigest() == support['source_sha256']
            assert data[support['start']:support['end']].decode() == support['quote']
    for case in gold['cases']:
        assert len(case['facts']) == len(set(case['facts']))
        assert all(f in gold['facts'] for f in case['facts'])
        assert bool(case['facts']) == (case['group'] != 'missing')
    return {'sources':len(sources), 'questions':len(ids), 'facts':len(gold['facts']),
            'fact_requirements':sum(len(c['facts']) for c in gold['cases']),
            'source_bytes':sum(map(len, blobs.values()))}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
