"""Explicit CPU embedding profiles. Existing MiniLM identity remains unchanged."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY_INSTRUCTION = 'Represent this sentence for searching relevant passages: '


def load(base_lock, name=None):
    name = name if name is not None else os.environ.get('VECTORNEXT_EMBEDDING_PROFILE', 'minilm')
    if name == 'minilm':
        lock, limit, pooling, prefix, version = (base_lock, 256, 'mean', '', 'minilm-mask-mean-l2-v1')
    elif name == 'bge-small-en-v1.5':
        lock, limit, pooling, prefix, version = (ROOT/'experiments/t31/models.bge.lock.json',
            512, 'cls', QUERY_INSTRUCTION, 'bge-cls-l2-v1')
    else:
        raise ValueError('unknown embedding profile: ' + str(name))
    return {'name': name, 'spec': json.loads(Path(lock).read_bytes())['models']['embedding'],
        'max_tokens': limit, 'dimensions': 384, 'pooling': pooling, 'query_prefix': prefix,
        'document_prefix': '', 'preprocessing': version}
