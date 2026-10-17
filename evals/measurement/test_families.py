"""Offline source-family, disclosure-boundary and statistical contract checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from . import families as f


def row(key, family='company:example', confidence='A', fmt='json', tier=f.PRIMARY):
    return {'case_id': key, 'number': int(key), 'family_key': family, 'confidence': confidence,
            'family_type': 'company' if family.startswith('company:') else 'article',
            'source_identity': 'Example', 'aliases': ['Old Example'], 'format': fmt,
            'tier': tier, 'label': 'supported', 'pending_decisions': []}


def ledger():
    return {'cases': [row('1'), row('2'), row('3', tier='stress_adjudication'),
                      row('4', 'article:wikipedia:example', 'B', 'txt'),
                      row('5', 'article:wikipedia:example', 'B', 'pdf')],
            'policy_hashes': {'families-v1.3.md': '1' * 64}}


def receipt(packet):
    return {'version': 't39-d6-custodian-receipt-v1.3',
            'handoff_sha256': f.digest(f.encoded(packet)), 'policy_hashes': packet['policy_hashes'],
            'custodian': packet['custodian'], 'candidate_count': 60,
            'candidate_by_format': {'txt': 20, 'pdf': 20, 'json': 20},
            'confidence_counts': {'A': 20, 'B': 40, 'C': 0, 'U': 0},
            'd3_counts': {'primary': 50, **{d: (10 if i == 0 else 0) for i, d in enumerate(f.DEFECTS)}},
            'd4_records_checked': 60, 'd5_tables_checked': 20,
            'primary_by_format_label': {'txt': {'supported': 10, 'negative': 10},
                                       'pdf': {'supported': 15, 'negative': 5},
                                       'json': {'supported': 10, 'negative': 0}},
            'established_primary_family_count': 25,
            'colliding_development_families': [], 'unresolved_development_families': [],
            'colliding_sealed_cases': 0, 'colliding_sealed_families': 0,
            'source_only_screening': True, 'lineage_review_complete': True,
            'private_audit_retained': True, 'model_outputs_used': False}


class FamilyTests(unittest.TestCase):
    def test_company_year_is_not_a_family(self):
        rs = [row('1'), row('2')]
        rs[0]['company_year_key'] = 'company:example:FY2018'
        rs[1]['company_year_key'] = 'company:example:FY2019'
        self.assertEqual(f.clusters(rs)['memberships'], {'company:example': 2})

    def test_parent_rename_keys_and_mixed_format_article_are_grouped(self):
        data = ledger()
        data['cases'][1]['source_identity'] = 'Renamed Example Subsidiary'
        packet = f.handoff(data)
        self.assertEqual(len(packet['families']), 2)
        self.assertEqual(packet['families'][0]['formats'], ['pdf', 'txt'])
        self.assertEqual(packet['families'][1]['exposed_cases'], 3)
        self.assertIn('Renamed Example Subsidiary', packet['families'][1]['names_and_aliases'])

    def test_handoff_has_no_questions_answers_case_ids_or_document_hashes(self):
        data = ledger()
        for r in data['cases']:
            r.update(question='PRIVATE QUESTION', answer='GOLD', document_sha256='SECRET')
        text = json.dumps(f.handoff(data))
        for forbidden in ('PRIVATE', 'GOLD', 'SECRET', 'case_id', 'question', 'document_sha256'):
            self.assertNotIn(forbidden, text)

    def test_unknowns_do_not_become_independent_families(self):
        stats = f.clusters([row('1'), row('2', 'company:guess', 'C'), row('3', '', 'U')])
        self.assertEqual(stats['families'], 1)
        self.assertEqual(stats['candidate_or_unknown_cases'], 2)

    def test_receipt_rejects_sealed_fields_and_unknown_keys_without_echoing(self):
        packet = f.handoff(ledger())
        for key in ('sealed_ids', 'private_audit_path', 'notes', 'sealed_hashes'):
            r = receipt(packet)
            r[key] = 'SEALED_SECRET'
            with self.assertRaises(ValueError) as ctx:
                f.validate_receipt(r, packet)
            self.assertNotIn('SEALED_SECRET', str(ctx.exception))
        r = receipt(packet)
        r['colliding_development_families'] = ['SEALED_SECRET']
        with self.assertRaises(ValueError):
            f.validate_receipt(r, packet)

    def test_identity_tampering_rejected(self):
        packet = f.handoff(ledger())
        for field in ('handoff_sha256', 'policy_hashes', 'custodian'):
            r = receipt(packet)
            r[field] = 'changed'
            with self.assertRaises(ValueError):
                f.validate_receipt(r, packet)

    def test_all_screening_partitions_and_requirements_are_checked(self):
        packet = f.handoff(ledger())
        mutations = [lambda r: r.update(d4_records_checked=59),
                     lambda r: r.update(d5_tables_checked=19),
                     lambda r: r.update(source_only_screening=False),
                     lambda r: r.update(lineage_review_complete=False),
                     lambda r: r.update(private_audit_retained=False),
                     lambda r: r.update(model_outputs_used=True),
                     lambda r: r['d3_counts'].update(primary=60),
                     lambda r: r['confidence_counts'].update(U=1),
                     lambda r: r['candidate_by_format'].update(txt=True),
                     lambda r: r['primary_by_format_label']['json'].update(negative=11),
                     lambda r: r.update(colliding_sealed_cases=1),
                     lambda r: r.update(established_primary_family_count=51)]
        for mutate in mutations:
            r = receipt(packet)
            mutate(r)
            with self.assertRaises(ValueError):
                f.validate_receipt(r, packet)

    def test_collision_moves_whole_development_family_and_keeps_prior_tiers(self):
        data = ledger()
        original = deepcopy(data)
        packet = f.handoff(data)
        r = receipt(packet)
        r.update(colliding_development_families=['company:example'],
                 colliding_sealed_cases=2, colliding_sealed_families=1)
        result = f.reconcile(data, packet, r)
        self.assertEqual(data, original)
        self.assertEqual([x['case_id'] for x in result['collision_diagnostics']], ['1', '2', '3'])
        self.assertEqual(result['collision_diagnostics'][2]['prior_tier'], 'stress_adjudication')
        self.assertEqual(result['retained_primary'], ['4', '5'])
        self.assertEqual(result['primary_collision_losses']['json']['supported'], 2)
        self.assertEqual(result['achieved_provisional_quotas']['total_primary'], 52)

    def test_unknown_sealed_prevents_full_claim(self):
        data = ledger()
        packet = f.handoff(data)
        r = receipt(packet)
        r['confidence_counts'].update(A=19, U=1)
        result = f.reconcile(data, packet, r)
        self.assertEqual(result['cross_split_verified_cases'], 0)
        self.assertFalse(result['whole_benchmark_independence'])
        self.assertIn('portion_only', result['claim'])

    def test_unresolved_development_and_candidate_cases_cannot_be_certified(self):
        data = ledger()
        data['cases'][0]['confidence'] = 'C'
        packet = f.handoff(data)
        r = receipt(packet)
        r['unresolved_development_families'] = ['article:wikipedia:example']
        result = f.reconcile(data, packet, r)
        self.assertEqual(result['retained_primary'], ['2'])
        self.assertEqual(result['cross_split_verified_cases'], 1)
        self.assertFalse(result['whole_benchmark_independence'])

    def test_mixed_format_clusters_counts_are_not_additive(self):
        stats = f.summary(ledger()['cases'])
        self.assertEqual(stats['primary_clusters']['families'], 2)
        self.assertEqual(sum(s['families'] for s in stats['primary_clusters_by_format'].values()), 3)
        self.assertIsNone(stats['collisions'])

    def test_bootstrap_resamples_families_with_all_members(self):
        rs = [dict(row(str(i), 'company:a'), correct=True) for i in range(1, 10)]
        rs.append(dict(row('10', 'company:b'), correct=False))
        stats = f.cluster_interval(rs, resamples=1000)
        self.assertEqual(stats['estimate'], .9)
        self.assertEqual(stats['ci95'], [0, 1])
        self.assertEqual(stats, f.cluster_interval(list(reversed(rs)), resamples=1000))
        with self.assertRaises(ValueError):
            f.cluster_interval(rs + rs[:1])
        rs[0]['confidence'] = 'C'
        with self.assertRaises(ValueError):
            f.cluster_interval(rs)

    def test_one_family_has_no_interval(self):
        stats = f.cluster_interval([dict(row('1'), correct=True)])
        self.assertIsNone(stats['ci95'])

    def test_reserve_strata_boundaries_and_determinism(self):
        self.assertEqual([f.size_band(n) for n in (4096, 4097, 16384, 16385)],
                         ['small', 'medium', 'medium', 'large'])
        rs = [dict(row(str(i)), split='development_reserve', noncollision_checked=True,
                   same_defect_screen_passed=True, previously_inspected=False,
                   source='tatqa', original_label='supported', structure='table',
                   question_type='numeric', supplied_text_bytes=4096) for i in range(1, 5)]
        stratum = ['tatqa', 'supported', 'json', 'table', 'numeric', 'small']
        self.assertEqual(f.reserve_order(rs, stratum, set()),
                         f.reserve_order(list(reversed(rs)), stratum, set()))
        self.assertEqual(f.reserve_order(rs, stratum[:-1] + ['large'], set()), [])
        for field, value in [('split', 'sealed'), ('confidence', 'C'),
                             ('noncollision_checked', False), ('same_defect_screen_passed', False),
                             ('previously_inspected', True)]:
            changed = deepcopy(rs)
            changed[0][field] = value
            with self.assertRaises(ValueError):
                f.reserve_order(changed, stratum, set())
        with self.assertRaises(ValueError):
            f.reserve_order(rs, stratum, {'company:example'})

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'receipt.json'
            p.write_text('{"candidate_count":60,"candidate_count":1}', encoding='utf-8')
            with self.assertRaises(ValueError):
                f.load(p)

    def test_builder_binds_sources_and_collapses_paper_versions(self):
        audit = {'opened_proposal_split': 'development', 'manifest_sha256': '0' * 64, 'cases': []}
        gold = {'cases': []}
        for n, version in [(1, 'v1'), (2, 'v2')]:
            sha = f.digest(b'Source')
            request = {'split': 'development', 'source': 'qasper', 'structure': 'prose',
                       'format': 'txt', 'document': f'paper-{n}.txt',
                       'family': 'qasper:1905.07791' + version}
            audit['cases'].append({'n': n, 'id': str(n), 'request': request,
                                   'label': {'split': 'development', 'original_id': str(n)},
                                   'document_sha256': sha, 'source_text': 'Source'})
            gold['cases'].append({'number': n, 'case_id': str(n), 'document': request['document'],
                                  'document_sha256': sha, 'source_text_sha256': sha,
                                  'format': 'txt', 'tier': f.PRIMARY, 'pending_decisions': [],
                                  'expected': 'supported', 'original_expected': 'supported'})
        result = f.build_ledger(audit, gold, {'tables': []}, {'qasper-dev.json': {}})
        self.assertEqual(result['summary']['primary_clusters']['families'], 1)
        audit['cases'][0]['source_text'] = 'Changed'
        with self.assertRaises(ValueError):
            f.build_ledger(audit, gold, {'tables': []}, {'qasper-dev.json': {}})
        audit['cases'][0]['source_text'] = 'Source'
        audit['cases'][0]['label']['split'] = 'sealed'
        with self.assertRaises(ValueError):
            f.build_ledger(audit, gold, {'tables': []}, {'qasper-dev.json': {}})

    def test_every_table_case_has_a_single_trace_with_real_local_clues(self):
        registry = f.load(f.ROOT / 'evals/measurement/table-families-v1.3.json')
        gold = f.load(f.ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json')
        expected = {c['number']: c for c in gold['cases'] if c['format'] == 'json'}
        seen = []
        for trace in registry['tables']:
            for n in trace['cases']:
                seen.append(n)
                path = f.ROOT / 'evals/measurement/table-sources-v1.2' / expected[n]['document']
                raw = path.read_bytes()
                self.assertEqual(f.digest(raw), expected[n]['document_sha256'])
                source = json.dumps(json.loads(raw), ensure_ascii=False)
                for clue in trace['needles']:
                    self.assertIn(clue, source)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(expected))
        self.assertEqual(len(registry['tables']), 32)


if __name__ == '__main__':
    unittest.main()
