# VectorNext active plan and handoff

Last updated: 2026-10-17 (UTC).
Design reference: [architecture.md](architecture.md).
Completed tasks and historical handoffs: [tasks-done.md](tasks-done.md).

## Current state

- **T01–T38 are complete.** Definitions and acceptance evidence are in [tasks-done.md](tasks-done.md); detailed results remain in [reports/](reports/).
- **Running defaults:** all three `:t39` services are healthy on localhost:8088. New questions and optional generated enrichment default to NuExtract; Gemma/Hybrid remain explicit. Two-call answering, f16 KV, MiniLM, structural ingestion and ranked 30/20/5 remain unchanged. The original library and six historical answer jobs were preserved. [Measurement, default migration and rollback](reports/t39-measurement.md).
- **Measurement:** 1,548 historical answer requests rescored offline in 93 groups, plus separate component checks. No quality suite rerun or holdout use. Live default smoke: one supported answer and one missed follow-up, retained without retries; enrichment succeeded.
- **Offline maintenance:** `storage-plan` and explicit `compact --apply` preserve full ingestion history, retry receipts, revision reservations and provenance. Synthetic churn reclaimed **93.6%** of logical bytes; that is not a real-library savings guarantee. [Retention, backup and recovery](maintenance.md).
- **Verified:** final Rust suite (176 main-suite passes), format/Clippy, Python, launcher, 71 frozen HTTP cases, 54 OpenAPI schemas, seven UI components and thirteen offline browser scenarios. Verification containers removed; prior images and verified pre-activation backups retained. [Evidence and limitations](reports/t39-measurement.md#verification-and-rollout).

## Active work

### T39 — Measurement foundation and NuExtract defaults

Status: **Internal source review and confirmed-family reconciliation complete; T39 remains active.** All development gold decisions are applied, including 107's waived Level A definition. The user delegated candidate screening; all 60 T39 candidates were reviewed and are now exposed to the assistant. Four confirmed company overlaps exclude nine development table questions. Current primary rosters: **92 development + 55 exposed candidates = 147**; derived/stress/collision diagnostics remain separate. Source identities are established for all primary cases, but comprehensive lineage is uncertified. Independent/blind and minimum-primary-size acceptance have not passed. No candidate-model inference has occurred; the older original holdout is untouched. [Review, receipt and limits](reports/t39-internal-review-v1.7.md).

The private successor builder, exact job-to-scorer projection and source-coordinate mapper are implemented. All 591 package files reproduce; 172 offline Linux measurement tests pass. Retained captures verify 75 table evidence occurrences across 10 records. The isolated format/control worker and actual nine-row table pipeline checks are also verified; two formatted prompts have only 51 tokens of headroom. Runtime integration and execution are now authorized under the [v1.8 amendment](../evals/measurement/internal-execution-v1.8.md). Finish ingestion-bound snapshots, runner/control/oracle integration, commit the execution freeze, and run the measurements through the final report. [Current integration evidence](reports/t39-internal-successor-preflight.md). NuExtract/ranked-five defaults are unchanged. Depends on T37 diagnostics/jobs and T38 retention; [design](architecture.md#measurement-foundation).

The user accepted the six remaining recommendations. Applied 010/034/047/053 in a new gold candidate and moved 071 to stress: **101 primary, 3 derived/inference, 16 stress**, with original v1 n=120 preserved. Case 107's Level A definition is active under the explicit user waiver; no independent-review attestation is claimed. The v1.7 whole-family overlay supersedes those provisional counts; sources and historical freezes are unchanged. [Current gold activation](reports/t39-gold-review-v1.6.md) · [Earlier gold review](reports/t39-gold-review-v1.5.md) · [D1](reports/t39-d1-adjudication-v1.1.md) · [D2](reports/t39-d2-adjudication-v1.1.md) · [D3 tiers](reports/t39-d3-tiers-v1.1.md) · [D4 typed facts](reports/t39-d4-typed-facts-v1.1.md) · [D5 context/proofs](reports/t39-d5-table-context-v1.2.md) · [D6 families](reports/t39-d6-families-v1.3.md) · [D7 scope/controls](reports/t39-d7-pilot-scope-v1.4.md) · [Answer sheet](reviews/t39-review-decisions.md).

| Item | Scope and acceptance | Status |
| --- | --- | --- |
| E0.1 Outcome matrix | Offline adapters inventory/rescore available historical raw captures, including the 16/28-question suites, without inference or source/label changes. Preserve legacy scores separately; exact values/support, four outcomes, errors/unscorable cases and rejected-gold diagnostics; Wilson intervals over distinct questions per arm/pass, explicit missing-capture denominators. | Complete; scope/limits in report |
| E0.2 Stage latency | Reuse and complete recorded stage/model audits; report per-request/attempt queue/load/work, planning/retrieval/rerank/assembly/assess/extract/validation, input/output tokens and unknown overhead without double counting. Produce current-mode and historical tables; include failures and distinguish missing/skipped. | Complete; scope/limits in report |
| Defaults | NuExtract-only for new API/CLI/browser/launcher submissions and NuExtract for new optional enrichment/model tools. Keep explicit Gemma/Hybrid and exact saved modes/policies; visible one-time preference migration. Verify native annotation adapter and old Gemma compatibility; structural ingestion remains default. | Complete; scope/limits in report |
| E0.3 Benchmark v2 | 150–300 questions, 25–30% negatives/ambiguity, at least 30% sealed by source family; public human labels, independently reviewed adaptations/custody, exact typed scoring and hashed inputs. | Original 180 preserved; development 92 primary / 3 derived / 16 stress / 9 collision diagnostics, candidates 55 / 2 / 3. Internal review and known collisions recorded; no blind/independent claim, full lineage uncertified, primary count 3 below target. Runtime integration/freeze pending |
| E0.4 Oracle ablations | Gold evidence and optional gold field definitions; identical captured candidate for validator comparison; preserve JSON materialization. Attribute ingestion/planning/retrieval/selection/assessment/extraction/validation, allowing multiple causes. | Capture, Rust comparison, attribution and isolated format/control worker tested; real controls/ablations pending internal-successor integration and final freeze |
| E0.5 Decision gate | Predeclare margin, D5 typed-value primary metric plus separate grounding/joint metrics and harmful-answer ceiling, paired/grouped comparison, sample-size adequacy and inconclusive outcome before measurements. Compare strategies in current NuExtract mode. | Protocol/statistics, successor builder and scorer/coordinate projections tested; live runner/control integration and committed freeze pending. Pilot cannot establish predeclared non-inferiority; retain ranked-five |
| E0.6 Residue audit | Isolated ingest/replace/remove before/after compaction; explain retained blobs/jobs/receipts and captured diagnostics under preserve-history-v1, separating search removal from erasure. | Complete: both originals/jobs, 3 receipts and 2 revision reservations retained; 1 unreferenced blob reclaimed. [Audit](reports/t39-residue.md) |

Verification: deterministic scorer/statistics/adapter tests, recorded latency reconciliation, exact numeric preservation, missing/malformed captures and failures, historical capture hash checks; relevant Rust/Python/HTTP/UI/launcher checks for defaults/instrumentation. Use isolated storage and one reusable test container at a time. No historical inference reruns, prompt tuning, new dataset acquisition or sealed holdout use for E0.1/E0.2. Any required live default smoke is bounded and separate from quality scoring. Record results/limits before completing each item; T39 stays active until its remaining approved work is complete.

Progress: E0.1/E0.2 and defaults verified; [results](reports/t39-measurement.md), [outcome matrix](reports/t39-outcomes.md). Retained narrower planner/retrieval/functional tracks are separate from full-answer denominators; pre-evaluation smoke records without comparable labels and normal-library captures are excluded. The live follow-up abstention is an observed limitation, not tuned away. No independent benchmark has run.

## Next useful step

Use the reproduced internal successor with v1.6 development gold, the v1.7 family overlay and private reviewed candidate records. No external receipt is awaited and no independent attestation may be fabricated. Carry exposure, lineage and quota limitations into every result. No reserve was drawn. Connect the tested evaluation worker and scorer/coordinate projections to the isolated durable-job runner and ingestion-bound snapshots; preserve original-label and v1 representation ablations. Freeze runtime/code/input hashes and the D7 control prompt/schema/scorer with final rosters before measured requests.

Use isolated sources and one GPU model at a time. Run one question-only control per final primary item/model, then development strategy/oracle comparisons, retaining failures and unknown controls; report exposed-candidate results separately. Actual table splitting/reranking/token checks are complete, but final planned fields still require normal token admission. [Budget evidence](reports/t39-table-pipeline-preflight.md). No real-layout extension is selected. The inadequate sample and exposed split prevent strategy-promotion/generalization claims. T39 is not complete; ANN and storage novelty remain deferred.

The items below are **proposed**, not scheduled or started. Assign the next task ID and define its scope, dependencies and acceptance criteria when the user selects work.

| Proposed work | Depends on | Purpose / decision needed |
| --- | --- | --- |
| NuExtract assessment consistency | T35, T36 | Scope separately if fresh results confirm inconsistent missing-evidence classification; do not change assessment during the planning comparison. |
| Confirm MiniLM / Ettin-17M | T32 | Check the observed evidence gain, negatives, ambiguity, format/token boundaries and latency on a small fresh set; keep defaults until a documented decision. |
| Reconcile chunk and reranker budgets | T32 | Address whole JSON records that fit Nomic's embedding window but exceed reranker admission. Preserve exact source values/evidence and explicit failures; scope the design before another Nomic comparison. |
| Clarification and ambiguity evaluation | Completed retrieval/answer work | Scope a separate clarification workflow and clearly worded ambiguity cases. Candidate retrieval coverage alone does not establish answerability. |

## Task tracking rules

1. Follow [architecture.md](architecture.md) and the current user request. Update the design first when a selected task changes a confirmed requirement or contract.
2. Keep only current status, active/approved upcoming tasks and a short proposed backlog here. Give each active task an ID, status, dependencies, scope, acceptance criteria, verification/progress and next concrete step.
3. Record actual checks and remaining issues. Mark complete only when acceptance criteria are met; preserve negative results and failures honestly.
4. Move a completed task's full entry and final handoff into [tasks-done.md](tasks-done.md). Keep only a concise current-state update here and link detailed reports; do not append a running session diary to this file.
5. Preserve task IDs, historical source/label/execution freezes, captures, scores, source-review exceptions and rollback instructions. The original holdout remains unused. Run only the checks and experiments appropriate to the authorized task.
6. Update README commands and architecture contracts when affected. Keep historical activation records in the archive distinct from the currently running deployment.

### Active-task entry format

```markdown
### Txx — Task title
Status: planned / in progress / blocked. Depends on: ...
Scope: ...
Acceptance: ...
Progress and verification: ...
Remaining issues: ...
Next concrete step: ...
```
