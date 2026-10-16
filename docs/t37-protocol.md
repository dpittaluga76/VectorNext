# Hybrid answering integration protocol

This is a bounded current-runtime regression check, not an independent quality benchmark. It reuses the eight observed synthetic cases and five exact TXT/JSON/PDF source files in `experiments/t36/`, without changing their bytes, requests, labels or original scores. The original holdout stays unused.

## Freeze before measured requests

`python -m experiments.t37.run freeze --run pilot-v1` records public runtime/scorer/source hashes, dirty-tree HEAD, all three image IDs, model locks/profiles, Compose configuration and hardware. The runner verifies those identities before ingestion and measured execution. Source archives and interrupted attempts are retained; measured requests are never retried into success. A repeat needs a new run name and empty storage.

Only the normal app's generation service is temporarily stopped for this check; document browsing stays available. Unrelated workloads are left untouched. The dedicated `vectornext-t37` project uses port 8097 and its own database/cache volumes. Exactly one GPU backend is permitted at a time. Restore the previous generator after evaluation until rollout is decided.

## Corpus and 24 questions

Ingest the five retained sources once with structural context; retain every ingestion failure in applicable denominators. Save committed documents/chunks/revisions before questions. In fixed request-file order, submit all eight questions in each mode, in the order **Hybrid, NuExtract only, Gemma only**. Poll durable job IDs; uncertain submissions are reconciled, never blindly resent. Jobs retain original history, document scope and request options. All three modes use the same corpus and candidate images. No prompt tuning or retrieval changes are allowed during the run.

Each mode denominator is eight. Seven cases can invoke planning; the aggregation case must receive the existing pre-inference 400 rejection and earns no model-planning credit. Track planning, validated answers, exact values/projections and source support separately. Retain all transport/model errors and negative outcomes.

The T37 scorer composes the unchanged T36 scorer with two corrections declared **before** T37 inference:

1. `aggregate_sum`: accept only the exact 400 `invalid_request` envelope saying `invalid record: aggregate question requires an unsupported corpus aggregation operation`. This is an API guard, not a model success.
2. `pdf_pressure`: permit the heading-expanded evidence only after checking the original PDF SHA-256, exact page-one heading, revision-matched PDF provenance, chunk ID, exact assembled text and spans. All original field cardinality, type, value, projection and factual-support checks still apply. This fixes the prior scorer's mismatch with legitimate evidence assembly; it does not loosen the application's proof validator.

Report both unchanged historical scoring and the corrected T37 result. No other label exceptions or post-run scorer edits are permitted. A mechanically validated plausible mistake can avoid Hybrid fallback; no semantic judge is added.

## Timing and operational checks

Capture every submission/result as exact bytes, job transitions, both attempt identities/diagnostics, fallback reasons, token usage and operation timings. Report queue wait, activation, attempt work, successful generation-call time and end-to-end latency separately. Attempt work includes CPU retrieval and generation; it is not pure inference. Model audit `inference_seconds` measures the generation HTTP call; missing audits on failures remain unavailable, never zero. Batch queue time and cold model loading are part of user-visible latency. Warm NuExtract latency must not be presented as fallback cost.

Sample GPU memory/utilization and host RAM throughout execution. Record backend processes during a separate bounded switching/outage drill. Verify NuExtract → Gemma → NuExtract, cancellation, an interrupted backend and recovery with no overlapping models. Synthetic operational requests are separate from the 24 scored questions. Deterministic mocks cover adversarial failures, fairness/quota/restart and proof rejection.

## Rollout

Run relevant Rust/Python, HTTP/OpenAPI, launcher, frontend and offline browser checks. Preserve previous images, export under the exclusive writer lock, verify restoration to a new destination, check unfinished ingestion policies, then activate Hybrid and verify the original library and one source-linked answer. Database exports exclude operational answer-job history; that sibling directory needs a separate stopped-volume copy when preserving it. Record all outcomes and limitations before completing T37.
