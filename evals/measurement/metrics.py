"""Measurement-v1 definitions. Unknown observations are never filled with zeros."""
import json
import math
import statistics
from decimal import Decimal


def exact_load(raw):
    return json.loads(raw, parse_float=Decimal)


def wilson(successes, total):
    if not 0 <= successes <= total:
        raise ValueError('invalid binomial counts')
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z/total
    centre = (p + z*z/(2*total)) / denominator
    radius = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0, centre-radius), min(1, centre+radius)]


def distribution(values):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return {'observed': 0, 'median': None, 'p95': None}
    return {'observed': len(values), 'median': statistics.median(values),
            'p95': values[max(0, math.ceil(.95*len(values))-1)]}


def outcome(expected, actual, correct, *, error=False, rejected=False, request_decline=False):
    if request_decline and correct:
        return 'request_declined_correct'
    if actual == 'supported':
        return 'answered_correct' if correct else 'answered_wrong'
    if actual in ('needs_clarification','unsupported'):
        return 'abstained_missed' if expected == 'supported' else 'request_declined_wrong'
    if error and not rejected:
        return 'system_error'
    if actual in ('ambiguous', 'insufficient_evidence') or rejected:
        if expected == 'supported':
            return 'abstained_missed'
        return 'abstained_correct' if correct else 'abstained_wrong'
    return 'unscorable'


def unwrap(body):
    if isinstance(body.get('raw_report'), str):
        return exact_load(body['raw_report'])
    if 'error' in body:
        return (body.get('error') or {}).get('diagnostics') or {}
    return body


def report_latency(report):
    """Inclusive buckets and child calls are separate, never added together."""
    stages = {k: float(v) for k, v in report.get('timings_ms', {}).items()}
    calls = []
    audit = report.get('audit') or {}
    for stage, value in [('planning', (report.get('planning') or {}).get('audit')),
                         ('assessment', audit.get('assessment_audit')),
                         ('extraction', audit if 'schema_validation' in audit else None),
                         ('prose', (report.get('presentation_draft') or {}).get('audit'))]:
        if not isinstance(value, dict):
            continue
        calls.append({'stage': stage, 'state': 'completed', 'origin': 'legacy_audit',
                      'elapsed_ms': float(value['elapsed_seconds'])*1000 if 'elapsed_seconds' in value else None,
                      'stages_ms': {'inference': float(value['inference_seconds'])*1000} if 'inference_seconds' in value else {},
                      'input_tokens': value.get('input_tokens'),
                      'output_tokens': (value.get('usage') or {}).get('completion_tokens')})
    parents = ('resolution_validation','structured_lookup','query_embedding_and_tokens','search_total',
               'facet_candidate_expansion','reranking_with_preparation','field_coverage_selection',
               'assembly_and_model_tokenization','answer_model_calls','validation_and_presentation')
    residual = (stages['answer_total'] - sum(stages.get(k,0) for k in parents)) if 'answer_total' in stages else None
    # This is elapsed time not accounted for by the observed parent buckets,
    # not a claim about its cause. Child search/model/presentation times overlap.
    return {'stages_ms': stages, 'calls': calls, 'unattributed_core_ms': residual,
            'reconciliation': 'unrecorded' if residual is None else 'overlapping_or_inconsistent' if residual < -1 else 'reconciled'}


def latency(body, wall_seconds=None, job=None):
    result = {'wall_ms': float(wall_seconds)*1000 if wall_seconds is not None else None,
              'attempts': [], 'final': report_latency(unwrap(body))}
    if job is None:
        return result
    result['job_total_ms'] = job.get('total_ms')
    for attempt in job.get('attempts', []):
        raw = attempt.get('response_text')
        report = unwrap(exact_load(raw)) if raw else {}
        measured = report_latency(report)
        operations = attempt.get('operations') or []
        observed = [c for op in operations for c in (op.get('model_measurement') or {}).get('calls', [])]
        if observed:
            measured['calls'] = observed
        elif not any(c['stage'] == 'planning' for c in measured['calls']):
            for op in operations:
                if op.get('operation') == 'plan_fields' and op.get('response_text'):
                    measured['calls'] += report_latency({'planning': exact_load(op['response_text'])})['calls']
        measured.update({k: attempt.get(k) for k in ('model','state','queue_ms','activation_ms','work_ms')})
        # Old failed activations wrote 0 even without a valid identity. Do not
        # relabel that sentinel as an observed zero-duration activation.
        if not attempt.get('identity'):
            measured['activation_ms'] = None
        result['attempts'].append(measured)
    return result


def aggregate(rows):
    if len({r['case'] for r in rows}) != len(rows):
        raise ValueError('duplicate questions in one arm/pass; split attempts before scoring')
    counts = {name: sum(r['outcome'] == name for r in rows) for name in (
        'answered_correct','answered_wrong','abstained_correct','abstained_missed',
        'abstained_wrong','request_declined_correct','request_declined_wrong','system_error','unscorable')}
    n = len(rows)
    correct = counts['answered_correct'] + counts['abstained_correct'] + counts['request_declined_correct']
    return {'questions': n, 'outcomes': counts, 'correct': correct,
            'correct_wilson95': wilson(correct, n),
            'answered_wrong_wilson95': wilson(counts['answered_wrong'], n),
            'outcome_wilson95': {name: wilson(count,n) for name,count in counts.items()},
            'answered_precision_wilson95': wilson(counts['answered_correct'], counts['answered_correct']+counts['answered_wrong']),
            'gold_matching_rejected_drafts': sum(r.get('rejected_gold_values') is True for r in rows),
            'wall_ms': distribution(r['latency']['wall_ms'] for r in rows)}
