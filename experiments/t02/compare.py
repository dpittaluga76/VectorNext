"""Compare completed T02 reports only after checking identical request payloads."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics

from .benchmark import DATASET, canonical, prepare, request_payload
from .fetch_models import sha256


def digest(payload):
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def compare(baseline, candidate, comparison="model"):
    old = baseline["model_checks"]
    old_schema, new_schema = old.get("schema_mode", "legacy"), candidate.get("schema_mode", "legacy")
    old_alias = old["server_properties"]["model_alias"]
    if comparison == "model":
        if old_schema != new_schema:
            raise ValueError("Model comparisons require the same schema")
    elif comparison == "schema":
        if old_schema != "legacy" or new_schema != "status":
            raise ValueError("Expected legacy-to-status schema comparison")
        if old["models_lock_sha256"] != candidate["models_lock_sha256"] or old_alias != candidate["server_properties"]["model_alias"]:
            raise ValueError("Schema comparisons require the same model")
    else:
        raise ValueError("Unknown comparison kind")
    if old["dataset_sha256"] != candidate["dataset_sha256"] or sha256(DATASET) != candidate["dataset_sha256"]:
        raise ValueError("Dataset revisions differ")
    if old["settings"] != candidate["settings"]:
        raise ValueError("Generation settings differ")
    if old["packages"] != candidate["packages"] or any(old["cpu_models"][role] != candidate["cpu_models"][role] for role in ["embedding", "reranker"]):
        raise ValueError("CPU model identities or package versions differ")
    if old["holdout_used"] or candidate["holdout_used"]:
        raise ValueError("Holdout data must not be used")
    passages, cases = prepare(json.loads(DATASET.read_text()))
    cases = {case["id"]: case for case in cases}

    def index(report):
        rows = report["generation"] + [report["long_context_probe"]]
        expected = {(case, label) for case in cases for label in ["first_pass", "warm_repeat"]} | {("q_pele_exact", "long_context")}
        result = {(row["case_id"], row["run"]): row for row in rows}
        if len(result) != len(rows) or set(result) != expected:
            raise ValueError("Incomplete or duplicated comparison cases")
        return result

    old_rows, new_rows = index(old), index(candidate)
    comparisons = []
    for key, before in old_rows.items():
        after = new_rows[key]
        padding = "Unrelated synthetic catalog note: the warehouse shelf is painted blue.\n" * 240 if key[1] == "long_context" else ""
        payload, _ = request_payload(cases[key[0]], passages, padding, model=old_alias, schema_mode=old_schema)
        if digest(payload) != before["prompt_sha256"]:
            raise ValueError(f"Baseline prompt changed for {key}")
        expected_new, _ = request_payload(cases[key[0]], passages, padding, model=old_alias, schema_mode=new_schema)
        # Reconstruct both exact contracts; no unrestricted permission to change prompts.
        del expected_new["model"]
        if digest(expected_new) != after["model_independent_prompt_sha256"]:
            raise ValueError(f"Candidate prompt differs for {key}")
        comparisons.append({
            "case_id": key[0], "run": key[1],
            "baseline_correct": before["status_correct"] and before["fields_correct"],
            "candidate_correct": after["status_correct"] and after["fields_correct"],
            "baseline_seconds": before["wall_seconds"], "candidate_seconds": after["wall_seconds"],
        })

    def summary(report):
        rows = report["generation"]
        result = {"summary_including_long_probe": report["summary"], "passes": {}}
        for label in ["first_pass", "warm_repeat"]:
            subset = [row for row in rows if row["run"] == label]
            result["passes"][label] = {
                "questions": len(subset),
                "status_correct": sum(row["status_correct"] for row in subset),
                "status_and_fields_correct": sum(row["status_correct"] and row["fields_correct"] for row in subset),
                "median_seconds": statistics.median(row["wall_seconds"] for row in subset),
            }
        return result

    return {
        "comparison_kind": comparison,
        "same_payload_except_model_alias": comparison == "model",
        "same_payload_except_response_schema": comparison == "schema",
        "verified_request_pairs": len(comparisons),
        "same_dataset_and_settings": True, "holdout_used": False,
        "baseline": summary(old), "candidate": summary(candidate), "cases": comparisons,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", choices=["model", "schema"], default="model")
    args = parser.parse_args()
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()), args.comparison)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
