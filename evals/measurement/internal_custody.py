"""Aggregate delegated source review without publishing candidate content.

This is not the independent-custodian receipt format. No model or network calls.
Private inputs remain private; outputs use a fixed aggregate allowlist.
"""
import argparse
from collections import Counter
from pathlib import Path

from .families import (DEFECTS, FORMATS, LABELS, PRIMARY, counts, digest, encoded,
                       load, save, summary)
from .typed_facts import permitted_values

VERSION = 't39-internal-custody-v1.7'
MANIFEST = '3e3a1c37fd3a9d3e216eaaebcf0d41dc9adad718f24a9d2fa6c6a77cb33452b1'
DERIVED = 'derived_inference'
STRESS = 'stress_adjudication'


def require(condition, message):
    if not condition:
        # Never include private values in exceptions.
        raise ValueError(message)


def validate_private(audit, ledger):
    require(audit['version'] == VERSION, 'Wrong internal review version')
    require(audit['proposal_manifest_sha256'] == MANIFEST, 'Wrong proposal')
    require(audit['development_ledger_sha256'] == digest(encoded(ledger)),
            'Development ledger binding changed')
    for name in ('independent_review', 'blind_holdout', 'candidate_model_outputs_used',
                 'original_holdout_accessed'):
        require(audit[name] is False, 'Review provenance must remain internal and source-only')
    require(audit['implementation_exposed'] is True, 'Exposure must be explicit')
    require(ledger['sealed_content_opened'] is True and
            ledger['implementation_exposed_candidates'] == 60,
            'Current ledger must record candidate exposure')
    rows = audit['cases']
    require(len(rows) == 60 and len({r['case_id'] for r in rows}) == 60,
            'Exactly 60 unique candidates required')
    dev_keys = {r['family_key'] for r in ledger['cases'] if r['family_key']}
    require(set(audit['unresolved_development_families']) <= dev_keys,
            'Unknown development family')
    for row in rows:
        require(row['format'] in FORMATS and row['label'] in LABELS, 'Invalid case class')
        require(row['confidence'] in ('A', 'B', 'C', 'U'), 'Invalid confidence')
        require(row['confidence'] == 'U' or bool(row['family_key']), 'Family key missing')
        reason = row['primary_reason']
        require(reason in ('primary', *DEFECTS), 'Invalid defect')
        expected_tier = PRIMARY if reason == 'primary' else (
            DERIVED if reason == 'requires_derivation' else STRESS)
        require(row['tier'] == expected_tier, 'Defect/tier mismatch')
        require(row['source_only_reviewed'] is True and row['d4_checked'] is True,
                'Incomplete source/fact review')
        require(row['pending_decisions'] == [], 'Unresolved gold decision')
        require(row['gold']['case_id'] == row['case_id'] and
                row['gold']['document_sha256'] == row['document_sha256'],
                'Gold/source identity mismatch')
        if row['label'] == 'supported':
            require(bool(row['gold']['roles']), 'Supported case requires fact roles')
            for role in row['gold']['roles']:
                require(role['source_type'] == 'string' and bool(permitted_values(role)),
                        'Missing finite string values')
                require(bool(role['proof_sets']), 'Supported case requires source proofs')
        if row['format'] == 'json':
            require(row['d5_checked'] is True and row['annotation_sha256'] and
                    row['coordinate_proofs'], 'Incomplete table review')
        matches = row['development_family_matches']
        require(len(set(matches)) == len(matches) and set(matches) <= dev_keys,
                'Invalid development collision keys')
        require(not matches or row['confidence'] in ('A', 'B'),
                'Candidate identity cannot certify collision')
        if row['family_key'] in dev_keys and row['confidence'] in ('A', 'B'):
            require(row['family_key'] in matches, 'Known identity collision omitted')
        require(row['lineage_status'] in ('identity_collision', 'upstream_identity_checked',
                                         'unresolved_lineage'), 'Invalid lineage status')
    return rows


def aggregate(audit, ledger):
    rows = validate_private(audit, ledger)
    primary = [r for r in rows if r['tier'] == PRIMARY]
    collisions = sorted({key for r in rows for key in r['development_family_matches']})
    matched = [r for r in rows if r['development_family_matches']]
    partition = {k: sum(r['primary_reason'] == k for r in rows)
                 for k in ('primary', *DEFECTS)}
    return {
        'version': VERSION,
        'proposal_manifest_sha256': MANIFEST,
        'development_ledger_sha256': digest(encoded(ledger)),
        'private_audit_sha256': digest(encoded(audit)),
        'review_kind': 'delegated_internal_source_review',
        'independent_review': False, 'blind_holdout': False,
        'implementation_exposed_candidates': len(rows),
        'candidate_model_outputs_used': False, 'original_holdout_accessed': False,
        'approved_for_execution': False,
        'candidate_count': len(rows),
        'candidate_by_format': {f: sum(r['format'] == f for r in rows) for f in FORMATS},
        'confidence_counts': {t: sum(r['confidence'] == t for r in rows) for t in 'ABCU'},
        'd3_counts': partition,
        'd4_records_checked': len(rows),
        'd5_table_cases_checked': sum(r['format'] == 'json' for r in rows),
        'd5_distinct_tables_checked': len({r['annotation_sha256'] for r in rows
                                         if r['format'] == 'json'}),
        'primary_by_format_label': counts(primary),
        'established_primary_family_count': len({r['family_key'] for r in primary
                                                if r['confidence'] in ('A', 'B')}),
        'primary_cluster_sizes': dict(sorted(Counter(Counter(
            r['family_key'] for r in primary if r['confidence'] in ('A', 'B')).values()).items())),
        'colliding_development_families': collisions,
        'colliding_candidate_cases': len(matched),
        'colliding_candidate_families': len({r['family_key'] for r in matched}),
        'unresolved_candidate_lineage_cases': sum(r['lineage_status'] == 'unresolved_lineage'
                                                 for r in rows),
        'unresolved_development_families': sorted(audit['unresolved_development_families']),
        'whole_split_separation_verified': False,
        'source_screening_complete': True,
        'lineage_review_complete': not audit['unresolved_development_families'] and
                                    all(r['lineage_status'] != 'unresolved_lineage' for r in rows),
        'policy_sha256': digest(Path(__file__).with_name('internal-custody-v1.7.md').read_bytes()),
    }


def reconcile(receipt, ledger):
    require(receipt['version'] == VERSION and receipt['independent_review'] is False and
            receipt['blind_holdout'] is False and receipt['approved_for_execution'] is False,
            'Internal receipt cannot confer independent or execution approval')
    require(receipt['proposal_manifest_sha256'] == MANIFEST and
            receipt['implementation_exposed_candidates'] == 60 and
            receipt['original_holdout_accessed'] is False and
            receipt['candidate_model_outputs_used'] is False and
            receipt['whole_split_separation_verified'] is False,
            'Receipt review scope changed')
    require(receipt['development_ledger_sha256'] == digest(encoded(ledger)),
            'Receipt ledger mismatch')
    keys = {r['family_key'] for r in ledger['cases']}
    collision = set(receipt['colliding_development_families'])
    unresolved = set(receipt['unresolved_development_families'])
    require(collision <= keys and unresolved <= keys, 'Unknown development keys')
    lost = [r for r in ledger['cases'] if r['family_key'] in collision]
    retained = [r for r in ledger['cases'] if r['family_key'] not in collision]
    primary = [r for r in retained if r['tier'] == PRIMARY]
    remaining = summary(retained)
    remaining.update(custodian_status='delegated_internal_review_complete',
                     collisions=len(collision))
    return {
        'version': 't39-internal-development-overlay-v1.7',
        'receipt_sha256': digest(encoded(receipt)),
        'development_ledger_sha256': digest(encoded(ledger)),
        'original_development_cases': len(ledger['cases']),
        'colliding_development_families': sorted(collision),
        'excluded_development': [{'case_id': r['case_id'], 'number': r['number'],
             'family_key': r['family_key'], 'prior_tier': r['tier'],
             'original_label': r['original_label'], 'reason': 'family_collision'} for r in lost],
        'primary_losses': counts([r for r in lost if r['tier'] == PRIMARY]),
        'remaining': remaining,
        'remaining_primary_with_unresolved_lineage': sum(r['family_key'] in unresolved
                                                        for r in primary),
        'certified_primary_cases': 0,
        'claim': 'Known identity collisions removed; broader lineage separation remains uncertified. Internal exposed pilot only.',
        'replacements_drawn': 0,
        'source_gold_bytes_changed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-audit', type=Path, required=True)
    parser.add_argument('--development-ledger', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, required=True)
    args = parser.parse_args()
    audit, ledger = load(args.private_audit), load(args.development_ledger)
    receipt = aggregate(audit, ledger)
    overlay = reconcile(receipt, ledger)
    # Validate and compute both before publishing; never overwrite a retained version.
    require(not args.receipt.exists() and not args.overlay.exists(), 'Output already exists')
    save(args.receipt, receipt)
    save(args.overlay, overlay)
    print('Internal aggregate receipt and development overlay written; no execution approval.')


if __name__ == '__main__':
    main()
