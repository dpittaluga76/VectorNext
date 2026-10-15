"""T25 live smoke on fresh isolated data; never use the normal library."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def run(url, output, fixtures, resume=None):
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((fixtures / 'manifest.json').read_bytes())
    for name, wanted in manifest.items():
        assert hashlib.sha256((fixtures / name).read_bytes()).hexdigest() == wanted, name
    (output / 'input-manifest.json').write_text(json.dumps(manifest, indent=2))
    counter = 0
    prior = {}
    if resume:
        for path in sorted(resume.glob('*-request.json')):
            saved = json.loads(path.read_bytes())
            if saved['path'] == '/v1/ui/ask':
                prior[json.dumps(saved['request'], sort_keys=True)] = (saved,
                    path.with_name(path.name.replace('-request.json', '-response.json')))

    def call(path, value=None, body=None, kind='application/json'):
        nonlocal counter
        key = json.dumps(value, sort_keys=True)
        if path == '/v1/ui/ask' and key in prior:
            saved, captured = prior[key]
            counter += 1
            raw = captured.read_bytes()
            (output / f'{counter:03d}-response.json').write_bytes(raw)
            (output / f'{counter:03d}-request.json').write_text(json.dumps(
                {**saved, 'recovered_from':str(captured)}, indent=2))
            return json.loads(raw)
        if value is not None:
            body = json.dumps(value).encode()
        request = urllib.request.Request(url + path, data=body,
            headers={'Content-Type':kind, 'X-VectorNext-Client':'1'})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        counter += 1
        (output / f'{counter:03d}-response.json').write_bytes(raw)
        (output / f'{counter:03d}-request.json').write_text(json.dumps(
            {'path':path, 'request':value, 'status':status, 'seconds':time.monotonic()-started}, indent=2))
        if path != '/v1/ui/ask':
            assert status < 400, (status, raw.decode())
        return json.loads(raw)

    library = call('/v1/ui/library')['documents']
    assert resume or not library, 'Requires an empty isolated library'
    assert call('/readyz')['ready'], 'Wait for readiness before running; no automatic retries'

    def upload(name):
        identity = str(uuid.uuid4())
        metadata = {'upload_id':identity, 'filename':name}
        boundary = 'facet-' + identity
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
            + json.dumps(metadata).encode()
            + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n\r\n'.encode()
            + (fixtures / name).read_bytes() + f'\r\n--{boundary}--\r\n'.encode())
        job = call('/v1/ui/upload', body=body, kind=f'multipart/form-data; boundary={boundary}')
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            saved = call('/v1/job', {'job_id':job['job_id']})
            assert not saved['last_failure'], saved
            if saved['stage'] == 'Committed':
                print(f'Uploaded {name}', flush=True)
                return job['document_id']
            time.sleep(1)
        raise AssertionError('ingestion deadline')

    names = ('aster.txt','boreal.txt','cobalt.pdf','exact.json')
    aster, boreal, pdf, exact = ([next(d['document_id'] for d in library if d['filename'] == n) for n in names]
        if resume else [upload(n) for n in names])
    results = []
    failures = []

    def ask(ids, question, expected, **extra):
        result = call('/v1/ui/ask', {'question':question, 'document_ids':ids,
            'options':{'evidence_strategy':'facet_coverage_v1'}, **extra})
        if 'error' in result:
            print(question, result['error'], flush=True)
            failures.append({'question':question, 'error':result['error']})
            return result, {}
        raw = json.loads(result['raw_report'], parse_float=Decimal)
        print(question, result['outcome'], [(f['name'], f['value_text']) for f in result['fields']], flush=True)
        assert raw['selection']['strategy'] == 'facet_coverage_v1'
        assert len(raw['selection']['candidate_keys']) <= 20
        assert len(raw['selection']['admitted_primary_keys']) <= 5
        assert all(e['key']['document_id'] in ids for e in result['evidence'])
        assert all(s['request']['filter'] == raw['retrieval']['request']['filter'] for s in raw['selection']['candidate_searches'])
        if expected is None:
            assert result['outcome'] == 'insufficient_evidence', result
        else:
            assert result['outcome'] == 'supported', result
            assert sorted(f['value_text'] for f in result['fields']) == sorted(expected), result
            assert all(f['evidence_id'] in {e['id'] for e in result['evidence']} for f in result['fields'])
        results.append({'question':question,'outcome':result['outcome'], 'fields':result['fields'],
                        'selection_summary':result['workflow']['selection_summary']})
        return result, raw

    first, raw = ask([aster], 'In which year did the Aster station open?', ['2017'])
    if raw:
        assert raw['planning']['plan']['status'] == 'ready'
    ask([aster], 'Who directs that station?', ['Maya Chen'], history=[
        {'role':'user','text':'In which year did the Aster station open?'},
        {'role':'assistant','text':'opening_year: 2017 (integer)'}])
    ask([aster,boreal], 'How many solar panels does Aster station have, and how many antennas does Boreal station have?', ['17','29'])
    ask([pdf], 'How many sensors does Cobalt station have?', ['7'])
    ask([exact], 'What are the amount, zero and unknown values in precision-check?',
        ['9007199254740993.00000000000001','0','null'], fields={
            'amount':{'kind':'number','pointer':'/amount'},
            'zero':{'kind':'integer','pointer':'/zero'},
            'unknown':{'kind':'integer','nullable':True,'pointer':'/unknown'}})
    ask([aster], 'Who built the Aster station?', None,
        fields={'builder':{'kind':'string','description':'Builder of Aster station'}})
    # Separately declared diagnostic control: retain the original question/history,
    # bypass only automatic field planning. It cannot erase the automatic failure.
    ask([aster], 'Who directs that station?', ['Maya Chen'], history=[
        {'role':'user','text':'In which year did the Aster station open?'},
        {'role':'assistant','text':'opening_year: 2017 (integer)'}],
        fields={'director':{'kind':'string','description':'Director of Aster station'}})
    ask([aster,boreal], 'How many solar panels does Aster station have, and how many antennas does Boreal station have?',
        ['17','29'], fields={
            'aster_panels':{'kind':'integer','description':'Number of solar panels at Aster station'},
            'boreal_antennas':{'kind':'integer','description':'Number of antennas at Boreal station'}})
    ask([pdf], 'How many sensors does Cobalt station have?', ['7'],
        fields={'sensors':{'kind':'integer','description':'Number of sensors at Cobalt station'}})
    (output / 'summary.json').write_text(json.dumps({'passed':not failures,'requests':counter,
        'results':results,'failures':failures,'continued_from':str(resume) if resume else None},indent=2))
    print(f'Facet integration smoke: {len(results)} completed checks, {len(failures)} failures', flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fixtures', type=Path, default=Path('tests/fixtures/facets'))
    parser.add_argument('--resume', type=Path, help='Continue the isolated library; replay already captured asks without inference')
    args = parser.parse_args()
    run(args.url, args.output, args.fixtures, args.resume)
