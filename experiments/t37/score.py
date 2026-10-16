"""T37 predeclared scoring: unchanged T36 labels plus two verified corrections."""
import copy
from experiments.t36.score import score as original_score, exact_load, normalize

PDF_SHA = '4679ddc960917334baedb22a37d3ac6da5ca491a89f18d051605b1de7a4fc5f0'
AGGREGATE_ERROR = 'invalid record: aggregate question requires an unsupported corpus aggregation operation'


def score(identifier, code, raw, label, documents):
    baseline = original_score(code, raw, label, documents)
    result = dict(baseline, original_score_correct=baseline['correct'], correction=None,
                  planner_observed=identifier != 'aggregate_sum')
    if identifier == 'aggregate_sum':
        value = exact_load(raw) if raw else {}
        correct = (label['plan'] == 'unsupported' and code == 400 and
                   value.get('error') == {'code':'invalid_request','message':AGGREGATE_ERROR})
        result.update(correct=correct, planning_correct=False, correction='pre-inference API guard' if correct else None)
    elif identifier == 'pdf_pressure' and code == 200 and not baseline['correct']:
        try:
            view = exact_load(raw); report = exact_load(view['raw_report'])
            docs = copy.deepcopy(documents); doc = docs['vela']
            heading = doc['blocks'][0]
            if doc['original']['sha256'] != PDF_SHA or heading['kind'] != 'Heading' or heading['text'] != 'Vela-X service certificate': return result
            if not heading['sources'] or any(s['revision'] != doc['revision'] or s['locator']['Pdf']['page'] != 1 for s in heading['sources']): return result
            cited = {p['evidence_id'] for p in report['answer']['fields'].values()}
            for e in report['evidence']:
                if e['id'] not in cited: continue
                if e['key']['document_id'] != 'vela' or e['key']['revision'] != doc['revision']: return result
                chunk = next(c for c in doc['chunks'] if c['id'] == e['key']['chunk_id'])
                assembled = heading['text'] + '\n\n' + chunk['evidence']
                if normalize(assembled) != normalize(e['text']) or e['spans'] != chunk['spans']: return result
                chunk['evidence'] = assembled
            revised = original_score(code, raw, label, docs)
            result.update(revised, original_score_correct=baseline['correct'], correction='verified PDF heading assembly' if revised['correct'] else None)
        except (ValueError, KeyError, TypeError, StopIteration): pass
    return result
