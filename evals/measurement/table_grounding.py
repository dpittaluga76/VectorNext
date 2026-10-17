"""Versioned D5 value-primary scoring and independent coordinate grounding."""
from collections import Counter

from . import typed_facts as d4


def covers(required, observed):
    if not isinstance(observed, dict):
        return False
    for key in ('table_id', 'source_sha256'):
        if not required.get(key) or required[key] != observed.get(key):
            return False
    if 'row' in required:
        if any(type(observed.get(k)) is not int or observed[k] != required[k] for k in ('row', 'col')):
            return False
        if 'utf8_start' not in required:
            return 'utf8_start' not in observed and 'utf8_end' not in observed
        if 'utf8_start' not in observed and 'utf8_end' not in observed:
            return True  # full original cell covers an explicitly cited fragment
    elif type(observed.get('paragraph')) is not int or observed['paragraph'] != required.get('paragraph'):
        return False
    a, b = observed.get('utf8_start'), observed.get('utf8_end')
    return (type(a) is int and type(b) is int and 0 <= a < b
            and a <= required.get('utf8_start', -1) and b >= required.get('utf8_end', b + 1))


def grounded(proof_sets, fields):
    """Both cited value identity and visible disambiguating context must match."""
    if not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields):
        return False
    if any(not isinstance(f.get('evidence_coordinates', []), list) for f in fields):
        return False
    return any(proof['required'] and any(covers(proof['value'], f.get('value_coordinate'))
                       and all(any(covers(ref, seen) for seen in f.get('evidence_coordinates', []))
                               for ref in proof['required']) for f in fields)
               for proof in proof_sets)


def recall_at_k(proof_sets, passages, k):
    if type(k) is not int or k < 1:
        raise ValueError('k must be positive')
    coordinates = [ref for passage in passages[:k] for ref in passage['visible_coordinates']]
    return {'k': k, 'passages_observed': min(k, len(passages)),
            'value_cell_retrieved': any(any(covers(p['value'], r) for r in coordinates) for p in proof_sets),
            'complete_proof_retrieved': any(p['required'] and all(any(covers(r, seen) for seen in coordinates)
                                               for r in p['required']) for p in proof_sets)}


def score_case(case, capture, table_proofs):
    result = d4.score_case(case, capture)
    result['prior_D4_joint_correct'] = result['correct']
    result['evidence_correct'] = None
    result['joint_correct'] = None
    result['correct_answer_wrong_evidence'] = False
    # Stress never enters the primary or derived factual denominator.
    if case['tier'] == 'stress_adjudication':
        result['conditional_grounding'] = []
        for reading in table_proofs.get('stress_readings', []):
            final_fields = capture.get('fields', []) if capture.get('status') == 'supported' else []
            final_fields = final_fields if isinstance(final_fields, list) else []
            fields = [f for f in final_fields if isinstance(f, dict)
                      and f.get('type') == 'string' and isinstance(f.get('value_text'), str)
                      and d4.floor(f['value_text']) == d4.floor(reading['value_string'])]
            result['conditional_grounding'].append({'reading': reading['id'],
                'value_present': bool(fields), 'evidence_correct': grounded(reading['proof_sets'], fields)})
        return result
    if not result['roles'] or not result.get('mapping_ok') or case['pending_decisions']:
        return result
    value_ok = all(r['type_ok'] and r['value_ok'] for r in result['roles'].values())
    evidence_ok = all(r['proof_ok'] for r in result['roles'].values())
    if case['format'] == 'json':
        evidence_ok = grounded(table_proofs['proof_sets'], capture['fields'])
    result['correct'] = value_ok
    result['outcome'] = 'answered_correct' if value_ok else 'answered_wrong'
    result['evidence_correct'] = evidence_ok
    result['joint_correct'] = value_ok and evidence_ok
    result['correct_answer_wrong_evidence'] = value_ok and not evidence_ok
    return result


def report(gold, captures, proof_registry):
    d4.validate_gold(gold)
    if set(captures) - {c['case_id'] for c in gold['cases']}:
        raise ValueError('Unknown capture IDs')
    proofs = {c['case_id']: c for c in proof_registry['cases']}
    rows = [score_case(c, captures.get(c['case_id'], {'status': 'error'}), proofs.get(c['case_id'], {}))
            for c in gold['cases']]
    views = {}
    for tier in ('primary_direct_extraction', 'derived_inference', 'stress_adjudication'):
        subset = [r for r in rows if r['tier'] == tier]
        views[tier] = {'roster_n': len(subset), 'scorable_n': sum(r['correct'] is not None for r in subset),
            'value_correct': sum(r['correct'] is True for r in subset),
            'joint_correct_supported_answers': sum(r['joint_correct'] is True for r in subset),
            'correct_answer_wrong_evidence': sum(r['correct_answer_wrong_evidence'] for r in subset),
            'grounding_observed_answer_count': sum(r['evidence_correct'] is not None for r in subset),
            'outcomes': dict(Counter(r['outcome'] for r in subset))}
    return {'definition': 'D5 v1.2 typed-value primary; grounding diagnostic; no production change',
            'approved_for_execution': False, 'views': views, 'cases': rows,
            'missing_capture_count': sum(c['case_id'] not in captures for c in gold['cases']),
            'sensitivity_review': {'status': 'unreviewed', 'primary_modified': False}}
