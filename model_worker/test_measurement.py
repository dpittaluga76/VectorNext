"""Failure observations must not change generation options or error behavior."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from .answers import generate, ASSESS_PROMPT


class MeasurementTests(unittest.TestCase):
    def worker(self, final):
        return SimpleNamespace(generation_profile={},generator_alias='fixture',calls={},
            generator=dict(model='fixture',revision='r1',artifact_sha256='a'*64,runtime='fixture'),
            http=Mock(side_effect=[{'prompt':'text'},{'tokens':[1,2]},final]))

    def test_success_and_invalid_output(self):
        for content, fails in [('{}',False),('broken',True)]:
            w=self.worker({'choices':[{'finish_reason':'stop','message':{'content':content}}],
                           'usage':{'completion_tokens':4}})
            if fails:
                with self.assertRaises(ValueError): generate(w,[],{'type':'object'},ASSESS_PROMPT)
            else: generate(w,[],{'type':'object'},ASSESS_PROMPT)
            observation=w.measurements[0]
            self.assertEqual(observation['state'],'failed' if fails else 'completed')
            self.assertEqual(observation['stage'],'assessment')
            self.assertEqual(observation['input_tokens'],2)
            self.assertEqual(observation['output_tokens'],4)
            self.assertEqual(set(observation['stages_ms']),{'preparation','inference','decode_validation'})
            self.assertFalse(w.http.call_args.args[1]['cache_prompt'])

    def test_transport_failure_retains_observed_inference_only(self):
        w=self.worker(ConnectionError('offline'))
        with self.assertRaises(ConnectionError): generate(w,[],{'type':'object'},ASSESS_PROMPT)
        observation=w.measurements[0]
        self.assertEqual(observation['state'],'failed')
        self.assertIsNone(observation['output_tokens'])
        self.assertNotIn('decode_validation',observation['stages_ms'])
        self.assertIn('inference',observation['stages_ms'])


if __name__ == '__main__': unittest.main()
