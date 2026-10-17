"""Build D4 DEVELOPMENT review artifacts from verified, unchanged source bytes.

No inference, sealed access, fixture rewriting or execution approval. All extra
alternatives below come from the source/question and D1-D4 adjudications.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .audit_labels import verified_input
from .typed_facts import digest, floor, permitted_values, diagnostic_key, validate_gold


# number: role, scale, unit, period, unit/context pointers, question target.
# Source scale is independent of TAT-QA's annotation; a blank source stays blank.
TABLES = {
    2: ('opening_balance', 'thousand', 'dollars', 'fiscal 2019', ['/records/8/text', '/records/0/cells/1'], 'amount'),
    12: ('total_energy_consumption', 'unit', 'MWh', 'year ended 31 December 2018', ['/records/3/cells/0', '/records/1/cells/1', '/records/2/cells/2'], 'amount'),
    13: ('direct_energy_consumption', 'unit', 'MWh', 'year ended 31 December 2019', ['/records/4/cells/0', '/records/1/cells/1', '/records/2/cells/1'], 'amount'),
    21: ('net_deferred_tax_assets', 'million', 'dollars', 'fiscal year end 2019', ['/records/2/cells/2', '/records/1/cells/1'], 'amount'),
    22: ('allowance_for_credit_losses', 'million', 'dollars', '31 December 2019', ['/records/0/cells/0', '/records/1/cells/0', '/records/1/cells/1'], 'amount'),
    23: ('accrued_compensation_and_benefits', 'million', 'dollars', '30 June 2019', ['/records/1/cells/0', '/records/0/cells/1', '/records/1/cells/1'], 'amount'),
    24: ('software_revenue', 'thousand', 'dollars', '2018', ['/records/0/cells/0', '/records/0/cells/1'], 'amount'),
    25: ('order_intake_change', 'percent', 'percent', '2019 compared with 2018', ['/records/0/cells/3'], 'percentage'),
    28: ('cash_dividend_per_share', 'unit', 'NT dollars per share', '2019', ['/records/0/cells/3', '/records/1/cells/4'], 'amount'),
    29: ('legal_reserve', 'thousand', 'NT dollars', '2019', ['/records/0/cells/1', '/records/1/cells/2'], 'amount'),
    30: ('outstanding_rights', 'unit', 'rights', 'end of period 2019', ['/records/1/cells/1', '/records/0/cells/1'], 'count'),
    40: ('aerospace_and_defense', 'million', 'dollars', 'year ended 30 June 2019', ['/records/1/cells/0', '/records/0/cells/1', '/records/1/cells/1'], 'amount'),
    41: ('non_usd_current_monetary_assets', 'million', 'RMB', '31 December 2019', ['/records/0/cells/2', '/records/1/cells/0'], 'amount'),
    48: ('total_basic_eps', 'unit', 'cents per share', '2019, 53 weeks', ['/records/10/cells/0', '/records/0/cells/1', '/records/1/cells/1'], 'amount'),
    49: ('total_diluted_eps', 'unit', 'cents per share', '2018, 52 weeks', ['/records/14/cells/0', '/records/0/cells/2', '/records/1/cells/2'], 'amount'),
    55: ('current_loss_allowance', 'thousand', 'dollars', '30 June 2019', ['/records/1/cells/1', '/records/0/cells/0', '/records/0/cells/1'], 'amount'),
    56: ('total_liabilities', 'million', 'dollars', '31 December 2019, revised preliminary allocation', ['/records/2/cells/0', '/records/0/cells/3', '/records/1/cells/3', '/records/2/cells/3'], 'amount'),
    62: ('state_income_taxes', 'million', 'dollars not established by unit header alone', 'year ended 3 January 2020; question scope disputed', ['/records/2/cells/2', '/records/1/cells/1'], 'amount'),
    64: ('expected_term', 'unit', 'years', '0.6: year ended 31 January 2020; 0.8: year ended 1 February 2019', ['/records/5/cells/0', '/records/1/cells/1', '/records/1/cells/2'], 'amount'),
    69: ('total_net_sales', 'million', 'dollars', 'fiscal 2018', ['/records/0/cells/0', '/records/1/cells/2'], 'amount'),
    80: ('basic_eps', 'unit', 'dollars per share', 'year ended 30 September 2019', ['/records/6/cells/0', '/records/7/cells/0', '/records/0/cells/1', '/records/1/cells/1'], 'amount'),
    82: ('currency', 'unit', 'INR per currency unit for comparison', 'FY2019 and FY2018', ['/records/0/cells/2', '/records/0/cells/3', '/records/10/text'], 'comparison'),
    86: ('domestic_state_loss_carryforwards', 'thousand', 'dollars', 'observation date not stated in table; 2039 is expiry', ['/records/0/cells/0', '/records/0/cells/1'], 'amount'),
    87: ('module_sales_increase', 'percent', 'percent', '2019 over 2018', ['/records/1/cells/4', '/records/2/cells/5'], 'percentage'),
    89: ('deferred_tax_assets_as_reported', 'unspecified', 'unspecified in supplied unit context', '28 February 2019, as reported', ['/records/0/cells/2', '/records/2/cells/1'], 'amount'),
    90: ('deferred_tax_assets_without_asc606', 'unspecified', 'unspecified in supplied unit context', '28 February 2019, without ASC 606 adoption', ['/records/0/cells/2', '/records/1/cells/3', '/records/2/cells/3'], 'amount'),
    91: ('gross_emissions', 'unit', 'tonnes CO2e', 'FY19, UK and Ireland', ['/records/1/cells/2', '/records/2/cells/1', '/records/13/text'], 'amount'),
    92: ('gross_emissions', 'unit', 'tonnes CO2e', 'FY18; UK/Ireland or full Group unresolved', ['/records/1/cells/2', '/records/2/cells/2', '/records/2/cells/3', '/records/13/text'], 'amount'),
    105: ('interest_rate_swap_carrying_amount', 'million', 'RMB', '2018', ['/records/1/cells/2', '/records/0/cells/2', '/records/2/cells/0'], 'amount'),
    108: ('operating_margin', 'percent', 'percent', 'fiscal 2018', ['/records/1/cells/0', '/records/1/cells/1'], 'percentage'),
    113: ('issued_dsu', 'unit', 'DSU', 'year ended 31 August 2019', ['/records/0/cells/0', '/records/0/cells/1'], 'count'),
    114: ('current_trade_receivables', 'thousand', 'dollars', '2019', ['/records/1/cells/2', '/records/0/cells/2', '/records/2/cells/0'], 'amount'),
    115: ('uk_revenue', 'million', 'dollars', 'year ended 31 March 2019', ['/records/1/cells/1', '/records/0/cells/1'], 'amount'),
    116: ('derivative_liabilities', 'unspecified', 'unspecified in supplied unit context', '31 December 2018', ['/records/0/cells/1', '/records/1/cells/2'], 'amount'),
    117: ('ground_leases', 'unit', 'restaurants / ground leases', 'fiscal 2020-2024', ['/records/0/cells/2', '/records/2/cells/1', '/records/4/cells/0'], 'count'),
    119: ('gross_profit_sales_percentage', 'percent', 'percent', 'year ended 31 December 2018', ['/records/12/text', '/records/0/cells/1', '/records/1/cells/2'], 'percentage'),
    120: ('granted_nonvested_shares', 'unit', 'shares', '2019 (between opening 2018 and closing 2019)', ['/records/0/cells/1', '/records/1/cells/0', '/records/5/cells/0'], 'count'),
}

# Explicit source-only per-case aliases, not automatic corpus-wide transforms.
TEXT_ALIASES = {
    3: ['“It’s Scotland’s oil”', 'It’s Scotland’s oil'],
    20: ['English'],
    31: ['production disruptions', 'distribution disruptions'],
    43: [],  # finite two-member grammar below
    54: ['3,209 reviews', '3209 reviews', '3,209', '3209', '$3,209$'],
    61: ['1910-1940', '1910 to 1940'],
    98: ['168637'],
    103: ['11-13th century', '11-13th century AD'],
}

TEXT_ROLES = {1: 'instance', 3: 'campaign', 4: 'job', 7: 'meaning', 8: 'math_type',
    14: 'dataset', 20: 'language', 27: 'annual_carriage_fees', 31: 'cause', 32: 'date',
    38: 'offspring_cells', 39: 'first_defense', 43: 'codes', 44: 'factor', 45: 'services',
    52: 'cities', 54: 'dataset_size', 57: 'year', 58: 'job_market_effect',
    59: 'holding_arrangements', 60: 'motivator_type', 61: 'period', 63: 'dataset',
    72: 'arrest_reason', 74: 'feature_representation', 81: 'user_count', 83: 'dataset',
    85: 'religion', 88: 'speaker', 93: 'district', 95: 'recognition', 97: 'height',
    98: 'buddhist_count', 101: 'translation', 103: 'period', 104: 'river',
    106: 'difference', 109: 'charging_basis', 112: 'purpose'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pointer(data, path):
    for part in path.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def location(case, path):
    return {'document_sha256': case['document_sha256'], 'pointer': path}


def occurrences(text, needle):
    """All literal occurrences with token boundaries, including repeated facts."""
    for match in re.finditer(re.escape(needle), text):
        a, b = match.span()
        if needle and needle[0].isalnum() and a and text[a - 1].isalnum():
            continue
        if needle and needle[-1].isalnum() and b < len(text) and text[b].isalnum():
            continue
        yield a, b


def floor_occurrences(text, value):
    """Source offsets with the scoring whitespace floor; fail on unmapped NFC."""
    if unicodedata.normalize('NFC', text) != text:
        raise ValueError('NFC changes source offsets: an explicit offset map is required')
    needle = floor(value)
    if not needle:
        return
    pattern = r'[ \t\r\n\u00a0]+'.join(re.escape(p) for p in needle.split(' '))
    for match in re.finditer(pattern, text):
        a, b = match.span()
        if needle[0].isalnum() and a and text[a - 1].isalnum():
            continue
        if needle[-1].isalnum() and b < len(text) and text[b].isalnum():
            continue
        yield a, b


def span(case, a, b):
    return {'document_sha256': case['document_sha256'],
            'utf8_start': len(case['source_text'][:a].encode('utf-8')),
            'utf8_end': len(case['source_text'][:b].encode('utf-8'))}


def evidence_spans(case, adjudication=None):
    if adjudication:
        return [dict(document_sha256=case['document_sha256'],
                     utf8_start=x['utf8_byte_start'], utf8_end=x['utf8_byte_end'])
                for x in adjudication['evidence']]
    support = case['label']['support']
    if case['request']['source'] == 'squad':
        return [span(case, x['answer_start'], x['answer_start'] + len(x['text'])) for x in support]
    evidence = {e for ann in support for e in ann['evidence']}
    return [span(case, a, b) for e in sorted(evidence) for a, b in occurrences(case['source_text'], e)]


def table_role(case):
    n = case['n']
    name, scale, unit, period, refs, target = TABLES[n]
    source = json.loads(case['source_text'])
    matches = case['label']['support']['possible_exact_cells']
    # Equal-valued wrong-role cells are NOT accepted proofs.
    match = matches[0]
    gold_path = f"/records/{match['record_index']}{match['pointer']}"
    if n == 2: gold_path = '/records/1/cells/1'
    if n == 80: gold_path = '/records/7/cells/1'
    if n == 92: gold_path = '/records/5/cells/2'
    value = pointer(source, gold_path)
    assert isinstance(value, str) and value in case['label']['alternatives'], n
    context = [{'pointer': p, 'value_string': pointer(source, p)} for p in refs]
    role = base_role(name, value)
    role.update(scale={'stated': scale, 'unit': unit, 'source_context': context,
                       'upstream_annotation': case['label']['support']['scale']},
                period=period, question_target=target,
                qualifier='Preserve row/group/period qualifiers in source_context; no inferred qualifier.',
                proof_sets=[[location(case, gold_path)]])
    if n == 82:
        # Correct comparison requires all competing rates, not merely the GBP name.
        role['proof_sets'] = [[location(case, '/records/2/cells/0')] +
            [location(case, f'/records/{row}/cells/{col}') for row in (1, 2, 3)]
            for col in (2, 3)]
    if scale in ('thousand', 'million') and n != 62:
        # Selected amount cases only. Explicit finite strings are persisted in gold.
        amount = Decimal(value.replace('$', '').replace(',', '').strip())
        converted = amount * Decimal('1000' if scale == 'thousand' else '1000000')
        raw = format(converted, 'f').rstrip('0').rstrip('.') if '.' in format(converted, 'f') else str(converted)
        comma = format(Decimal(raw), ',f')
        role['allowed_alternatives'] = [f'{value} {scale}']
        role['derived_alternatives'] = sorted({raw, comma, f'{raw} {unit}', f'{comma} {unit}'} |
            ({f'${raw}', f'${comma}'} if unit == 'dollars' else set()))
        role['format_diagnostic_remove_literals'] = [',', '$', ' ', scale]
        role['derived_proof_sets'] = [[location(case, gold_path)] + [location(case, p) for p in refs]]
    elif n in (12, 13, 30, 113, 117, 120):
        role['format_diagnostic_remove_literals'] = [',']
    elif n in (25, 87, 108, 119):
        role['format_diagnostic_remove_literals'] = ['%']
    if n == 2:
        role['derived_alternatives'] += ['$1.264 million', '1.264 million dollars']
        role['imprecise_alternatives'] = ['about $1.26 million']
    return role


def base_role(name, value):
    return {'id': name, 'value_string': value, 'source_type': 'string',
            'scale': {'stated': 'not_applicable', 'unit': None, 'source_context': []},
            'period': 'as stated in source/question; no new inference',
            'qualifier': 'preserve source wording', 'question_target': 'text_span',
            'allowed_alternatives': [], 'derived_alternatives': [], 'imprecise_alternatives': [],
            'proof_sets': [], 'derived_proof_sets': [], 'format_diagnostic_remove_literals': []}


def build(audit, reports):
    d1 = {x['number']: x for x in read(reports / 't39-d1-adjudication-v1.1.json')['cases']}
    d2 = {x['number']: x for x in read(reports / 't39-d2-adjudication-v1.1.json')['cases']}
    d3 = read(reports / 't39-d3-tiers-v1.1.json')
    roster = {x['number']: x for x in d3['development_roster']}
    cases = []
    for c in audit['cases']:
        n = c['n']; original = c['label']
        expected = roster[n]['D1_reviewed_expected']
        pending = [f'case {n:03d} source adjudication'] if n in (10, 34, 47, 53, 71, 107) else []
        roles = []
        if original['alternatives'] or expected == 'supported':
            if n in TABLES:
                roles = [table_role(c)]
            else:
                alts = original['alternatives'][:]
                adjudication = None
                if n in d1 and d1[n].get('accepted_aliases'):
                    alts = [a['value_text'] for a in d1[n]['accepted_aliases']]
                    adjudication = d1[n]
                if n in d2 and d2[n]['eligible_for_successor_adaptation']:
                    alts = d2[n].get('faithful_aliases', d2[n]['approved_literal_answers'])
                    adjudication = d2[n]
                role = base_role(TEXT_ROLES.get(n, 'answer'), alts[0])
                role['allowed_alternatives'] = list(dict.fromkeys(alts[1:] + TEXT_ALIASES.get(n, [])))
                spans = evidence_spans(c, adjudication)
                if n == 74:
                    # Preprocessing and LDA context do not prove the classifier feature.
                    spans = evidence_spans(c, {'evidence': [e for e in adjudication['evidence']
                                                           if e['role'] == 'classification']})
                if n == 81:
                    # Neither the rounded introduction nor split sizes prove the exact total.
                    spans = evidence_spans(c, {'evidence': [e for e in adjudication['evidence']
                                                           if '22,880 users' in e['quote']]})
                # Entailment/attribution depend on the combined statement, not a name match.
                role['proof_sets'] = [spans] if n in (4, 88) else [[s] for s in spans]
                if n in (81, 97):
                    role['imprecise_alternatives'] = d2[n]['imprecise_aliases']
                if n == 81: role['format_diagnostic_remove_literals'] = [',', ' users']
                if n == 54: role['format_diagnostic_remove_literals'] = ['$', ',', ' reviews']
                if n == 43:
                    role.update(members=[{'id': 'first_code', 'aliases': ['Taihō Code', 'Taihō Code (701)', 'the Taihō Code', 'the Taihō Code (701)']},
                                         {'id': 'second_code', 'aliases': ['Yōrō Code', 'Yōrō Code (718)', 'the Yōrō Code', 'the Yōrō Code (718)']}],
                                unordered=True, separators=[',', ', ', '/', ' / ', ' and '])
                    # Both names/years must be evidenced even when emitted separately.
                    role['proof_sets'] = [[span(c, a, b) for term in ('Taihō Code (701)', 'Yōrō Code (718)')
                                           for a, b in occurrences(c['source_text'], term)]]
                    for member, anchor in zip(role['members'], role['proof_sets'][0]):
                        member['proof_sets'] = [[anchor]]
                roles = [role]
        mappings = []
        for role in roles:
            for field in dict.fromkeys([role['id'], 'answer', 'value']):
                mappings.append({field: role['id']})
        if n == 43:
            mappings += [{'first_code': 'codes', 'second_code': 'codes'}, {'code_1': 'codes', 'code_2': 'codes'}]
        cases.append({'number': n, 'case_id': c['id'], 'question': c['request']['question'],
                      'document': c['request']['document'], 'document_sha256': c['document_sha256'],
                      'source_text_sha256': hashlib.sha256(c['source_text'].encode('utf-8')).hexdigest(),
                      'format': c['request']['format'], 'tier': roster[n]['tier'], 'expected': expected,
                      'pending_decisions': pending, 'original_alternatives': original['alternatives'],
                      'original_expected': original['expected'], 'roles': roles, 'allowed_field_mappings': mappings})
    return {'version': '1.1-d4-candidate', 'date': '2026-10-16', 'status': 'source_review_candidate',
            'approved_for_execution': False, 'independent_review': False, 'sealed_content_opened': False,
            'base_manifest_sha256': audit['manifest_sha256'],
            'pending_global_decisions': ['D5 table context/proof integration', 'D6 source families and custody',
                'D7 coverage', 'final adaptation/field mapping approval', 'runtime format instruction integration',
                'six specific case adjudications', 'single execution freeze'],
            'cases': cases}


def collision_audit(gold, audit):
    by_id = {c['id']: c for c in audit['cases']}
    results = []
    for case in gold['cases']:
        raw = by_id[case['case_id']]
        collisions = []; checked = 0
        for role in case['roles']:
            allowed = permitted_values(role)
            # Also test each constituent in a set, not just the joined representation.
            allowed |= {floor(a) for m in role.get('members', []) for a in m['aliases']}
            all_views = allowed | set(map(floor, role['derived_alternatives'] + role['imprecise_alternatives']))
            proofs = [p for group in role['proof_sets'] for p in group]
            if case['format'] == 'json':
                data = json.loads(raw['source_text'])
                for i, record in enumerate(data['records']):
                    for j, value in enumerate(record.get('cells', [])):
                        checked += 1
                        p = f'/records/{i}/cells/{j}'
                        exact = floor(value) in all_views
                        diagnostic = (bool(diagnostic_key(value, role)) and
                            diagnostic_key(value, role) in {diagnostic_key(v, role) for v in allowed})
                        if (exact or diagnostic) and not any(x.get('pointer') == p for x in proofs):
                            collisions.append({'role': role['id'], 'location': p, 'value_string': value,
                                'kind': 'exact_wrong_location' if exact else 'diagnostic_only_collision',
                                'primary_proof_accepts': False})
                    # A prose repetition in the table document cannot prove a different cell.
                    text = record.get('text', '')
                    for value in sorted(all_views):
                        for a, b in floor_occurrences(text, value):
                            collisions.append({'role': role['id'], 'location': f'/records/{i}/text',
                                'codepoint_span': [a, b], 'value_string': value,
                                'kind': 'narrative_occurrence_requires_separate_proof', 'primary_proof_accepts': False})
            else:
                text = raw['source_text']; checked = len(text.encode('utf-8'))
                for value in sorted(all_views):
                    for a, b in floor_occurrences(text, value):
                        loc = span(raw, a, b)
                        # A combined two-code phrase overlaps both correct anchors;
                        # its article/connector is not a collision with another fact.
                        if not any(p['utf8_start'] < loc['utf8_end'] and p['utf8_end'] > loc['utf8_start'] for p in proofs):
                            collisions.append({'role': role['id'], **loc, 'value_string': value,
                                'kind': 'outside_annotated_support_review_lead', 'primary_proof_accepts': False})
        results.append({'number': case['number'], 'format': case['format'],
                        'checked': checked, 'unit': 'table_cells' if case['format'] == 'json' else 'source_bytes',
                        'has_gold_roles': bool(case['roles']), 'collisions': collisions})
    return {'date': '2026-10-16', 'approved_for_execution': False,
            'scope': 'all 120 development cases; all 37 table cases and 83 text/PDF cases',
            'method': 'finite primary/derived/imprecise aliases vs all cells and whole-token text occurrences under the whitespace floor; wrong locations never added to proofs',
            'limitation': 'Literal occurrence audit detects candidate collisions, not every semantic paraphrase or wrong fact within an annotated paragraph. Negative cases have no positive aliases to compare.',
            'cases': results}


def verify_candidate(gold, audit):
    validate_gold(gold)
    by_id = {c['id']: c for c in audit['cases']}
    checks = {'source_documents': 0, 'proof_locations': 0, 'table_value_bindings': 0,
              'unit_period_context_bindings': 0}
    for c in gold['cases']:
        raw = by_id[c['case_id']]
        assert c['document_sha256'] == raw['document_sha256']
        text = raw['source_text'].encode('utf-8')
        assert c['source_text_sha256'] == hashlib.sha256(text).hexdigest()
        checks['source_documents'] += 1
        data = json.loads(raw['source_text']) if c['format'] == 'json' else None
        for role in c['roles']:
            for group in role['proof_sets'] + role['derived_proof_sets']:
                for p in group:
                    assert p['document_sha256'] == c['document_sha256']
                    if 'pointer' in p:
                        assert isinstance(pointer(data, p['pointer']), str)
                    else:
                        assert 0 <= p['utf8_start'] < p['utf8_end'] <= len(text)
                        text[p['utf8_start']:p['utf8_end']].decode('utf-8')
                    checks['proof_locations'] += 1
            if data is not None:
                assert any(pointer(data, p['pointer']) == role['value_string']
                           for group in role['proof_sets'] for p in group)
                checks['table_value_bindings'] += 1
                for context in role['scale']['source_context']:
                    assert pointer(data, context['pointer']) == context['value_string']
                    checks['unit_period_context_bindings'] += 1
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--reports', type=Path, default=Path('docs/reports'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit, count = verified_input(args.audit, args.proposal)
    gold = build(audit, args.reports)
    gold['source_verification'] = verify_candidate(gold, audit)
    gold['verified_development_members'] = count
    gold['source_inputs'] = {str(args.reports / name): digest(args.reports / name) for name in (
        't39-d1-adjudication-v1.1.json', 't39-d2-adjudication-v1.1.json', 't39-d3-tiers-v1.1.json')}
    outputs = {'t39-d4-gold-candidate-v1.1.json': gold,
               't39-d4-collision-audit-v1.1.json': collision_audit(gold, audit)}
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in outputs):
        raise ValueError('Output exists: version artifacts, never overwrite them')
    for name, value in outputs.items():
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'development_members_verified': count, 'cases': len(gold['cases']),
                      'model_runs': 0, 'approved_for_execution': False}))


if __name__ == '__main__':
    main()
