"""Apply accepted six-case decisions as a new, offline development candidate."""
import argparse
from collections import Counter
from copy import deepcopy
import itertools
from pathlib import Path

from .audit_labels import verified_input
from .build_typed_candidate import collision_audit, verify_candidate
from .families import digest, encoded, handoff, load, save, summary
from .pilot_controls import audit_pairing
from .typed_facts import validate_gold

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'docs/reports'
POLICY = ROOT / 'evals/measurement/gold-review-v1.5.md'
PREDECESSOR = REPORTS / 't39-d7-review-manifest-v1.4.json'
PREDECESSOR_SHA = '65ddc1d1d3c76b5c0f83e74d4f46b572261e9840dd502ee72df38956aee418fb'
SPANS = {10: [(0, 309), (310, 453)], 34: [(25035, 25700)],
         47: [(27060, 27204)], 53: [(8485, 8537), (8538, 8655)],
         71: [(0, 224)], 107: [(5909, 6112), (6415, 6672)]}
PENDING_107 = 'case 107 replacement activation awaits two independent source reviews'


def verify_previous():
    if digest(PREDECESSOR.read_bytes()) != PREDECESSOR_SHA:
        raise ValueError('Previous review manifest changed')
    latest = load(PREDECESSOR)
    manifests = [latest]
    for path, expected in latest['predecessors'].items():
        if digest((ROOT / path).read_bytes()) != expected:
            raise ValueError('Previous review manifest changed')
        manifests.append(load(ROOT / path))
    for manifest in manifests:
        for entry in manifest['artifacts']:
            if digest((ROOT / entry['path']).read_bytes()) != entry['sha256']:
                raise ValueError('Previously frozen artifact changed')
    return sum(len(m['artifacts']) for m in manifests)


def build(audit, base_gold, base_ledger, base_tiers):
    # Also validates all source/question/format/hash identities before mutation.
    audit_pairing(audit, base_gold, base_ledger, base_tiers)
    gold, ledger, tiers = map(deepcopy, (base_gold, base_ledger, base_tiers))
    sources = {c['n']: c for c in audit['cases']}
    cases = {c['number']: c for c in gold['cases']}
    decisions = []
    for n, ranges in SPANS.items():
        c = cases[n]
        raw = sources[n]['source_text'].encode('utf-8')
        evidence = [{'document_sha256': c['document_sha256'], 'utf8_start': a,
                     'utf8_end': b, 'quote': raw[a:b].decode('utf-8')} for a, b in ranges]
        proofs = [{k: v for k, v in e.items() if k != 'quote'} for e in evidence]
        previous = deepcopy(c)
        role = c['roles'][0]
        if n == 10:
            names = ['Bukhara', 'Besh Baliq', 'Almaliq', 'Samarqand']
            variants = set()
            for order in itertools.permutations(names):
                variants.add(', '.join(order[:-1]) + ' and ' + order[-1])
                variants.add(', '.join(order[:-1]) + ', and ' + order[-1])
            canonical = 'Bukhara, Besh Baliq, Almaliq and Samarqand'
            role.update(value_string=canonical, allowed_alternatives=sorted(variants - {canonical}),
                        unordered=True, separators=[',', ', ', ' / ', '; ', ' and '],
                        proof_sets=[proofs], qualifier='Complete set of four named destinations; order irrelevant.',
                        members=[{'id': f'place_{i+1}', 'aliases': [name],
                                  'proof_sets': [[proofs[0 if i == 0 else 1]]]} for i, name in enumerate(names)])
        elif n == 34:
            original = role['value_string']
            role.update(value_string='Always answer YES—the baseline used in batches 2 and 3.',
                        allowed_alternatives=[original, 'always YES (in batches 2 and 3)',
                                              'always YES (in batch 2 and 3)'],
                        period='batches 2 and 3', qualifier='Always-YES baseline; not batch-4 entailment.',
                        proof_sets=[proofs])
        elif n == 47:
            role.update(allowed_alternatives=[], proof_sets=[proofs])
        elif n == 53:
            role.update(value_string='car model, ignoring the model year',
                        allowed_alternatives=['car model', 'model of the car', 'model', 'the model'],
                        qualifier='Model identity without year; not manufacturer or an example vehicle.',
                        proof_sets=[proofs])
        elif n == 71:
            c['tier'] = 'stress_adjudication'
        c['pending_decisions'] = [PENDING_107] if n == 107 else []
        decisions.append({'number': n, 'case_id': c['case_id'], 'question': c['question'],
                          'source_text_sha256': c['source_text_sha256'], 'evidence': evidence,
                          'status': 'accepted_direction_pending_activation_reviews' if n == 107 else 'applied_to_candidate',
                          'before': previous, 'after': deepcopy(c)})
    gold.update(version='1.5-user-adjudicated-candidate', date='2026-10-17',
                pending_global_decisions=['case 107 activation reviews', 'family/custodian reconciliation',
                    'runtime format/proof/control integration', 'actual table budget checks', 'final execution freeze'])
    validate_gold(gold)
    gold['source_verification'] = verify_candidate(gold, audit)
    gold['source_inputs'].update({
        'docs/reports/t39-d4-gold-candidate-v1.1.json': digest((REPORTS / 't39-d4-gold-candidate-v1.1.json').read_bytes()),
        'evals/measurement/gold-review-v1.5.md': digest(POLICY.read_bytes())})
    for row in ledger['cases']:
        c = cases[row['number']]
        row.update(tier=c['tier'], pending_decisions=c['pending_decisions'])
    ledger.update(version='t39-family-ledger-v1.5', summary=summary(ledger['cases']))
    ledger['predecessor_inputs'] = ledger.pop('inputs')
    ledger['inputs'] = {'gold_sha256': digest(encoded(gold)),
                        'source_audit_canonical_sha256': digest(encoded(audit)),
                        'builder_sha256': digest(Path(__file__).read_bytes()),
                        'table_registry_sha256': ledger['predecessor_inputs']['table_registry_sha256'],
                        'verified_development_members': len(audit['verified_development_members'])}
    ledger['policy_hashes'].update({'gold-review-v1.5.md': digest(POLICY.read_bytes()),
                                    'gold-candidate-v1.5.json': digest(encoded(gold))})
    for name in ('pilot-scope-v1.4.md', 'closed-book-v1.4.txt', 'closed-book-v1.4.schema.json'):
        ledger['policy_hashes'][name] = digest((POLICY.parent / name).read_bytes())
    # The old D3 object has historical summary fields; expose a new minimal roster.
    excluded = deepcopy(tiers['cases'])
    c = cases[71]
    excluded.append({'number': 71, 'case_id': c['case_id'], 'question': c['question'],
                     'document': c['document'], 'document_sha256': c['document_sha256'],
                     'tier': c['tier'], 'primary_reason': 'premise_or_entity_ambiguous',
                     'secondary_tags': ['agreement_vs_punishment'],
                     'finding': 'Question calls the offered plea agreement a type of punishment.',
                     'original_expected': c['original_expected']})
    tiers = {'version': 't39-tiers-v1.5', 'approved_for_execution': False,
             'cases': sorted(excluded, key=lambda c: c['number']),
             'roster': [{'number': c['number'], 'case_id': c['case_id'], 'tier': c['tier']} for c in gold['cases']],
             'counts': dict(sorted(Counter(c['tier'] for c in gold['cases']).items()))}
    packet = handoff(ledger)  # Existing strict D6 wire schema; new content/hash.
    pilot = audit_pairing(audit, gold, ledger, tiers)
    pilot['version'] = 'pilot-audit-v1.5'
    pilot['input_sha256'] = {'gold': digest(encoded(gold)), 'ledger': digest(encoded(ledger)),
                             'tiers': digest(encoded(tiers)), 'policy': digest(POLICY.read_bytes())}
    adjudication = {'version': '1.5', 'date': '2026-10-17', 'user_acceptance': 'recommendationa accepted',
                    'review_kind': 'user_adjudication_after_internal_source_review',
                    'independent_review_acceptance': False, 'approved_for_execution': False,
                    'model_outputs_used': False, 'sealed_content_opened': False,
                    'decisions': decisions, 'proposed_107_definition': decisions[-1]['evidence'][-1]['quote'],
                    'case_107_activation': 'pending_two_independent_source_reviews'}
    collisions = collision_audit({'cases': [c for c in gold['cases'] if c['number'] in (10, 34, 47, 53)]}, audit)
    collisions.update(date='2026-10-17', scope='Four revised gold roles only; unchanged tables/cases retain their earlier collision audits.')
    return {'gold.json': gold, 'family-ledger.json': ledger, 'tiers.json': tiers,
            'custodian-input.json': packet, 'pilot-audit.json': pilot, 'adjudication.json': adjudication,
            'collision-audit.json': collisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frozen_count = verify_previous()
    audit, members = verified_input(args.audit, args.proposal)
    result = build(audit, load(REPORTS / 't39-d4-gold-candidate-v1.1.json'),
                   load(REPORTS / 't39-d6-family-ledger-v1.3.json'),
                   load(REPORTS / 't39-d3-tiers-v1.1.json'))
    receipt = load(ROOT / 'docs/reviews/t39-d6-custodian-receipt-template-v1.3.json')
    receipt.update(handoff_sha256=digest(encoded(result['custodian-input.json'])),
                   policy_hashes=result['custodian-input.json']['policy_hashes'])
    result['custodian-receipt-template.json'] = receipt
    result['build.json'] = {'version': '1.5', 'approved_for_execution': False,
                            'verified_development_members': members, 'frozen_artifact_entries_verified': frozen_count,
                            'predecessor_sha256': PREDECESSOR_SHA, 'source_audit_sha256': digest(args.audit.read_bytes()),
                            'builder_sha256': digest(Path(__file__).read_bytes()), 'policy_sha256': digest(POLICY.read_bytes()),
                            'model_calls': 0, 'sealed_opened': False}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in result.items():
        save(args.output / name, value)
    print(encoded({'tiers': result['tiers.json']['counts'],
                   'primary_family_clusters': {k: v for k, v in result['family-ledger.json']['summary']['primary_clusters'].items()
                                               if k != 'memberships'},
                   'verified_members': members, 'prior_frozen_entries': frozen_count}).decode())


if __name__ == '__main__':
    main()
