# Hybrid answering, durable jobs and one GPU backend

Date: 2026-10-16. Design: [architecture](../architecture.md). Contracts: [answer jobs](../answer-jobs.md). Protocol: [pre-run freeze](../t37-protocol.md). Reproduction: [commands and retained attempts](../../experiments/t37/README.md). Measurements: [JSON](t37-hybrid.json).

## Candidate and scope

The Rust application now owns Hybrid routing after schema, exact-value and source-proof validation. It accepts supported NuExtract facts or queues exactly one independent Gemma attempt. Forced modes never cross models. Invalid requests and deterministic unsupported operations do not become fallbacks. Optional prose errors preserve validated facts. Rejected drafts never enter evidence or conversation history.

The separate durable coordinator provides stable request identities, revision bindings, cancellation, batching, quota reservations and restart recovery without replaying uncertain attempts. A supervisor leases one GPU backend for a complete attempt, reaps it before switching and reconciles uncertain state before reuse. The browser/CLI use durable jobs; the synchronous API remains a compatibility adapter. Runtime remains three services with Axum/Tokio/utoipa, local assets, CPU MiniLM embeddings/reranking and unchanged ranked 30/20/5 retrieval.

Only Gemma 4 12B QAT Q4_0 and repaired NuExtract3 Q4_K_M are supported. Keep their temperatures 0/0.2, seed 42, two-call assessment/extraction, 4,096-token context, one slot, f16 KV and disabled prompt caching. Optional generated ingestion still has its original Gemma identity. Setup prepares both models; Start is offline and checks saved ingestion policies before replacing services.

The candidate froze **150 files and three image IDs** before inference. All five retained TXT/JSON/PDF sources committed once into isolated storage. Each mode used that same corpus. The image IDs and source ZIP hash are in the measurements. No prompt tuning, measured-request retries, historical large-suite rerun or original holdout use occurred.

## All 24 scheduled outcomes

| Case | Hybrid | NuExtract only | Gemma only |
| --- | --- | --- | --- |
| Requested berth count with identifying constraints | Supported, NuExtract | Supported | Supported |
| PDF pressure with page/heading evidence | Supported, NuExtract | Supported | Supported |
| Explicitly requested identifying fields | Supported, NuExtract | Supported | Supported |
| Follow-up draft measurement | Supported, NuExtract | Supported | Supported |
| Exact integer `9007199254741237` | Supported, NuExtract | Supported | Supported |
| Unknown manual count | NuExtract → Gemma; insufficient evidence | Insufficient evidence | Insufficient evidence |
| Unresolved subject | NuExtract → Gemma; clarification | Clarification | Clarification |
| Unsupported corpus aggregation | Pre-inference 400; no model attempt | Same | Same |
| Correct under predeclared integration scoring | **8/8** | **8/8** | **8/8** |
| Unchanged prior scorer | **6/8** | **6/8** | **6/8** |

The two scoring corrections were declared before inference: verify legitimate PDF heading-expanded evidence against its exact original provenance, and recognize the existing aggregation API guard without giving model-planning credit. Historical scores/labels were not rewritten. These are five supported factual answers and three correct negative/API outcomes per mode, not eight factual answers. Hybrid used fallback for **2/7 admitted questions** (2/8 scheduled); all five supported NuExtract answers skipped Gemma.

This small internally authored, previously observed regression set establishes integration behavior, not broad answer quality. A plausible wrong answer that passes the existing mechanical checks can avoid fallback. There is no extra semantic judge.

## Latency, queueing and memory

Each arm submits its eight requests as a batch. Hybrid starts with NuExtract already resident; the later forced arms include model switching. These end-to-end figures are operational batch observations, not a controlled warm per-question speed comparison.

| Measurement | Hybrid | NuExtract only | Gemma only |
| --- | ---: | ---: | ---: |
| Common five supported cases: median attempt work | 3.62 s | 3.54 s | 12.55 s |
| Common five supported cases: p95 attempt work (five samples) | 5.88 s | 6.03 s | 18.13 s |
| Admitted, sleep-excluded: median user-visible time | 15.39 s (6) | 48.48 s (7) | 118.00 s (7) |
| Admitted, sleep-excluded: p95 user-visible time | 90.29 s | 55.09 s | 141.96 s |

Attempt work includes CPU retrieval and model operations after activation; it is not pure inference. The JSON report separately provides generation HTTP time, queue time and loading time. The missing-count Hybrid fallback took **90.29 s**: **20.34 s queueing + 60.94 s activation + 8.42 s attempt work**, plus observation/coordination overhead. Gemma activation elsewhere took 64.39–64.45 s; NuExtract activation took 28.13–30.84 s. Do not describe the roughly 3.6-second NuExtract path as the cost of fallback. Five-case p95 is the maximum observation, not a stable tail estimate.

One Hybrid clarification crossed overnight PC sleep, which the user confirmed. Its original **19,036.12-second** observation and full result remain intact. The observer hit its deadline, then a resumed terminal observation hit the same deadline check; subsequent resume reconciled the existing record and continued unattempted questions. No measured question was resubmitted. That turn remains in correctness and is excluded only from the separate derived timing summaries; the raw summary is unchanged. System sleep is not counted as an application/backend failure.

Across **125 device/host samples**, peak whole-device memory was **7,735 / 8,188 MiB**, leaving 453 MiB at that sample. Minimum available host RAM was 16,303,087,616 bytes and maximum host RAM load was 75%. These include other machine activity and are not model allocation measurements. Sampling pauses during sleep. WDDM paging was not instrumented; no claim of a comfortable memory margin or absence of paging is made.

## Verification and rollout status

Offline checks passed: Rust all-target regressions, twelve final focused queue/routing/recovery/cancellation/upgrade checks, formatting and Clippy; 89 Python checks covering assets, worker, scheduler, supervisor, processor, workflow and reliability; 71 frozen HTTP cases, five boundary checks and three OpenAPI checks; six frontend components, TypeScript/Vite build, thirteen offline workspace scenarios and two real-adapter documentation/browser scenarios. Ten scorer checks and launcher contracts also passed. Eleven retained BGE/Nomic/Ettin CPU profile checks additionally passed after moving the shared encoders, including exact legacy identities, real token limits, pooling and scoring-head behavior; their first invocation lacked the required read-only model mount and was corrected without modifying artifacts. The new production setup image also verified all 14 existing CPU/Gemma/NuExtract artifacts by size and SHA-256 with networking disabled and the model mount read-only; no weights were downloaded or changed. Tests use isolated storage and synthetic processors when inference is unnecessary.

Initial verification exposed mock compatibility, readiness schema, narrow-layout and cancellation-race defects. Those were fixed and relevant checks rerun before the final candidate freeze. Cancellation now survives concurrent activation/outcome updates and blocks subsequent internal generation stages after an active call finishes. The generated-policy guard rejects incompatible unfinished jobs without rewriting them.

The separate live drill passed all six checks: NuExtract → Gemma → NuExtract, cancellation of a queued job with zero attempts, killing the active NuExtract backend followed by exactly one supported Gemma fallback, and killing/restarting the API during NuExtract followed by an `interrupted_uncertain` record and exactly one Gemma attempt. No uncertain attempt replayed. **236 process samples observed at most one backend**, with no sampling errors. Failed activation/artifacts/aliases, leases, background priority, active-call cancellation and queue fairness/quota/staleness are covered deterministically by the offline tests. Sampling alone does not prove absence of every sub-second overlap; stop/reap ownership and its unit tests provide the stronger invariant.

The isolated project was stopped, all its volumes/captures retained, and the old normal generator was restored and checked healthy. Prior image IDs remain available and additionally tagged `:pre-t37`. With the API stopped, a complete volume TAR was hash-verified, the database was exported, and restoration into a new volume produced an exactly equal snapshot and ingestion-job listing. The saved-generator compatibility check passed. Backup: ignored `backups/t37-preactivation-20261016/`; independent restored volume: `vectornext_t37_rollback_verified`. The JSON report records archive/manifest hashes. Original library: **one PDF, 35 chunks, generation 1**; document bytes, revision and ingestion jobs compare equal before/after activation. No private source content is included in this public report.

The actual Windows launcher `-Action Start -AnswerMode hybrid -NoBrowser` activated all three services without builds/downloads. Both model artifacts, queue readiness and default Hybrid mode were verified. A live browser question on the existing PDF produced a supported NuExtract answer with clickable evidence, revision-checked original PDF access, exact diagnostic export and persistence after reload. The first browser helper failed when it passed a relative PDF URL to a client without a base URL, after already receiving/inspecting a valid answer; its captures remain. A separately retained helper attempt fixed URL resolution and completed the operational checks. Those two normal-library questions are outside the 24-case evaluation, as are five executed drill questions and one cancelled queued submission.

Final visual review found a stale “Local Gemma” readiness label and missing separate queue/model indicators. A **browser-only release amendment** fixes those labels/layout, displays both installed models versus the loaded one, and disables questions on a failed answer queue while preserving browsing. Six component checks, type/build checks and all thirteen offline browser scenarios passed afterward. The release API image is `sha256:9a67837dfd711b4f73bc4d3fab47db55b52ffc987d57c34dd279155ca40f4c90`; the measured image remains tagged `vectornext-app:t37-measured`. Hash comparison confirms that the Rust binary and every non-UI application file are identical; processor/generator images are unchanged. Only `frontend/src/App.tsx` and `frontend/src/style.css` differ among the original frozen files. Final desktop/narrow-layout readiness and library inspection passed against the release with zero new inference or external requests. The original freeze is deliberately unchanged; verify/reproduce it with its source ZIP and retained measured image, not the amended release tag.

A network-disabled rebuild attempt missed a dependency-fetch build-cache entry and failed before producing an image. The ordinary explicit build reused cached dependencies and succeeded. This does not change the offline routine-Start contract; all normal runtime/browser checks used local assets.

### Rollback on this machine

The generated local override pins all three original image IDs and the old `12b` processor/generator setting; its resolved Compose configuration was checked against the retained container inspection. Finish/cancel current jobs and export their diagnostics if needed, then:

```powershell
docker compose -f compose.app.yaml stop vectornext processor llm
docker compose -f compose.app.yaml -f backups/t37-preactivation-20261016/rollback.json up -d --no-build --pull never vectornext processor llm
```

There is no database-format change in this task. The old application can use the same database; it does not expose the sibling answer-job history, which remains on disk. For an untouched pre-activation database, use the already verified copy instead:

```powershell
docker compose -f compose.app.yaml stop vectornext
docker compose -f compose.app.yaml run --rm --no-deps --pull never admin restore /backups/t37-preactivation-20261016/export /storage/rollback-t37
$env:VECTORNEXT_DATA='/storage/rollback-t37'
docker compose -f compose.app.yaml -f backups/t37-preactivation-20261016/rollback.json up -d --no-build --pull never vectornext processor llm
```

The restore target must not already exist; choose another new path rather than overwrite it. Keep the environment setting for subsequent recreations. To return to Hybrid, stop the old services, use the normal launcher without the rollback override, and retain whichever explicit data path you intend. Do not delete volumes or silently substitute a backup for newer user documents. Existing artifacts, the full-volume TAR and original image tags remain retained.

## Preserved history and remaining limits

The [public pre-Hybrid archive](../../archives/llm/) contains 189 exact working-tree source files, including uncommitted experiment code. Its SHA-256 is `9585937fe45ff80b81cee01554e36e85ee6e08898386f75681e44854208578ec`; per-file hashes and the removed-runner inventory are retained. Historical reports, protocols, sources, labels, scores and artifact locks remain. Production encoders/downloads/locks now live in `model_assets`; old generator choices and experiment switches are absent from active configuration. Embedding/reranking experiments, downloaded weights, images, private data and rollback copies are retained.

Answer-job exports preserve exact diagnostic JSON text; database exports deliberately exclude the sibling operational answer-job directory. Browser conversations remain local to IndexedDB. Atomic reservations prevent two unfinished turns in one conversation, but full concurrent-tab history merging is still unsupported. Cancellation is non-preemptive, queue retention can fill, and a model switch has substantial cold cost. Forced interrupted work needs explicit resubmission. A coordinator or uncertain lease-release failure fails closed until restart.
