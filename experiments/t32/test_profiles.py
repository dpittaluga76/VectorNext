import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from experiments.t02.encoders import Encoder, nomic_pool_normalize
from model_worker.server import Worker
from model_worker.cache import digest
from model_worker.reranker_profile import load


class Profiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'VECTORNEXT_EMBEDDING_PROFILE':'nomic-v1.5','VECTORNEXT_CACHE':cls.temp.name}):
            cls.nomic = Worker()
        with patch.dict(os.environ, {'VECTORNEXT_RERANKER_PROFILE':'ettin-17m'}):
            cls.ettin = Encoder('reranker')

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_legacy_identities_unchanged(self):
        with patch.dict(os.environ, {'VECTORNEXT_EMBEDDING_PROFILE':'minilm','VECTORNEXT_RERANKER_PROFILE':'minilm','VECTORNEXT_CACHE':self.temp.name}):
            worker, reranker = Worker(), Encoder('reranker')
        self.assertEqual(worker.space,json.loads(Path('experiments/t31/minilm-space-before.json').read_bytes()))
        self.assertEqual(reranker.identity(),json.loads(Path('experiments/t32/minilm-reranker-before.json').read_bytes()))
        self.assertNotEqual(worker.space,self.nomic.space)
        self.assertNotEqual(digest(reranker.identity()),digest(self.ettin.identity()))
        for model in (worker,self.nomic): model.handle({'op':'embed','input':'Shared cache synthetic input.'})
        self.assertEqual(worker.calls['embed'],1)
        self.assertEqual(self.nomic.calls['embed'],1)

    def test_nomic_dimensions_prefix_and_token_boundaries(self):
        w=self.nomic
        self.assertEqual(w.space['dimensions'],768)
        self.assertEqual(w.space['query_prefix'],'search_query: ')
        self.assertEqual(w.space['document_prefix'],'search_document: ')
        self.assertEqual(w.count('word '*1022),1024)
        self.assertEqual(len(w.handle({'op':'embed','input':'word '*1022})),768)
        with self.assertRaisesRegex(ValueError,'token limit'):w.handle({'op':'embed','input':'word '*1023})
        with self.assertRaisesRegex(ValueError,'token limit'):w.handle({'op':'embed','input':w.space['query_prefix']+'word '*1022})

    def test_publisher_pooling_and_head_match_torch(self):
        # Torch is already installed for the PDF processor, not a new worker dependency.
        sys.path.append('/usr/local/lib/python3.12/site-packages')
        import torch
        import torch.nn.functional as F
        rng=np.random.default_rng(732)
        hidden=rng.normal(size=(2,5,768)).astype(np.float32)
        mask=np.array([[1,1,1,0,0],[1,1,1,1,1]],dtype=np.int64)
        x=torch.from_numpy(hidden); weights=torch.from_numpy(mask[:,:,None]).float()
        pooled=(x*weights).sum(1)/weights.sum(1)
        expected=F.normalize(F.layer_norm(pooled,(768,)),p=2,dim=1).numpy()
        np.testing.assert_allclose(nomic_pool_normalize(hidden,mask),expected,atol=1e-6)
        head=self.ettin.head; h=rng.normal(size=(2,5,256)).astype(np.float32);x=torch.from_numpy(h[:,0,:])
        x=F.gelu(F.linear(x,torch.from_numpy(head.first['linear.weight'])),approximate='none')
        x=F.layer_norm(x,(256,),torch.from_numpy(head.norm['norm.weight']),torch.from_numpy(head.norm['norm.bias']),1e-5)
        x=F.linear(x,torch.from_numpy(head.last['linear.weight']),torch.from_numpy(head.last['linear.bias']))
        np.testing.assert_allclose(head(h),x.numpy().reshape(-1),atol=2e-6)

    def test_real_padding_and_output_shapes(self):
        pairs=[('Which animal swims?','The fish swims in water.'),('Which animal swims?','A wooden chair has four legs and a flat seat.')]
        scores,lengths=self.ettin.run(pairs)
        self.assertEqual(scores.shape,(2,))
        self.assertTrue(np.isfinite(scores).all())
        one,_=self.ettin.run(pairs[:1]);np.testing.assert_allclose(scores[:1],one,atol=1e-5)
        self.assertEqual(self.ettin.tokenizer.padding['pad_id'],50283)
        self.assertGreater(scores[0],scores[1])
        vectors,_=self.nomic.encoder.run(['search_query: fish','search_query: a longer synthetic input for padding'])
        alone,_=self.nomic.encoder.run(['search_query: fish']);np.testing.assert_allclose(vectors[:1],alone,atol=1e-5)

    def test_pair_limit_and_unknown_profiles(self):
        with self.assertRaisesRegex(ValueError,'exceeds 512'): self.ettin.run([('question','word '*600)])
        with self.assertRaisesRegex(ValueError,'unknown reranker'):load(Path('missing'),name='typo')
        with self.assertRaisesRegex(ValueError,'unknown embedding'):
            with patch.dict(os.environ, {'VECTORNEXT_EMBEDDING_PROFILE':'typo'}):Worker()

    def test_head_hashes_and_cache_identity(self):
        identity=self.ettin.identity()
        self.assertIn('4_Dense/model.safetensors',identity['artifact_sha256'])
        changed=json.loads(json.dumps(identity));changed['artifact_sha256']['4_Dense/model.safetensors']='0'*64
        self.assertNotEqual(digest(identity),digest(changed))
        with self.assertRaises(ValueError):self.ettin.head(np.ones((2,256),dtype=np.float32))

    def test_missing_corrupt_artifacts_fail_closed(self):
        with patch.dict(os.environ, {'VECTORNEXT_RERANKER_PROFILE':'ettin-17m'}):
            with patch('experiments.t02.encoders.verify', return_value=False):
                with self.assertRaisesRegex(ValueError,'Missing or corrupt reranker'): Encoder('reranker')
            with self.assertRaisesRegex(ValueError,'Missing or corrupt reranker'):
                Encoder('reranker',root=Path(self.temp.name)/'missing')


if __name__ == '__main__':unittest.main()
