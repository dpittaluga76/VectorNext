"""Bounded CPU inference using the publishers' pinned FP32 ONNX exports."""

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from .fetch_models import LOCK, artifact_path, verify

ort.disable_telemetry_events()


def mean_pool_normalize(hidden, mask):
    weights = mask[..., None].astype(np.float32)
    counts = weights.sum(axis=1)
    if np.any(counts == 0):
        raise ValueError("Cannot pool an empty attention mask")
    pooled = (hidden * weights).sum(axis=1) / counts
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError("Invalid embedding norm")
    return (pooled / norms).astype(np.float32)


def cls_pool_normalize(hidden):
    if hidden.ndim != 3 or hidden.shape[1] == 0:
        raise ValueError('CLS pooling requires token hidden states')
    pooled = hidden[:, 0, :]
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.isfinite(norms).all() or not np.isfinite(pooled).all():
        raise ValueError('Invalid CLS embedding norm')
    return (pooled / norms).astype(np.float32)


def nomic_pool_normalize(hidden, mask):
    weights = mask[..., None].astype(np.float32)
    counts = weights.sum(axis=1)
    if np.any(counts == 0):
        raise ValueError('Cannot pool an empty attention mask')
    pooled = (hidden * weights).sum(axis=1) / counts
    centered = pooled - pooled.mean(axis=-1, keepdims=True)
    normalized = centered / np.sqrt(pooled.var(axis=-1, keepdims=True) + np.float32(1e-5))
    norms = np.linalg.norm(normalized, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError('Invalid Nomic embedding norm')
    return (normalized / norms).astype(np.float32)


class Encoder:
    def __init__(self, role, root=Path("/models"), threads=4):
        if role not in {"embedding", "reranker"}:
            raise ValueError("Unknown encoder role")
        self.role = role
        self.profile = None
        self.reranker_profile = None
        if role == 'embedding':
            from model_worker.embedding_profile import load
            self.profile = load(LOCK)
            self.spec = self.profile['spec']
        else:
            from model_worker.reranker_profile import load
            self.reranker_profile = load(LOCK)
            self.spec = self.reranker_profile['spec']
        for artifact in self.spec["files"]:
            if not verify(artifact_path(root, self.spec, artifact), artifact):
                raise ValueError(f"Missing or corrupt {role} artifact: {artifact['path']}")
        directory = root / self.spec["directory"]
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_truncation()
        config = json.loads((directory/'config.json').read_bytes())
        pad_id = config.get('pad_token_id', 0)
        if self.tokenizer.token_to_id('[PAD]') != pad_id:
            raise ValueError('Tokenizer/model padding ID mismatch')
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token="[PAD]")
        self.max_tokens = (self.profile or self.reranker_profile)['max_tokens']
        if self.profile and self.profile['pooling'] == 'cls':
            config = json.loads((directory/'config.json').read_bytes())
            pooling = json.loads((directory/'1_Pooling/config.json').read_bytes())
            if (config['hidden_size'] != self.profile['dimensions']
                    or config['max_position_embeddings'] < self.max_tokens
                    or not pooling.get('pooling_mode_cls_token')
                    or pooling.get('pooling_mode_mean_tokens')):
                raise ValueError('BGE model/pooling configuration does not match the selected profile')
        if self.profile and self.profile['pooling'] == 'mean-layernorm':
            pooling = json.loads((directory/'1_Pooling/config.json').read_bytes())
            if (config['hidden_size'] != self.profile['dimensions']
                    or config['max_position_embeddings'] < self.max_tokens
                    or not pooling.get('pooling_mode_mean_tokens')):
                raise ValueError('Nomic model/pooling configuration mismatch')
        self.head = None
        if self.reranker_profile and self.reranker_profile['name'] == 'ettin-17m':
            from model_worker.ettin import Head
            self.head = Head(directory)
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(directory / "onnx/model.onnx"), options, providers=["CPUExecutionProvider"])
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise RuntimeError("Expected CPU-only inference")

    def run(self, inputs):
        if not inputs or len(inputs) > 32:
            raise ValueError("Batch size must be between 1 and 32")
        encoded = self.tokenizer.encode_batch(inputs, add_special_tokens=True)
        lengths = [sum(item.attention_mask) for item in encoded]
        if max(lengths) > self.max_tokens:
            raise ValueError(f"Input exceeds {self.max_tokens} tokens including special tokens; split before inference")
        tensors = {
            "input_ids": np.array([item.ids for item in encoded], dtype=np.int64),
            "attention_mask": np.array([item.attention_mask for item in encoded], dtype=np.int64),
            "token_type_ids": np.array([item.type_ids for item in encoded], dtype=np.int64),
        }
        feed = {item.name: tensors[item.name] for item in self.session.get_inputs()}
        outputs = self.session.run(None, feed)
        if self.role == "embedding":
            values = (cls_pool_normalize(outputs[0]) if self.profile['pooling'] == 'cls'
                      else nomic_pool_normalize(outputs[0], tensors['attention_mask']) if self.profile['pooling'] == 'mean-layernorm'
                      else mean_pool_normalize(outputs[0], tensors["attention_mask"]))
            if values.shape != (len(inputs), self.profile['dimensions']):
                raise RuntimeError(f"Unexpected embedding shape {values.shape}")
        else:
            values = self.head(outputs[0]) if self.head else outputs[0].reshape(-1).astype(np.float32)
            if values.shape != (len(inputs),):
                raise RuntimeError(f"Unexpected reranker shape {values.shape}")
        if not np.isfinite(values).all():
            raise RuntimeError("Nonfinite model output")
        return values, lengths

    def identity(self):
        identity = {
            "repo": self.spec["repo"], "revision": self.spec["revision"],
            "artifact_sha256": {f["path"]: f["sha256"] for f in self.spec["files"] if f["path"] in {"onnx/model.onnx", "tokenizer.json"}},
            "format": "publisher_fp32_onnx", "providers": self.session.get_providers(),
            "preprocessing_version": (self.profile or self.reranker_profile)['preprocessing'],
            "onnxruntime_version": ort.__version__,
            "max_tokens_including_special": self.max_tokens,
            "query_prefix": self.profile['query_prefix'] if self.profile else "", "document_prefix": self.profile['document_prefix'] if self.profile else "",
            "tokenizer": "pinned tokenizer.json; original WordPiece normalization",
            "pooling": (("CLS then L2 normalization" if self.profile['pooling'] == 'cls' else
                         "attention-mask mean then layer normalization then L2 normalization" if self.profile['pooling'] == 'mean-layernorm' else "attention-mask mean then L2 normalization")
                        if self.profile else "none; raw relevance logit, higher is better, not a probability"),
            "dimensions": self.profile['dimensions'] if self.profile else 1,
            "dtype": "float32", "truncation": "reject", "max_batch": 32,
        }
        if self.head:
            identity['artifact_sha256'] = {f['path']: f['sha256'] for f in self.spec['files']}
            identity['tokenizer'] = 'pinned tokenizer.json; publisher pair template and padding'
            identity['pooling'] = 'CLS then publisher Dense/GELU/LayerNorm/Dense; raw logit'
            identity['head_runtime'] = 'numpy=' + np.__version__ + ';math.erf;cpu-fp32'
        return identity
