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


class Encoder:
    def __init__(self, role, root=Path("/models"), threads=4):
        if role not in {"embedding", "reranker"}:
            raise ValueError("Unknown encoder role")
        self.role = role
        self.spec = json.loads(LOCK.read_text())["models"][role]
        for artifact in self.spec["files"]:
            if not verify(artifact_path(root, self.spec, artifact), artifact):
                raise ValueError(f"Missing or corrupt {role} artifact: {artifact['path']}")
        directory = root / self.spec["directory"]
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.max_tokens = 256 if role == "embedding" else 512
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
            values = mean_pool_normalize(outputs[0], tensors["attention_mask"])
            if values.shape != (len(inputs), 384):
                raise RuntimeError(f"Unexpected embedding shape {values.shape}")
        else:
            values = outputs[0].reshape(-1).astype(np.float32)
            if values.shape != (len(inputs),):
                raise RuntimeError(f"Unexpected reranker shape {values.shape}")
        if not np.isfinite(values).all():
            raise RuntimeError("Nonfinite model output")
        return values, lengths

    def identity(self):
        return {
            "repo": self.spec["repo"], "revision": self.spec["revision"],
            "artifact_sha256": {f["path"]: f["sha256"] for f in self.spec["files"] if f["path"] in {"onnx/model.onnx", "tokenizer.json"}},
            "format": "publisher_fp32_onnx", "providers": self.session.get_providers(),
            "preprocessing_version": "minilm-mask-mean-l2-v1" if self.role == "embedding" else "minilm-pair-raw-logit-v1",
            "onnxruntime_version": ort.__version__,
            "max_tokens_including_special": self.max_tokens,
            "query_prefix": "", "document_prefix": "",
            "tokenizer": "pinned tokenizer.json; original WordPiece normalization",
            "pooling": "attention-mask mean then L2 normalization" if self.role == "embedding" else "none; raw relevance logit, higher is better, not a probability",
            "dimensions": 384 if self.role == "embedding" else 1,
            "dtype": "float32", "truncation": "reject", "max_batch": 32,
        }
