# VectorNext active plan and handoff

Last updated: 2026-10-16 (UTC).
Design reference: [architecture.md](architecture.md).
Completed tasks and historical handoffs: [tasks-done.md](tasks-done.md).

## Current state

- **T01–T37 are complete.** Definitions, acceptance criteria and historical handoffs are in [tasks-done.md](tasks-done.md); detailed evidence remains in [reports/](reports/).
- **Running defaults:** three-service `:t37-hybrid` deployment on localhost:8088. Hybrid uses repaired NuExtract3 first, with one queued Gemma 4 12B fallback. Forced Gemma/NuExtract modes are available. Two-call answering, f16 KV, MiniLM, structural ingestion and ranked 30/20/5 remain unchanged.
- **Latest result:** all 24 integration cases passed the predeclared scoring rules (**8/8 per mode**, unchanged historical scorer **6/8**). Hybrid accepted all five supported NuExtract answers and fell back on two of seven admitted questions. Common-supported median attempt work: **3.62/3.54/12.55 s** for Hybrid/NuExtract/Gemma. This excludes queue/loading; the missing-evidence fallback took **90.29 s**, including **60.94 s** loading. [Results, interruption and limits](reports/t37-hybrid.md).
- **Verified:** Rust regressions/format/Clippy; 89 Python checks; 71 frozen HTTP cases, five boundaries, three OpenAPI checks; six components and thirteen offline workspace plus two adapter/browser scenarios; launcher/scorer contracts and eleven retained CPU-profile checks. Six bounded live switching/cancellation/outage/restart checks passed; 236 process samples observed at most one backend. The PC-sleep observation stays in raw captures and correctness, excluded only from derived timing.
- **Activation and preservation:** full-volume copy plus export/restore verified; original PDF, 35 chunks, revision and ingestion jobs unchanged. Hybrid readiness, source-linked browser answer, original PDF, reload and export passed. A final browser-only readiness amendment is separately verified; Rust binary and all non-UI files match the measured image retained as `:t37-measured`. Prior images, private backup, all data/caches/freezes and 189-file public pre-cleanup archive are retained. Test services are stopped; original holdout unused.

## Active work

T37's full handoff is in [the completed archive](tasks-done.md#t37--hybrid-answering-with-queued-gemma-fallback). Use [answer-job contracts](answer-jobs.md) and [rollout/rollback instructions](reports/t37-hybrid.md) when operating the app.

**Repository configuration cleanup — complete.** Removed seven standalone experiment/verification Compose files; the README lists the five retained app/setup/developer configurations. [History and prior revision](tasks-done.md#experiment-compose-cleanup) preserve their purpose and recovery path, and affected guides identify deployment commands as historical. All five retained configurations passed `docker compose -f <file> config --quiet`; launcher references and 26 added local documentation links/anchors passed inspection. Supported configuration bytes, application code and frozen evaluation artifacts are unchanged; no services or GPU evaluations were run.

No active implementation work. The user confirmed that the reported disabled Ask button was not an issue; no fix is needed.

## Next useful step

Select and scope further quality/performance work; model-switch latency and broad semantic reliability remain explicit limitations.

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
