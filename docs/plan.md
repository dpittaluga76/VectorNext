# VectorNext active plan and handoff

Last updated: 2026-10-17 (UTC).
Design reference: [architecture.md](architecture.md).
Completed tasks: [tasks-done.md](tasks-done.md).

## Current state

- **T01–T39 are complete within their recorded scopes.** T39 closes the authorized
  internal pilot; its original independent/blind and minimum-size criteria were
  not met. [Completion and waivers](tasks-done.md#t39--measurement-foundation-and-nuextract-defaults).
- **Running app:** three healthy services at localhost:8088. NuExtract is the
  default and currently loaded model; explicit Gemma/Hybrid remain available.
  Two-call answering, f16 KV, MiniLM, structural ingestion and ranked 30/20/5 stay.
  Library, ingestion jobs and six historical answer-job summaries survived exactly.
- **Latest measurement:** strict five/two/facet development scores 17/92, 16/92,
  18/92; ranked-five exposed candidates 6/55. String-plan and field-mapping
  contract failures materially limit interpretation. Neither candidate qualifies.
  [Results](reports/t39-internal-results/README.md) · [Findings](reports/t39-internal-results/findings.md).
- **Verification:** 181 frozen measurement checks and 22 final offline checks;
  Rust main suite, helpers, formatting/Clippy. Initial HTTP timing-bound failure
  and passing unchanged rerun retained. Earlier HTTP/OpenAPI/browser/default
  verification is recorded in [the migration report](reports/t39-measurement.md).
- **Retention:** test containers/networks removed; private captures, failed attempts,
  evaluation volumes, model files, images and rollback copies preserved. Offline
  compaction preserves ingestion history/retry guarantees; [maintenance](maintenance.md).

## Active work

None. No evaluation process or external review approval is pending. T39's
remaining independent-validation, sensitivity-review and stress-adjudication
limitations are documented; they were not silently counted as passed.

## Next useful decision

Prioritize the automatic-planner/measurement-contract mismatch before further
retrieval tuning. Numeric plans violate this benchmark's string-only contract;
valid-looking field names outside its frozen lists also fail. Unsupported-plan
responses need separate source-grounded review. A follow-up must distinguish app
behavior from benchmark formatting, freeze fresh cases before running, and retain
these results unchanged. Do not tune this exposed pilot into a claimed gain.

These are **proposals**, not scheduled tasks. Assign an ID and update architecture,
scope and acceptance when the user selects one.

| Proposed work | Dependency | Decision / purpose |
| --- | --- | --- |
| Planner and measurement-contract alignment | T39 | Define fair automatic-field/typed-value scoring and inspect overbroad unsupported decisions; use fresh fixtures. |
| Independent benchmark successor | T39 | Fresh custody/review, source-family separation, adequate size and real-layout PDF probe if the claim requires it. |
| NuExtract assessment consistency | T35–T39 | Investigate missed answers with verified evidence; preserve frozen prompts until a separate experiment is approved. |
| Confirm MiniLM / Ettin-17M | T32 | Small fresh recall/negative/token-boundary comparison; keep defaults pending evidence. |
| Reconcile chunk and reranker budgets | T32 | Whole JSON records must fit both embedding and reranker admission without losing exact source evidence. |
| Clarification and ambiguity workflow | Retrieval/answer work | Evaluate explicit ambiguity handling separately from ordinary factual extraction. |

ANN indexes and storage novelty remain deferred until a real workload justifies
investment. The original unused holdout remains untouched.

## Task tracking rules

1. Follow [architecture.md](architecture.md) and the current user request; update
   design before changing a confirmed contract.
2. Keep only current state, active/approved tasks and a short proposed backlog here.
   Active entries need ID, status, dependencies, scope, acceptance, verification,
   remaining issues and next action.
3. Record actual failures, unknowns and waivers. Complete only the authorized scope;
   never describe an unmet criterion as passed.
4. Move completed specifications/handoffs to [tasks-done.md](tasks-done.md), with
   detailed evidence in `docs/reports/`. Preserve historical freezes and captures.
5. Update current README commands and architecture when affected. Do not append
   experiment diaries to AGENTS.md or run unapproved follow-up evaluations.
