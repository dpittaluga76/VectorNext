import copy
import json
import unittest
import jsonschema
from .answers import messages, pointer_catalog, schema


class PointerCoverageTests(unittest.TestCase):
    def value(self):
        return {'question': 'What was measured?', 'history': [], 'fields': {
            'count': {'kind': 'integer', 'nullable': False, 'description': '', 'pointer': None}},
            'evidence': [{'id': 'E1', 'key': {'document_id': 'a', 'revision': 'r1'},
                          'record': {}, 'text': '{"a/b":{"~value":[0,null,true,1.00000000000000000001]},"label":"x"}'},
                         {'id': 'E2', 'key': {'document_id': 'b', 'revision': 'r1'}, 'record': {}, 'text': '{"count":9}'}]}

    def test_exact_source_types_paths_null_zero_and_boolean(self):
        v = self.value(); catalog = pointer_catalog(v['fields'], v['evidence'])
        self.assertEqual(catalog['E1']['count'], ['/a~1b/~0value/0', '/a~1b/~0value/1'])
        self.assertEqual(catalog['E2']['count'], ['/count'])
        v['fields']['count']['kind'] = 'number'
        self.assertIn('/a~1b/~0value/3', pointer_catalog(v['fields'], v['evidence'])['E1']['count'])

    def test_schema_binds_pointer_to_actual_evidence_and_honors_explicit_pointer(self):
        v = self.value(); s = schema(v['fields'], v['evidence'], True)
        answer = {'status': 'supported', 'fields': {'count': {'evidence_id': 'E1', 'value': None, 'quote': '', 'pointer': '/a~1b/~0value/0'}}}
        jsonschema.validate(answer, s)
        for pointer in ['/count', '/missing', '/a~1b/~0value/2']:
            bad = copy.deepcopy(answer); bad['fields']['count']['pointer'] = pointer
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad, s)
        v['fields']['count']['pointer'] = '/missing'
        s = schema(v['fields'], v['evidence'], True)
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(answer, s)
        jsonschema.validate({'status': 'insufficient_evidence', 'fields': {}}, s)

    def test_baseline_unchanged_and_catalog_visible_without_numeric_reserialization(self):
        v = self.value(); baseline = messages(v)
        v['constrain_pointers'] = False
        self.assertEqual(baseline, messages(v))
        self.assertEqual(schema(v['fields'], v['evidence']), schema(v['fields'], v['evidence'], False))
        v['constrain_pointers'] = True
        prompt = json.loads(messages(v)[1]['content'])
        self.assertIn('EXISTING JSON POINTERS BY EVIDENCE AND REQUESTED TYPE', prompt)
        self.assertIn('1.00000000000000000001', prompt['EVIDENCE'][0]['text'])
        self.assertNotIn('value', pointer_catalog(v['fields'], v['evidence'])['E2'])

    def test_catalog_bounds_fail_closed(self):
        v = self.value(); v['evidence'][0]['text'] = json.dumps(list(range(257)))
        with self.assertRaisesRegex(ValueError, '256'): pointer_catalog(v['fields'], v['evidence'])
        v['evidence'][0]['text'] = json.dumps({'x' * 2049: 1})
        with self.assertRaisesRegex(ValueError, 'bounds'): pointer_catalog(v['fields'], v['evidence'])


if __name__ == '__main__': unittest.main()
