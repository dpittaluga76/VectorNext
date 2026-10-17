# T39 — Measurement foundation: outcome scoring, latency and defaults

E0.1 and E0.2 are implemented. The remaining measurement epic stays active: independently labelled benchmark, pre-registered gates, oracle ablations and residue audit have not run. Architecture and plan were updated before implementation. NuExtract-only is now the running default by user choice; this is not a benchmark promotion claim.

## Offline outcome reporting

The new [measurement tool](../../evals/measurement/README.md) rescored **1,548 retained answer requests in 93 arm/cache-pass groups**, including all original 112-request/28-question and 96-request/16-question runs. It also reports **384 retrieval-only, 81 planner-only and 50 functional smoke/development observations separately**. None required inference. All 2,156 consumed input files were hashed and checked again before output. Historical sources, labels, manifests, captures, scores and the unused original holdout were not changed.

[Complete outcome matrix](t39-outcomes.md) · [Machine-readable results, cases and input identities](t39-measurement.json) · [Verification identities](t39-verification.json)

The matrix uses stricter source-supported correctness than an exact-answer-only score. For example:

| Historical block | Questions | Answered correct | Answered wrong under frozen support labels | Abstained correct | Abstained missed | System errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original independent suite, five/cold | 28 | 10 | 2 | 4 | 10 | 2 |
| Original coverage suite, five/cold | 16 | 6 | 1 | 2 | 7 | 0 |

The first row's supported/negative correct total is 14/28 under this metric; it does **not** replace the historical 16/28 exact-answer result. Original scores and reviewed source exceptions remain separate. In the retained Hybrid integration pilot, each mode has 6/8 strict frozen successes and **8/8 with its two already-reviewed exceptions**: PDF heading assembly and the pre-inference aggregation guard. Those are label/scorer distinctions, not newly discovered application regressions.

Every outcome has a Wilson 95% interval over distinct questions within its group. Repeated models, strategies and cache passes are not pooled as independent trials. Value correctness, annotated support, wrong negative categories, request declines and infrastructure failures remain distinguishable. **40 rejected drafts match the frozen gold values** across the repeated runs; this is not 40 unique questions or proof of 40 validator false rejections. A candidate can have correct values and an invalid quote or pointer. Unavailable/truncated drafts and unresolved JSON null placeholders are not guessed.

Coverage is explicit: pre-evaluation T02–T09 worker/smoke records have no comparable frozen answer labels; normal-library operational captures and the original holdout are excluded. Component experiments and source smokes receive their narrower checks, not invented end-to-end semantic labels. A fresh clone without local raw captures cannot reproduce unavailable runs; the report lists exact inputs and the tool processes available catalogued families. Missing planned responses in discovered blocks remain in the denominator. There were zero unscorable full-answer rows in this capture set; twelve recorded preflight failures with empty responses remain system errors.

## Where answer time goes

This table uses the retained 26B control's ranked-five cold block on the 16-question suite. It illustrates the reported 16–29-second range without rerunning the model.

| Observation | Median | Observed requests/calls |
| --- | ---: | ---: |
| End-to-end request | 29.51 s | 16 |
| Query embedding and token checks | 0.010 s | 16 |
| Candidate search, including filters/fusion | 0.00031 s | 16 |
| Reranking and preparation | 0.313 s | 16 |
| Evidence assembly and model tokenization | 0.627 s | 16 |
| Combined answer-model calls | 28.26 s | 16 |
| Assessment call, including its preparation | 14.29 s | 16 |
| Extraction call, including its preparation | 15.42 s | 12 |

Assessment/extraction are children of combined model time; they must not be added to it. Extraction is conditional, so those medians also have different denominators. Historical audits without inference-only durations remain labelled as whole calls. Per-request parent-bucket reconciliation is reported, not a fabricated allocation of residual time.

Durable-job captures show why inference and user-visible time need separate reporting:

| Retained integration mode | Median request wall time | Median attempt queue | Median attempt work |
| --- | ---: | ---: | ---: |
| NuExtract only | 46.68 s | 44.42 s | 3.50 s |
| Gemma only | 111.58 s | 104.90 s | 11.56 s |
| Hybrid | 15.39 s | 7.54 s | 3.39 s |

These were queued historical batches, not a new fair resident-model latency comparison. There are eight request rows per mode, seven admitted attempts in each forced mode and nine in Hybrid. Do not sum medians or describe warm NuExtract work as fallback latency. Hybrid's raw p95 includes the recorded overnight observer interruption (about 19,036 seconds); the tool preserves it instead of silently trimming it. Activation observations and sample counts remain in the JSON report.

New worker replies retain per-call preparation, inference and decoding/validation durations, input/output token counts and completed/failed state. Rust stores this optional internal measurement on durable attempt operations even when the worker returns an error. A killed worker or broken transport can still leave details unrecorded. Existing prompts, budgets, retrieval, validation and retry behavior are unchanged.

## NuExtract default and live checks

New API, CLI, browser and launcher questions use NuExtract-only. Explicit Gemma and Hybrid remain available. The browser and launcher visibly migrate the old default preference once, while historical turns and queued requests keep their original modes. New optional generated enrichment also uses NuExtract's native adapter and temperature 0.2. Structural ingestion remains the normal default.

Enrichment configuration now accepts exact JSON temperatures `0` and `0.2`. Old integer-zero serialization and saved Gemma identities are preserved; the worker matches a complete saved configuration to a supported profile before acquiring its lease. Existing Gemma enrichment remains at temperature 0. The scheduler validates the selected temperature for both foreground and background generation. Two-call answering, f16 KV, MiniLM, ranked 30/20/5 and the three-service layout remain unchanged.

Two synthetic API questions ran against an isolated database, sharing the normal supervisor's single GPU backend through leases:

| Question | Observed outcome | Job time | Recorded calls |
| --- | --- | ---: | --- |
| Farpoint station probe count | Supported, exact value `8` | 3.727 s | Planning, assessment, extraction |
| Follow-up asking for its director | Insufficient evidence despite an answer in the source | 2.330 s | Planning, assessment |

The missed follow-up is retained as a limitation; neither question was retried, and no prompt was tuned. An independent synthetic NuExtract enrichment operation succeeded. These are bounded integration observations, not an accuracy benchmark. The initial smoke assertion stopped on the missed follow-up; recovery read the existing durable jobs and performed only the not-yet-attempted enrichment check.

## Verification and rollout

- Final offline Rust suite: **176 main-suite tests passed**, with two intentionally ignored helper/benchmark tests; the spawned child-process check also passed. Formatting and Clippy passed. Exact fractional-temperature round trips, preserved old policy serialization, supported-policy upgrade guards and retained failure measurements have dedicated checks.
- Python: 48 worker/planner/scheduler/measurement checks passed, then 18 focused default-policy/supervisor checks passed after adding two new cases. Five standalone measurement/statistics checks and full historical adapter execution passed. Recorded denominators and reviewed integration exceptions were cross-checked.
- Frontend type/build and seven component checks passed. All thirteen offline Docker browser scenarios passed. An existing asynchronous clear-record assertion was corrected to wait for completion after its first run raced the request.
- Frozen HTTP compatibility covered 71 cases; five browser boundary checks and four CPU-worker transport checks passed. All 54 OpenAPI schemas validate; the documented answer-mode default is `nuextract`. Launcher migration/offline-start/stop checks passed.
- Initial release startup correctly failed on the old integer-only enrichment temperature contract. The exact-number extension was documented, tested and rebuilt before activation. Earlier reporting passes exposed pilot-subset and document-envelope adapter mistakes; corrected reports are published, and intermediate attempts remain locally retained. No failed run was reported as passing.

All three `:t39` images are built and running. Before activation, the API was stopped, a full-volume TAR was verified against all original file sizes/hashes, and a database export was created under ignored `backups/t39-preactivation-20261016/`. Previous image IDs remain available. The actual Windows launcher started the new deployment offline. Readiness reports NuExtract-only; the original **one-document library** and all **six historical answer-job summaries** compare equal before and after activation. No original-library question was used as a test fixture. Task-created verification containers were removed; no unrelated containers, images, weights or data were pruned.

Rollback to the immediately previous deployment, after finishing current work:

```powershell
docker compose -f compose.app.yaml -f backups/t39-preactivation-20261016/rollback.json up -d --no-build --pull never vectornext processor llm
```

That override pins the previous three image IDs and previous Hybrid server default. Browser preferences are independent: select Hybrid explicitly if desired. **The previous binary cannot read new generated-enrichment jobs using fractional temperature 0.2.** Before any later rollback, inspect saved policies; use the verified pre-activation export restored into a new destination if necessary, preserving newer data and answer-job history separately. Never overwrite a newer library with the backup. Existing structural/Gemma policies retain their old representation. The full-volume TAR also retains answer-job history, which ordinary database exports exclude.

## Next

T39 remains active. The [continuation report](t39-continuation.md) records the completed residue audit, declared protocol, 180-question proposal and tested capture/attribution tools. Independent case review and sealed custody are pending with Daniel Pittaluga / Architect before measured strategy/oracle comparisons. This work does not select a new evidence strategy, tune either model or establish broad semantic reliability.
