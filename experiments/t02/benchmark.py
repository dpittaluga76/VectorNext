"""Exercise local models on supplied dev excerpts, not a database/RAG benchmark."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator
import numpy as np

from .encoders import Encoder
from .fetch_models import LOCK, sha256


DATASET = Path("/workspace/evals/dataset.json")
BASE = "http://llm:8080"
CONTEXT = 4096
OUTPUT = 256
MODEL = os.environ.get("VECTORNEXT_GENERATOR_ALIAS", "vectornext-gemma4-e2b")
FIELD_TYPES = {
    "year": "integer", "goals": "integer", "opponent": "string", "assists": "integer",
    "player_id": "string", "flow": "number", "unit": "string", "water_temperature_c": "number",
    "wait": "integer", "torque": "number", "interval": "integer",
}
REQUEST_FIELDS = {
    "q_pele_exact": ["year", "goals", "opponent"],
    "q_wrapped": ["goals"], "q_followup": ["year", "goals", "opponent"],
    "q_ambiguous": ["goals"], "q_missing_match": ["goals"], "q_null_unknown": ["assists"],
    "q_zero": ["goals"], "q_raw_null": ["assists"], "q_player_id": ["player_id"],
    "q_array": ["goals"], "q_table": ["flow", "unit", "water_temperature_c"],
    "q_cross_page": ["wait", "unit"], "q_scan": ["torque", "unit"],
}
SYSTEM = (
    "Answer only from the supplied synthetic source excerpts, never from outside knowledge. "
    "All people, matches and equipment facts in these fixtures are fictional. "
    "Preserve the question's year, opponent, record identity, value types and units. "
    "Use status supported only when the excerpts support the requested answer. "
    "If the question singles out a match but several matches fit, use ambiguous. "
    "If a requested fact is absent or a numeric count is unknown/null, use insufficient_evidence. "
    "A request for a raw JSON value can correctly return null. Never replace null or missing with zero. "
    "For supported answers return exactly the requested fields and cite the source excerpt IDs. "
    "Otherwise return empty fields and cite any excerpts showing the ambiguity or missing value. "
    "Return only the JSON object required by the schema."
)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def request(path, data=None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=180) as response:
        return json.load(response)


def answer_schema(fields, mode="legacy"):
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["status", "fields", "source_ids"],
        "properties": {
            "status": {"enum": ["supported", "ambiguous", "insufficient_evidence"]},
            "fields": {"type": "object", "additionalProperties": False,
                       "properties": {key: {"type": [FIELD_TYPES[key], "null"]} for key in fields}},
            "source_ids": {"type": "array", "items": {"type": "string"}},
        },
    }
    if mode == "legacy":
        return schema
    if mode != "status":
        raise ValueError("Unknown answer-schema mode")
    # Separate complete branches work with llama.cpp's grammar subset; its
    # converter does not support if/then/else or mixing properties with oneOf.
    branches = []
    for status in ["supported", "ambiguous", "insufficient_evidence"]:
        branch = copy.deepcopy(schema)
        branch["properties"]["status"] = {"const": status}
        if status == "supported":
            branch["properties"]["fields"]["required"] = list(fields)
        else:
            branch["properties"]["fields"] = {"type": "object", "properties": {}, "additionalProperties": False}
        branches.append(branch)
    return {"oneOf": branches}


def prepare(data):
    """Gold source transcriptions are supplied inputs; gold answers never enter prompts."""
    for document in data["documents"]:
        if sha256(DATASET.parent / document["path"]) != document["sha256"]:
            raise ValueError(f"Fixture revision changed: {document['id']}")
    passages = []
    for entry in data["evidence"]:
        loc = entry["locator"]
        value = entry["expected"]
        if loc["kind"] == "json":
            text = f"JSON pointer {loc['pointer']}: {canonical(value)}"
        else:
            text = value
        passages.append({"id": entry["id"], "document_id": entry["document_id"], "locator": loc, "text": text})
    cases = [case for case in data["cases"] if case["split"] == "dev"]
    if set(REQUEST_FIELDS) != {case["id"] for case in cases}:
        raise ValueError("Dev request contract changed; review the benchmark before using new cases")
    return passages, cases


def document_for(case_id):
    if case_id in {"q_zero", "q_raw_null", "q_player_id", "q_null_unknown"}:
        return "matches_json"
    if case_id == "q_array":
        return "array_json"
    if case_id in {"q_table", "q_cross_page"}:
        return "guide_pdf"
    if case_id == "q_scan":
        return "scan_pdf"
    return "matches_txt"


def messages_for(case, passages, padding=""):
    if case["split"] != "dev":
        raise ValueError("Holdout prompts are forbidden in this feasibility experiment")
    excerpts = [p for p in passages if p["document_id"] == document_for(case["id"])]
    user = {
        "history": case.get("history", []), "question": case["question"],
        "requested_fields": REQUEST_FIELDS[case["id"]],
        "excerpts": [{"source_id": p["id"], "text": p["text"]} for p in excerpts],
    }
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": padding + canonical(user)}], excerpts


def request_payload(case, passages, padding="", model=MODEL, schema_mode="legacy"):
    messages, supplied = messages_for(case, passages, padding)
    schema = answer_schema(REQUEST_FIELDS[case["id"]], schema_mode)
    return {
        "model": model, "messages": messages,
        "temperature": 0, "seed": 42, "max_tokens": OUTPUT, "cache_prompt": False,
        "reasoning": "off",
        "response_format": {"type": "json_schema", "json_schema": {"name": "evidence_answer", "strict": True, "schema": schema}},
    }, supplied


def infer(case, passages, label, padding="", schema_mode="legacy"):
    payload, supplied = request_payload(case, passages, padding, schema_mode=schema_mode)
    schema = payload["response_format"]["json_schema"]["schema"]
    template = request("/apply-template", {"messages": payload["messages"], "reasoning": "off"})
    tokens = request("/tokenize", {"content": template["prompt"], "add_special": True})["tokens"]
    if len(tokens) + OUTPUT > CONTEXT:
        raise ValueError(f"Request exceeds input/output budget: {len(tokens)} + {OUTPUT} > {CONTEXT}")
    start = time.perf_counter()
    response = request("/v1/chat/completions", payload)
    elapsed = time.perf_counter() - start
    choice = response["choices"][0]
    content = choice["message"]["content"]
    errors = []
    try:
        answer = json.loads(content)
        errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(answer))
    except (TypeError, ValueError) as error:
        answer = None
        errors.append(str(error))
    expected = case["expected"]
    status_correct = answer is not None and answer.get("status") == expected["status"]
    fields_correct = answer is not None and canonical(answer.get("fields")) == canonical(expected.get("fields", {}))
    known = {p["id"] for p in supplied}
    refs = answer.get("source_ids", []) if isinstance(answer, dict) else []
    references_valid = isinstance(refs, list) and all(isinstance(ref, str) and ref in known for ref in refs)
    if expected["status"] == "supported":
        support_complete = references_valid and any(set(s) <= set(refs) for s in expected["support_sets"])
    elif expected["status"] == "ambiguous":
        support_complete = references_valid and all(set(a["support_set"]) <= set(refs) for a in expected["alternatives"])
    else:
        support_complete = None
    return {
        "case_id": case["id"], "run": label, "wall_seconds": elapsed,
        "input_tokens_preflight": len(tokens), "usage": response.get("usage"),
        "timings": response.get("timings"), "finish_reason": choice.get("finish_reason"),
        "answer": answer, "raw_content": content, "schema_errors": errors,
        "status_correct": status_correct, "fields_correct": fields_correct,
        "references_valid": references_valid, "gold_support_complete": support_complete,
        "prompt_sha256": hashlib.sha256(canonical(payload).encode()).hexdigest(),
        "model_independent_prompt_sha256": hashlib.sha256(canonical({k: v for k, v in payload.items() if k != "model"}).encode()).hexdigest(),
    }


def measure_encoders(passages, cases):
    start = time.perf_counter()
    embedding = Encoder("embedding")
    embedding_load = time.perf_counter() - start
    texts = [p["text"] for p in passages]
    start = time.perf_counter()
    vectors, lengths = embedding.run(texts)
    first = time.perf_counter() - start
    repeat_times = []
    for _ in range(3):
        start = time.perf_counter()
        repeated, _ = embedding.run(texts)
        repeat_times.append(time.perf_counter() - start)
    delta = float(np.max(np.abs(vectors - repeated)))
    if delta > 1e-6:
        raise RuntimeError(f"Repeated embeddings differ: {delta}")
    start = time.perf_counter()
    reranker = Encoder("reranker")
    reranker_load = time.perf_counter() - start
    rows = []
    for case in cases:
        if case["id"] not in {"q_pele_exact", "q_zero", "q_table", "q_cross_page"}:
            continue
        start = time.perf_counter()
        query, query_lengths = embedding.run([case["question"]])
        query_time = time.perf_counter() - start
        dense_scores = (vectors @ query[0]).tolist()
        dense_order = sorted(range(len(texts)), key=lambda i: (-dense_scores[i], i))
        start = time.perf_counter()
        scores, pair_lengths = reranker.run([(case["question"], texts[i]) for i in dense_order])
        rerank_time = time.perf_counter() - start
        reranked = sorted(zip(dense_order, scores.tolist()), key=lambda item: (-item[1], item[0]))
        rows.append({
            "case_id": case["id"], "query_seconds": query_time, "rerank_seconds": rerank_time,
            "query_tokens": query_lengths[0], "max_pair_tokens": max(pair_lengths),
            "dense": [{"id": passages[i]["id"], "score": dense_scores[i]} for i in dense_order],
            "reranked": [{"id": passages[i]["id"], "logit": score} for i, score in reranked],
        })
    limits = {}
    for role, encoder, value in [("embedding", embedding, "word " * 300), ("reranker", reranker, ("query", "word " * 600))]:
        try:
            encoder.run([value])
        except ValueError:
            limits[role] = "rejected without truncation"
        else:
            raise RuntimeError(f"{role} silently accepted an oversized input")
    return {
        "embedding": embedding.identity(), "reranker": reranker.identity(),
        "embedding_load_with_checksum_seconds": embedding_load,
        "reranker_load_with_checksum_seconds": reranker_load,
        "documents": len(texts), "max_document_tokens": max(lengths),
        "embedding_first_batch_seconds": first, "embedding_warm_batch_seconds": repeat_times,
        "repeat_max_abs_delta": delta, "norm_min": float(np.linalg.norm(vectors, axis=1).min()),
        "norm_max": float(np.linalg.norm(vectors, axis=1).max()), "limit_checks": limits,
        "ranking_probes": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/results/models.json"))
    parser.add_argument("--schema-mode", choices=["legacy", "status"], default="legacy")
    args = parser.parse_args()
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    passages, cases = prepare(data)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "T02 supplied-excerpt model feasibility; not end-to-end retrieval",
        "dataset_sha256": sha256(DATASET), "models_lock_sha256": sha256(LOCK),
        "split": "dev", "holdout_used": False,
        "schema_mode": args.schema_mode,
        "packages": {name: importlib.metadata.version(name) for name in ["numpy", "onnxruntime", "tokenizers", "jsonschema"]},
        "settings": {"context_tokens": CONTEXT, "output_tokens": OUTPUT, "parallel_generation": 1,
                     "thinking": False, "temperature": 0, "seed": 42, "cache_prompt": False, "cpu_threads": 4},
        "server_properties": request("/props"), "generation": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    try:
        report["cpu_models"] = measure_encoders(passages, cases)
        print("CPU embeddings and reranking complete", flush=True)
        for label in ["first_pass", "warm_repeat"]:
            for case in cases:
                row = infer(case, passages, label, schema_mode=args.schema_mode)
                report["generation"].append(row)
                save()
                print(f"{label} {case['id']}: {row['wall_seconds']:.3f}s, schema={not row['schema_errors']}, facts={row['status_correct'] and row['fields_correct']}", flush=True)
        # Exercise a larger prompt near the 4K deployment limit using dev data only.
        long_case = next(c for c in cases if c["id"] == "q_pele_exact")
        padding = "Unrelated synthetic catalog note: the warehouse shelf is painted blue.\n" * 240
        report["long_context_probe"] = infer(long_case, passages, "long_context", padding, schema_mode=args.schema_mode)
        # The server itself must reject an oversized request when context shifting is off.
        try:
            request("/v1/chat/completions", {"model": MODEL, "messages": [{"role": "user", "content": "word " * 5000}], "max_tokens": 1})
        except HTTPError as error:
            report["server_overflow"] = {"http_status": error.code, "body": error.read().decode()}
            if error.code != 400:
                raise RuntimeError("Unexpected context overflow status") from error
        else:
            raise RuntimeError("Server did not reject an oversized prompt")
        rows = report["generation"] + [report["long_context_probe"]]
        report["technical_pass"] = all(not r["schema_errors"] and r["finish_reason"] == "stop" and r["references_valid"] for r in rows)
        report["cpu_process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["summary"] = {
            "requests": len(rows), "schema_valid": sum(not r["schema_errors"] for r in rows),
            "status_and_fields_correct": sum(r["status_correct"] and r["fields_correct"] for r in rows),
            "support_complete": sum(r["gold_support_complete"] is True for r in rows),
            "support_applicable": sum(r["gold_support_complete"] is not None for r in rows),
            "wall_median_seconds": float(np.median([r["wall_seconds"] for r in report["generation"]])),
        }
    except Exception as error:
        report["technical_pass"] = False
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()
    print(json.dumps(report["summary"]), flush=True)
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
