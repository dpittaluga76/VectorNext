from copy import deepcopy
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

if sys.platform != 'linux':
    raise unittest.SkipTest('Evaluation-worker checks use the Linux processor image; cache locking needs fcntl')

from model_worker import answers, planning
from model_worker.cache import digest
from model_worker.generator_profile import load
from .evaluation_worker import EvaluationWorker, closed_book, formatted_operation, prepared
from .format_contract import INSTRUCTION


def fake_worker(outputs, profile='12b', tokens=50):
    replies = iter(outputs)
    calls = []

    def http(path, payload, priority='background'):
        calls.append((path, deepcopy(payload), priority))
        if path == '/apply-template':
            return {'prompt': 'native rendered prompt'}
        if path == '/tokenize':
            return {'tokens': [1] * tokens}
        if path == '/v1/chat/completions':
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': reply}}],
                    'usage': {'completion_tokens': 9}}
        raise AssertionError(path)
    return SimpleNamespace(http=Mock(side_effect=http), wire=calls,
        generation_profile=load(profile), generator_alias=load(profile)['alias'], calls={},
        generator=dict(model='fixture', revision='r1', artifact_sha256='a' * 64, runtime='fixture'))


def input_value():
    return {'question': 'What amount was reported?', 'history': [],
        'fields': {'answer': {'kind': 'string', 'nullable': False, 'description': 'Reported amount'}},
        'evidence': [{'id': 'e1', 'key': {'document_id': 'fixture', 'revision': 'r1', 'chunk_id': 'c1'},
                      'text': '$1,264', 'record': None, 'labels': [], 'sources': []}]}


class EvaluationWorkerTests(unittest.TestCase):
    def test_instruction_is_applied_once_and_question_unchanged(self):
        source = [{'role': 'system', 'content': answers.PROMPT}, {'role': 'user', 'content': 'untrusted question'}]
        first, contract = prepared(source)
        second, _ = prepared(first)
        self.assertEqual(first, second)
        self.assertEqual(first[1], source[1])
        self.assertEqual(source[0]['content'], answers.PROMPT)
        self.assertEqual(first[0]['content'].count(INSTRUCTION.read_text(encoding='utf-8')), 1)
        self.assertEqual(contract['stage'], 'extraction')
        with self.assertRaises(ValueError):
            prepared([{'role': 'system', 'content': 'unrecognized prompt'}])

    def test_all_three_stages_share_instruction_for_both_models(self):
        ready = {'status': 'ready', 'fields': [{'name': 'answer', 'kind': 'string',
                 'nullable': False, 'description': 'Requested amount'}]}
        final = {'status': 'supported', 'fields': {'answer': {'value': '$1,264',
                 'evidence_id': 'e1', 'quote': '$1,264', 'pointer': None}}}
        for profile, temperature in [('12b', 0), ('nuextract3-requested-facts-v1', .2)]:
            w = fake_worker([json.dumps(ready), '{"status":"supported","reason":"fixture source"}', json.dumps(final)], profile)
            plan = formatted_operation(w, {'op': 'plan_fields', 'input': {'question': 'Amount?', 'history': []}})
            result = formatted_operation(w, {'op': 'answer', 'input': input_value()})
            self.assertEqual(result['answer'], final)
            audits = [plan['audit'], result['audit']['assessment_audit'], result['audit']]
            self.assertEqual([a['evaluation_format']['stage'] for a in audits], ['planning', 'assessment', 'extraction'])
            inference = [p for path, p, _ in w.wire if path == '/v1/chat/completions']
            preparation = [p for path, p, _ in w.wire if path == '/apply-template']
            self.assertEqual(len(inference), 3)
            for body, counted, audit in zip(inference, preparation, audits):
                self.assertEqual(body['messages'], counted['messages'])
                self.assertEqual(body['messages'][0]['content'].count(INSTRUCTION.read_text(encoding='utf-8')), 1)
                self.assertEqual(body['temperature'], temperature)
                self.assertEqual(body['seed'], 42)
                self.assertFalse(body['cache_prompt'])
                self.assertEqual(audit['prompt_sha256'], digest(body['messages'][0]['content']))
                options = {k: body[k] for k in ('chat_template_kwargs',) if k in body}
                self.assertEqual(audit['request_sha256'], digest({'messages': body['messages'], **options} if options else body['messages']))
                if options:
                    self.assertEqual(body['chat_template_kwargs'], counted['chat_template_kwargs'])
                    self.assertIn('template', body['chat_template_kwargs'])
            self.assertEqual([b['max_tokens'] for b in inference], [768, 192, 768])

    def test_admission_counts_both_effective_prompts_without_generating(self):
        w = fake_worker([])
        self.assertEqual(formatted_operation(w, {'op': 'answer_tokens', 'input': input_value()}), 50)
        self.assertEqual([p for p, _, _ in w.wire], ['/apply-template', '/tokenize'] * 2)

    def test_non_string_plan_rejected_without_silent_coercion(self):
        plan = {'status': 'ready', 'fields': [{'name': 'answer', 'kind': 'number', 'nullable': False,
                                             'description': 'Requested amount'}]}
        w = fake_worker([json.dumps(plan)])
        with self.assertRaisesRegex(ValueError, 'string-field'):
            formatted_operation(w, {'op': 'plan_fields', 'input': {'question': 'Amount?', 'history': []}})
        self.assertEqual(plan['fields'][0]['kind'], 'number')
        self.assertEqual(len([p for p, _, _ in w.wire if p == '/v1/chat/completions']), 1)
        v = input_value()
        v['fields']['answer']['kind'] = 'number'
        w = fake_worker([])
        with self.assertRaises(ValueError):
            formatted_operation(w, {'op': 'answer', 'input': v})
        self.assertFalse(w.wire)

    def test_negative_assessment_skips_extraction(self):
        w = fake_worker(['{"status":"insufficient_evidence","reason":"fixture missing"}'])
        result = formatted_operation(w, {'op': 'answer', 'input': input_value()})
        self.assertEqual(result['answer']['status'], 'insufficient_evidence')
        self.assertEqual(len([p for p, _, _ in w.wire if p == '/v1/chat/completions']), 1)

    def test_bindings_restored_even_when_backend_fails(self):
        bindings = (answers.generate, answers.count_prompt, planning.generate)
        w = fake_worker([ConnectionError('offline')])
        with self.assertRaises(ConnectionError):
            formatted_operation(w, {'op': 'answer', 'input': input_value()})
        self.assertEqual(bindings, (answers.generate, answers.count_prompt, planning.generate))
        self.assertEqual(w.measurements[-1]['state'], 'failed')

    def test_closed_book_receives_only_question_and_own_frozen_instruction(self):
        for profile, temperature in [('12b', 0), ('nuextract3-requested-facts-v1', .2)]:
            w = fake_worker(['{"status":"answer","answer":"9007199254740993"}'], profile)
            result = closed_book(w, {'question': 'Original question'})
            self.assertEqual(result['control']['answer'], '9007199254740993')
            body = w.wire[-1][1]
            self.assertEqual(body['messages'][1], {'role': 'user', 'content': 'Original question'})
            self.assertNotIn(INSTRUCTION.read_text(encoding='utf-8'), body['messages'][0]['content'])
            self.assertEqual(body['temperature'], temperature)
            self.assertEqual(body['max_tokens'], 768)
            self.assertFalse(body['cache_prompt'])
            self.assertEqual(w.measurements[-1]['stage'], 'closed_book')

    def test_closed_book_rejects_evidence_and_gold_hints_before_calling(self):
        for key in ('history', 'evidence', 'fields', 'title', 'gold', 'format', 'family'):
            w = fake_worker([])
            with self.assertRaises(ValueError):
                closed_book(w, {'question': 'Original question', key: []})
            self.assertFalse(w.wire)

    def test_closed_book_malformed_and_over_budget_are_errors_without_retry(self):
        for raw in ('broken', '{"status":"answer","answer":12}', '{"status":"abstain","answer":"no"}'):
            w = fake_worker([raw])
            with self.assertRaises(Exception):
                closed_book(w, {'question': 'Question'})
            self.assertEqual(len([p for p, _, _ in w.wire if p == '/v1/chat/completions']), 1)
        w = fake_worker([], tokens=3329)
        with self.assertRaisesRegex(ValueError, 'budget'):
            closed_book(w, {'question': 'Question'})
        self.assertFalse(any(path == '/v1/chat/completions' for path, _, _ in w.wire))

    def test_evaluation_worker_blocks_enrichment_before_lease_acquisition(self):
        w = EvaluationWorker.__new__(EvaluationWorker)
        w.http = Mock(side_effect=AssertionError('must not acquire'))
        for op in ('generate', 'rewrite'):
            with self.assertRaises(ValueError):
                w.handle({'op': op})
        w.http.assert_not_called()

    def test_transport_capture_preserves_exact_candidate_text_and_failure(self):
        from model_worker.server import Worker
        with tempfile.TemporaryDirectory() as directory:
            w = EvaluationWorker.__new__(EvaluationWorker)
            w.capture_directory, w.transport_sequence = Path(directory), 0
            w.lease, w.generation_profile = {'model': 'nuextract', 'token': 'fixture-token'}, {'name': 'fixture'}
            response = {'choices': [{'message': {'content': '{"answer":"9007199254740993.00000001"}'}}]}
            with patch.object(Worker, 'http', return_value=response):
                self.assertEqual(w.http('/v1/chat/completions', {'messages': []}, 'interactive'), response)
            saved = json.loads((Path(directory) / 'transport-000.response.json').read_bytes())
            self.assertEqual(saved, {'capture_type': 'decoded_transport', 'response': response})
            with patch.object(Worker, 'http', side_effect=ConnectionError('offline')):
                with self.assertRaises(ConnectionError):
                    w.http('/apply-template', {'messages': []}, 'interactive')
            self.assertTrue((Path(directory) / 'transport-001.request.json').exists())
            self.assertTrue((Path(directory) / 'transport-001.error.json').exists())
            self.assertFalse((Path(directory) / 'transport-001.response.json').exists())

    def test_processor_entrypoint_is_separate_from_production(self):
        from deployment import processor_server as base
        before = set(base.OPS)
        from .evaluation_processor import EvaluationRuntime, OPS
        with tempfile.TemporaryDirectory() as directory:
            runtime = EvaluationRuntime(Path(directory))
            for lane in runtime.lanes.values():
                self.assertIn('evals.measurement.evaluation_worker', lane.command)
                self.assertIsNone(lane.child)
            with patch.object(base.Runtime, 'health', return_value={'ready': True}):
                self.assertEqual(runtime.health()['measurement_adapter']['production_entry_point'], False)
        self.assertIn('closed_book', OPS)
        self.assertNotIn('generate', OPS)
        self.assertEqual(base.OPS, before)


if __name__ == '__main__':
    unittest.main()
