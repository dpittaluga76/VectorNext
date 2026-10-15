"""Separate immutable data and execution manifests. No source/label regeneration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from evals.score import exact, resolve, pointer_parts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BLOCKS = [('five-cold', 'ranked', 5), ('two-cold', 'ranked', 2), ('coverage-cold', 'coverage_v1', 5),
          ('coverage-warm', 'coverage_v1', 5), ('two-warm', 'ranked', 2), ('five-warm', 'ranked', 5)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    data = json.loads((HERE / 'dataset.json').read_text(encoding='utf-8'))
    requests = json.loads((HERE / 'requests.json').read_text(encoding='utf-8'))
    docs = {d['id']: d for d in data['documents']}
    assert len(docs) == len(data['documents']) == 8
    refs = {e['id']: e for e in data['evidence']}
    assert len(refs) == len(data['evidence'])
    for doc in docs.values():
        assert digest(HERE / doc['path']) == doc['sha256'], doc['id']
    for ref in refs.values():
        raw = (HERE / docs[ref['document_id']]['path']).read_bytes()
        loc = ref['locator']
        if loc['kind'] == 'text':
            start, end = loc['byte_start'], loc['byte_end']
            value = raw[start:end].decode('utf-8')
            assert value == ref['expected']
            assert loc['line_start'] == raw[:start].count(b'\n') + 1
            assert loc['line_end'] == raw[:end].count(b'\n') + 1
            runs = [[start + len(value[:m.start()].encode()), start + len(value[:m.end()].encode())]
                    for m in re.finditer(r'\S+', value)]
            assert runs and runs == ref['content_runs']
        else:
            assert exact(resolve(json.loads(raw), pointer_parts(loc['pointer'])), ref['expected'])
    cases = {c['id']: c for c in data['cases']}
    assert len(cases) == len(data['cases']) == 16 and cases.keys() == requests.keys()
    for identifier, case in cases.items():
        req = requests[identifier]
        assert set(req) <= {'question', 'fields', 'history'}
        assert req['question'] == case['question'] and case['split'] == 'comparison'
        for spec in req['fields'].values():
            assert set(spec) == {'kind', 'description', 'nullable'}
        exp = case['expected']
        if exp['status'] == 'supported':
            assert req['fields'].keys() == exp['fields'].keys() == exp['field_sources'].keys()
            assert exp['support_sets'] and all(s and set(s) <= refs.keys() for s in exp['support_sets'])
        else:
            assert not exp['fields']
        for alternatives in exp.get('alternatives', []):
            assert alternatives['support_set'] and set(alternatives['support_set']) <= refs.keys()
    return data, requests, cases


def verify(kind='execution'):
    if kind == 'execution':
        verify('data')
    manifest = json.loads((HERE / (kind + '-freeze.json')).read_text(encoding='utf-8'))
    for path, expected in manifest['files'].items():
        if digest(ROOT / path) != expected:
            raise ValueError('frozen input changed: ' + path)
    return manifest


def public_inputs(data, requests):
    cases = {case['id']: case for case in data['cases']}
    if cases.keys() != requests.keys() or any(c['question'] != requests[k]['question'] for k, c in cases.items()):
        raise ValueError('request/case mismatch')
    return cases


def create(kind):
    validate()
    path = HERE / (kind + '-freeze.json')
    if path.exists():
        raise ValueError('freeze already exists')
    if kind == 'data':
        files = [ROOT / 'docs/t14-protocol.md', HERE / 'sources.json', HERE / 'dataset.json', HERE / 'requests.json',
                 HERE / 'build_dataset.py', HERE / 'acquire.py', HERE / 'score.py', ROOT / 'evals/score.py',
                 ROOT / 'evals/independent/acquire.py'] + list((HERE / 'fixtures').glob('*'))
    else:
        verify('data')
        files = [HERE / 'data-freeze.json', ROOT / 'compose.app.yaml', ROOT / 'compose.coverage.yaml',
                 ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', ROOT / 'docker/app.Dockerfile',
                 ROOT / 'docker/app-processor.Dockerfile', ROOT / 'docker/app-llm.Dockerfile',
                 ROOT / 'evals/run.py']
        for directory in ['src', 'model_worker', 'processor', 'deployment', 'experiments/t02', 'evals/coverage']:
            files += [p for p in (ROOT / directory).rglob('*') if p.suffix in {'.rs', '.py'} or p.name.endswith('.lock.json')]
    value = {'version': 1, 'kind': kind, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
             'blocks': BLOCKS, 'holdout_used': False,
             'files': {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(files))}}
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return verify(kind)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--create', choices=['data', 'execution'])
    parser.add_argument('--kind', choices=['data', 'execution'], default='execution'); args = parser.parse_args()
    manifest = create(args.create) if args.create else verify(args.kind)
    print('Verified', manifest['kind'], len(manifest['files']), 'frozen files')
