"""Synthetic review records only; never opens the candidate package."""
import copy
import unittest

from .families import digest, encoded, validate_receipt
from .internal_custody import (MANIFEST, PRIMARY, STRESS, VERSION, aggregate, reconcile)


def fixture():
    ledger = {'sealed_content_opened': True, 'implementation_exposed_candidates': 60,
        'cases': [dict(number=1, case_id='dev', family_key='company:example',
        source_identity='Public development company', confidence='A', format='json',
        tier=PRIMARY, label='supported', original_label='supported')]}
    rows = []
    for i in range(60):
        rows.append(dict(case_id=f'PRIVATE-ID-{i}', question='PRIVATE QUESTION',
            format='txt', label='supported', confidence='B', family_key='paper:example',
            tier=PRIMARY, primary_reason='primary', source_only_reviewed=True,
            d4_checked=True, pending_decisions=[], document_sha256='source',
            gold=dict(case_id=f'PRIVATE-ID-{i}', document_sha256='source', roles=[dict(
                value_string='PRIVATE GOLD', source_type='string', allowed_alternatives=[],
                proof_sets=[[{'private': 'proof'}]])]),
            development_family_matches=[], lineage_status='upstream_identity_checked'))
    audit = dict(version=VERSION, proposal_manifest_sha256=MANIFEST,
        development_ledger_sha256=digest(encoded(ledger)), independent_review=False,
        blind_holdout=False, candidate_model_outputs_used=False, original_holdout_accessed=False,
        implementation_exposed=True, cases=rows, unresolved_development_families=[])
    return audit, ledger


class InternalCustodyTests(unittest.TestCase):
    def test_public_projection_omits_private_values(self):
        a, l = fixture()
        r = aggregate(a, l)
        self.assertNotIn('PRIVATE', encoded(r).decode())
        self.assertEqual(r['implementation_exposed_candidates'], 60)
        self.assertFalse(r['blind_holdout'])
        self.assertFalse(r['approved_for_execution'])
        self.assertEqual(r['primary_cluster_sizes'], {60: 1})

    def test_independence_and_exposure_cannot_be_forged(self):
        for key in ('independent_review', 'blind_holdout', 'candidate_model_outputs_used',
                    'original_holdout_accessed', 'implementation_exposed'):
            with self.subTest(key=key):
                a,l=fixture();a[key]=not a[key]
                with self.assertRaises(ValueError): aggregate(a,l)

    def test_duplicate_missing_or_wrong_split_is_refused(self):
        a,l=fixture();a['cases'][1]['case_id']=a['cases'][0]['case_id']
        with self.assertRaises(ValueError): aggregate(a,l)
        a,l=fixture();a['cases'].pop()
        with self.assertRaises(ValueError): aggregate(a,l)
        a,l=fixture();a['proposal_manifest_sha256']='other-holdout'
        with self.assertRaises(ValueError): aggregate(a,l)

    def test_incomplete_review_does_not_produce_receipt(self):
        for name,value in [('d4_checked',False),('source_only_reviewed',False),
                           ('pending_decisions',['unresolved'])]:
            a,l=fixture();a['cases'][0][name]=value
            with self.assertRaises(ValueError): aggregate(a,l)

    def test_table_review_requires_coordinate_and_annotation(self):
        a,l=fixture();a['cases'][0].update(format='json',d5_checked=False)
        with self.assertRaises(ValueError): aggregate(a,l)
        a['cases'][0].update(d5_checked=True,annotation_sha256='a',coordinate_proofs=[{}])
        r=aggregate(a,l)
        self.assertEqual(r['d5_table_cases_checked'],1)

    def test_stress_not_counted_as_primary(self):
        a,l=fixture();a['cases'][0].update(tier=STRESS,primary_reason='scope_or_period_ambiguous')
        r=aggregate(a,l)
        self.assertEqual(r['d3_counts']['primary'],59)
        self.assertEqual(r['d3_counts']['scope_or_period_ambiguous'],1)

    def test_known_collision_cannot_be_hidden(self):
        a,l=fixture();a['cases'][0].update(family_key='company:example',confidence='A')
        with self.assertRaises(ValueError): aggregate(a,l)
        a['cases'][0]['development_family_matches']=['company:example']
        r=aggregate(a,l);o=reconcile(r,l)
        self.assertEqual(o['excluded_development'][0]['case_id'],'dev')
        self.assertEqual(o['remaining']['primary_cases'],0)
        self.assertEqual(o['certified_primary_cases'],0)
        self.assertEqual(l['cases'][0]['tier'],PRIMARY)

    def test_candidate_identity_cannot_certify_collision(self):
        a,l=fixture();a['cases'][0].update(confidence='C',development_family_matches=['company:example'])
        with self.assertRaises(ValueError): aggregate(a,l)

    def test_ledger_rebinding_or_execution_approval_is_rejected(self):
        a,l=fixture();r=aggregate(a,l)
        bad=copy.deepcopy(l);bad['cases'][0]['label']='negative'
        with self.assertRaises(ValueError): reconcile(r,bad)
        r['approved_for_execution']=True
        with self.assertRaises(ValueError): reconcile(r,l)

    def test_old_independent_receipt_validator_stays_closed(self):
        a,l=fixture();r=aggregate(a,l)
        with self.assertRaises(ValueError): validate_receipt(r,{})

    def test_current_ledger_cannot_claim_unopened_candidates(self):
        a,l=fixture();l['sealed_content_opened']=False
        a['development_ledger_sha256']=digest(encoded(l))
        with self.assertRaises(ValueError): aggregate(a,l)

    def test_reconciliation_cannot_launder_review_scope(self):
        for key,value in [('proposal_manifest_sha256','other'),
                          ('implementation_exposed_candidates',0),
                          ('original_holdout_accessed',True),
                          ('candidate_model_outputs_used',True),
                          ('whole_split_separation_verified',True)]:
            with self.subTest(key=key):
                a,l=fixture();r=aggregate(a,l);r[key]=value
                with self.assertRaises(ValueError): reconcile(r,l)


if __name__ == '__main__':
    unittest.main()
