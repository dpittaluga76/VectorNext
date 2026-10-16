# VectorNext active plan and handoff

Last updated: 2026-10-16 (UTC).
Design reference: [architecture.md](architecture.md).
Completed tasks and historical handoffs: [tasks-done.md](tasks-done.md).

## Current state

- **T01–T38 are complete.** Definitions and acceptance evidence are in [tasks-done.md](tasks-done.md); detailed results remain in [reports/](reports/).
- **Running defaults:** the healthy three-service `:t37-hybrid` deployment remains on localhost:8088. Hybrid uses repaired NuExtract3 with one queued Gemma 4 12B fallback; forced modes, two-call answering, f16 KV, MiniLM, structural ingestion and ranked 30/20/5 remain unchanged. [Hybrid verification and rollback](reports/t37-hybrid.md).
- **Available update:** API/client/admin now select the built `vectornext-app:t38`; processor/generator stay on `:t37-hybrid`. A later Start/Rebuild applies the new API. Normal services were not restarted, and the user library was not compacted during verification.
- **Offline maintenance:** `storage-plan` and explicit `compact --apply` preserve full ingestion history, retry receipts, revision reservations and provenance. Synthetic churn reclaimed **93.6%** of logical bytes; that is not a real-library savings guarantee. [Retention, backup and recovery](maintenance.md).
- **Verified:** 186 Rust checks, format/Clippy, twelve error and twelve process-kill boundaries, four isolated release CLI checks, 71 frozen HTTP cases, five browser boundaries, launcher and previous-binary smoke. Test containers/scratch volume removed; prior images and all user data retained. [Results and limitations](reports/t38-compaction.md).

## Active work

No implementation task is active. T38's complete scope and handoff are in [the archive](tasks-done.md#t38--safe-offline-compaction-and-garbage-collection). Full ingestion history and receipt/revision metadata still grow; maintenance requires downtime and temporary disk headroom. Interrupted workspaces need explicit inspection. No model-quality suites or historical holdout were used.

## Next useful step

Use the documented offline dry run during planned downtime to assess real-library reclaimable bytes before scheduling compaction. Further quality/performance work requires a separately selected scope; model-switch latency and broad semantic reliability remain limitations. ANN and storage novelty are deferred pending measured workload need.

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
