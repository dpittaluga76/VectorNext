"""Score original, revision-bound evidence; never pass labels to inference."""
import json
import math
from pathlib import Path
import statistics
import sys

STAGES = ('raw', 'selected', 'primary')


def key(value):
    return (value['document_id'], value['revision'], value['chunk_id'])


def normalize(text):
    return ' '.join(text.split())


def catalog(documents):
    return {(d['document_id'],d['revision'],c['id']):
            {'evidence':c['evidence'], 'source_sha256':d['original']['sha256']}
            for d in documents for c in d['chunks']}


def covered(fact, keys, chunks):
    for k in keys:
        identity = key(k)
        chunk = chunks.get(identity)
        if not chunk:
            raise ValueError(f'unresolvable captured key: {identity}')
        for support in fact['supports']:
            if (identity[0] == support['document_id']
                and chunk['source_sha256'] == support['source_sha256']
                and normalize(support['quote']) in normalize(chunk['evidence'])):
                return True
    return False


def score_case(case, response, facts, chunks):
    successful = response is not None and response.get('status') == 'ok'
    result = {'id':case['id'], 'group':case['group'], 'error':not successful,
              'required':len(case['facts'])}
    for stage in STAGES:
        keys = response.get(stage, []) if successful else []
        found = [name for name in case['facts'] if covered(facts[name],keys,chunks)]
        result[stage] = {'covered':found, 'hits':len(keys),
                         'recall':len(found)/len(case['facts']) if case['facts'] else None,
                         'complete':len(found)==len(case['facts']) if case['facts'] else None}
    if response:
        result['timings'] = {name:response[name] for name in
            ('elapsed_ms','embedding_ms','search_ms','rerank_ms') if name in response}
        result['probes'] = len(response.get('searches', []))
    return result


def distribution(values):
    values=sorted(values)
    return {'n':len(values), 'median':statistics.median(values),
            'p95':values[math.ceil(.95*len(values))-1]} if values else None


def score_file(path, gold):
    records = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
    chunks = catalog(next(r['documents'] for r in records if r.get('kind')=='finish'))
    responses = {}
    for r in records:
        if 'id' in r:
            if r['id'] in responses: raise ValueError('duplicate response')
            responses[r['id']] = r
    assert set(responses) <= {c['id'] for c in gold['cases']}
    rows = [score_case(c,responses.get(c['id']),gold['facts'],chunks) for c in gold['cases']]
    summary = {'capture':str(path), 'requests':len(rows), 'errors':sum(r['error'] for r in rows),
               'stages':{}, 'latency':{}, 'cases':rows}
    positive=[r for r in rows if r['required']]
    for stage in STAGES:
        summary['stages'][stage] = {'complete':sum(r[stage]['complete'] for r in positive),
            'positive_questions':len(positive), 'facts':sum(len(r[stage]['covered']) for r in positive),
            'fact_requirements':sum(r['required'] for r in positive),
            'macro_recall':statistics.mean(r[stage]['recall'] for r in positive),
            'hits':distribution([r[stage]['hits'] for r in rows])}
    for name in ('elapsed_ms','embedding_ms','search_ms','rerank_ms'):
        summary['latency'][name]=distribution([r['timings'][name] for r in rows if name in r.get('timings',{})])
    summary['worker_stats']=next(r['stats'] for r in records if r.get('kind')=='finish')
    return summary


if __name__ == '__main__':
    gold=json.loads(Path('evals/evidence/gold.json').read_text(encoding='utf-8'))
    print(json.dumps([score_file(p,gold) for p in sys.argv[1:]],ensure_ascii=False,indent=2))
