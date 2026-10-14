"""Integration smoke run on source fixtures only. Never loads evaluation labels."""
import argparse
import json
from pathlib import Path
import subprocess
import time

SOURCES = [
    ("fictional", "fictional_matches.txt", "-", ""),
    ("array", "array_matches.json", "-", ""),
    ("nested", "nested_matches.json", "-", "/matches"),
    ("equipment", "equipment_guide.pdf", "tests/fixtures/pdf/equipment_guide.json", ""),
    ("scan", "scanned_note.pdf", "tests/fixtures/pdf/scanned_note.json", ""),
]


def run(*args):
    p = subprocess.run(["model_ingest", *args], capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {"kind": "integration smoke, not retrieval/answer quality", "runs": [], "annotations": [], "probes": {}}
    start = time.perf_counter()
    for policy in ("plain", "structural", "generated"):
        database = str(Path(args.root) / policy)
        for name, filename, artifact, pointer in SOURCES:
            summary = run(database, name, "evals/fixtures/" + filename, name + "-v1", policy, artifact, pointer)
            summary["policy"] = policy
            result["runs"].append(summary)
            print(json.dumps(summary), flush=True)
        inspected = run("inspect", database)
        assert inspected["generation"] == 5 and len(inspected["documents"]) == 5
        for doc in inspected["documents"]:
            for chunk in doc["chunks"]:
                assert len(next(iter(chunk["vectors"].values()))) == 384
                if chunk["generated_context"]:
                    result["annotations"].append({"document": doc["document_id"], "chunk": chunk["id"],
                                                  "evidence": chunk["evidence"], "annotation": chunk["generated_context"]["text"]})
        # Technical query-embedding/index smoke probe, not a scored evaluation question.
        probe = run("probe", database, "equipment temperature and pressure limits", policy)
        assert probe["trace"]["generation"] == 5 and probe["trace"]["dense_scored"] > 0
        assert probe["passages"] and probe["passages"][0]["key"]["document_id"] == "equipment"
        result["probes"][policy] = probe
    result["seconds"] = time.perf_counter() - start
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__": main()
