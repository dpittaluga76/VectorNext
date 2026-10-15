# Human-readable workflow reports

T12 adds an optional Markdown view to the existing CLI. It explains ingestion, search and answering using recorded API results, without an extra model call. Start with the [Voyager workflow example](reports/t12-voyager-workflow.md).

## View a run

Build the updated application image using `docker compose -f compose.app.yaml build vectornext`. With the application ready, append `--explain` to an ingestion, job, wait, retry, search or ask command:

```sh
docker compose -f compose.app.yaml run --rm client ask /app/tests/fixtures/answers/voyager.json --explain
docker compose -f compose.app.yaml run --rm client search "Voyager 1 launch Jupiter Saturn" --limit 3 --explain
docker compose -f compose.app.yaml run --rm client job voyager-demo-v1 --explain
```

`--explain` prints readable Markdown instead of JSON. Without it, the CLI continues to print the original server bytes, including exact JSON numbers. The report shows the input, major steps, selected evidence and result. A failed operation still exits with a failure status.

## Save ingestion, search and answering together

Create a local output folder. The following PowerShell commands use fresh document/job IDs and new output files; select different names for another run:

```powershell
New-Item -ItemType Directory -Force data/workflows
docker compose -f compose.app.yaml run --rm -v "${PWD}/data/workflows:/reports" client ingest /app/evals/independent/fixtures/voyager1.txt --document voyager-workflow --job voyager-workflow-v1 --wait --report /reports/ingest.md --capture /reports/ingest.capture.json
docker compose -f compose.app.yaml run --rm -v "${PWD}/data/workflows:/reports" client search "Voyager 1 launch Jupiter Saturn" --limit 3 --report /reports/search.md --capture /reports/search.capture.json
docker compose -f compose.app.yaml run --rm -v "${PWD}/data/workflows:/reports" client ask /app/tests/fixtures/answers/voyager.json --report /reports/answer.md --capture /reports/answer.capture.json
docker compose -f compose.app.yaml run --rm -v "${PWD}/data/workflows:/reports" client explain /reports/ingest.capture.json /reports/search.capture.json /reports/answer.capture.json --report /reports/workflow.md
```

Read **`data/workflows/workflow.md`**. `--report` saves UTF-8 Markdown while retaining normal JSON stdout; `--capture` saves the exact response and limited context for later rendering. Existing destinations are refused before the operation begins. Reporting options do not scope the search to the newly uploaded file; queries use the current searchable corpus.

The final `explain` command only reads captures. It works with all services stopped and never contacts the API or loads a model. It can also run on a host with Python:

```sh
python -m deployment.client explain data/workflows/ingest.capture.json data/workflows/search.capture.json data/workflows/answer.capture.json --report data/workflows/workflow-copy.md
```

## What the report means

T13 extends the same reports with coordinator failure/restart instructions, PDF warnings before publication, rejected admission attempts and explicitly unvalidated answer drafts. See [recovery and failure diagnostics](reliability.md) and the [operational workflow example](reports/t13-operational-workflow.md). Old captures remain readable; missing diagnostic fields are never invented.

- **Ingestion** follows durable job stages: original saved, document read, chunks prepared, context applied, embeddings created and revision published. For committed jobs, an extra read-only document inspection supplies counts, format, model identity and PDF warnings. It must match the job's document and revision. A newer revision is never substituted.
- **Search** shows keyword/semantic candidates, filters, fusion and duplicate removal, then short source excerpts. Standalone search does not rerank or generate an answer.
- **Answering** includes conversation context actually used, reranking, evidence assembly, answerability, extraction, validation, formatting and optional prose drafts. Field values retain their types and numeric precision. Source quotes and locations stay separate from generated prose.
- **Invocation and code references** show the client arguments, API handler and high-level functions behind recorded steps. New captures save the original argument list; the equivalent Python command uses POSIX shell quoting, without reconstructing the outer Docker command or environment. Older captures remain readable and explicitly label missing arguments. The published Voyager example recovers its operation arguments from the saved run record, labeled accordingly. Code references describe the current implementation, not an instrumented call stack; skipped/unrecorded steps do not list calls. Replaying an old capture after a code change may therefore show newer implementation references.
- **Completed, skipped, failed and unrecorded** describe the available observations. Ingestion is reconstructed from the saved stage, not a live event timeline. Per-stage ingestion/search timings and embedding/reranking cache hits are currently unrecorded. Answer timings and cached prompt-token counts appear when the API supplies them; nested durations must not be added.
- An HTTP error often lacks a complete trace. The report preserves the error and marks earlier details unrecorded rather than assuming those steps never ran. Worker recovery and deeper error diagnostics remain T13.

Reports are bounded summaries; long passages and large result lists use labeled previews. Captures retain client arguments and the full response, which can include source text and vectors. Keep captures with the local documents they describe; repository examples contain only attributed public-source data. Validation is mechanical and does not independently establish factual correctness.

## Verification

Reporting and CLI regression checks run offline, without models:

```powershell
docker compose run --rm -v "${PWD}:/workspace:ro" evals python -m unittest deployment.test_workflow -v
```

They cover partial/failed jobs, revision mismatches, TXT/PDF/JSON details, source locations, ambiguity/abstention, exact numeric input/output, null versus the string `null`, safe Markdown rendering, offline replay, transport errors and refusal to overwrite captures. Invocation checks cover special-character quoting, old captures, recovered command provenance and code references for skipped/failed stages, including disabled reranking. See [T12 verification](reports/t12-workflow.md) for the fresh live demo and retained failure examples.
