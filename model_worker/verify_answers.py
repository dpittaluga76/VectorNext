"""Explicit T08 development checks against a pre-ingested source corpus; no T01 labels."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def field(kind, **kwargs): return {"kind": kind, **kwargs}


def cases():
    match = {"year": field("integer"), "goals": field("integer"), "opponent": field("string")}
    return [
        ("pele", {"question": "How many goals did Pele score against Argentina in 1954?", "fields": match,
                  "template": "Match year {year}, Pele goals: {goals}, rival: {opponent}", "prose": True},
         "supported", {"year": 1954, "goals": 3, "opponent": "Argentina"}),
        ("conversation", {"question": "How many goals did he score in that match?", "history": [
            {"role": "user", "text": "I am asking about Pele against Argentina in 1954, not 1955."}], "fields": {"goals": field("integer")}},
         "supported", {"goals": 3}),
        ("ambiguous", {"question": "How many goals did Pele score against Argentina?", "fields": {"goals": field("integer")}}, "ambiguous", {}),
        ("absent", {"question": "How many goals did Pele score against Argentina in 1970?", "fields": {"goals": field("integer")}}, "insufficient_evidence", {}),
        ("json_zero", {"question": "How many goals did Iris Vega score against Lakeside in 2021?", "fields": {"goals": field("integer")}}, "supported", {"goals": 0}),
        ("json_null", {"question": "What raw JSON value is stored for Iris Vega's assists against Lakeside in 2021?", "fields": {"assists": field("integer", nullable=True)}}, "supported", {"assists": None}),
        ("json_unknown_count", {"question": "How many assists did Iris Vega make against Lakeside in 2021?", "fields": {"assists": field("integer")}}, "insufficient_evidence", {}),
        ("json_missing", {"question": "What raw JSON value is stored for Iris Vega's assists against Lakeside in 2022?", "fields": {"assists": field("integer", nullable=True)}}, "insufficient_evidence", {}),
        ("scan", {"question": "What torque should be used for connector J2?", "fields": {"torque": field("integer"), "unit": field("string")}}, "supported", {"torque": 6, "unit": "N m"}),
        ("cross_page", {"question": "How many minutes should one wait before restarting the Harbor H2 pump after code C7?", "fields": {"minutes": field("integer")}}, "supported", {"minutes": 8}),
        ("table", {"question": "What is the nominal flow of model H2 at water temperature 20 C? Include the flow unit.", "fields": {"flow": field("integer"), "unit": field("string")}}, "supported", {"flow": 12, "unit": "L/min"}),
        ("structured_null", {"question": "Read the raw goals and assists fields of record m-001.", "scope": "structured_lookup",
            "filter": {"Attribute": {"key": "record", "pointer": "/id", "predicate": {"Eq": "m-001"}, "trust": "SourceOrDeterministic"}},
            "fields": {"goals": field("integer", pointer="/stats/goals"), "assists": field("integer", nullable=True, pointer="/stats/assists")}}, "supported", {"goals": 0, "assists": None}),
        ("aggregate", {"question": "How many goals did Pele score in total?", "scope": "corpus_aggregate", "fields": {"goals": field("integer")}}, "rejected", {}),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("output")
    parser.add_argument("--case", action="append", dest="selected")
    args = parser.parse_args()
    root = Path(args.output); root.mkdir(parents=True, exist_ok=True)
    results = []
    for name, request, expected_status, expected_fields in cases():
        if args.selected and name not in args.selected: continue
        path = Path("/tmp") / f"t08-{name}.json"
        path.write_text(json.dumps(request), encoding="utf-8")
        start = time.monotonic()
        proc = subprocess.run(["ask", args.database, str(path)], capture_output=True, text=True, timeout=420)
        elapsed = time.monotonic() - start
        (root / (name + ".stdout.json")).write_text(proc.stdout, encoding="utf-8")
        (root / (name + ".stderr.txt")).write_text(proc.stderr, encoding="utf-8")
        report = json.loads(proc.stdout) if proc.returncode == 0 else None
        actual_status = report["answer"]["status"] if report else "rejected"
        actual_fields = {k: v["value"] for k, v in report["answer"]["fields"].items()} if report else {}
        prose_ok = (not request.get("prose") or (report is not None and report["presentation_draft"]["status"] == "draft"))
        result = {"case": name, "request": request, "exit_code": proc.returncode, "elapsed_seconds": elapsed, "prose_draft_returned": prose_ok,
                  "expected_status": expected_status, "expected_fields": expected_fields, "actual_status": actual_status,
                  "actual_fields": actual_fields, "schema_and_source_checks": report["validation"] if report else None,
                  "exact_answer_correct": actual_status == expected_status and actual_fields == expected_fields
                      and (expected_status != "rejected" or "corpus aggregation" in proc.stderr),
                  "report_file": name + ".stdout.json", "error": proc.stderr[-1500:] if proc.returncode else None}
        results.append(result)
        (root / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("case", "actual_status", "actual_fields", "exact_answer_correct", "elapsed_seconds")}), flush=True)
    if not all(r["exact_answer_correct"] and r["prose_draft_returned"] for r in results): raise SystemExit(1)


if __name__ == "__main__": main()
