"""Explicit reranker profiles; no implicit model fallback or token truncation."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(base_lock, name=None):
    name = name if name is not None else os.environ.get('VECTORNEXT_RERANKER_PROFILE', 'minilm')
    if name == 'minilm':
        lock, version = base_lock, 'minilm-pair-raw-logit-v1'
    elif name == 'ettin-17m':
        lock = ROOT/'experiments/t32/models.lock.json'
        version = 'ettin-cls-dense-gelu-exact-layernorm-eps1e-5-dense-raw-v1'
    else:
        raise ValueError('unknown reranker profile: '+str(name))
    return {'name': name, 'spec': json.loads(Path(lock).read_bytes())['models']['reranker'],
            'max_tokens': 512, 'preprocessing': version}
