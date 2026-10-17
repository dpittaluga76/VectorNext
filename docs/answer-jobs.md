# Durable answer jobs

The Rust API owns answer routing and source validation. The CPU processor never decides whether a rejected answer deserves fallback. The GPU supervisor owns one backend and grants an identity-bound lease for each complete attempt.

## Submit and reconcile

```http
POST /v1/answer-jobs
Content-Type: application/json
X-VectorNext-Client: 1

{"request_id":"a-stable-client-uuid","mode":"hybrid","kind":"ui","payload":{"question":"What was the recorded launch date?","document_ids":["your-document-id"]}}
```

Use a fresh 16–128-character ASCII alphanumeric/hyphen ID. Keep it and the original payload until acknowledged. The response is HTTP 202 with a durable job view. `GET /v1/answer-jobs/{request_id}` reconciles an interrupted submission and polls its result. Identical normalized submissions return the same record; conflicting ID reuse returns 409. A transport failure is not evidence that submission failed: reconcile before any explicit resubmission. Input/queue admission errors do not start fallback.

`kind: "structured"` wraps the existing `/v1/ask` body (`request`, optional `options` and `space_id`). `kind: "ui"` wraps the existing `/v1/ui/ask` body (question, document IDs, optional history, fields, template, prose and options). Put `mode` on the outer submission. Omitted mode is NuExtract-only; explicit alternatives are `gemma` and `hybrid`. Legacy synchronous endpoints also accept an optional top-level mode and wait on this same coordinator. They retain their existing status/result contracts; structured reports gain `answer_job` diagnostics, and browser reports include these inside opaque `raw_report` text.

`GET /v1/answer-jobs` returns summaries, unfinished count, capacity, retention usage and queue health. Full individual records contain both attempt states, exact original responses, identities, fallback reason and `diagnostics_text` for export. `response_text` holds the final exact response JSON. Browser jobs also expose `result`, whose answer values are text plus types. Do not parse and reserialize exact response/diagnostic text with JavaScript numbers.

```http
POST /v1/answer-jobs/a-stable-client-uuid/cancel
Content-Type: application/json
X-VectorNext-Client: 1

{}
```

Cancellation immediately removes waiting work. An active backend call finishes; a cancelled lease rejects subsequent template/token/generation operations, including extraction after assessment inside the same worker RPC. `POST .../clear` with `{}` removes only a terminal record. Clear is explicit and does not cancel active work. Unknown IDs return 404. Retained records are never automatically evicted.

## Routing, revisions and recovery

Hybrid tries repaired NuExtract3 first. Only a supported factual answer that passes existing schema, exact-value and source-proof validation ends the route. Model declines, ambiguity, insufficient evidence, malformed output, rejected proofs and model failures can use one Gemma attempt. Invalid requests, pre-inference unsupported operations, stale document bindings, cancellation and admission failures finish directly. Forced modes never cross models. Gemma independently plans automatic fields from the original question/history; explicitly supplied fields stay unchanged. No rejected NuExtract draft enters the next attempt or conversation context. Prose remains optional and cannot invalidate already supported facts.

The coordinator stores exact requests and selected document revisions, not an alias for the current library. Both attempts use those bindings. If a required revision changes or cannot be reconstructed after restart, the job becomes stale. Newly added documents never silently join an existing job's search universe. Captured browser evidence remains historical after source replacement/removal.

Queued jobs resume after restart. A loading/running attempt is marked uncertain rather than replayed. An interrupted Hybrid NuExtract attempt can spend its one remaining Gemma attempt after the generation backend is reconciled. An interrupted Gemma or forced-model attempt requires a new explicit submission. Coordinator/storage failure stops admission until restart; it never clears poisoned state in place. Cancellation remains durable across recovery.

## Bounds and recorded time

The HTTP semaphore still admits 16 requests immediately, independently of the 16-unfinished-answer limit. Each unfinished record reserves 16 MiB inside the total 256 MiB retention quota. Terminal records consume their actual encoded bytes. Consequently retained history can reduce available unfinished capacity; export and clear terminal records when full. Records use atomic replacement, file/directory sync and checksum verification under the API's exclusive writer ownership.

The model batch switches when empty, after four attempts with opposite-model work waiting, or after 30 seconds of opposite-model waiting once the active attempt finishes. Waiting 15 minutes before the next attempt starts produces `queue_timeout`. Interactive leases outrank waiting background enrichment, without preempting inference. Model activation can take up to 240 seconds; existing operation deadlines remain in force.

Attempt `queue_ms` measures waiting before that attempt is selected. `activation_ms` records backend switching/verification/loading; `work_ms` includes CPU retrieval plus model operations after activation. Generation audits record `inference_seconds`, token usage and available backend timings. These quantities are distinct from total user-visible latency. Failures with no generation audit have unknown inference time, not zero. Loading/waiting states are recorded operational states, not progress percentages or model reasoning.

## Files, browser history and rollback

For `/storage/db`, operational records live in `/storage/db.answer-jobs` on the same durable API volume. **Database export/restore excludes answer-job history.** Preserve it separately with a stopped-volume copy if required. Removing the database while leaving its sibling job directory is not a fresh evaluation: use a new volume/project. Model weights and disposable caches remain outside database exports.

Conversations, captured evidence, mode and pending IDs stay in IndexedDB for this browser origin. Reload polls saved IDs. An atomic pending-turn reservation prevents concurrent unfinished turns in the same conversation across tabs; full concurrent-tab history merging remains unsupported. Export conversations before clearing browser data. Other conversations and API callers may queue concurrently. A browser storage failure prevents a new question from being submitted without its saved identity.

Setup installs both pinned models. Start performs no build/download, validates saved ingestion generator policies before replacing services and leaves incompatible jobs untouched. New optional generated enrichment uses NuExtract at temperature 0.2. Existing enrichment retains its exact saved identity, including Gemma at temperature 0; both remain supported. See the [integration protocol](t37-protocol.md), [architecture](architecture.md) and [rollout report](reports/t37-hybrid.md) for verified backup, activation and rollback evidence.

Attempt operations now preserve optional version-1 `model_measurement` observations: stage, completed/failed state, preparation/inference/decoding durations and observed input/output tokens. They survive normal worker error responses; lost processes/transports can still leave stages unknown. These are children of attempt work time, not additional elapsed time. Exact result/diagnostic text remains authoritative. See [measurement definitions](../evals/measurement/README.md) and the [current default migration/rollback](reports/t39-measurement.md).
