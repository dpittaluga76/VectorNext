"""Offline D4 scorer. Input proofs must be resolved from captured source evidence.

This is deliberately separate from historical scorers and production validation.
It neither runs models nor awards primary credit using diagnostic normalization.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re
import unicodedata


def floor(value):
    """The entire global normalization policy; do not add semantic rewrites."""
    if not isinstance(value, str):
        raise TypeError('Fact values must be strings')
    return re.sub(r'[ \t\r\n\u00a0]+', ' ', unicodedata.normalize('NFC', value)).strip(' ')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same_location(required, observed):
    if required['document_sha256'] != observed.get('document_sha256'):
        return False
    if 'pointer' in required:
        return observed.get('pointer') == required['pointer']
    start, end = observed.get('utf8_start'), observed.get('utf8_end')
    return (type(start) is int and type(end) is int and 0 <= start < end
            and start <= required['utf8_start'] and end >= required['utf8_end'])


def proved(role, fields, key='proof_sets'):
    observed = [p for f in fields for p in f.get('proofs', [])]
    return any(group and all(any(same_location(p, q) for q in observed) for p in group)
               for group in role.get(key, []))


def permitted_values(role):
    """Enumerate, never contain-match, a finite per-case language."""
    values = [role['value_string'], *role['allowed_alternatives']]
    members = role.get('members', [])
    if members:
        for combination in itertools.product(*(m['aliases'] for m in members)):
            orders = itertools.permutations(combination) if role['unordered'] else [combination]
            for order in orders:
                values.extend(sep.join(order) for sep in role['separators'])
    return set(map(floor, values))


def diagnostic_key(value, role):
    """Only case-declared literal removals; never used by primary matching."""
    value = floor(value)
    for literal in role['format_diagnostic_remove_literals']:
        value = value.replace(literal, '')
    return floor(value)


def member_hits(role, values):
    """Exact component diagnostic; partial/extra/duplicate lists still fail primary."""
    members = role.get('members', [])
    tokens = []
    for value in values:
        pieces = [floor(value)]
        for separator in role.get('separators', []):
            pieces = [p for piece in pieces for p in piece.split(separator)]
        tokens.extend(map(floor, pieces))
    return {m['id']: any(t in set(map(floor, m['aliases'])) for t in tokens) for m in members}


def role_result(role, fields):
    typed = all(f.get('type') == 'string' and isinstance(f.get('value_text'), str) for f in fields)
    result = {'type_ok': typed, 'value_ok': False, 'proof_ok': proved(role, fields),
              'derived_proof_ok': proved(role, fields, 'derived_proof_sets'),
              'derived_exact': False, 'imprecise': False, 'diagnostic': 'type_failure',
              'members': {}, 'unlisted': False}
    if not typed:
        return result
    values = [floor(f['value_text']) for f in fields]
    members = role.get('members', [])
    if len(values) == 1:
        result['value_ok'] = values[0] in permitted_values(role)
        result['derived_exact'] = values[0] in set(map(floor, role['derived_alternatives']))
        result['imprecise'] = values[0] in set(map(floor, role['imprecise_alternatives']))
    elif members and len(values) == len(members):
        assignments = [order for order in itertools.permutations(members)
                       if all(value in set(map(floor, member['aliases']))
                              for value, member in zip(values, order))]
        result['value_ok'] = bool(assignments)
        # A correct unordered pair with swapped/wrong citations is not supported.
        result['proof_ok'] = result['proof_ok'] and any(
            all(proved(member, [field]) for member, field in zip(order, fields))
            for order in assignments)
    result['members'] = member_hits(role, values)
    if members and result['value_ok']:
        result['members'] = {m['id']: True for m in members}
    if result['value_ok']:
        result['diagnostic'] = 'match' if result['proof_ok'] else 'proof_failure'
    elif result['derived_exact']:
        result['diagnostic'] = 'scale_conversion'
    elif result['imprecise']:
        result['diagnostic'] = 'supported_imprecise_candidate'
    else:
        keys = {diagnostic_key(v, role) for v in permitted_values(role)} - {''}
        formatting = len(values) == 1 and diagnostic_key(values[0], role) in keys
        result['diagnostic'] = 'format_like_nonmatch' if formatting else 'factual_or_unlisted_nonmatch'
        result['unlisted'] = True
    return result


def score_case(case, capture):
    """Score one normalized capture; exact names/layouts are frozen per case.

    Production rejected drafts must not be placed in fields. They remain a
    separate diagnostic stream. Model assertions alone are not verified proofs.
    """
    result = {'case_id': case['case_id'], 'number': case['number'], 'tier': case['tier'],
              'outcome': None, 'correct': None, 'roles': {}, 'review_queue': [],
              'stress_behaviors': {}, 'scale_conversion_correct': False}
    if case['tier'] == 'stress_adjudication':
        result['outcome'] = 'stress_not_accuracy_scored'
        # Human observations are deliberately not guessed from status or prose.
        result['stress_behaviors'] = {key: 'unreviewed' for key in (
            'identifies_ambiguity', 'states_assumption', 'conditional_source_backed_answers',
            'unsupported_certainty')}
        return result
    if case['pending_decisions']:
        result['outcome'] = 'pending_gold_not_scored'
        return result
    status = capture.get('status')
    fields = capture.get('fields', [])
    if (not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields)
            or status not in ('supported', 'ambiguous', 'insufficient_evidence', 'rejected', 'error')):
        result['outcome'] = 'malformed_capture'
        result['correct'] = False
        return result
    for field in fields:
        proofs = field.get('proofs', [])
        if not isinstance(proofs, list) or any(not isinstance(p, dict) for p in proofs):
            result.update(outcome='malformed_capture', correct=False)
            return result
    if status == 'error':
        result['outcome'] = 'system_error'
        result['correct'] = False
        return result
    if status != 'supported':
        result['correct'] = status == case['expected'] and not fields
        result['outcome'] = ('abstained_correct' if result['correct'] else
                             'abstained_missed' if case['expected'] == 'supported' else
                             'incorrect_negative_decision')
        return result
    if case['expected'] != 'supported':
        result.update(correct=False, outcome='answered_wrong')
        return result
    names = [f.get('name') for f in fields]
    layouts = case['allowed_field_mappings']
    mapping = next((layout for layout in layouts
                    if len(names) == len(layout) and all(isinstance(n, str) for n in names)
                    and set(names) == set(layout)), None)
    if mapping is None:
        result.update(correct=False, outcome='answered_wrong', mapping_ok=False)
        result['review_queue'].append({'reason': 'unlisted_field_mapping', 'fields': fields})
        return result
    result['mapping_ok'] = True
    for role in case['roles']:
        selected = [f for f in fields if mapping[f['name']] == role['id']]
        if not selected:
            raise ValueError('Gold layout omits a required role')
        r = role_result(role, selected)
        result['roles'][role['id']] = r
        if r['unlisted']:
            result['review_queue'].append({'reason': 'unlisted_value', 'role': role['id'],
                                          'fields': selected})
    result['correct'] = all(r['type_ok'] and r['value_ok'] and r['proof_ok']
                            for r in result['roles'].values())
    result['scale_conversion_correct'] = (not result['correct'] and
        all(r['type_ok'] and r['proof_ok'] and (r['value_ok'] or (r['derived_exact'] and r['derived_proof_ok']))
            for r in result['roles'].values()) and
        any(r['derived_exact'] for r in result['roles'].values()))
    result['outcome'] = 'answered_correct' if result['correct'] else 'answered_wrong'
    return result


def report(gold, captures):
    validate_gold(gold)
    expected = {c['case_id'] for c in gold['cases']}
    if set(captures) - expected:
        raise ValueError('Unknown capture IDs')
    rows = [score_case(c, captures.get(c['case_id'], {'status': 'error'})) for c in gold['cases']]
    views = {}
    for tier in ('primary_direct_extraction', 'derived_inference', 'stress_adjudication'):
        selected = [r for r in rows if r['tier'] == tier]
        views[tier] = {'roster_n': len(selected), 'scorable_n': sum(r['correct'] is not None for r in selected),
            'correct_count': sum(r['correct'] is True for r in selected),
            'outcomes': dict(Counter(r['outcome'] for r in selected)),
            'failure_counts': dict(Counter(v['diagnostic'] for r in selected
                                         for v in r['roles'].values() if v['diagnostic'] != 'match'))}
    return {'label_status': gold['status'], 'approved_for_execution': False,
            'views': views, 'scale_conversion_correct_count': sum(r['scale_conversion_correct'] for r in rows),
            'sensitivity_review': {'status': 'unreviewed', 'corrected_primary': False,
                                   'additional_correct_count': None,
                                   'queue_count': sum(bool(r['review_queue']) for r in rows)},
            'missing_capture_count': len(expected - set(captures)), 'cases': rows}


def oracle_fields(case):
    """Gold names/types/locations only; intentionally excludes answers/aliases."""
    if case['pending_decisions'] or case['expected'] != 'supported' or case['tier'] == 'stress_adjudication':
        raise ValueError('Case is not ready for an oracle field proposal')
    # Neutral names avoid encoding the answer into a field name (e.g. GBP).
    return {'case_id': case['case_id'], 'fields': [{'name': r['id'], 'kind': 'string',
                'required': True, 'locations': r['proof_sets']} for r in case['roles']]}


def validate_gold(gold):
    """Fail closed on malformed reviewed lists; schema is also published for tooling."""
    seen = set()
    for case in gold['cases']:
        if case['case_id'] in seen:
            raise ValueError('Duplicate gold case ID')
        seen.add(case['case_id'])
        roles = {r['id'] for r in case['roles']}
        if len(roles) != len(case['roles']):
            raise ValueError('Duplicate fact role')
        for role in case['roles']:
            if role['source_type'] != 'string':
                raise ValueError('D4 final fact types must be string')
            for name in ('allowed_alternatives', 'derived_alternatives', 'imprecise_alternatives',
                         'format_diagnostic_remove_literals'):
                if not isinstance(role[name], list) or any(not isinstance(x, str) for x in role[name]):
                    raise ValueError(f'Invalid string list: {name}')
            floor(role['value_string'])
            primary = permitted_values(role)
            if primary & set(map(floor, role['derived_alternatives'] + role['imprecise_alternatives'])):
                raise ValueError('Primary/derived/imprecise lists overlap')
            if not role['proof_sets'] or any(not group for group in role['proof_sets']):
                raise ValueError('Missing source proof requirement')
            for group in role['proof_sets']:
                for loc in group:
                    if not re.fullmatch(r'[0-9a-f]{64}', loc['document_sha256']):
                        raise ValueError('Invalid document hash')
                    if 'pointer' in loc:
                        if not loc['pointer'].startswith('/') or re.search(r'~(?![01])', loc['pointer']):
                            raise ValueError('Invalid JSON pointer')
                    elif not (type(loc.get('utf8_start')) is int and type(loc.get('utf8_end')) is int
                              and 0 <= loc['utf8_start'] < loc['utf8_end']):
                        raise ValueError('Invalid UTF-8 evidence span')
        for mapping in case['allowed_field_mappings']:
            if set(mapping.values()) != roles:
                raise ValueError('Field layout must cover exactly all roles')


def verify_paired_format(automatic, oracle, instruction_sha256, *, same_evidence=True):
    """Contract check for future captured arms; never manufacture an audit."""
    keys = ['question_sha256', 'instruction_sha256', 'scorer_sha256', 'gold_sha256',
            'model_identity_sha256', 'retrieval_settings_sha256']
    if same_evidence:
        keys.append('assembled_evidence_sha256')
    for key in keys:
        if not automatic.get(key) or automatic[key] != oracle.get(key):
            raise ValueError(f'Paired arm mismatch: {key}')
    if automatic['instruction_sha256'] != instruction_sha256:
        raise ValueError('Wrong frozen answer-format instruction')
    for audit in (automatic, oracle):
        if audit.get('format_applied_stages') != ['planning', 'assessment', 'extraction']:
            raise ValueError('Instruction not recorded at all stages')
    return 'field_planning_ablation' if same_evidence else 'gold_evidence_ablation_not_planning_cost'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold', type=Path, required=True)
    parser.add_argument('--captures', type=Path, required=True,
                        help='Normalized capture map by case ID; not raw model assertions')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = report(json.loads(args.gold.read_text(encoding='utf-8')),
                    json.loads(args.captures.read_text(encoding='utf-8')))
    result['inputs'] = {str(p): digest(p) for p in (args.gold, args.captures, Path(__file__))}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
