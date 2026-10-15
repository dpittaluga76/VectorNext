import copy
import json
from pathlib import Path
import unittest
import jsonschema
from model_worker.answers import pointer_catalog, schema, messages
from experiments.t27.test_protocol import ProtocolTests
from .run import SUITES


class RankedPointerTests(unittest.TestCase):
    def value(self):
        fields = {'reading': {'kind':'integer','nullable':False,'pointer':None,'description':'sensor count'}}
        return fields, [
            {'id':'E1','record':{},'text':'{"nested":{"count":7},"flag":true,"missing":null}'},
            {'id':'E2','record':{},'text':'{"other":11}'}]

    def test_record_type_binding_and_no_dot_repair(self):
        fields, evidence = self.value()
        contract = schema(fields,evidence,True)
        proof = {'value':None,'quote':'','evidence_id':'E1','pointer':'/nested/count'}
        def answer(p): return {'status':'supported','fields':{'reading':p}}
        jsonschema.validate(answer(proof),contract)
        for changes in ({'pointer':'nested.count'}, {'pointer':'/other'}, {'pointer':'/flag'},
                        {'evidence_id':'E2'}, {'evidence_id':'E3'}, {'value':7}):
            with self.subTest(changes=changes), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(answer(proof|changes),contract)
        # A permitted but semantically irrelevant same-type path still needs model/source checks.
        jsonschema.validate(answer(proof|{'evidence_id':'E2','pointer':'/other'}),contract)

    def test_null_explicit_missing_and_empty_supported_branch(self):
        fields,evidence=self.value()
        self.assertIn('/missing',pointer_catalog(fields,evidence)['E1']['reading'])
        fields['reading']['pointer']='/not-present'
        contract=schema(fields,evidence,True)
        self.assertNotIn('supported', [b['properties']['status']['const'] for b in contract['oneOf']])
        for status in ('ambiguous','insufficient_evidence'):
            jsonschema.validate({'status':status,'fields':{}},contract)

    def test_mixed_prose_and_only_supplied_records(self):
        fields,evidence=self.value()
        evidence=evidence[:1]+[{'id':'E9','record':None,'text':'Sensor count is 7.'}]
        contract=schema(fields,evidence,True)
        jsonschema.validate({'status':'supported','fields':{'reading':
            {'value':7,'quote':'7','evidence_id':'E9','pointer':None}}},contract)
        self.assertNotIn('E2',json.dumps(contract))

    def test_depth_byte_bounds_and_exact_type_catalog(self):
        fields,evidence=self.value()
        evidence[0]['text']='{"a/b":{"~x":[0,null,true,9007199254740997.00000000000003]}}'
        self.assertEqual(pointer_catalog(fields,evidence)['E1']['reading'],['/a~1b/~0x/0','/a~1b/~0x/1'])
        fields['reading']['kind']='number'
        self.assertIn('/a~1b/~0x/3',pointer_catalog(fields,evidence)['E1']['reading'])
        evidence[0]['text']='['*65+'0'+']'*65
        with self.assertRaisesRegex(ValueError,'depth/path'): pointer_catalog(fields,evidence)
        evidence[0]['text']=json.dumps({str(i)+'x'*200: i for i in range(200)})
        with self.assertRaisesRegex(ValueError,'byte budget'): pointer_catalog(fields,evidence)

    def test_preserved_freezes_and_208_denominator(self):
        from .fresh_check import validate
        from .run import validate_inputs
        validate();validate_inputs()
        self.assertEqual(sum((16 if name=='t14' else 28)*len(spec[2]) for name,spec in SUITES.items()),208)


if __name__ == '__main__': unittest.main()
