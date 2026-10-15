"""Frozen planner-only comparison. No source documents or gold reach inference."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]


def validate(freeze=ROOT/'experiments/t26/input-freeze.json'):
    for name, digest in json.loads(freeze.read_bytes()).items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name


def score(case, result):
    plan = result.get('result', {}).get('plan', {})
    if plan.get('status') != case['status']:
        return ['status']
    actual = plan.get('fields', [])
    if len(actual) != len(case['fields']):
        return ['field_count']
    unmatched = list(actual)
    errors = []
    for expected in case['fields']:
        def matches(field):
            words = (field.get('name','') + ' ' + field.get('description','')).lower()
            return (field.get('kind') == expected['kind'] and field.get('nullable') == expected['nullable']
                and all(any(term in words for term in alternatives) for alternatives in expected['terms']))
        found = next((f for f in unmatched if matches(f)), None)
        if found is None:
            errors.append({'unmatched_field': expected})
        else:
            unmatched.remove(found)
    return errors


def run(url, output, cases_path=ROOT/'experiments/t26/cases.json', freeze=ROOT/'experiments/t26/input-freeze.json'):
    validate(freeze)
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(cases_path.read_bytes())
    results = []
    for case in cases:
        request = {'op':'plan_fields','input':case['input']}
        started = time.monotonic()
        try:
            req = urllib.request.Request(url+'/rpc/interactive', data=json.dumps(request).encode(), headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=450) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except Exception as error:
            status, raw = 0, json.dumps({'transport_error':str(error)}).encode()
        (output/(case['id']+'-response.json')).write_bytes(raw)
        result = json.loads(raw)
        entry = {'id':case['id'],'input':case['input'],'http_status':status,
                 'seconds':time.monotonic()-started,'errors':score(case,result),'result':result}
        (output/(case['id']+'-capture.json')).write_text(json.dumps(entry,indent=2))
        results.append(entry)
        print(case['id'], result.get('result',{}).get('plan',result), 'errors:',entry['errors'], flush=True)
    summary={'cases':len(cases),'passed':sum(not r['errors'] for r in results),'results':results}
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    validate(freeze)
    if summary['passed'] != len(cases): raise SystemExit(1)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cases',type=Path,default=ROOT/'experiments/t26/cases.json')
    parser.add_argument('--freeze',type=Path,default=ROOT/'experiments/t26/input-freeze.json')
    args=parser.parse_args()
    run(args.url,args.output,args.cases,args.freeze)
