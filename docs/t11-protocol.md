# T11 independent source evaluation

Status: frozen before inference. Design reference: architecture sections 6–10. This protocol is written before inference on the new corpus.

The [pre-query parser amendment](t11-protocol-amendment-01.md) records a UTF-8 ingestion crash, preserved original attempt, minimal correctness repair and replacement code freeze. The source/question/label freeze is unchanged; no model comparison had run when the repair was made.

## Question and scope

Compare `primary_limit=2` against the unchanged default `primary_limit=5` on independently sourced public facts. Keep structural ingestion, 30 candidates per search branch, 20 reranked candidates, models, prompts, temperature 0, seed, source bytes, chunks and vectors fixed. Do not tune retrieval, prompts or labels after seeing comparison outcomes. Preserve T01/T10 sources, labels, reports and six unused holdout questions.

The corpus contains 16 attributed NASA mission TXT snapshots, two original NASA PDFs, and two original USGS earthquake JSON responses. Its 28 questions comprise 23 supported, two ambiguous, and three insufficient-evidence cases, including four questions requiring three or four source documents. It is independent of the old synthetic corpus, not an independently administered benchmark or proof that the generator has never seen these public facts. Codex authored questions and source references before querying; supporting evidence is required even for familiar facts. URLs, acquisition times, original/derived hashes and transformations are recorded. Keep downloaded third-party content under its source terms, separate from the repository code license.

Include direct facts, similar-mission distractors, exact JSON values/types, PDF evidence, ambiguous and unavailable facts, and questions needing at least three distinct source passages. Use all frozen comparison cases; a separate public request file carries only the original questions, requested field schemas and optional templates. Gold values and evidence locations must never enter prompts or indexes. Freeze source, request, label and code/model identities before the first comparison request. The former six holdout cases remain unused.

## Execution

Use the dedicated `vectornext-t11` Docker project, localhost port 8091 and its own database/cache volumes. Ingest the corpus once. Preserve every ingestion failure and apply the same resulting corpus to both variants; do not silently remove difficult documents. If a document cannot be ingested, report its dependent cases as unavailable rather than dropping them from the planned denominator.

Execute four complete query blocks in counterbalanced order: five/cold, two/cold, two/warm, five/warm. Cold means a fresh CPU/API process and empty variant processing cache with model weights loaded; warm reuses that variant's prior disk cache after process recreation. Record this scope and uncontrolled OS caches. Do not reuse generated answers. No separate model-size, chunking or generated-context trial is part of T11. Other workloads can affect latency; record observed device activity and do not stop unrelated processes.

## Scoring and decision

Report per-question outcomes and paired differences, not repeated calls as independent questions. Retain exact typed-field/status/template results separately from reviewed source support, raw chunk recall, recall with original labels, and final-context completeness. Record source coverage for multi-passage cases explicitly; a correct fact recalled without cited source support is not a supported success. Use the existing source-aware scorer, with any new equivalence rules fixed before inference. Retain raw strings and exact-match scores even if a date spelling/alias is separately judged equivalent. Report failures in denominators.

Measure end-to-end latency, prepared/actual model tokens, per-stage costs, queues and sampled memory. Describe nested timings and sampling limits. Source review is Codex inspection, not independent human adjudication. A small corpus cannot establish tail latency or statistical non-inferiority.

The default stays five unless two preserves every supported, ambiguous and insufficient-evidence outcome in both passes, loses no complete source support (especially on multi-passage questions), and reduces median response latency by at least 20%. Even a pass supports an opt-in recommendation on this corpus; changing the general default requires broader evidence. Any additional lost supported answer or source coverage is enough to retain five. If both variants fail, identify the stage and record follow-up work rather than tuning on the frozen comparison.

## Deliverables

- Versioned source snapshots/provenance, public requests, labels, validation and reproducible runner.
- Complete two-versus-five report, source review, retained failures and exact run identities.
- A real, cited, exercised README example replacing the fictional Pelé quickstart; retain old synthetic regression fixtures unchanged.
- Updated architecture/plan/handoff with actual results and remaining limitations.
