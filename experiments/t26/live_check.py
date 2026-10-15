"""Source-backed automatic planning on a fresh, isolated T26 library. No retries."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

from .planner_check import ROOT, validate

CASES = [
    ('count', ['quartz.txt'], 'How many sensors are installed at Quartz outpost?', ['11'], []),
    ('followup', ['quartz.txt'], 'Who directs that outpost?', ['Ana Reed'], [
        {'role': 'user', 'text': 'How many sensors are installed at Quartz outpost?'},
        {'role': 'assistant', 'text': 'sensor_count: 11 (integer)'}]),
    ('separate_counts', ['quartz.txt', 'meridian.txt'],
     'How many cameras does Quartz outpost have, and how many radios does Meridian outpost have?', ['4', '6'], []),
    ('pdf', ['dawn.pdf'], 'How many sensors does the Dawn weather mast have?', ['13'], []),
    ('exact_json', ['precision.json'],
     'What are the exact numeric amount, integer zero and raw nullable integer unknown stored in precision-lumen?',
     ['9007199254740993.00000000000001', '0', 'null'], []),
    ('missing', ['quartz.txt'], 'Who built Quartz outpost?', None, []),
    ('clarification', ['quartz.txt'], 'Who leads it?', 'question needs clarification', []),
    ('aggregation', ['quartz.txt', 'meridian.txt'], 'Sum the sensor counts across all outpost records.',
     'does not support calculations across records', []),
]


def run(url, output, cases_path=None, fixtures=ROOT/'tests/fixtures/planning',
        freeze=ROOT/'experiments/t26/input-freeze.json', version='field-planning-v2'):
    validate(freeze)
    cases = json.loads(cases_path.read_bytes()) if cases_path else CASES
    output.mkdir(parents=True, exist_ok=False)
    (output / 'cases.json').write_text(json.dumps(cases, indent=2))
    (output / 'runner-sha256.txt').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    counter = 0

    def call(path, value=None, body=None, kind='application/json'):
        nonlocal counter
        counter += 1
        if value is not None:
            body = json.dumps(value).encode()
        started = time.monotonic()
        request = urllib.request.Request(url + path, data=body,
            headers={'Content-Type': kind, 'X-VectorNext-Client': '1'})
        try:
            with urllib.request.urlopen(request, timeout=450) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except Exception as error:
            status, raw = 0, json.dumps({'transport_error': str(error)}).encode()
        (output / f'{counter:03d}-response.json').write_bytes(raw)
        (output / f'{counter:03d}-request.json').write_text(json.dumps({
            'path': path, 'request': value, 'http_status': status,
            'body_sha256': hashlib.sha256(body).hexdigest() if body else None,
            'seconds': time.monotonic()-started}, indent=2))
        return status, json.loads(raw)

    status, library = call('/v1/ui/library')
    assert status == 200 and not library['documents'] and not library['jobs'], 'Requires a fresh isolated database'
    status, ready = call('/readyz')
    assert status == 200 and ready['ready'], ready
    ids = {}
    for name in dict.fromkeys(n for _, names, *_ in cases for n in names):
        identity = str(uuid.uuid4())
        metadata = {'upload_id': identity, 'filename': name}
        boundary = 'planning-' + identity
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
            + json.dumps(metadata).encode()
            + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n\r\n'.encode()
            + (fixtures / name).read_bytes() + f'\r\n--{boundary}--\r\n'.encode())
        status, job = call('/v1/ui/upload', body=body, kind=f'multipart/form-data; boundary={boundary}')
        assert status < 400 and status > 0, job
        deadline = time.monotonic() + 240
        while True:
            status, saved = call('/v1/job', {'job_id': job['job_id']})
            assert status == 200 and not saved['last_failure'], saved
            if saved['stage'] == 'Committed':
                ids[name] = job['document_id']
                break
            assert time.monotonic() < deadline, 'ingestion deadline'
            time.sleep(1)
        print('Uploaded', name, flush=True)

    results = []
    for case_id, names, question, expected, history in cases:
        scope = [ids[n] for n in names]
        request = {'question': question, 'history': history, 'document_ids': scope,
                   'options': {'evidence_strategy': 'facet_coverage_v1'}}
        status, result = call('/v1/ui/ask', request)
        errors = []
        try:
            if isinstance(expected, str):
                assert status == 400 and result['error']['code'] == 'invalid_request', result
                message = result['error']['message']
                assert expected in message or (case_id == 'aggregation' and 'unsupported corpus aggregation' in message), result
            else:
                assert status == 200, result
                raw = json.loads(result['raw_report'])
                assert raw['planning']['plan']['status'] == 'ready'
                assert raw['planning']['audit']['planning_version'] == version
                assert raw['planning']['audit']['evidence_available'] is False
                original = json.dumps({'question': question, 'history': history}, sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False).encode()
                assert raw['planning']['audit']['input_sha256'] == hashlib.sha256(original).hexdigest()
                assert all('pointer' not in f and 'value' not in f for f in raw['planning']['plan']['fields'])
                assert raw['selection']['strategy'] == 'facet_coverage_v1'
                assert all(e['key']['document_id'] in scope for e in result['evidence'])
                if expected is None:
                    assert result['outcome'] == 'insufficient_evidence' and not result['fields'], result
                else:
                    assert result['outcome'] == 'supported', result
                    assert sorted(f['value_text'] for f in result['fields']) == sorted(expected), result
                    evidence = {e['id']: e for e in result['evidence']}
                    assert all(f['evidence_id'] in evidence for f in result['fields'])
                    if case_id == 'separate_counts':
                        assert {evidence[f['evidence_id']]['key']['document_id'] for f in result['fields']} == set(scope)
                    if case_id == 'exact_json':
                        assert expected[0] in result['raw_report']
        except (AssertionError, KeyError, TypeError) as error:
            errors.append(str(error)[:500])
        entry = {'id': case_id, 'http_status': status, 'outcome': result.get('outcome'),
                 'values': [f['value_text'] for f in result.get('fields', [])], 'errors': errors}
        results.append(entry)
        print(json.dumps(entry), flush=True)
    summary = {'cases': len(results), 'passed': sum(not r['errors'] for r in results), 'results': results}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))
    validate(freeze)
    if summary['passed'] != len(results):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--fixtures', type=Path, default=ROOT/'tests/fixtures/planning')
    parser.add_argument('--freeze', type=Path, default=ROOT/'experiments/t26/input-freeze.json')
    parser.add_argument('--version', default='field-planning-v2')
    args = parser.parse_args()
    run(args.url, args.output, args.cases, args.fixtures, args.freeze, args.version)
