"""Frozen synthetic evidence-only and end-to-end checks. No retries or label prompts."""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from deployment.client import Client

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'experiments/t28'


def validate():
    for name, digest in json.loads((HERE/'input-freeze.json').read_bytes()).items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('fresh fixture/scorer changed: '+name)


def score(case, answer, fixed=False):
    errors = []
    if answer.get('status') != case['status']: return ['status']
    fields = answer.get('fields', {})
    if case['status'] != 'supported': return [] if not fields else ['unexpected fields']
    if set(fields) != set(case['expected']): return ['field set']
    for name, expected in case['expected'].items():
        proof = fields[name]
        if proof.get('pointer') != expected['pointer']: errors.append(name+':pointer')
        if fixed:
            if proof.get('evidence_id') != expected['evidence_id']: errors.append(name+':evidence')
            if proof.get('value') is not None or proof.get('quote') != '': errors.append(name+':placeholder')
        else:
            actual = proof.get('value')
            literal = ('null' if actual is None else 'true' if actual is True else
                       'false' if actual is False else str(actual))
            if literal != expected['value_text']: errors.append(name+':exact value')
    return errors


def run(url, processor, output):
    validate()
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads((HERE/'cases.json').read_bytes())
    results = []
    client = Client(url)
    # Fixed evidence isolates generation from retrieval/admission effects.
    for case in cases:
        evidence = [{'id': f'E{i+1}', 'key': {'document_id': name, 'revision': 'synthetic-v1', 'chunk_id': 'whole'},
                     'record': {}, 'text': (HERE/'fixtures'/name).read_text(encoding='utf-8')}
                    for i, name in enumerate(case['documents'])]
        value = {'question': case['question'], 'history': [], 'fields': case['fields'],
                 'evidence': evidence, 'constrain_pointers': True}
        request = urllib.request.Request(processor+'/rpc/interactive', data=json.dumps({'op':'answer','input':value}).encode(),
                                         headers={'Content-Type':'application/json'})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=720) as response: code, raw = response.status, response.read()
        except urllib.error.HTTPError as error: code, raw = error.code, error.read()
        except Exception as error: code, raw = 0, json.dumps({'error':str(error)}).encode()
        (output/(case['id']+'-fixed.json')).write_bytes(raw)
        result = json.loads(raw, parse_float=Decimal)
        errors = score(case, result.get('result',{}).get('answer',{}), fixed=True) if code == 200 else ['HTTP '+str(code)]
        row = {'id':case['id'], 'mode':'fixed', 'status':code, 'seconds':time.monotonic()-start, 'errors':errors}
        results.append(row); print(row, flush=True)
    code, documents = client.request('/v1/documents')
    if code != 200 or documents['documents']: raise ValueError('fresh database required')
    names = list(dict.fromkeys(name for case in cases for name in case['documents']))
    for name in names:
        code, result = client.request('/v1/ingest', {'job_id':'fresh-'+name, 'document_id':name, 'media_type':'Json',
            'policy':'structural', 'record_pointer':'', 'source_base64':base64.b64encode((HERE/'fixtures'/name).read_bytes()).decode()})
        if code != 202: raise ValueError(('ingestion',code,result))
        _, job = client.wait('fresh-'+name, seconds=240)
        (output/(name+'-job.json')).write_bytes(client.raw)
        if job.get('stage') != 'Committed': raise ValueError(('ingestion failed',job))
    for case in cases:
        start = time.monotonic()
        code, _ = client.request('/v1/ask', {'request':{'question':case['question'], 'fields':case['fields'],
            'filter':{'DocumentIds':case['documents']}}})
        raw = client.raw
        (output/(case['id']+'-source.json')).write_bytes(raw)
        report = json.loads(raw, parse_float=Decimal)
        errors = score(case, report.get('answer',{})) if code == 200 else ['HTTP '+str(code)]
        if code == 200:
            admitted = {e['id']:e for e in report['evidence']}
            for name, proof in report.get('answer',{}).get('fields',{}).items():
                expected = case['expected'].get(name)
                source = admitted.get(proof['evidence_id'],{}).get('key',{}).get('document_id')
                if expected and source != case['documents'][int(expected['evidence_id'][1:])-1]: errors.append(name+':source')
        row = {'id':case['id'], 'mode':'source', 'status':code, 'seconds':time.monotonic()-start, 'errors':errors}
        results.append(row); print(row, flush=True)
    validate()
    summary = {'cases':len(results),'passed':sum(not r['errors'] for r in results),'results':results}
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if summary['passed'] != summary['cases']: raise SystemExit(1)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',required=True)
    parser.add_argument('--processor',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    run(args.url,args.processor,args.output)
