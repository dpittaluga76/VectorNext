"""Activate the explicitly approved Level A definition without rewriting v1.5."""
import argparse
from copy import deepcopy
from pathlib import Path

from .audit_labels import verified_input
from .build_gold_review import verify_previous as verify_older
from .build_typed_candidate import collision_audit, verify_candidate
from .families import digest, encoded, handoff, load, save, summary
from .pilot_controls import audit_pairing
from .typed_facts import validate_gold

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/reports/t39-gold-review-v1.5'
POLICY = ROOT / 'evals/measurement/gold-review-v1.6.md'
PREDECESSOR_SHA = 'c4f4d028174f84fb8055f37326991b4d3ae46eda845c275aa30c14cc38303ecc'
SOURCE_SHA = '8b40b29eabc1d84c3a09a9512910aac0ae394df97d6552bd8e30c9f31261a7f2'
CANONICAL = 'any form of non-acceptable language (profanity) or a targeted offense, which can be veiled or direct'
DEFINITION = ('Offensive (OFF): We label a post as offensive if it contains ' + CANONICAL
              + '. This category includes insults, threats, and posts containing profane language or swear words.')
WAIVER = 'Ok, skip the two-reviewer requirement for 107, apply the Level A definition, and continue with T39.'


def verify_previous():
    count = verify_older()
    manifest = BASE / 'manifest.json'
    if digest(manifest.read_bytes()) != PREDECESSOR_SHA:
        raise ValueError('v1.5 manifest changed')
    previous = load(manifest)
    for entry in previous['artifacts']:
        if digest((ROOT / entry['path']).read_bytes()) != entry['sha256']:
            raise ValueError('v1.5 artifact changed: ' + entry['path'])
    return count + len(previous['artifacts'])


def build(audit):
    gold, ledger, tiers = [load(BASE / name) for name in ('gold.json', 'family-ledger.json', 'tiers.json')]
    audit_pairing(audit, gold, ledger, tiers)
    case = next(c for c in gold['cases'] if c['number'] == 107)
    source = next(c for c in audit['cases'] if c['n'] == 107)['source_text'].encode('utf-8')
    if digest(source) != SOURCE_SHA or source[6415:6672].decode('utf-8') != DEFINITION:
        raise ValueError('Level A source bytes changed')
    before = deepcopy(case)
    evidence = [{'document_sha256': SOURCE_SHA, 'utf8_start': a, 'utf8_end': b,
                 'quote': source[a:b].decode('utf-8')} for a, b in ((5909, 6112), (6264, 6341), (6415, 6672))]
    first_sentence = DEFINITION.split('. This category')[0] + '.'
    variants = {CANONICAL + '.', first_sentence, first_sentence.removeprefix('Offensive (OFF): '),
                DEFINITION, DEFINITION.removeprefix('Offensive (OFF): ')}
    case['roles'][0].update(value_string=CANONICAL, allowed_alternatives=sorted(variants),
        qualifier='Level A: profanity/non-acceptable language OR a targeted offense, veiled or direct.',
        proof_sets=[[{k: v for k, v in evidence[-1].items() if k != 'quote'}]])
    case['allowed_field_mappings'] += [{'definition': 'answer'}, {'offensive_language_definition': 'answer'}]
    case['pending_decisions'] = []
    gold.update(version='1.6-user-adjudicated-candidate', date='2026-10-17',
        pending_global_decisions=[p for p in gold['pending_global_decisions'] if p != 'case 107 activation reviews'])
    gold['source_inputs'].update({'docs/reports/t39-gold-review-v1.5/manifest.json': PREDECESSOR_SHA,
                                 'evals/measurement/gold-review-v1.6.md': digest(POLICY.read_bytes())})
    validate_gold(gold)
    gold['source_verification'] = verify_candidate(gold, audit)
    for row in ledger['cases']:
        if row['number'] == 107:
            row['pending_decisions'] = []
    ledger.update(version='t39-family-ledger-v1.6', summary=summary(ledger['cases']))
    ledger['predecessor_v1_5_inputs'] = deepcopy(ledger['inputs'])
    ledger['inputs'].update(gold_sha256=digest(encoded(gold)), builder_sha256=digest(Path(__file__).read_bytes()))
    ledger['policy_hashes'].update({'gold-review-v1.6.md': digest(POLICY.read_bytes()),
                                    'gold-candidate-v1.6.json': digest(encoded(gold))})
    tiers['version'] = 't39-tiers-v1.6'
    packet = handoff(ledger)
    pilot = audit_pairing(audit, gold, ledger, tiers)
    pilot.update(version='pilot-audit-v1.6', input_sha256={
        'gold': digest(encoded(gold)), 'ledger': digest(encoded(ledger)),
        'tiers': digest(encoded(tiers)), 'policy': digest(POLICY.read_bytes())})
    adjudication = {'version': '1.6', 'date': '2026-10-17', 'user_instruction': WAIVER,
        'review_kind': 'user_waiver_after_internal_source_review', 'independent_review_acceptance': False,
        'approved_for_execution': False, 'model_outputs_used': False, 'sealed_content_opened': False,
        'waived_requirement': 'two independent source reviews for case 107',
        'case_107_activation': 'applied_to_candidate', 'evidence': evidence, 'before': before, 'after': deepcopy(case)}
    receipt = load(BASE / 'custodian-receipt-template.json')
    receipt.update(handoff_sha256=digest(encoded(packet)), policy_hashes=packet['policy_hashes'])
    collisions = collision_audit({'cases': [case]}, audit)
    collisions.update(date='2026-10-17', scope='Case 107 only; prior collision audits retained unchanged.')
    return {'gold.json': gold, 'family-ledger.json': ledger, 'tiers.json': tiers,
            'pilot-audit.json': pilot, 'custodian-input.json': packet,
            'custodian-receipt-template.json': receipt, 'adjudication.json': adjudication,
            'collision-audit.json': collisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--proposal', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    count = verify_previous()
    audit, members = verified_input(args.audit, args.proposal)
    result = build(audit)
    result['build.json'] = {'version': '1.6', 'approved_for_execution': False,
        'verified_development_members': members, 'frozen_artifact_entries_verified': count,
        'predecessor_sha256': PREDECESSOR_SHA, 'source_audit_sha256': digest(args.audit.read_bytes()),
        'builder_sha256': digest(Path(__file__).read_bytes()), 'policy_sha256': digest(POLICY.read_bytes()),
        'model_calls': 0, 'sealed_opened': False}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in result.items():
        save(args.output / name, value)
    print(encoded({'tiers': result['tiers.json']['counts'], 'pending_gold_cases': [
        c['number'] for c in result['gold.json']['cases'] if c['pending_decisions']],
        'verified_members': members, 'prior_frozen_entries': count}).decode())


if __name__ == '__main__':
    main()
