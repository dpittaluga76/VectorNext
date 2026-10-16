"""Schema checks against an isolated T19 API with synthetic documents only."""
from decimal import Decimal
import json
import os
import unittest
import urllib.request
import urllib.error
import time
from jsonschema import Draft202012Validator


@unittest.skipUnless(os.environ.get('VECTORNEXT_TEST_URL'), 'isolated API URL required')
class OpenApiTests(unittest.TestCase):
    def call(self, path, value=None):
        body = None if value is None else json.dumps(value).encode()
        req = urllib.request.Request(os.environ['VECTORNEXT_TEST_URL'] + path, data=body,
                                     headers={'Host': 'localhost:8099', 'Content-Type': 'application/json',
                                              'X-VectorNext-Client': '1'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read(), parse_float=Decimal)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read(), parse_float=Decimal)

    def setUp(self):
        status, self.spec = self.call('/openapi.json')
        self.assertEqual(status, 200)

    def validate_response(self, path, method='get', value=None, schema_path=None):
        status, response = self.call(path, value)
        schema = self.spec['paths'][schema_path or path][method]['responses'][str(status)]['content']['application/json']['schema']
        Draft202012Validator({**schema, 'components': self.spec['components']}).validate(response)
        return response

    def test_all_paths_have_schemas_and_references_resolve(self):
        expected = {'/healthz', '/readyz', '/v1/metrics', '/v1/documents', '/v1/document',
                    '/v1/jobs', '/v1/job', '/v1/retry', '/v1/ingest', '/v1/search', '/v1/ask',
                    '/v1/ui/library', '/v1/ui/upload', '/v1/ui/upload-status', '/v1/ui/remove',
                    '/v1/ui/source', '/v1/ui/original', '/v1/ui/ask', '/v1/answer-jobs',
                    '/v1/answer-jobs/{request_id}', '/v1/answer-jobs/{request_id}/cancel', '/v1/answer-jobs/{request_id}/clear'}
        self.assertEqual(set(self.spec['paths']), expected)
        self.assertTrue(self.spec['openapi'].startswith('3.1.'))
        schemas = self.spec['components']['schemas']
        self.assertIn('facet_coverage_v1', schemas['AnswerOptions']['properties']['evidence_strategy']['enum'])
        for name, schema in schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)
        def walk(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    self.assertTrue(value['$ref'].startswith('#/components/schemas/'))
                    self.assertIn(value['$ref'].split('/')[-1], schemas)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.spec)
        for path, methods in self.spec['paths'].items():
            for method, operation in methods.items():
                self.assertTrue(operation['operationId'])
                if method == 'post':
                    self.assertTrue(operation['requestBody']['required'])
                    self.assertIn('X-VectorNext-Client', [p['name'] for p in operation['parameters']])
                self.assertIn('503', operation['responses'])

    def test_live_envelopes_and_exact_legacy_answer_match_schemas(self):
        for path in ['/healthz', '/readyz', '/v1/metrics', '/v1/documents', '/v1/jobs', '/v1/ui/library']:
            with self.subTest(path=path):
                self.validate_response(path)
        library = self.call('/v1/ui/library')[1]
        self.assertTrue(library['documents'], 'Run isolated docs browser fixture first')
        doc = next(d for d in library['documents'] if d['filename'] == 'exact.json')
        scope = {'document_id': doc['document_id'], 'revision': doc['revision']}
        self.validate_response('/v1/document', 'post', {'document_id': doc['document_id']})
        self.validate_response('/v1/ui/source', 'post', scope)
        self.validate_response('/v1/ui/remove', 'post', {**scope, 'revision': 'stale'})
        self.validate_response('/v1/ui/upload-status', 'post', {'upload_id': doc['document_id'][4:]})
        for job in self.call('/v1/jobs')[1]['jobs']:
            self.validate_response('/v1/job', 'post', {'job_id': job['job_id']})
        self.validate_response('/v1/search', 'post', {'text': 'amount'})
        result = self.validate_response('/v1/ask', 'post', {'request': {
            'question': 'Exact stored amount', 'scope': 'structured_lookup',
            'filter': {'DocumentIds': [doc['document_id']]},
            'fields': {'amount': {'kind': 'number', 'pointer': '/amount'}}}})
        self.assertEqual(str(result['answer']['fields']['amount']['value']), '9007199254740993.00000000000001')
        self.validate_response('/v1/ui/ask', 'post', {'question': 'amount', 'document_ids': [doc['document_id']]})
        result = self.validate_response('/v1/ui/ask', 'post', {'question': 'amount', 'document_ids': [doc['document_id']], 'options': {'evidence_strategy':'facet_coverage_v1'}})
        self.assertIn('Facet coverage', result['workflow']['selection_summary'])
        self.assertEqual(result['fields'][0]['value_text'], '9007199254740993.00000000000001')
        for path in ['/v1/ask', '/v1/ui/ask', '/v1/document', '/v1/job', '/v1/ingest']:
            with self.subTest(invalid=path):
                self.validate_response(path, 'post', {})

    def test_durable_answer_job_envelopes_reconciliation_and_clear(self):
        doc = next(d for d in self.call('/v1/ui/library')[1]['documents'] if d['filename']=='exact.json')
        payload={'request':{'question':'Read exact values','scope':'structured_lookup','filter':{'DocumentIds':[doc['document_id']]},
                            'fields':{'amount':{'kind':'number','pointer':'/amount'}}}}
        request={'request_id':'schema-job-'+str(time.time_ns()),'kind':'structured','mode':'gemma','payload':payload}
        job=self.validate_response('/v1/answer-jobs','post',request)
        self.assertEqual(self.call('/v1/answer-jobs',request)[1]['request_id'],job['request_id'])
        self.assertEqual(self.call('/v1/answer-jobs',{**request,'mode':'hybrid'})[0],409)
        path='/v1/answer-jobs/'+job['request_id']
        for _ in range(50):
            job=self.validate_response(path,schema_path='/v1/answer-jobs/{request_id}')
            if job['terminal']: break
            time.sleep(.1)
        self.assertTrue(job['terminal'])
        self.assertIn('9007199254740993.00000000000001',job['response_text'])
        self.assertNotIn('result',job)
        self.validate_response('/v1/answer-jobs')
        self.validate_response(path+'/clear','post',{},'/v1/answer-jobs/{request_id}/clear')
        self.assertEqual(self.call(path)[0],404)
        schema={**self.spec['components']['schemas']['AnswerSubmission'],'components':self.spec['components']}
        validator=Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(request))
        self.assertFalse(validator.is_valid({**request,'kind':'ui'}))
        self.assertFalse(validator.is_valid({**request,'payload':{**payload,'mode':'gemma'}}))
