"""Frozen literal-source and exact-value scorer; no labels enter inference."""
from decimal import Decimal
import json
from pathlib import Path
from evals.evidence.score import distribution, normalize, key


def exact_load(raw):
    return json.loads(raw, parse_float=Decimal)


def score(code, raw, gold, documents):
    body = exact_load(raw) if raw else {}
    report = body if code == 200 else body.get('error', {}).get('diagnostics', {})
    if not isinstance(report, dict): report = {}
    chunks = {(d['document_id'], d['revision'], c['id']): c['evidence']
              for d in documents.values() for c in d['chunks']}
    def resolve(keys):
        return [(k['document_id'], chunks[key(k)]) for k in keys]
    def coverage(passages):
        found = [i for i, fact in enumerate(gold['facts']) if any(
            doc == fact['document'] and normalize(fact['text']) in normalize(text)
            for doc, text in passages)]
        return {'found': found, 'complete': len(found) == len(gold['facts']) if gold['facts'] else None}
    retrieval = report.get('retrieval') or {}
    ranked = report.get('ranked', [])
    evidence = report.get('evidence', [])
    # Ranked-first-five is a ranking metric; budget-admitted evidence is separate.
    stages = {name: coverage(resolve([r['key'] for r in rows])) for name, rows in (
        ('raw', retrieval.get('deduplicated', [])),
        ('selected', retrieval.get('results', [])[:20]), ('ranked_five', ranked[:5]))}
    stages['assembled'] = coverage([(e['key']['document_id'], e['text']) for e in evidence])
    answer = report.get('answer', {})
    fields = answer.get('fields', {})
    values = {name: proof['value'] for name, proof in fields.items()}
    # Bool is not an integer; missing values are not null and large ints never use float.
    exact = set(values) == set(gold['values']) and all(
        not isinstance(values[k], bool) and values[k] == v for k, v in gold['values'].items())
    cited = {p.get('evidence_id') for p in fields.values()}
    citation_coverage = coverage([(e['key']['document_id'], e['text']) for e in evidence if e['id'] in cited])
    correct = (code == 200 and answer.get('status') == gold['status'] and exact
        and report.get('validation', {}).get('mechanical_support') == 'passed'
        and (not gold['facts'] or citation_coverage['complete']))
    return {'correct': correct, 'status': answer.get('status'),
        'values_text': {k: str(v) if not isinstance(v, str) else v for k, v in values.items()},
        'coverage': stages, 'citations': citation_coverage,
        'timings_ms': {k: float(v) for k, v in report.get('timings_ms', {}).items()},
        'prompt_tokens': report.get('prompt_tokens'), 'error': body.get('error') and str(body['error'].get('message', ''))}


def summarize(root):
    root = Path(root); gold = exact_load(Path('experiments/t32/gold.json').read_bytes())
    from .run import ARMS
    result = {'requests': 24, 'arms': {}}
    for name, embedding, _ in ARMS:
        folder = root/name; docs = exact_load((root/embedding/'documents.json').read_bytes())
        rows = []
        for identifier, label in gold.items():
            row = json.loads((folder/(identifier+'.row.json')).read_bytes())
            raw = (folder/(identifier+'.response.json')).read_bytes()
            row['score'] = score(row['http_status'], raw, label, docs)
            rows.append(row)
        result['arms'][name] = {'correct': sum(r['score']['correct'] for r in rows), 'total': 6,
            'latency_seconds': distribution([r['seconds'] for r in rows]),
            'stage_medians_ms': {stage: distribution([r['score']['timings_ms'][stage] for r in rows
                if stage in r['score']['timings_ms']]) for stage in sorted({s for r in rows for s in r['score']['timings_ms']})},
            'coverage_complete': {s: sum(r['score']['coverage'][s]['complete'] is True for r in rows)
                for s in ('raw','selected','ranked_five','assembled')}, 'positive_denominator': 5, 'cases': rows}
    baseline = result['arms']['minilm-minilm']['cases']
    for arm in result['arms'].values():
        arm['gained'] = [b['case'] for a,b in zip(baseline,arm['cases']) if b['score']['correct'] and not a['score']['correct']]
        arm['lost'] = [b['case'] for a,b in zip(baseline,arm['cases']) if a['score']['correct'] and not b['score']['correct']]
    return result
