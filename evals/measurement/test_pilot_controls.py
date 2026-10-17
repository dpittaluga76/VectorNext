import copy
import json
import unittest

from . import pilot_controls as p


def case(cid='a', expected='supported'):
    return {'case_id': cid, 'tier': p.PRIMARY, 'expected': expected,
            'pending_decisions': [], 'roles': [{'value_string': '$1,264',
            'allowed_alternatives': ['$1,264 thousand']}] if expected == 'supported' else []}


def reply(value, status='answer'):
    return json.dumps({'status': status, 'answer': value})


def audit_inputs():
    audit = {'opened_proposal_split': 'development', 'cases': []}
    gold, ledger = {'cases': []}, {'cases': []}
    for n, fmt, text in ((1, 'pdf', 'A paragraph.\n'), (2, 'txt', 'A paragraph. ')):
        cid = str(n)
        row = {'number': n, 'case_id': cid, 'document': f'{n}.{fmt}',
               'document_sha256': 'a' * 64, 'source_text_sha256': p.sha(text.encode()),
               'format': fmt, 'question': 'Which paragraph?', 'tier': p.PRIMARY,
               'source': 'squad', 'label': 'supported', 'pending_decisions': []}
        gold['cases'].append(copy.deepcopy(row))
        ledger['cases'].append(copy.deepcopy(row))
        audit['cases'].append({'n': n, 'id': cid, 'document_sha256': 'a' * 64,
                              'source_text': text, 'request': {**row, 'split': 'development'}})
    return audit, gold, ledger, {'cases': []}


class ControlTests(unittest.TestCase):
    def test_question_only_messages_do_not_include_gold_hints(self):
        messages = p.control_messages('How many?')
        self.assertEqual(messages[1], {'role': 'user', 'content': 'How many?'})
        self.assertEqual(len(messages), 2)
        for forbidden in ('case_id', 'document', 'history', 'field', 'gold'):
            self.assertNotIn(forbidden, messages[1]['content'])
        with self.assertRaises(ValueError):
            p.control_messages(' ')

    def test_positive_matches_only_declared_strings(self):
        c = case()
        for value in ('$1,264', '$1,264 thousand', '\u00a0$1,264\n'):
            self.assertTrue(p.score_control(c, reply(value))['closed_book_gold_match'])
        for value in ('1264', '$1,264,000', '$12$', 'about $1.26 million'):
            self.assertFalse(p.score_control(c, reply(value))['closed_book_gold_match'])

    def test_numeric_json_is_invalid_not_coerced(self):
        for value in (1264, 9007199254740993, 12.5, None, True, [], {}):
            self.assertEqual(p.score_control(case(), reply(value))['state'], 'unknown')

    def test_large_integer_strings_remain_exact(self):
        c = case()
        c['roles'][0]['value_string'] = '9007199254740993'
        self.assertTrue(p.score_control(c, reply('9007199254740993'))['closed_book_gold_match'])
        self.assertFalse(p.score_control(c, reply('9007199254740992'))['closed_book_gold_match'])

    def test_duplicate_extra_and_incoherent_fields_are_malformed(self):
        for raw in ('{"status":"answer","answer":"bad","answer":"$1,264"}',
                    '{"status":"answer","answer":"$1,264","extra":0}',
                    reply('$1,264', 'abstain'), reply(None, 'unknown'), '[]', 'not json'):
            self.assertEqual(p.score_control(case(), raw)['reason'], 'malformed_control')

    def test_two_codes_require_whole_set_no_containment(self):
        c = case()
        c['roles'] = [{'value_string': 'AA and BB', 'allowed_alternatives': [],
                       'members': [{'aliases': ['AA']}, {'aliases': ['BB']}],
                       'unordered': True, 'separators': [' and ', ', ']}]
        for value in ('AA and BB', 'BB, AA'):
            self.assertTrue(p.score_control(c, reply(value))['closed_book_gold_match'])
        for value in ('AA', 'AA, BB, CC', 'AA, AA'):
            self.assertFalse(p.score_control(c, reply(value))['closed_book_gold_match'])

    def test_negative_abstention_does_not_remove_negatives(self):
        c = case('n', 'insufficient_evidence')
        s = p.score_control(c, reply(None, 'abstain'))
        self.assertEqual(s['state'], 'negative_abstained')
        self.assertIsNone(s['closed_book_gold_match'])
        self.assertEqual(p.score_control(c, reply('world fact'))['state'], 'negative_answered')

    def test_adjusted_excludes_positive_match_but_keeps_negatives_and_nonmatches(self):
        cs = [case(), case('b'), case('n', 'insufficient_evidence')]
        controls = {'a': reply('$1,264'), 'b': reply('wrong'), 'n': reply(None, 'abstain')}
        r = p.score_views(cs, controls, {'a': True, 'b': False, 'n': True})
        self.assertEqual(r['all_primary'], {'n': 3, 'correct': 2, 'positive_n': 2, 'negative_n': 1})
        self.assertEqual(r['adjusted_primary'], {'n': 2, 'correct': 1, 'positive_n': 1, 'negative_n': 1})

    def test_unknown_control_blocks_adjusted_headline_not_full_primary(self):
        for controls in ({}, {'a': None}, {'a': 'malformed'}):
            r = p.score_views([case()], controls, {'a': True})
            self.assertIsNone(r['adjusted_primary'])
            self.assertEqual(r['unknown_controls'], 1)
            self.assertEqual(r['all_primary']['correct'], 1)

    def test_pending_gold_does_not_score_either_headline(self):
        c = case()
        c['pending_decisions'] = ['review']
        r = p.score_views([c], {'a': reply('$1,264')}, {'a': True})
        self.assertIsNone(r['all_primary'])
        self.assertIsNone(r['adjusted_primary'])

    def test_missing_rag_is_retained_as_failure(self):
        r = p.score_views([case()], {'a': reply(None, 'abstain')}, {})
        self.assertEqual(r['adjusted_primary']['n'], 1)
        self.assertEqual(r['adjusted_primary']['correct'], 0)
        self.assertEqual(r['missing_rag_failures'], 1)

    def test_duplicate_and_foreign_capture_identities_rejected(self):
        with self.assertRaises(ValueError):
            p.score_views([case(), case()], {}, {})
        with self.assertRaises(ValueError):
            p.score_views([case()], {'foreign': reply('bad')}, {})
        with self.assertRaises(ValueError):
            p.score_views([case()], {}, {'a': 1})

    def test_normalized_pair_is_detected_without_exact_hash_match(self):
        r = p.audit_pairing(*audit_inputs())
        self.assertEqual(r['primary_pairs']['exact_paragraph'], [])
        self.assertEqual(r['primary_pairs']['normalized_paragraph'], [[1, 2]])
        self.assertEqual(r['primary_pairs']['question_and_normalized_paragraph'], [[1, 2]])

    def test_shared_paragraph_different_question_is_not_a_pair(self):
        a, g, l, t = audit_inputs()
        a['cases'][1]['request']['question'] = g['cases'][1]['question'] = 'A different question?'
        r = p.audit_pairing(a, g, l, t)
        self.assertEqual(r['primary_pairs']['normalized_paragraph'], [[1, 2]])
        self.assertEqual(r['primary_pairs']['question_and_normalized_paragraph'], [])

    def test_source_changes_sealed_inputs_and_roster_mismatch_are_rejected(self):
        for mutation in ('bytes', 'sealed', 'roster'):
            a, g, l, t = audit_inputs()
            if mutation == 'bytes':
                a['cases'][0]['source_text'] = 'Changed source'
            elif mutation == 'sealed':
                a['cases'][0]['request']['split'] = 'sealed'
            else:
                l['cases'].pop()
            with self.assertRaises(ValueError):
                p.audit_pairing(a, g, l, t)

    def test_nonprimary_pdf_exclusion_remains_separate(self):
        a, g, l, t = audit_inputs()
        for r in (g['cases'][0], l['cases'][0]):
            r['tier'] = 'stress_adjudication'
        t['cases'] = [{**g['cases'][0], 'primary_reason': 'scope_or_period_ambiguous',
                       'finding': 'Period is ambiguous', 'original_expected': 'supported'}]
        r = p.audit_pairing(a, g, l, t)
        self.assertEqual(r['primary_n'], 1)
        self.assertEqual(r['excluded_pdfs'][0]['number'], 1)


if __name__ == '__main__':
    unittest.main()
