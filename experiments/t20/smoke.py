"""Explicit two-document adapter/SQL check, separate from measured corpora."""
import hashlib
import json
import numpy as np
from .run import VectorNext, Postgres, update_digest, reference, score, FILTERS, CONFIGS

vnx=VectorNext(); pg=Postgres(2)
vnx.call('open',documents=2)
assert vnx.call('stats')[0]['documents']==0,'smoke storage already exists'
pg.setup()
vectors=np.zeros((64,384),dtype=np.float32)
vectors[:32,0]=1; vectors[32:,1]=1
digest=hashlib.sha256()
for i in range(2):
    doc={'id':f'd{i:05}','bucket':i,'texts':[f'Smoke document {i} chunk {j}.' for j in range(32)],'vectors':vectors[i*32:(i+1)*32].tolist()}
    update_digest(digest,doc); vnx.call('insert',document=doc); pg.insert(doc)
assert vnx.call('verify')[0]['digest']==pg.digest()==digest.hexdigest()
vnx.call('index'); pg.indexes(); pg.indexes(hnsw=True)
query=vectors[0].tolist()
for scope in FILTERS:
    expected=reference(vectors,query,scope,2)
    for config in CONFIGS:
        if config=='vectornext': hits=vnx.call('search',documents=2,filter=scope,vector=query)[0]['hits']
        else: pg.configure(config); hits,_=pg.query({'vector':query,'filter':scope},config)
        assert score(hits,expected,query,vectors,scope,2)['correct'],(scope,config,hits)
assert pg.stats()['chunks']==vnx.call('stats')[0]['chunks']==64
json.dumps(pg.stats(),allow_nan=False)
print('Smoke passed: identical persistence digest, all four filters/configurations and resource reads.')
