"""Post-run aggregation of frozen T14 scores. Does not change labels or requests."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from .freeze import BLOCKS, ROOT, HERE, verify


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)] if values else None


def summarize(run):
    verify()
    root = ROOT / 'data/t14' / run
    dataset = json.loads((HERE / 'dataset.json').read_text(encoding='utf-8'))
    cases = {c['id']: c for c in dataset['cases']}
    result = {'version': 1, 'run': run, 'protocol': 'docs/t14-protocol.md', 'annotation': 'v2',
              'source_count': len(dataset['documents']), 'case_count': len(cases), 'blocks': {}, 'paired': {},
              'default': 'ranked five', 'holdout_used': False, 'capture_sha256': {}}
    ingestion = json.loads((root / 'ingestion/complete.json').read_bytes())
    result['ingestion'] = {'admitted': sum(r['committed'] for r in ingestion['rows']),
                           'planned': len(ingestion['rows']), 'chunks': ingestion['chunks'],
                           'startup_seconds': ingestion['startup_seconds'], 'wall_seconds': ingestion['wall_seconds']}
    result['runtime'] = json.loads((root / 'ingestion/metadata.json').read_bytes())
    result['sampled_resources'] = {'gpu_peak_mib': 0, 'services': {}}
    lookup = {}
    for block, strategy, primary in BLOCKS:
        path = root / block / 'complete.json'
        value = json.loads(path.read_text(encoding='utf-8')); rows = value['cases']
        for sample in value['samples']:
            result['sampled_resources']['gpu_peak_mib'] = max(result['sampled_resources']['gpu_peak_mib'], sample.get('gpu_mib', 0))
            for service in ('vectornext', 'processor', 'llm'):
                peaks = result['sampled_resources']['services'].setdefault(service, {})
                for key in ('current_bytes', 'anonymous_bytes', 'file_bytes'):
                    peaks[key] = max(peaks.get(key, 0), sample.get(service, {}).get(key, 0))
        assert len(rows) == len(cases) and {r['case'] for r in rows} == cases.keys()
        lookup[block] = {r['case']: r for r in rows}
        scores = [r['score'] for r in rows if r['score']]
        walls = [r['wall_seconds'] for r in rows]
        tokens = [s['prompt_tokens'] for s in scores if s['prompt_tokens'] is not None]
        traces = {}
        for row in rows:
            if row['report_file']:
                raw_path = root / block / row['report_file']
                sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                assert sha == row['report_sha256']
                result['capture_sha256'][block + '/' + row['report_file']] = sha
                trace = json.loads(raw_path.read_bytes())
                if row['http_status'] == 200:
                    traces[row['case']] = {
                        'evidence_groups': len(trace['evidence']),
                        'source_documents': sorted({e['key']['document_id'] for e in trace['evidence']}),
                        'admitted_primaries': len(trace['selection']['admitted_primary_keys']) if trace.get('selection') else None,
                        'field_selection_ms': trace.get('timings_ms', {}).get('field_coverage_selection'),
                    }
        groups = {}
        for status in ('supported', 'ambiguous', 'insufficient_evidence'):
            subset = [r for r in rows if cases[r['case']]['expected']['status'] == status]
            groups[status] = {'correct': sum(bool(r['score'] and r['score']['answer_correct']) for r in subset), 'total': len(subset)}
        result['blocks'][block] = {'strategy': strategy, 'primary_limit': primary, 'total': len(rows),
            'correct': sum(s['answer_correct'] for s in scores), 'status_correct': sum(s['status_correct'] for s in scores),
            'supported_with_annotated_proofs': sum(s['supported_with_annotated_proofs'] for s in scores),
            'complete_contexts': sum(s['stages']['context']['complete'] is True for s in scores),
            'context_denominator': sum(c['expected']['status'] != 'insufficient_evidence' for c in cases.values()),
            'http_errors': sum(r['http_status'] != 200 for r in rows), 'scoring_errors': sum(bool(r['scoring_error']) for r in rows),
            'median_seconds': statistics.median(walls), 'p95_seconds': percentile(walls, .95),
            'median_prompt_tokens': statistics.median(tokens) if tokens else None,
            'by_status': groups, 'gpu_peak_mib': max((s.get('gpu_mib', 0) for s in value['samples']), default=0),
            'cases': [{'case': r['case'], 'correct': bool(r['score'] and r['score']['answer_correct']),
                       'status': (r['score'] or {}).get('actual_status'), 'http_status': r['http_status'],
                       'seconds': r['wall_seconds'], 'prompt_tokens': (r['score'] or {}).get('prompt_tokens'),
                       'annotated_proofs': (r['score'] or {}).get('supported_with_annotated_proofs', False),
                       'context_complete': (r['score'] or {}).get('stages', {}).get('context', {}).get('complete'),
                       'evidence_selection': traces.get(r['case']),
                       'error': r['error'], 'scoring_error': r['scoring_error']} for r in rows]}
    gate = []
    for cache in ('cold', 'warm'):
        baseline = lookup['five-' + cache]
        for candidate in ('two', 'coverage'):
            compared = lookup[candidate + '-' + cache]; regressions = []; gains = []; context_losses = []; proof_losses = []
            for identifier in cases:
                before = baseline[identifier]['score'] or {}; after = compared[identifier]['score'] or {}
                if before.get('answer_correct') and not after.get('answer_correct'): regressions.append(identifier)
                if not before.get('answer_correct') and after.get('answer_correct'): gains.append(identifier)
                if before.get('stages', {}).get('context', {}).get('complete') is True and after.get('stages', {}).get('context', {}).get('complete') is not True:
                    context_losses.append(identifier)
                if before.get('supported_with_annotated_proofs') and not after.get('supported_with_annotated_proofs'):
                    proof_losses.append(identifier)
            speedup = 1 - result['blocks'][candidate + '-' + cache]['median_seconds'] / result['blocks']['five-' + cache]['median_seconds']
            negatives_pass = all(compared[k]['score'] and compared[k]['score']['answer_correct'] for k, c in cases.items() if c['expected']['status'] != 'supported')
            passed = not (regressions or context_losses or proof_losses) and negatives_pass and speedup >= .20
            result['paired'][candidate + '-' + cache] = {'exact_gains': gains, 'exact_losses': regressions,
                'context_losses': context_losses, 'proof_losses': proof_losses, 'negative_outcomes_preserved': bool(negatives_pass),
                'median_latency_reduction': speedup, 'gate_pass': passed,
                'case_latency_delta_seconds': {k: compared[k]['wall_seconds'] - baseline[k]['wall_seconds'] for k in cases}}
            if candidate == 'coverage': gate.append(passed)
    result['coverage_adoption_gate_passed'] = all(gate)
    result['decision'] = 'Candidate clears this diagnostic gate; broader independent validation still required.' if all(gate) else 'Retain ranked five; coverage_v1 remains experimental.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    if args.output.exists(): raise ValueError('summary already exists; do not overwrite archived results')
    value = summarize(args.run)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, block in value['blocks'].items():
        print(name, block['correct'], '/', block['total'], 'median', round(block['median_seconds'], 3), 'errors', block['http_errors'])
    print(value['decision'])
