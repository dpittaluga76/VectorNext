# Ingestion recovery and failure diagnostics

T13 follows [the architecture](architecture.md). It makes operational failures visible while preserving strict PDF admission, durable job identities and answer validation. Start with the [recorded operational workflow](reports/t13-operational-workflow.md) or [verification report](reports/t13-reliability.md).

## Inspect a stopped workflow

Rebuild the API/client and CPU processor after updating the repository:

```powershell
docker compose -f compose.app.yaml build vectornext processor
docker compose -f compose.app.yaml up -d vectornext processor
docker compose -f compose.app.yaml run --rm client ready
docker compose -f compose.app.yaml run --rm client job YOUR_JOB_ID --explain
```

`/readyz` includes `storage.coordinator`: `not_started`, `running`, `failed` or `stopped`, with an error and recovery instruction when failed. `/v1/job` and `/v1/jobs` also expose this state. A coordinator panic or unrecoverable coordinator error is caught and stops ingestion admission; it cannot silently disappear while readiness stays true. Storage readiness remains separate. Healthy committed documents can still be inspected/searched. The client stops waiting when it observes a failed/stopped coordinator and exits with failure for unfinished work.

Restart the API to recover a failed coordinator. It reopens the database and resumes unfinished stages that have no saved failure:

```powershell
docker compose -f compose.app.yaml restart vectornext
docker compose -f compose.app.yaml run --rm client ready
```

A job with `last_failure` still requires explicit retry after its cause is addressed:

```powershell
docker compose -f compose.app.yaml run --rm client retry YOUR_JOB_ID --busy-retries 3 --explain
docker compose -f compose.app.yaml run --rm client wait YOUR_JOB_ID --explain
```

Coordinator state is process-local; saved job stages/failures remain durable. Restarting clears the process-local failure state. A poisoned database mutex is not cleared in place. Ordinary saved job failures do not kill the coordinator or block unrelated jobs. A coordinator failure during uncertain storage work still requires reopening storage.

## Busy admission

`ingest` and `retry` retry only HTTP 503 errors explicitly identified as `busy`. The default budget is three retries (four total attempts), with 1, 2 and 4 second delays. `--busy-retries 0` disables retries; the maximum is five (15 seconds of scheduled delay). Actual operation time is additional. The same payload and job ID are reused.

Every rejected admission is printed to stderr, including the attempt number and next delay or exhausted budget. With `--capture`, all such attempts are also saved in `context.admission_attempts`; `--explain`/`--report` show them. Normal JSON stdout remains the final server response with exact numeric literals preserved. Pre-admission failures are client-side observations, not durable jobs; retain the capture for an audit trail.

Transport timeouts, unknown outcomes, generic unavailable capabilities and validation failures are never automatically retried. A busy error inside an already accepted job becomes a durable stage failure and needs explicit `retry`. This avoids an unbounded background retry loop. An identical completed upload continues to return its original publication receipt.

## Review partial PDFs before accepting text

Job inspection reads the saved, hash-checked PDF artifact even if strict ingestion failed before parsing/publication. `pdf_diagnostics` includes extraction status, page native/OCR counts and confidence, warning locations, source/artifact identity, the immutable partial-text policy and an actionable next step. The API exposes up to 100 warnings with bounded messages and a total count; the report previews eight. The original artifact keeps all diagnostics.

Strict ingestion still rejects partial extraction. After reviewing warnings, explicitly opt in using **a new job ID**:

```powershell
docker compose -f compose.app.yaml run --rm -v "${PWD}/documents:/input:ro" client ingest /input/example.pdf --document example --job example-partial-v2 --allow-partial --wait --explain
```

Changing `--allow-partial` under the original job ID is rejected. If replacing an already committed document, also supply its current `--expected-revision`. Partial-text publication keeps all warnings and source locations. It does not interpret illustrations or establish that OCR is correct. Failed conversion before an artifact exists still has no page-level report.

## Inspect a rejected answer

Missing selected JSON pointers and quoted-value/schema/source validation failures return HTTP 400 with `error.code = "answer_rejected"`. `error.diagnostics` includes the failing phase, original question and requested fields, an **unvalidated draft**, selected evidence previews/locations and a review instruction. There is no top-level `answer` or formatted result in that error response.

Diagnostics retain exact typed JSON values. Drafts larger than 32 KiB use a labeled preview; selected evidence is capped at ten groups, 1,200 text characters and twelve source references per group. These are diagnostic summaries, not complete prompt dumps. Other errors without a produced candidate retain their existing error envelope. `ask --explain` and saved reports display these failures without promoting the draft to a supported answer. No inference is added and validation rules are unchanged.

## Reproduce the operational drill

The drill uses project `vectornext-t13`, port 8093, `/storage/reliability`, existing local model assets and a **fresh dedicated volume**. It refuses existing jobs/data or a reused capture directory. It stops/restarts only this project's API/CPU services and never removes volumes. Keep an earlier volume and its captures; use a separate checkout/environment for another clean run rather than deleting them.

```powershell
docker compose -f compose.app.yaml -f compose.reliability.yaml -p vectornext-t13 build vectornext processor
docker compose -f compose.app.yaml -f compose.reliability.yaml -p vectornext-t13 up -d --no-deps processor vectornext
python -m deployment.reliability --run my-fresh-run
docker compose -f compose.app.yaml -f compose.reliability.yaml -p vectornext-t13 stop vectornext processor
```

The host runner drives containerized services; it never opens the database directly. It uses CPU embeddings and real NASA Apollo/Perseverance PDFs, deliberately overlaps uploads, kills the API during work, exercises a processor outage, explicitly retries, and checks publication receipts and the unchanged committed Voyager revision. It starts no generation service. Panic supervision and rejected-answer drafts are checked separately using deterministic Rust fixtures, not a new GPU quality evaluation.
