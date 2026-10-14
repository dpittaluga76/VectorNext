# VectorNext build plan and handoff

Last updated: 2026-10-14.
Design reference: [architecture.md](architecture.md).

## Current state

- Phase: architecture brainstorming and documentation.
- Implemented: no application code, model integration, ingestion pipeline, storage engine, UI, or Docker Compose deployment.
- Available: repository instructions, architecture proposal, and this task plan.
- User-confirmed scope: our own vector database; local models and GPU; Docker; TXT/PDF/JSON; approximately 400 files of 10–30 KB; MinIO/Redis optional.
- Proposed, not finalized: Rust core, Python processor, llama.cpp GPU service, Docling PDF parsing, exact vector search plus BM25, local reranking, selective contextual enrichment.
- Exact model artifacts, API/file formats, evaluation data, and quality/latency thresholds are not selected.

### Environment observations

Observed during discussion on 2026-10-14:

- NVIDIA RTX 4060, approximately 8 GB VRAM.
- Approximately 64 GB system RAM (63.1 GiB reported by the OS).
- Docker CLI installed; desktop-linux context present.
- WSL default distribution Ubuntu, default version 2.
- Docker engine was not reachable at the time of the check.

These observations are not ongoing blockers or proof of a working GPU container. Recheck when the task requires execution. No model was downloaded and no inference/container GPU test was performed.

## Next useful step

During continued brainstorming, resolve the highest-impact open design question requested by the user and update the architecture.

When implementation is requested, start with T01 (small synthetic fixtures and evaluation contracts), then T02 (local inference feasibility). Do not choose a large model or build the full stack before checking the 8 GB GPU budget. Complete a task's acceptance criteria and record evidence before marking it done.

## Work queue

All implementation tasks below are pending. Dependencies refer to task IDs, not to required separate chats or agents.

### T01 — Establish fixtures and evaluation contracts

Status: pending. Dependencies: none.

Create small synthetic TXT, PDF, and JSON fixtures with answer questions and exact supporting source references. Include a wrapped paragraph, a cross-page passage, a table with headers/units, a scanned page, nested JSON, and close-match distractors with different years/opponents. Include missing evidence and ambiguous questions.

Acceptance:

- Fixture content is synthetic or appropriately licensed and its origin is documented.
- Any Pelé/1954 example is explicitly hypothetical; do not treat it as verified sports history.
- Expected answers distinguish correct evidence, missing evidence, ambiguity, and exact structured values.
- Metrics distinguish parsing, candidate retrieval, reranking, answer extraction, and latency.
- A minimal evaluation schema and runnable validation command exist and are documented.

### T02 — Validate local models and GPU container execution

Status: pending. Dependencies: T01 for representative inputs.

Evaluate a small quantized local generation model and dedicated embedding/reranking candidates. Pin runtime images and model identities after checking current compatibility. Prepare a small repeatable Docker GPU smoke test.

Acceptance:

- NVIDIA device access and actual inference inside a container are demonstrated separately.
- Peak VRAM, context/output limits, cold start, and representative latency are recorded.
- Embeddings have reproducible dimensions and documented query/document encoding conventions.
- Reranking and structured extraction are exercised on representative fixtures.
- Model files persist outside container layers; normal inference works without remote model calls after setup.
- Commands, artifact versions, and limitations are recorded; no unsupported performance claims.

### T03 — Define core contracts and durable storage

Status: pending. Dependencies: T01; embedding configuration informed by T02.

Implement document/block/chunk records, source references, revisions, embedding-space identities, a write journal, and snapshots. Specify framing, checksums, commit/flush order, atomic publication, and recovery. Keep model operations outside transactions.

Acceptance:

- Round trips preserve text, typed metadata, provenance, and stored vectors.
- Crash/truncation tests distinguish committed batches from incomplete writes.
- Replacement is atomic to readers; deletion affects new query snapshots.
- Snapshot/replay restores state without rerunning an LLM or embedding model.
- Duplicate/retried operations and incompatible embedding configurations have explicit behavior.

### T04 — Implement exact and keyword retrieval

Status: pending. Dependencies: T03.

Implement exact vector search, BM25 postings, typed filters, ranking fusion, and candidate deduplication. Keep the core callable with supplied vectors so correctness tests do not require model inference.

Acceptance:

- Exact similarity results match an independent reference on meaningful fixtures, including ties and filtered subsets.
- Keyword, dense, and fused rankings can be inspected separately.
- Hidden/deleted revisions are not returned and embedding spaces cannot be mixed.
- Search evaluation records where relevant evidence enters or leaves the candidate set.

### T05 — Build TXT/JSON ingestion and durable jobs

Status: pending. Dependencies: T03; model stages can use deterministic substitutes until T07.

Implement the processor contract, job/stage persistence, source preservation, TXT block parsing, typed JSON records, and versioned chunking. Keep structural context separate from evidence.

Acceptance:

- TXT source mappings survive normalization and splitting.
- JSON retains types, null/missing distinction, record identity, and nested field meaning.
- JSON pointers are revision-scoped; large narrative fields stay linked to their records.
- Chunk inputs respect tokenizer limits, including context overhead.
- Restarting/retrying a job does not duplicate published records or expose partial revisions.

### T06 — Add PDF structure, tables, and OCR

Status: pending. Dependencies: T05.

Validate the proposed Docling adapter on fixtures, then integrate structure-preserving PDF extraction and local OCR in the CPU processor.

Acceptance:

- Native, scanned, and mixed-content fixtures produce traceable evidence without duplicate OCR/native text.
- Reading order, cross-page spans, table headers/units, and page coordinates are checked against the source.
- Partial/low-quality extraction is reported honestly; chart understanding is not implied.
- Parser/OCR models are pinned and available offline; processing resources are bounded.

### T07 — Integrate embeddings and contextualization

Status: pending. Dependencies: T02, T04, T05, T06.

Connect plain, structural, and generated-context ingestion modes. Add dedicated embeddings, model/version-aware cache identities, and complete revision publication.

Acceptance:

- Generated annotations remain distinguishable from original evidence.
- Context sources, prompts, and model versions are recorded.
- Changing a heading/context/model invalidates affected cached results appropriately.
- CPU/GPU stages can fail and resume without corrupting committed data.
- The same fixture corpus can be indexed under each policy for comparison.

### T08 — Add reranking, evidence assembly, and answers

Status: pending. Dependencies: T07.

Implement query embedding, reranking, context expansion, source-linked structured extraction, template formatting, optional prose rewriting, and explain output. Add a bounded generation scheduler with interactive priority.

Acceptance:

- Original question constraints survive rewriting and conversational reference resolution.
- Context assembly includes needed headers/labels and removes duplicate evidence within its budget.
- Supported, ambiguous, and insufficient-evidence cases are distinguishable.
- Schema validation, source-reference validity, and answer correctness are evaluated separately.
- Interactive requests are not indefinitely starved by ingestion; active-generation behavior is documented.
- Corpus-wide aggregates are not fabricated from top-k passages. Full structured aggregation remains explicit scope if implemented.

### T09 — Package the integrated Docker deployment

Status: pending. Dependencies: T02 through T08.

Package the three services with pinned images, persistent volumes, internal networking, configurable model paths, capability health/readiness, and a minimal API client or inspection interface. Earlier tasks may use partial Compose setups; this task validates the integrated deployment.

Acceptance:

- A documented fresh-start procedure works on the target host.
- GPU inference is proven in the integrated deployment, with only the intended service using GPU access initially.
- Restart/rebuild preserves documents, committed records, model files, and job progress.
- Search/answer capability failures are explicit and do not corrupt data.
- A consistent export/restore procedure is exercised; Docker volumes alone are not described as backups.

### T10 — Evaluate and tune the architecture

Status: pending. Dependencies: T09.

Compare plain, structural, and generated context on the same evaluation set and hardware. Tune chunking, candidate budgets, field weights, reranking, and model sizing from observed failures.

Acceptance:

- Report evidence recall, final relevance, answer accuracy/support, insufficient-evidence handling, ingestion time, per-stage/end-to-end latency, and peak memory.
- Separate cold/warm runs and include queue time and all local model processing costs.
- Preserve a held-out question set when tuning to reduce overfitting.
- Document what improved, what regressed, and what remains uncertain.
- Propose approximate indexes or additional infrastructure only against a demonstrated bottleneck.

## Session handoff discipline

Keep the Current state and Next useful step sections accurate. For each meaningful work session, add one concise entry below with changed files/capabilities, task IDs, verification actually performed, unresolved issues, and the next step. Do not paste full chat transcripts or command logs.

### 2026-10-14 — Initial repository handoff

- Captured confirmed requirements and the architecture proposal from the design conversation.
- Added AGENTS.md, this plan, and architecture.md; expanded README.md with navigation and resume prompts.
- Application code and implementation tasks remain untouched.
- Verification: all local Markdown links resolved; git diff --check passed; all four documentation files had no trailing whitespace. No application tests were run because no application exists yet.
- Next: continue the requested design discussion, or begin T01 when implementation is requested.
