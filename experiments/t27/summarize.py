"""Failure-inclusive, paired T27 gate calculations. Never rewrites historical scores."""
import argparse
import json
import math
from pathlib import Path
import statistics

from .run import MODELS, SUITES
from .preflight import write


def summary(rows):
    times = [r['wall_seconds'] for r in rows if r.get('wall_seconds') is not None]
    scores = [r.get('score') or {} for r in rows]
    return {'planned': len(rows), 'http_success': sum(r['http_status'] == 200 for r in rows),
            'exact': sum(s.get('answer_correct', False) for s in scores),
            'missing_timings': len(rows)-len(times),
            'median_seconds': statistics.median(times) if times else None,
            'p95_seconds': sorted(times)[math.ceil(.95*len(times))-1] if times else None,
            'annotated_supported': sum(s.get('answer_correct', False) and s.get('expected_status') == 'supported'
                and bool(s.get('proofs')) and all(p['gold_source_overlap'] for p in s['proofs'].values()) for s in scores)}


def compare(baseline, candidate):
    old = {r['case']: r for r in baseline}
    new = {r['case']: r for r in candidate}
    if old.keys() != new.keys() or len(old) != len(baseline) or len(new) != len(candidate):
        raise ValueError('paired case identity mismatch')
    regressions, support_losses, new_false_support = [], [], []
    for identifier, row in old.items():
        a, b = row.get('score') or {}, new[identifier].get('score') or {}
        if a.get('answer_correct') and not b.get('answer_correct'):
            regressions.append(identifier)
        if a.get('answer_correct'):
            for field, proof in a.get('proofs', {}).items():
                if proof['gold_source_overlap'] and not b.get('proofs', {}).get(field, {}).get('gold_source_overlap'):
                    support_losses.append({'case': identifier, 'field': field})
        expected = a.get('expected_status') or b.get('expected_status')
        if expected in ('ambiguous', 'insufficient_evidence') and a.get('actual_status') != 'supported' and b.get('actual_status') == 'supported':
            new_false_support.append(identifier)
    left, right = summary(baseline), summary(candidate)
    common = [k for k in old if old[k]['http_status'] == 200 and new[k]['http_status'] == 200
              and old[k].get('wall_seconds') is not None and new[k].get('wall_seconds') is not None]
    common_old = statistics.median(old[k]['wall_seconds'] for k in common) if common else None
    common_new = statistics.median(new[k]['wall_seconds'] for k in common) if common else None
    reduction = lambda a, b: (a-b)/a if a is not None and b is not None and a > 0 else None
    return {'control': left, 'candidate': right, 'correctness_regressions': regressions,
            'source_support_losses': support_losses, 'new_false_support': new_false_support,
            'median_reduction': reduction(left['median_seconds'], right['median_seconds']),
            'common_success_count': len(common), 'common_control_median': common_old,
            'common_candidate_median': common_new, 'common_median_reduction': reduction(common_old, common_new)}


def summarize(root):
    blocks = {}
    failures = []
    count = 0
    for suite, (_, _, variants, _) in SUITES.items():
        for block, _, _ in variants:
            rows = [json.loads((root/suite/block/model/'complete.json').read_bytes())['cases'] for model in MODELS]
            expected = 16 if suite == 't14' else 28
            if any(len(r) != expected for r in rows):
                raise ValueError('incomplete planned denominator')
            result = compare(*rows)
            count += sum(map(len, rows))
            key = suite+'/'+block
            blocks[key] = result
            for gate in ('correctness_regressions', 'source_support_losses', 'new_false_support'):
                if result[gate]:
                    failures.append({'block': key, 'gate': gate, 'cases': result[gate]})
            if block.startswith('five-'):
                floor = 8 if suite == 't14' else 16
                if result['candidate']['exact'] < floor:
                    failures.append({'block': key, 'gate': 'historical_floor'})
                if result['control']['missing_timings'] or result['candidate']['missing_timings']:
                    failures.append({'block': key, 'gate': 'incomplete_latency'})
                for gate in ('median_reduction', 'common_median_reduction'):
                    if result[gate] is None or result[gate] < .20:
                        failures.append({'block': key, 'gate': gate, 'value': result[gate]})
    if count != 416:
        raise ValueError('incorrect total denominator')
    return {'requests': count, 'blocks': blocks, 'evaluation_gates_passed': not failures,
            'failures': failures, 'promotion': 'requires separate preflight and application verification',
            'interpretation': 'Observed current-runtime regression sets; repeated requests are not independent questions.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve existing reports; use a fresh output path')
    result = summarize(args.root)
    write(args.output, result)
    print(json.dumps({'requests': result['requests'], 'evaluation_gates_passed': result['evaluation_gates_passed'],
                      'failed_gates': len(result['failures'])}))
