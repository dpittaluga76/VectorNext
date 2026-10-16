# VectorNext active plan and handoff

Last updated: 2026-10-16 (UTC).
Design reference: [architecture.md](architecture.md).
Completed tasks and historical handoffs: [tasks-done.md](tasks-done.md).

## Current state

- **T01–T32 are complete.** Their task definitions, acceptance criteria and verification history are in the completed-task archive; detailed measurements remain in [reports/](reports/).
- **Running defaults:** three-service local deployment on `:t28-12b`, Gemma 4 12B, two-call answering, f16 KV, MiniLM embeddings and reranking, structural ingestion and ranked 30/20/5 retrieval. Facet coverage remains opt-in.
- **Latest result:** the 24-request Nomic/Ettin pilot favors MiniLM embeddings with Ettin reranking for further confirmation. Frozen correctness improved 4/6 → 5/6 and median latency 12.80 → 9.68 s; six unique questions do not establish broad quality. Both Nomic arms encountered the 512-token reranker limit. [Results and separate source review](reports/t32-replacements.md).
- **Verification:** T32 passed 64 Python and 163 top-level Rust checks plus offline packaging. The normal library is unchanged; experiment containers are stopped and captures/volumes retained.
- **Deployment boundary:** experimental model profiles and the numeric-range repair in current source have not been activated in the normal app. Publishing source changes does not change the running deployment.

## Active work

No implementation or evaluation task is currently in progress. The plan/archive cleanup is complete. No new benchmark, model promotion or deployment is authorized by this tracker.

## Next useful step

Recommended: scope a short, fresh confirmation of **MiniLM embeddings + Ettin-17M reranking**, comparing it with the current MiniLM baseline before deciding whether to promote Ettin. This replaces the reranker only; finding an embedding replacement remains separate work.

The items below are **proposed**, not scheduled or started. Assign the next task ID and define its scope, dependencies and acceptance criteria when the user selects work.

| Proposed work | Depends on | Purpose / decision needed |
| --- | --- | --- |
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
