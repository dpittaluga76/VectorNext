"""No GPU: call-count, schema, budgeting and failure boundaries of the experiment."""
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import jsonschema
from model_worker import answers


class SingleCallTests(unittest.TestCase):
    def value(self):
        return {'question': 'What is the count?', 'history': [],
            'fields': {'count': {'kind': 'integer', 'nullable': False, 'pointer': None}},
            'constrain_pointers': True, 'evidence': [{'id': 'E1',
            'key': {'document_id': 'd', 'revision': 'r'},
            'text': '{"count":9007199254740993}', 'record': {'count': 9007199254740993}}]}

    def worker(self, result, mode='single_call_v1'):
        calls = []
        def http(path, payload, priority):
            calls.append((path, payload, priority))
            if path == '/apply-template': return {'prompt': payload['messages'][0]['content']}
            if path == '/tokenize': return {'tokens': [1] * (100 if payload['content'] == answers.PROMPT else 200)}
            self.assertFalse(payload['cache_prompt'])
            self.assertEqual((payload['temperature'], payload['seed'], payload['max_tokens']), (0, 42, 768))
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result)}}]}
        return SimpleNamespace(answer_mode=mode, http=http, calls={}, generator_alias='test',
            generator=dict(model='test', revision='r', artifact_sha256='a', runtime='runtime')), calls

    def test_modes_are_explicit_and_default_is_unchanged(self):
        with patch.dict(os.environ, {}, clear=True): self.assertEqual(answers.answer_mode(), 'two_call')
        with patch.dict(os.environ, {'VECTORNEXT_ANSWER_MODE': 'typo'}):
            with self.assertRaisesRegex(ValueError, 'unknown answer mode'): answers.answer_mode()

    def test_one_generation_preserves_pointer_schema_and_audit(self):
        result = {'status': 'supported', 'fields': {'count': {'value': None, 'quote': '', 'evidence_id': 'E1', 'pointer': '/count'}}}
        worker, calls = self.worker(result)
        reply = answers.handle(worker, 'answer', self.value())
        self.assertEqual(reply['answer'], result)
        self.assertEqual([p for p, _, _ in calls], ['/apply-template', '/tokenize', '/v1/chat/completions'])
        self.assertTrue(reply['audit']['assessment_skipped'])
        self.assertNotIn('assessment_audit', reply['audit'])
        self.assertEqual(reply['audit']['answer_mode'], 'single_call_v1')
        bad = json.loads(json.dumps(result)); bad['fields']['count']['pointer'] = 'count'
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad, reply['audit']['schema'])

    def test_abstentions_remain_available_and_malformed_outputs_are_not_retried(self):
        for status in ('ambiguous', 'insufficient_evidence'):
            result = {'status': status, 'fields': {}}
            worker, _ = self.worker(result)
            self.assertEqual(answers.handle(worker, 'answer', self.value())['answer'], result)
        worker, calls = self.worker({'status': 'supported', 'fields': {}})
        with self.assertRaises(jsonschema.ValidationError): answers.handle(worker, 'answer', self.value())
        self.assertEqual(len(calls), 3)

    def test_evidence_budget_still_counts_both_prompts(self):
        worker, calls = self.worker(None)
        self.assertEqual(answers.handle(worker, 'answer_tokens', self.value()), 200)
        self.assertEqual(len(calls), 4)


if __name__ == '__main__': unittest.main()
