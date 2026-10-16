import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from experiments.t02.encoders import Encoder, cls_pool_normalize
from model_worker.server import Worker
from model_worker.embedding_profile import QUERY_INSTRUCTION, load
from model_worker.cache import digest


class EmbeddingProfilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'VECTORNEXT_CACHE': cls.temp.name, 'VECTORNEXT_EMBEDDING_PROFILE': 'bge-small-en-v1.5'}):
            cls.bge = Worker()

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_default_space_is_byte_compatible_and_separate(self):
        with patch.dict(os.environ, {'VECTORNEXT_CACHE': self.temp.name, 'VECTORNEXT_EMBEDDING_PROFILE': 'minilm'}):
            old = Worker()
        reference = json.loads(Path('experiments/t31/minilm-space-before.json').read_bytes())
        self.assertEqual(old.space, reference)
        self.assertNotEqual(digest(old.space), digest(self.bge.space))
        self.assertEqual(self.bge.space['query_prefix'], QUERY_INSTRUCTION)
        self.assertEqual(self.bge.space['document_prefix'], '')
        self.assertIn('bge-cls-l2-v1', self.bge.space['preprocessing'])
        changed = dict(self.bge.space, query_prefix='')
        self.assertNotEqual(digest(changed), digest(self.bge.space))
        for worker in (old,self.bge): worker.handle({'op':'embed','input':'Shared cache input.'})
        self.assertEqual(old.calls['embed'],1)
        self.assertEqual(self.bge.calls['embed'],1)

    def test_cls_matches_actual_first_token_and_padding_is_invariant(self):
        encoder = self.bge.encoder
        tokens = encoder.tokenizer.encode_batch(['A blue boat.', 'A longer sentence with several different words.'])
        arrays = {'input_ids':np.array([x.ids for x in tokens],dtype=np.int64),
                  'attention_mask':np.array([x.attention_mask for x in tokens],dtype=np.int64),
                  'token_type_ids':np.array([x.type_ids for x in tokens],dtype=np.int64)}
        hidden = encoder.session.run(None,{x.name:arrays[x.name] for x in encoder.session.get_inputs()})[0]
        expected = hidden[:,0,:]; expected = expected/np.linalg.norm(expected,axis=1,keepdims=True)
        actual,_ = encoder.run(['A blue boat.', 'A longer sentence with several different words.'])
        np.testing.assert_allclose(actual,expected,atol=1e-6)
        alone,_ = encoder.run(['A blue boat.'])
        np.testing.assert_allclose(actual[0],alone[0],atol=1e-6)
        self.assertEqual(encoder.session.get_providers(),['CPUExecutionProvider'])
        with self.assertRaises(ValueError): cls_pool_normalize(np.zeros((1,2,384),dtype=np.float32))
        with np.errstate(over='ignore', invalid='ignore'):
            for value in (np.finfo(np.float32).max, np.nan, np.inf):
                with self.assertRaises(ValueError):
                    cls_pool_normalize(np.full((1,2,384),value,dtype=np.float32))

    def test_real_token_boundary_and_prefix_budget_reject_truncation(self):
        w = self.bge
        self.assertEqual(w.count('word '*510),512)
        vector = w.handle({'op':'embed','input':'word '*510})
        self.assertEqual(len(vector),384)
        with self.assertRaisesRegex(ValueError,'token limit'): w.handle({'op':'embed','input':'word '*511})
        with self.assertRaisesRegex(ValueError,'token limit'):
            w.handle({'op':'embed','input':QUERY_INSTRUCTION+'word '*510})
        self.assertGreater(w.count(QUERY_INSTRUCTION+'boat'),w.count('boat'))

    def test_unknown_profile_does_not_fall_back(self):
        with self.assertRaisesRegex(ValueError,'unknown embedding profile'): load(Path('missing'),name='typo')


if __name__ == '__main__': unittest.main()
