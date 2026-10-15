# VectorNext build plan and handoff

Last updated: 2026-10-15.
Design reference: [architecture.md](architecture.md).

## Current state

- Phase: T01 through T23 complete. Architecture/task definitions were updated before implementation. Production retrieval defaults are unchanged after T23; scope final evidence selection on new data next.
- T23 complete: twelve fresh attributed NIST sources, 24 frozen questions and 96 offline CPU requests; 188 chunks admitted. Expanded candidates improve complete shortlist coverage 18/20 → 20/20, but final-five coverage remains 16/20 in both arms. Five scorer checks, one experimental Rust check, fixture/source freezes, format/Clippy and synthetic smoke passed. [Results and source-review limits](reports/t23-evidence.md). All experiment containers exited; data/caches retained, normal app unchanged.
- T22 complete: immutable bounded scalar/document/media filter postings, exact scan fallback and unchanged search/API contracts. Verified 135 Rust checks, format/Clippy, 4,224 paired release requests, retained original volume hashes and offline production startup. [Results](reports/t22-filters.md). Compose selects built T22 API; normal app remains on T19.
- T21 complete: bounded version-2 checkpoint stream with legacy reads, unchanged publication/journal/backup contracts and nine new regressions. Both formerly failing T20 states checkpoint/export/restore correctly on fresh copies; 132 Rust and 768 exact-query checks passed. Old-binary rollback requires a pre-upgrade copy; batch/job and total backup limits remain. [Results](reports/t21-checkpoints.md). T21 services stopped; original T20 data unchanged; normal app still running T19, with Compose selecting the built T21 API image for the next startup.
- T20 complete: isolated CPU comparison at 12,800/51,200 supplied vectors, independent exact oracle, pgvector exact/HNSW, fixed filters, load/resource measurements and interruption recovery. All 4,096 timed requests completed; 2,048 exact requests and 512 recovery checks passed. PostgreSQL exact was faster in every warm group. VectorNext checkpoints failed at both sizes (64 MiB frame); journal recovery passed, but the dependent export path is blocked at those states. Verified 123 Rust/eight Python checks, format/Clippy, builds, smoke and manifests. [Results and limitations](reports/t20-pgvector.md). All benchmark services stopped; failed attempts, data and volumes retained; normal application unchanged.
- T15 complete: exact English numeric grouping, named-month date-year boundaries and numeric-fragment checks in complete supplied evidence. Preserves quotes/typed values, JSON pointer/null semantics and API/storage contracts. Verified 108 Rust/90 Python checks, format/lint, the three-case probe, release image build/liveness and T14 archive integrity. [Results](reports/t15-numeric-proofs.md). No GPU benchmark rerun or revised T14 quality score.
- T14 complete: opt-in field-focused selection and actual-record JSON pointer constraints, annotation v2 and a new eight-source/16-question frozen comparison. All 96 local requests completed: five 8/16, two 7/16, coverage 8/16 in each pass. Coverage cut median latency 43.5–44.4%; retain five by default. [Results](reports/t14-evidence-coverage.md), [workflow](reports/t14-coverage-workflow.md) and [source-review limitations](reports/t14-source-review.md). All T14 services stopped; volumes/captures retained. 101 Rust/116 Python checks passed; a separate probe exposed numeric proof-boundary defects for T15.
- T13 complete: supervised coordinator, pre-publication PDF diagnostics, bounded busy-admission retries and rejected-answer error envelopes. Verified 97 Rust/90 Python checks and a fresh CPU operational drill with real illustrated NASA PDFs, interruption/retry, unchanged committed data and idempotent publication. [Results and limits](reports/t13-reliability.md). Test services stopped; captures and volumes retained.
- Implemented: Rust storage/retrieval and TXT/JSON/PDF ingestion, durable jobs, and 66 foundation tests (18 storage, 20 TXT/JSON/job durability, 8 PDF, 18 retrieval, 2 diagnostic); offline CPU Docling/Tesseract adapter with 13 tests; synthetic fixtures/schema/validator and 27 T01 tests; an offline Docker local-model experiment with pinned downloads, GPU generation, CPU embeddings/reranking, 11 T02 contract tests, optional status-dependent output constraints, and archived measurements.
- T07 implemented: real MiniLM embeddings, three context policies, separately attributed Gemma 4 26B annotations, bounded caches, Docker ingestion/inspection/probe tools, seven additional Rust tests and five Python worker tests. Total core checks: 73.
- T08 implemented: snapshot-scoped hybrid retrieval/CPU reranking, budgeted source evidence assembly, two-stage Gemma answers, exact JSON pointer reads, source/type checks, deterministic templates, separate prose drafts, complete filtered structured lookup, and bounded generation priority. Ten additional Rust tests bring the core total to 83; Python worker/answer/scheduler coverage totals 18. All 13 source-authored development cases passed; see [T08 results](reports/t08-answers.md) for qualifications and prior failures.
- T09 implemented: shared Rust API/database owner, isolated CPU service with bounded lanes, local client, capability readiness, three-service Compose, and offline checksummed export/restore. Six new Rust checks bring the total to 89; four CPU transport checks bring Python worker coverage to 22. Integrated TXT/JSON/PDF ingestion, actual GPU answers, full model outages, restart/rebuild, interrupted work and exact restoration passed; see [T09 results](reports/t09-deployment.md).
- T10 complete: isolated evaluation runner, source-coverage/answer scorer, independent keyword weights, bounded answer budgets and stage/resource/queue measurements. Six configurations produced 156 responses on the same 13 development questions, cold/warm; only one-primary context failed the table question in both passes. Two primaries passed 26/26 and reduced median response time by 30–32%, but five remain the general default. Generated context added ingestion cost without final answer gain. The 400-document/12,800-vector capacity probe measured 9.946-ms median hybrid search; this is supplied-vector capacity, not corpus quality. Verified 90 Rust, 36 fixture/scorer and 22 worker/transport checks, Linux formatting/Clippy and Compose. See [T10 results](reports/t10-evaluation.md). Six holdout questions remain unused.
- T11 complete: 20 attributed NASA/USGS source snapshots, 28 frozen questions, 47 source references and four counterbalanced two-versus-five blocks. Admitted 18 documents / 658 chunks; six questions from unavailable PDFs remain in the denominator. Five scored 16/28 and two 15/28 in both passes. Two cut median latency by 46–50% but lost two answers and improved one; retain five by default. Repaired a UTF-8 line-mapping panic before any comparison queries and preserved the initial attempt. Verified 91 Rust, 54 evaluation and 22 worker/transport checks, formatting/Clippy, Compose and the real NASA Voyager README demo. See [T11 results](reports/t11-independent.md). This first public-source set is Codex-authored, not independently administered; broad quality remains unproven.
- T12 complete: opt-in human-readable ingestion/search/answer reports, client commands, API/function references, exact-response captures and offline replay in the existing CLI. Verified 25 new reporting/client checks and 58 existing evaluation/transport checks, a fresh Docker Voyager ingestion/search/Gemma answer, and retained failure/abstention examples. Command references were added through offline replay without new inference. Read [the Voyager report](reports/t12-voyager-workflow.md), [usage guide](workflow-debugging.md) and [verification](reports/t12-workflow.md). T12 services are stopped; captures and volumes retained. The original T11 execution freeze remains unchanged; the intentional client extension requires a historical checkout to repeat that exact experiment.
- Not implemented: public authentication/multi-user service, corpus aggregates, approximate indexing, or broad independently administered quality validation.
- Available: public project overview and quickstart in the [README](../README.md), detailed [development/operations commands](development.md), repository instructions, architecture, this task plan, the [storage specification](storage.md), [retrieval specification](retrieval.md), [source-coverage diagnostics](reports/t04-retrieval.md), and [evaluation guide](../evals/README.md).
- User-confirmed scope: our own vector database; local models and GPU; Docker; TXT/PDF/JSON; approximately 400 files of 10–30 KB; MinIO/Redis optional.
- Adopted: Rust storage/retrieval and deterministic TXT/JSON preparation, CPU Python Docling/Tesseract PDF artifacts, source-preserving PDF chunking and partial-quality policy, serializable processor stages, separate durable jobs, version-1 journal/checkpoint contracts, Linux/Docker durability, immutable per-space indexes, exact cosine, BM25, typed filters, RRF, and conservative evidence deduplication. T07 adopts a persistent Python child in the CLI container and a separate GPU generation service. T08 adds CPU reranking, source-linked typed answers, and bounded GPU priority. T09 adds shared application ownership, CPU admission, isolated services and verified backups.
- Exact model artifacts are pinned as T02 feasibility baselines; final quality selection, stable public API compatibility, and quality/latency thresholds remain open. The synthetic contract and first public-source comparison are implemented; future quality changes require new frozen validation data.
- Requested T02 follow-ups complete: Gemma 4 26B A4B QAT Q4_0 with 22 CPU expert layers improves dev outcome classification to 13/13. The subsequent status-dependent schema, still at temperature 0, improves exact outputs from 10/13 to 13/13 in both passes with a correct larger probe. Repeated short requests measured 4.39 s. Strict citation completeness remains 13/23; see the [schema result](reports/t02-status-schema.md) and earlier [model comparison](reports/t02-gemma4-26b.md). T03's scope is unchanged.

### Environment observations

Observed during discussion on 2026-10-14:

- NVIDIA RTX 4060, approximately 8 GB VRAM.
- Approximately 64 GB system RAM (63.1 GiB reported by the OS).
- Docker CLI installed; desktop-linux context present.
- WSL default distribution Ubuntu, default version 2.
- Docker engine was not reachable at the time of the check.

During T01 on the same date, Docker became reachable (server 29.6.2). The evaluation image built and CPU-only validation/tests ran successfully with container networking disabled. This does not prove GPU device access or inference. No model was downloaded and no inference/container GPU test was performed.

T02 subsequently demonstrated container GPU visibility and actual CUDA inference on the RTX 4060 (driver 616.92), with all 36 transformer/output layers offloaded and CPU-mapped embedding buffers retained. Models were downloaded and checksum-verified, then used offline across container recreation. Final sampled whole-device VRAM peak: 2,857 MiB; process startup to healthy: 19.62 s. The generation service was stopped afterward. Full evidence and qualifications: [T02 report](reports/t02-local-models.md).

## Next useful step

Scope a fresh final evidence-selection experiment: T23 recovered evidence into the fixed reranker shortlist but lost it in the final five passages. Compare a bounded coverage/diversity policy against ranked selection on new frozen data, with explicit latency and source-support criteria, before any production change. Clarification/ambiguity remains a separate later proposal. Preserve all historical captures, the now-observed T23 corpus and the unused original holdout. No next implementation task is automatically authorized.

## Work queue

Dependencies refer to task IDs, not to required separate chats or agents. Task status is recorded beside each task.

### T01 — Establish fixtures and evaluation contracts

Status: done. Dependencies: none.

Create small synthetic TXT, PDF, and JSON fixtures with answer questions and exact supporting source references. Include a wrapped paragraph, a cross-page passage, a table with headers/units, a scanned page, nested JSON, and close-match distractors with different years/opponents. Include missing evidence and ambiguous questions.

Acceptance:

- Fixture content is synthetic or appropriately licensed and its origin is documented.
- Any Pelé/1954 example is explicitly hypothetical; do not treat it as verified sports history.
- Expected answers distinguish correct evidence, missing evidence, ambiguity, and exact structured values.
- Metrics distinguish parsing, candidate retrieval, reranking, answer extraction, and latency.
- A minimal evaluation schema and runnable validation command exist and are documented.

Completion evidence (2026-10-14):

- Five synthetic documents, 22 exact evidence references, and 19 questions (13 dev, 6 holdout) in `evals/`. Includes every requested fixture category, explicit hypothetical labeling, typed answers, ambiguity, and missing evidence.
- JSON Schema plus semantic/source checks validate hashes, UTF-8 byte ranges/lines, typed JSON Pointers, PDF page regions, references, and deterministic answer templates.
- `evals/metrics.md` separates parsing, retrieval, reranking, assembly, answer/status correctness, presentation, and runtime measurements.
- Docker image built; `docker compose run --rm evals` passed; all 27 tests passed in the offline container. Includes deliberately corrupt labels/references and generator repeatability within one toolchain.
- All three final PDF pages were rendered and visually reviewed. Native PDF text was verified against its page regions; the scan is image-only and its J2/6 N m transcription was visually checked. No OCR engine or search/model quality was evaluated.
- Run instructions and limitations are in [evals/README.md](../evals/README.md).

### T02 — Validate local models and GPU container execution

Status: done. Dependencies: T01 for representative inputs.

Evaluate a small quantized local generation model and dedicated embedding/reranking candidates. Pin runtime images and model identities after checking current compatibility. Prepare a small repeatable Docker GPU smoke test.

Acceptance:

- NVIDIA device access and actual inference inside a container are demonstrated separately.
- Peak VRAM, context/output limits, cold start, and representative latency are recorded.
- Embeddings have reproducible dimensions and documented query/document encoding conventions.
- Reranking and structured extraction are exercised on representative fixtures.
- Model files persist outside container layers; normal inference works without remote model calls after setup.
- Commands, artifact versions, and limitations are recorded; no unsupported performance claims.

Completion evidence (2026-10-14):

- `compose.models.yaml` and `experiments/t02/` provide explicit pinned setup, offline model verification, device visibility checks, GPU generation, CPU embedding/reranking, and a repeatable host measurement driver.
- Exact public model revisions and 14 SHA-256-verified artifacts persist under ignored `models/`, mounted read-only for inference. Official llama.cpp b11617/CUDA 12.8 release binaries are checksum-pinned; base images and Python packages are pinned.
- Final run `20261014T135900Z`: all 36 transformer/output layers on CUDA; 2,857 MiB sampled total device peak (1,302 MiB before); 19.62 s process startup; 0.764 s median repeated short generation; 384-dimensional normalized embeddings, repeated-vector max difference 0.0; CPU reranking exercised on four representative questions.
- All five T02 contract tests passed. Final offline smoke driver exited 0; 27 responses had valid JSON schemas/source IDs; larger-context execution and server overflow rejection were exercised. Model files were reverified offline before fresh container creation. T01 fixture integrity and Compose configuration also passed.
- Quality limitation: only 8/13 dev questions matched status and typed fields exactly in each pass; the 3,723-token probe also answered incorrectly. Ambiguity and zero/null handling remain unresolved. This completes feasibility, not retrieval or answer-quality acceptance. Holdout questions were not used.
- See [measured results](reports/t02-local-models.md), [machine-readable evidence](reports/t02-local-models.json), and [run instructions](../experiments/t02/README.md). No database ingestion, PDF/OCR processing, or end-to-end retrieval was implemented in T02.
- Requested 26B follow-up: two CPU/GPU placements completed the same 27 requests, with all prompt payloads verified against the archived baseline. Selected `--n-cpu-moe 22` for 813 MiB less sampled GPU use than 20 layers at roughly 7% more repeated-request latency. Both scored 13/13 statuses and 10/13 exact status/fields per pass, plus a correct larger probe; strict citation completeness was 13/23 versus E2B's 14/23. Seven contract tests and negative comparison checks passed. Complete evidence: [26B report](reports/t02-gemma4-26b.md).

### T03 — Define core contracts and durable storage

Status: done. Dependencies: T01; embedding configuration informed by T02.

Implementation contract: [storage.md](storage.md). Rust core, Linux/Docker durability, supplied vectors, and explicit crash/retry semantics; no GPU dependency.

Implement document/block/chunk records, source references, revisions, embedding-space identities, a write journal, and snapshots. Specify framing, checksums, commit/flush order, atomic publication, and recovery. Keep model operations outside transactions.

Acceptance:

- Round trips preserve text, typed metadata, provenance, and stored vectors.
- Crash/truncation tests distinguish committed batches from incomplete writes.
- Replacement is atomic to readers; deletion affects new query snapshots.
- Snapshot/replay restores state without rerunning an LLM or embedding model.
- Duplicate/retried operations and incompatible embedding configurations have explicit behavior.

Completion evidence (2026-10-14):

- `src/contracts.rs`: documents/revisions, blocks, chunk spans, TXT/PDF/JSON locators, typed attributed values, generated context kept separate from evidence, and immutable embedding-space identities. Supplied vectors are checked for space membership, dimensions, finiteness, nonzero length, and declared normalization. Tests include 384-dimensional baseline-shaped vectors and other dimensions; no model inference occurs.
- `src/storage.rs`, `src/frame.rs`, and `src/blob.rs`: exclusive writer lock, durable content-addressed originals, CRC-framed prepare/commit journal, explicit file/directory flush order, atomic reader generations, compare-and-swap revisions, permanent retry receipts/revision reservations, checkpoint publication, and replay. Complete corruption fails closed; incomplete tails are repaired. Write/checkpoint errors require reopening.
- `docker compose build core` passed with Rust 1.87.0 and locked dependencies. Final image: `sha256:dcf5ff94891ff9e523f71288f1b2276e794ced5cb700227c7d992ab4ded59247`. `docker compose run --rm core` passed all 18 tests (2.27 s test execution), then the same suite passed with test databases on a temporary Docker disk volume (82.23 s). One ignored helper is invoked by the subprocess test. Temporary verification volumes and containers were removed afterward.
- Coverage includes every byte truncation across two transactions; complete-header/payload/commit corruption; old/new reader replacement and deletion; exact large integers, decimals, null/zero/missing/string IDs and float32 bits; source provenance; retry/revision conflicts; unknown/incompatible spaces; real OS write errors; injected transaction/checkpoint boundary failures; process writer exclusion and forced termination without destructors. A concurrent subprocess lock-lifetime race found during verification was fixed with explicit RAII unlock.
- Offline `cargo fmt --check` and `cargo clippy --locked --offline --all-targets -- -D warnings` passed in the container. Base and model-override Compose configurations validated. The existing T01 integrity validator still passed (5 documents, 22 evidence records, 19 questions). No GPU service or model benchmark was run.
- Limits: storage is a Rust library, not a server; Linux local filesystem/Docker only. Format 1 caps each batch/checkpoint frame at 64 MiB, retains the whole journal, old originals, and retry/revision history, and has no migration/compaction/export API. Raising the checkpoint limit or streaming checkpoints will be needed if measured state exceeds the cap. Source mappings are structurally checked, not parsed/verified for factual accuracy. Failure simulations do not certify host power-loss behavior. These limits do not block supplied-vector retrieval in T04.

### T04 — Implement exact and keyword retrieval

Status: done. Dependencies: T03.

Implementation contract: [retrieval.md](retrieval.md). Build immutable per-space indexes from committed snapshots, with supplied vectors, inspectable branch/fusion results, exact typed filters, and conservative source-preserving deduplication.

Implement exact vector search, BM25 postings, typed filters, ranking fusion, and candidate deduplication. Keep the core callable with supplied vectors so correctness tests do not require model inference.

Acceptance:

- Exact similarity results match an independent reference on meaningful fixtures, including ties and filtered subsets.
- Keyword, dense, and fused rankings can be inspected separately.
- Hidden/deleted revisions are not returned and embedding spaces cannot be mixed.
- Search evaluation records where relevant evidence enters or leaves the candidate set.

Completion evidence (2026-10-14):

- `src/search/` implements exact cosine with float64 accumulation, our own field-separated BM25 postings, explicit typed/Boolean filters, weighted RRF, and evidence deduplication. Indexes retain shared records from one committed generation/embedding space; same-dimensional but different spaces cannot mix. No storage-format changes or model calls.
- Filters use exact decimal magnitude comparisons (including huge exponents), nested JSON Pointers, explicit presence tests, and three-valued missing/untrusted behavior. Generated attributes require opt-in for filtering. Evidence/structural/generated keyword fields remain separate, with generated-field weight zero by default.
- Dense, keyword, fused, deduplicated, and final candidates are returned separately, with keyword contributions, filter diagnostics, suppression mappings, and source-resolvable keys. Deduplication never merges different documents or source locations; partial overlaps remain for later context assembly.
- The offline Docker suite passed 38 tests: all 18 storage regressions, 18 retrieval tests, and two example/coverage tests. Exact cosine matched an independently normalized reference over 64 deterministic vectors; hand-calculated BM25/RRF checks passed. Coverage includes stable ties, filtering before top-k, null/missing/type fidelity, provenance trust, vector/space/config rejection, old/new revision visibility, recovery, and concurrent reads.
- Container formatting and Clippy checks passed. A lint issue in the diagnostic helper was fixed and its two tests reran successfully. Final report image: `sha256:1fee548049054007b5e52edfe4631aecf25755abb0f41a17488c738ac166b90f`. The core service now runs `--all-targets` so example diagnostics are included by default.
- `examples/search_eval.rs` recorded eight cases over six prepared synthetic TXT documents/eight chunks. Gold source intervals are scored after retrieval. The report records keyword recovery of a dense omission, losses from wrong filters/final limits, two-span support, duplicate suppression, ambiguity alternatives, and undefined insufficient-evidence recall. Exact code/corpus/case identities and all ranking stages are archived in [T04 results](reports/t04-retrieval.md) and JSON. Archived source hashes matched the workspace. No T01 holdout labels, model inference, or GPU service were used.
- Limits: no ingestion or semantic/model-quality benchmark yet; indexes rebuild explicitly per snapshot; basic Unicode/diacritic tokenizer without language-specific segmentation; filters do not provide tenant/security isolation; partial-overlap assembly/reranking remain T08. The 64 MiB storage frame/checkpoint limit and deferred compaction remain unchanged. T05 is ready.

### T05 — Build TXT/JSON ingestion and durable jobs

Status: done. Dependencies: T03; model stages can use deterministic substitutes until T07.

Implement the processor contract, job/stage persistence, source preservation, TXT block parsing, typed JSON records, and versioned chunking. Keep structural context separate from evidence.

Acceptance:

- TXT source mappings survive normalization and splitting.
- JSON retains types, null/missing distinction, record identity, and nested field meaning.
- JSON pointers are revision-scoped; large narrative fields stay linked to their records.
- Chunk inputs respect tokenizer limits, including context overhead.
- Restarting/retrying a job does not duplicate published records or expose partial revisions.

Completion evidence (2026-10-14):

- `src/ingestion/` implements versioned `Processor` request/result contracts, `Encoder` token-count/vector boundaries, and local deterministic TXT/JSON preparation. Parsing/encoding occurs before durable mutation. [ingestion.md](ingestion.md) specifies adopted behavior and limits; the architecture records why deterministic preparation reuses Rust while Python remains the proposed PDF/model adapter.
- TXT retains immutable UTF-8 originals, optional BOM handling, CRLF/CR-to-LF maps, original byte/line ranges, heading/list/paragraph blocks, section-bounded merging, sentence/word/character fallback splitting, and parent/neighbor links. Tests reconstruct mapped source ranges and every indexed block span across Unicode and forced splits.
- JSON retains exact types/precision, null versus missing, full nested `record` attributes, subtree `value` attributes, revision-scoped escaped pointers, optional source IDs, and sibling metadata outside a configured record array. Oversized containers split at children; long narrative strings retain their record and field links. Duplicate keys/IDs, reserved serializer keys, unsupported encodings, and impossible budgets fail visibly. Original bytes remain available after failure.
- Jobs bind source/configuration/document/CAS identities, persist each stage and failures in atomic checksummed files, reject stale worker results, and publish through a stable T03 batch receipt. Pending drafts never enter search. Tests cover each restart boundary, competing replacements, corrupted/truncated jobs, real I/O errors, injected write/sync/rename/directory-sync failures, process termination without destructors, and publication before the completion marker—even after later deletion.
- The offline Docker suite passed all 58 tests (38 prior core regressions plus 20 ingestion/durability checks), formatting, Clippy with warnings denied, and Compose configuration validation. The three existing TXT/JSON source fixtures ingest, checkpoint, reopen, and return keyword results; no holdout question labels were read or changed. `examples/ingest.rs` is a Docker-runnable ingestion inspector using the synthetic encoder.
- All 20 ingestion/durability checks also passed on the `vectornext-core-checks` Docker disk volume. Final verified core image: `sha256:411c65666dfcb96c2aab4d8c64178b5b17e2ab5847a9aba4bfcd316886524c9b`. The documented inspector ran in fresh offline containers against `vectornext-ingestion-demo`: TXT produced 6 blocks/4 chunks at generation 1; nested JSON with `/matches` produced 7 blocks/7 chunks at generation 2. Retrying the TXT job returned its original generation-1 receipt while the database stayed at generation 2. The demo volume is retained for repeatable inspection; test containers were removed automatically.
- Limits: strict UTF-8 TXT; explicit heading syntax; zero forced-split overlap; scalar/narrative JSON rather than domain-specific semantic mapping; copied full-record attributes are not independent aggregate records; reserved serializer key rejected; bounded in-memory processing and 64 MiB frames; no cleanup/cancellation/leases/server yet. Real semantic embeddings, generated context, GPU scheduling, and answering remain later tasks. No GPU workload or model benchmark was started.

### T06 — Add PDF structure, tables, and OCR

Status: done. Dependencies: T05.

Validate the proposed Docling adapter on fixtures, then integrate structure-preserving PDF extraction and local OCR in the CPU processor.

Acceptance:

- Native, scanned, and mixed-content fixtures produce traceable evidence without duplicate OCR/native text.
- Reading order, cross-page spans, table headers/units, and page coordinates are checked against the source.
- Partial/low-quality extraction is reported honestly; chart understanding is not implied.
- Parser/OCR models are pinned and available offline; processing resources are bounded.

Completion evidence (2026-10-14):

- `processor/` implements a versioned Docling Slim 2.139.0/Heron/TableFormer/Tesseract 5.5.0 CPU adapter with exact model revisions, file hashes, runtime/data hashes, locked Python packages, and explicit setup. `compose.processor.yaml` runs normal conversion offline with two CPUs, 4 GiB memory, 128 processes/threads, 512 MiB temporary storage, and no GPU/database mount. CLI limits: 16 MiB input/output, 32 pages, 1440-point dimensions, 10,000 items, 180 seconds.
- `src/ingestion/pdf.rs` binds source/profile/canonical artifact identities, checks geometry/UTF-8 spans/structure, preserves furniture separately, builds section-aware cross-page and table-row chunks with header units and context sources, and integrates with existing durable jobs/publication. Optional PDF fields preserve old TXT/JSON serialization. Strict mode rejects partial extraction; explicit opt-in retains warnings. Real embeddings remain T07.
- Two existing PDFs and three separately authored synthetic fixtures were converted offline; all six source pages were visually checked. Native table values/coordinates, the cross-page C7 passage, scanned J2/6 N m text, mixed-page methods, and duplicate-free searchable-scan output were verified. The invisible-layer fixture is honestly labeled OCR. Diagrams remain partial. Controlled tests exercise low confidence, missing pages, omitted text, and page/dimension limits.
- Final offline verification: all 66 Rust tests, all 13 Python tests, formatting, and Clippy with warnings denied passed. The 8 PDF tests also passed on a Docker disk volume. Compose configurations and T01 fixture integrity passed. The documented CLI published 25 blocks/14 chunks to `vectornext-pdf-demo`; a fresh-container retry reused the receipt at generation 1. Test captures match the final profile; prior extraction payloads were unchanged apart from that identity.
- Measured CPU conversion calls: 15.045 s native guide including lazy model initialization, then 4.545–7.188 s for the remaining fixtures with a reused converter. Python peak RSS: 1,314,572 KiB (~1.25 GiB), not container-wide memory. These are single small-fixture observations. Exact images, source/code hashes, measurements, limitations, and commands: [T06 report](reports/t06-pdf.md), [JSON](reports/t06-pdf.json), [contract](pdf-ingestion.md), and README.
- Limits: English clean-scan baseline; no chart/diagram semantics or broad layout-quality claim; region rather than glyph provenance; ambiguous multi-page tables reported partial; repeated-header heuristic; no production scheduler/API, semantic embeddings, generated context, or answers. Holdout answers were not used for tuning or changed. No GPU service or model benchmark was started.

### T07 — Integrate embeddings and contextualization

Status: done. Dependencies: T02, T04, T05, T06.

Connect plain, structural, and generated-context ingestion modes. Add dedicated embeddings, model/version-aware cache identities, and complete revision publication.

Acceptance:

- Generated annotations remain distinguishable from original evidence.
- Context sources, prompts, and model versions are recorded.
- Changing a heading/context/model invalidates affected cached results appropriately.
- CPU/GPU stages can fail and resume without corrupting committed data.
- The same fixture corpus can be indexed under each policy for comparison.

Completed 2026-10-14:

- Added versioned context policies, deterministic bounded scopes, separate reports/annotations, exact input identities, strict stage mutation checks, and a persistent Rust-to-Python model bridge. Optional configuration preserves old job serialization. MiniLM reuses the pinned T02 artifacts/tokenizer/pooling conventions with an explicit real embedding-space identity.
- Added a 64-MiB checksummed atomic cache with file-operation locking, complete input/model/prompt keys, exact token-limit checks, temperature-zero Gemma 4 26B generation, and Docker ingestion/inspection/retrieval-probe tools. PDF input reuses unchanged T06 validated artifacts.
- Verification: 73 core tests; seven new tests also passed on disk; five CPU-model/injected-generation tests; formatting and Clippy with warnings denied. Five source fixtures committed under all three policies (28 chunks each); nine eligible prose chunks yielded eight annotations and one abstention. A technical retrieval probe found the equipment document first for every policy.
- Cache replay into fresh databases succeeded with Gemma stopped, identical receipts, and zero new embedding/generation inference. An empty-cache run reproduced its receipt. A real uncached service outage left a durable `Chunked` job and zero publication, then resumed and committed once after restart. Committed data reopened without models/cache/network. See [T07 report](reports/t07-model-ingestion.md).
- Limits: redundant summaries, unmeasured retrieval improvement, fixed scope/token bounds, sequential inference, all JSON generation skipped, no answers or production scheduling/API. Source fixtures and labels were not regenerated or tuned. The GPU service was stopped; database/cache volumes and ignored raw reports remain available.

### T08 — Add reranking, evidence assembly, and answers

Status: done. Dependencies: T07.

Implement query embedding, reranking, context expansion, source-linked structured extraction, template formatting, optional prose rewriting, and explain output. Add a bounded generation scheduler with interactive priority.

Acceptance:

- Original question constraints survive rewriting and conversational reference resolution.
- Context assembly includes needed headers/labels and removes duplicate evidence within its budget.
- Supported, ambiguous, and insufficient-evidence cases are distinguishable.
- Enforce status-dependent field requirements without collapsing supported raw nulls, zero, missing values, or unsupported counts. The T02 schema experiment is a tested starting contract, not completed T08 integration.
- Schema validation, source-reference validity, and answer correctness are evaluated separately.
- Interactive requests are not indefinitely starved by ingestion; active-generation behavior is documented.
- Corpus-wide aggregates are not fabricated from top-k passages. Full structured aggregation remains explicit scope if implemented.

Completed 2026-10-14:

- Added `src/answers.rs`, the Docker `ask` CLI, CPU reranking, budgeted source expansion/deduplication, status assessment and field proofs, templates, optional prose drafts, and explain/audit output. JSON uses model-selected record/pointer locations with exact Rust source reads; filtered structured lookup bypasses generation. Corpus aggregation is explicitly rejected.
- Added a bounded GPU admission wrapper with interactive priority, FIFO within class, non-preemptive active work, overload/expiry errors, separate health, and fail-closed uncertain backend state. Existing T07 enrichment requests use background priority without changing their cache/configuration identities.
- Verification: 83 Rust tests, 10 answer tests repeated on disk, 18 Python worker/answer/scheduler checks in the recorded test sequence, formatting and Linux Clippy. All 13 development cases passed in a complete pass, followed by a successful prose check after preserving exact numeric display literals across the Python boundary. Typical observed model CLI timings were 10.23–26.91 seconds, median 17.79 seconds; these include CPU startup and are not a general benchmark.
- Live queue order was active background, interactive, waiting background; health responded in 8.1 ms during generation. After stopping Gemma, exact zero/null lookup still worked, generation-dependent asking failed explicitly, and the database remained generation 5 with five documents/28 chunks and committed jobs.
- Earlier ambiguity, bad prose/quote, null transcription, and duplicate table expansion failures are retained and explained in [T08 results](reports/t08-answers.md) and [JSON evidence](reports/t08-answers.json). The development suite informed implementation; it is not held-out quality evidence. No source/label regeneration occurred.
- Limits: fallible semantic assessment and record/pointer selection; bounded evidence may omit ambiguity; optional prose remains a draft; no aggregates, shared CPU admission/API, or concurrent same-database CLI owner. Background generation can starve under sustained interactive traffic; long active work can expire waiting requests. Next: T09 integrated deployment and export/restore.

### T09 — Package the integrated Docker deployment

Status: done. Dependencies: T02 through T08.

Package the three services with pinned images, persistent volumes, internal networking, configurable model paths, capability health/readiness, and a minimal API client or inspection interface. Earlier tasks may use partial Compose setups; this task validates the integrated deployment.

Acceptance:

- A documented fresh-start procedure works on the target host.
- GPU inference is proven in the integrated deployment, with only the intended service using GPU access initially.
- Restart/rebuild preserves documents, committed records, model files, and job progress.
- Search/answer capability failures are explicit and do not corrupt data.
- A consistent export/restore procedure is exercised; Docker volumes alone are not described as backups.

Delivered: `compose.app.yaml`, `src/service/`, `src/backup.rs`, `deployment/`, Docker images, setup/restore commands and [deployment contract](deployment.md). Verified 89 Rust checks, six new checks on disk, 22 Python checks, formatting/Clippy, five fixture ingestions, two actual GPU answers, source-only operation with models stopped, durable failures, interrupted-stage recovery, rebuild/recreation and byte-identical restored records/jobs/receipts. See [T09 results](reports/t09-deployment.md). Local API/client only; no public-service hardening or quality tuning.

### T10 — Evaluate and tune the architecture

Status: done. Dependencies: T09. Protocol: [evaluation.md](evaluation.md).

Compare plain, structural, and generated context on the same evaluation set and hardware. Tune chunking, candidate budgets, field weights, reranking, and model sizing from observed failures.

Acceptance:

- Report evidence recall, final relevance, answer accuracy/support, insufficient-evidence handling, ingestion time, per-stage/end-to-end latency, and peak memory.
- Separate cold/warm runs and include queue time and all local model processing costs.
- Preserve a held-out question set when tuning to reduce overfitting.
- Document what improved, what regressed, and what remains uncertain.
- Propose approximate indexes or additional infrastructure only against a demonstrated bottleneck.

Completed 2026-10-14:

- Added reproducible API ingestion/query runs, explicit dev-only requests, source/hash/type-aware scoring, original-source review, stage/cumulative metrics, memory sampling, bounded answer options and independent keyword weights. Compared plain, structural and generated policies, retained a corrected fully plain retrieval run and both one-/two-primary trials. All policies kept the same 28 original chunk bodies/spans; six holdout questions stayed unused.
- Baseline and two-primary settings answered 13/13 correctly in each cache pass. One primary missed the nominal table row in both passes and abstained; retain that failure. Two primaries reduced median response time from 18.077/17.952 seconds to 12.577/12.229 seconds. Keep five as the general default pending independent multi-passage tests. Generated ingestion took 72.157 seconds versus structural 24.757 seconds with no final answer gain; structural remains the default.
- Recorded all 156 HTTP outcomes, 118 supported outputs with 14 distinct reviewed proof signatures, raw/source-label/final-context recall, exact fields and status handling, parsing fidelity, resource/startup/queue measurements, 48 offline configurations and 39 exact baseline retrieval replays. A separate supplied-vector 400-document/12,800-chunk probe measured 9.946-ms median search and 79.3-MiB peak RSS. Generation dominates latency; no measured need for approximate search or additional services.
- Verified 90 Rust checks, 36 Python fixture/scorer checks, 22 worker/answer/scheduler/transport checks, Linux formatting/Clippy, Compose and unchanged dataset integrity. Live queue priority and 136.817-second model restart were recorded; maximum sampled whole-device usage was 6,352 MiB. All T10 services stopped, data/caches/models retained, T07/T09 data untouched. See [report](reports/t10-evaluation.md) and [JSON evidence](reports/t10-evaluation.json).
- Limits: related synthetic development questions, unmeasured real-corpus precision, Codex source inspection rather than independent human judgment, sequential cache passes with uncontrolled OS caches, sampled memory, and a capacity-only scale probe. Free-form presentation, alternative model sizes and chunk boundaries were not retuned without supporting failures. Next: independent corpus and explicit acceptance targets.

### T11 — Evaluate independent public sources and publish a real demo

Status: done. Dependencies: T10. Protocol: [t11-protocol.md](t11-protocol.md).

Completion evidence (2026-10-14):

- Froze 20 real NASA/USGS sources, 28 public requests and 47 evidence references before inference. The first ingestion attempt exposed a UTF-8 end-byte panic; the [pre-query amendment](t11-protocol-amendment-01.md) preserves it and documents the minimal regression-tested repair. No answer queries preceded the repair; source questions, labels, models and scoring rules were unchanged.
- The replacement run ingested 18/20 documents into 658 chunks. Apollo was rejected under strict partial-extraction policy and Perseverance hit a busy processing lane. Their six questions remain in every denominator; this does not measure PDF retrieval quality.
- Completed five/cold, two/cold, two/warm and five/warm: 112 requests, 104 HTTP successes and eight retained HTTP 400 errors. Five scored 16/28 in each pass; two scored 15/28. Cold medians were 22.269 s versus 11.081 s; warm medians 21.173 s versus 11.515 s. Two lost a three-document answer and the Uranus follow-up while fixing the Galileo distractor case; the conservative decision gate fails, so five remain the default.
- Inspected 17 distinct proof groups covering all 46 supported responses. Preserved raw source-overlap failures for valid alternative passages and three annotation spans crossing blank separators; separate [review evidence](reports/t11-source-review.json) explains them without rewriting labels or scores. Rejected drafts remain unavailable for full diagnosis.
- Packaged the real NASA Voyager source/request and verified README ingest/search/ask in a fresh separate database. Verified 167 automated checks (91 Rust, 54 evaluation, 22 worker/transport), formatting/Clippy, Compose and 86 frozen inputs. See [full results](reports/t11-independent.md) and [machine-readable evidence](reports/t11-independent.json).
- Stopped all T11 services; retained both attempts, caches and raw captures. All T01/T10 records and six holdout questions remain unchanged. The reliability/coverage follow-ups, now T13/T14, are not part of this completed evaluation.

User requested an independent factual dataset, two-versus-five passage comparison, and a real README example. Adopt this as an additional task without changing the original regression fixtures.

Acceptance:

- Source snapshots have primary-source URLs, acquisition dates, hashes, transformation and reuse notes; real source facts replace synthetic data only in the new corpus/demo.
- Freeze questions, typed expectations and exact source references before model evaluation; separate public requests from gold labels. Preserve the original holdout.
- Include distractors, source-spanning questions, TXT/PDF/JSON, ambiguity and unavailable evidence; report all planned cases and ingestion failures.
- Compare identical corpus/model/search settings with only two versus five primary passages changed; report paired quality/support/context coverage, latency/tokens/resources and every failed attempt.
- Apply the protocol's conservative decision rule; retain five by default unless justified, and disclose dataset/measurement limits.
- Replace README example/quickstart with a cited real fact, verify it live, and update report, reproducible commands and handoff.

### T12 — Explain the workflow with human-readable debug information

Status: done. Dependencies: T09–T11. Implemented following the user's request to run T12.

Generate a short, readable account of what happened during ingestion, search and answering. A reader should be able to follow the workflow from the input to the result without understanding the internals or reading raw logs. Cover every major stage that ran; keep each stage's explanation shallow and concrete.

Scope:

- Ingestion: identify the document and format; summarize reading/parsing or OCR, records/chunks created, context policy, embedding and storage; show warnings and the final job outcome.
- Search: show the question, any history or rewrite actually used, keyword/vector search, filtering/fusion, reranking and selected passages. Include useful counts, source names/locations and short excerpts rather than vectors, large payloads or score dumps.
- Answering: show the evidence supplied, local model used, answerability decision, extraction, validation and formatting; end with the answer or a clear ambiguity, insufficient-evidence or failure outcome. Label optional rewrites separately when they ran.
- Present steps in execution order with plain-language status, measured elapsed time and known cache reuse when available. Distinguish completed, skipped, failed and unrecorded steps; do not invent events, timings, reasons or model reasoning.
- Include the client invocation, API handler and high-level function references. Preserve missing/recovered command provenance and distinguish implementation references from measured runtime calls.
- Add an opt-in readable view to the existing CLI that can be saved as text or Markdown. Keep the existing structured API reports available. Build the explanation from recorded execution data, without additional LLM calls or another service.

Acceptance:

- A reader can identify the input, what the workflow did, which source passages informed the result, and where it stopped or failed from one concise report.
- Ingestion, standalone search and question answering each have readable coverage. Include TXT/PDF/JSON-specific steps when applicable, and make skipped optional stages visible.
- Exercise a successful factual answer plus ambiguous/insufficient-evidence and failed-ingestion or failed-answer cases. Reports match actual recorded stages and source references; unavailable details are explicitly marked.
- Preserve existing answers, exact typed values, source provenance, retrieval/model defaults and normal JSON output. Reporting does not change retrieval or inference behavior.
- Document the implemented commands and provide a readable report for the real Voyager example. Check the presentation using retained captures or targeted fixtures; no broad GPU benchmark is needed for formatting work.

Boundary: this task explains the workflow at a high level. Deep profiling, full prompt/token/vector dumps, a web dashboard and the reliability/retrieval fixes below remain outside its scope. Minimal stage metadata may be added where needed to explain actual execution; worker recovery and detailed rejected-draft diagnostics remain T13.

Completion evidence (2026-10-14):

- Implemented `deployment/workflow.py` and CLI `--explain`, `--report`, `--capture`, plus offline `explain`. Reports preserve execution outcomes, source excerpts/locations and exact typed values, label skipped/unrecorded steps, and add no inference or services. Extra document inspection is read-only and revision-checked.
- Passed 78 offline checks: 20 new workflow/client regressions, four existing transport checks and 54 existing evaluation checks. Verified default raw JSON output, precise outbound filter literals, null/string-null distinction, safe Markdown, failures and non-overwrite behavior.
- Fresh isolated Docker run on port 8092 ingested the real Voyager TXT into 86 blocks/25 chunks, returned three search hits, and answered the 1977/1979/1980 timeline with local Gemma. The combined [workflow report](reports/t12-voyager-workflow.md) was rendered offline from those exact captures. Four retained T11 responses exercise ambiguity, insufficient evidence, rejected JSON-pointer and PDF-ingestion failures.
- Published seven public-source captures, [usage instructions](workflow-debugging.md) and [verification evidence](reports/t12-workflow.md). Stopped only `vectornext-t12`; retained its database/cache and `data/t12/20261014-workflow/` records. No Rust, model, prompt or default changes. T11's old freeze and results remain intact; the new CLI intentionally differs from the historical execution hash.
- Follow-up: added recorded client arguments, API handlers and stage function references; regenerated the Voyager/failure reports offline. The three published Voyager envelopes recover command arguments from the saved run record; original responses and raw drill files remain unchanged. Fixed the report's disabled-reranking status. Passed 83 offline checks (25 workflow/client, four transport, 54 evaluation); no model rerun.

### T13 — Harden ingestion recovery and failure diagnostics

Status: done. Dependencies: T11–T12. Findings motivating the scope are preserved in T11; do not change its sources, labels, captures or scores.

Implemented: supervised coordinator state through readiness/job inspection; restart from durable stages; stored PDF diagnostics before publication; bounded client retries only for explicit busy admission, recording every rejection in stderr/captures. Saved stage failures still require explicit retry. Rejected-answer drafts remain inside error envelopes. No quality retuning or GPU run.

- Make a failed ingestion coordinator visible to readiness/job inspection; exercise recovery after an unexpected worker failure without losing committed documents or silently hanging queued work.
- Expose actionable PDF extraction diagnostics before publication and exercise the existing explicit partial-text policy with real illustrated PDFs. Preserve warnings; do not silently weaken strict ingestion.
- Handle transient busy admission through a bounded, observable retry path that preserves job idempotency and records every rejected attempt.
- Preserve useful rejected-answer diagnostics for missing JSON pointers and quoted-value failures without reporting invalid drafts as supported answers.
- Verify with targeted regressions and a fresh operational drill. Existing T11 outcomes become regression evidence, not fresh independent quality validation.

Completion evidence (2026-10-14): 97 Rust and 90 Python checks passed, plus formatting/Clippy/Compose and final image builds. The fresh `vectornext-t13` CPU drill preserved five busy rejections, strict rejection and explicit partial-text publication of two illustrated NASA PDFs (48/four warnings), actual API termination, one durable processor-outage failure and explicit retry into 500 chunks. The committed Voyager revision stayed unchanged and publication remained idempotent. Coordinator panic and rejected-answer envelopes have deterministic regressions. All T13 services stopped, volumes/captures retained; [report](reports/t13-reliability.md), [workflow](reports/t13-operational-workflow.md) and [recovery guide](reliability.md) record limits and commands. Historical T11 sources/labels/scores/freezes remain unchanged.

### T14 — Evaluate question-aware evidence coverage

Status: done. Dependencies: T11 and T13. Keep the general five-primary default. The [T14 protocol](t14-protocol.md) fixed the candidate, annotation v2, new eight-source/16-question corpus, six comparison blocks and adoption gate before inference.

- Evaluate source diversity and constraint coverage before selecting a smaller context; a fixed count alone can omit another mission or a distant passage in the same document.
- Investigate conversational retrieval: in T11, the Uranus follow-up ranks Neptune passages first despite carrying the original history.
- Address structured pointer selection using the actual record schema, without copying gold answers into requests or embedding evaluation labels.
- Separate orbit counts from moon-encounter counts and other numeric distractors through evidence selection and verified field support; do not hard-code benchmark entities or answers.
- Version an improved annotation protocol for duplicate supporting passages and source spans separated only by whitespace. Retain T11's original metrics and its separately reviewed exceptions.
- Freeze a new evaluation set before measuring any proposed adaptive strategy. Preserve the six original T01 holdout questions and do not claim benchmark gains from tuning on T11.

Completion evidence (2026-10-14): eight sources/201 chunks, all 27 source references faithful, 96 requests across six completed blocks. Five scored 8/16 with 29.18/28.53-second medians, two 7/16 with 18.19/17.34 seconds, coverage 8/16 with 16.50/15.86 seconds. The gate failed; one ambiguity label has a separately documented wording limitation. Coverage recovered some fields but missed others and cannot restore absent candidates. JSON pointer constraints ran with real local Gemma; defaults and T11 labels/scores/freezes remain unchanged. Verified 101 Rust/116 Python checks, formatting/Clippy/Compose/images; separate diagnostic confirms numeric-quote false negatives and a fragment false positive. See [results](reports/t14-evidence-coverage.md). Stopped only T14 services; retain data and captures.

### T15 — Source-exact numeric proof validation

Status: complete. Dependencies: T14. Implemented after T14's frozen comparison. Preserved the matching 272-file tree in `backups/t14-source-before-t15.zip` before runtime changes; both original freezes and every archived file hash verified.

- Accept defensible thousands-separated numbers and date-year quotations while preserving the exact original quote and typed value. T14 exposed correct drafts rejected for `7,329`/`7329` and `Feb. 25,1969`/`1969`.
- Validate numeric boundaries against the full source occurrence, not only the model's submitted quote. The deterministic `examples/proof_boundaries.rs` probe exposes acceptance of quote `3` from source `Count: 3,000.`; preserve it as a regression.
- Reject numeric fragments, changed signs/decimals, ambiguous separators and precision loss. Keep exact JSON source reads and missing/null/zero semantics unchanged. No blanket punctuation stripping or benchmark-specific values.
- Add focused source-support regressions and verify unchanged API/storage contracts. T14 is now observed regression evidence; any new quality claim needs a fresh protocol/corpus. Keep its original freezes, responses, scores and source-review exception intact.

Completion evidence (2026-10-14): added `src/answers/numeric.rs`, routed prose numeric validation through full supplied-source boundaries, and added seven focused Rust regressions. Exact English grouping and named-month date years pass; clipped signs/digits/decimals and ambiguous unsupported notation fail. The unchanged probe now reports accepted/rejected/accepted. Passed 108 Rust/90 Python checks, format/lint, release API build/liveness and archive/data integrity checks. Fixed an initial lint finding; final checks are clean. API/storage/JSON/null contracts and retrieval/model defaults are unchanged. [Report](reports/t15-numeric-proofs.md). No GPU rerun or new quality claim; T14's historical evidence remains byte-identical.

### T16 — Browser API and simple questions

Status: complete (2026-10-15). Depends on T15. [Verification](reports/t16-t18-local-app.md).

- Serve UI assets and same-origin browser requests through the Rust API while preserving CLI routes and rejecting unrelated origins.

- Add `/v1/ui/` multipart uploads, automatic IDs, compact library summaries, revision-bound sources and replacement/removal. Preserve optional filenames without changing absent-field legacy serialization.

- Sequential uploads retain an identity across bounded busy retries; unknown outcomes are reconciled before resubmission. PDF preparation is distinct from durable job progress. Existing limits and structural context remain defaults.

- Require current revisions for replacement/removal and reject changes during unfinished ingestion. Preserve historical jobs and existing reclamation behavior.

- Add bounded local field planning from question/history only, followed by existing answer validation. No inferred answers, pointers, filters or replacement queries; advanced fields bypass planning and aggregates remain unsupported.

- Return exact answer literals/types, citations and recorded workflow data, with raw reports as opaque JSON text.

- Acceptance: browser-compatible uploads of TXT/PDF/JSON and ordinary factual questions without manually supplied IDs/fields. Verify API/CLI compatibility, retry/revision races, planner failures, null/zero and exact numeric fidelity.

### T17 — React document and answer workspace

Status: complete (2026-10-15). Depends on T16. [Verification](reports/t16-t18-local-app.md).

- React + TypeScript + Vite + shadcn/ui; responsive library/conversation/evidence layout, system fonts, accessible controls and light/dark themes. Docker builds static assets into the API image.

- Drag/drop sequential uploads, real processing states, failure/retry, revision-safe replacement and confirmed removal. Advanced JSON pointer/partial-PDF controls.

- Ordinary questions default to factual fields with clickable sources; clearly distinguish ambiguity, missing evidence and rejected drafts. Optional prose remains labelled.

- Exact TXT/PDF/JSON evidence, page/pointer references and original PDF opening; captured historical evidence cannot silently become a newer revision. Readable recorded workflow with detailed function references, honest waiting states and elapsed time.

- IndexedDB browser-only conversation/evidence persistence, export/clear and visible four-exchange context; exclude rejected drafts, reject oversized turns, start new conversations when scope changes.

- Advanced field/template/retrieval controls retain ranked 30/20/5. No CDN/runtime frontend server.

- Acceptance: upload/ask/source/replace/remove workflows require no terminal or request JSON after startup. Verify reload/history, precision, keyboard/narrow layouts, untrusted text and storage/transport/model failures in browser tests.

### T18 — Setup and startup

Status: complete (2026-10-15). Depends on T17. [Verification](reports/t16-t18-local-app.md).

- Windows PowerShell launcher and double-click command entry point with separate Setup, Start, Rebuild and Stop actions.

- Setup checks Docker/GPU and invokes existing pinned model/image preparation with progress; Start reuses installed artifacts and opens the browser after API liveness.

- Capability readiness remains visible while models load; unavailable generation does not block browsing. Stop only the normal project, preserving all persistent data.

- Update README/handoff and verify prerequisite failures, cached offline startup, rebuild and stop behavior.

- Acceptance: one shortcut reaches a usable UI after setup, with clear readiness feedback.

### T19 — Migrate the API to Axum with OpenAPI documentation

Status: complete (2026-10-15). Depends on T18. [Verification and limitations](reports/t19-axum.md).

- Replace production tiny_http with Axum/Tokio; register routes and collect schemas through utoipa-axum. Keep tiny_http only for existing test mocks and pin dependencies compatible with Rust 1.87.
- Preserve all legacy/browser endpoint contracts, exact values, origin checks, body/multipart limits, custom headers, static/PDF sources, revision guards and retry reconciliation. Override framework routing/extractor defaults to retain current rejection behavior.
- Run synchronous Application calls in bounded spawn_blocking work. Preserve immediate 16-handler admission and separate model lanes. Work retains its permit after disconnect; no new operation timeouts/retries or database/model rewrites.
- Add /openapi.json and locally bundled /docs with interactive Swagger UI, no CDN/external validation, exact raw responses and same-origin Try it out. Add the workspace link and README instructions.
- Capture deterministic HTTP behavior before replacement, using isolated data and processor substitutes. Verify route/method/query/error compatibility, limits, origin handling, revisions, admission saturation/disconnects, recovery, all answer outcomes, exact large numbers/null/zero and OpenAPI coverage.
- Run Rust tests/format/Clippy, relevant Python regressions, frontend checks and Docker browser workflows including offline documentation. Preserve the old API image for rollback; do not rerun GPU quality benchmarks or historical evaluation sets.
- Acceptance met: existing browser/CLI workflows passed, local API documentation worked with external networking disabled, and deployment remains three services. Verified 122 Rust, 118 Python unit/regression, 71 frozen HTTP cases plus five boundary/two schema checks, five component and eleven browser tests; format/Clippy/builds passed. Normal API upgraded with unchanged documents and dependency containers; T18 image retained.

### T20 — Benchmark VectorNext against PostgreSQL + pgvector

Status: complete (2026-10-15). Depends on T19. Architecture and task updated before implementation. [Protocol](t20-protocol.md), [recovery amendment](t20-protocol-amendment-01.md), [results](reports/t20-pgvector.md) and [reproduction](../experiments/t20/README.md).

- Add a dedicated CPU-only Compose project with isolated storage and adapters. Pin PostgreSQL/pgvector, runner dependencies and image identities. Do not change the production backend, search implementation or normal services.
- Freeze a protocol and deterministic corpus/query manifests before measurements: 400 and 1,600 documents, 32 chunks each, 384-dimensional supplied float32 vectors, matching text/attributes, top-10 queries and unfiltered/5%-document/1%-attribute/empty scopes. This measures vector storage/search, not semantic relevance or end-to-end RAG quality.
- Validate exact results against an independent float64 cosine reference with documented numerical/tie tolerance. Include failures in denominators. Compare pgvector HNSW separately at fixed search budgets with recall; no tuning on observed results.
- Apply equal service CPU/RAM limits; record hardware, versions, configuration, input/source hashes and query plans. Report initial-pass and warm p50/p95/p99 across counterbalanced passes, retaining per-query results. Separate client round-trip from engine diagnostics; explain adapter differences and do not claim a cold disk cache.
- Measure acknowledged per-document ingestion, index preparation, database disk usage and idle/query memory with explicit scope. Exercise interruption/restart and verify acknowledged records/query results. Do not imply physical power-loss certification or maturity parity.
- Add generator/oracle/scorer/filter checks; run relevant Rust tests, formatting/Clippy and isolated verification. Preserve historical evaluations and the unused holdout; no GPU/model quality rerun.
- Acceptance: reproducible commands and retained measurements for both corpus sizes, exact-result correctness or explicit failures, separate ANN recall/latency, recovery checks, comparison report and README summary. Record limitations and stop only benchmark services, retaining volumes/artifacts, before marking complete.

Completion evidence:

- Final run `20261015-fixed-v3`: 4,096 requests completed, no query errors; both exact engines passed all 2,048 exact timed checks. Warm unfiltered medians were VectorNext/PostgreSQL 8.818/5.673 ms at 12,800 vectors and 43.862/22.729 ms at 51,200. HNSW ef=40 medians were 0.586/0.843 ms with 100%/99.0625% recall. Selectively filtered HNSW-labelled configurations used exact B-tree/sort plans; report this distinction.
- Both VectorNext checkpoint attempts failed on the existing 64 MiB frame limit. Amendment 01 records rejection/reopening and journal recovery without changing engine code or queries. PostgreSQL checkpointed; both engines retained the full acknowledged-data digest including sentinel documents and passed 512/512 post-kill exact checks. Offline export depends on checkpoint and inherits the limit (code-derived, not separately executed).
- Verified 123 Rust tests, eight benchmark Python tests, formatting/Clippy, release/runner builds, a separate two-document smoke test, 39 execution-source hashes, corpus hashes and all capture denominators. No GPU/model, semantic-quality or concurrent-load claim. Production code and historical evaluation artifacts remain unchanged.
- Initial Decimal-report failure and the earlier completed small-corpus run/checkpoint failure remain under separate v1/v2 directories with matching source archives. All three attempts have identical input hashes. All benchmark services are stopped; isolated volumes, networks and captures remain. Normal application services remain healthy. Benchmark acceptance is complete; the storage defect is an explicit follow-up.

### T21 — Remove the checkpoint/export state-size bottleneck

Status: complete (2026-10-15). Depends on T20. Architecture and plan updated before implementation. [Verification](reports/t21-checkpoints.md), [format/compatibility](storage.md#t21-bounded-checkpoint-stream) and [reproduction](../experiments/t21/README.md). Matching T20 sources are preserved in `backups/t20-source-before-t21.zip` (SHA-256 `32e41ca95f4a86f4bd4c5fcd6bd2150449cb16fb521a3348c40cd3550da9d1fc`).

- Preserve the matching pre-T21 T20 source tree and all benchmark evidence. Add a versioned, bounded checkpoint stream with 1 MiB data segments, sequence checks, per-frame CRCs and a terminal count/length/SHA-256 manifest. Stream JSON without a complete-state clone/serialized buffer; retain the existing in-memory database model.
- Read legacy snapshots and emit new snapshots with the same complete state, journal offset/prefix digest, exact values, spaces, receipts and revision history. Keep document/job frame limits and the VNXSTORE1 journal marker; older readers must fail closed on new snapshot kinds. Document the rollback boundary and keep backup manifest compatibility.
- Preserve temporary-file publication, file/directory fsync, atomic rename, sole-writer exclusion and poisoning after failed/uncertain checkpoint writes. Never silently fall back from a corrupt published checkpoint. Reject missing, duplicate, reordered, oversized, truncated, mismatched and trailing segments before returning a database.
- Verify legacy migration, multi-segment boundaries, all publication faults, journal suffix replay, exact large numbers/null/zero, retries and tombstoned revisions, unfinished jobs, missing originals and malformed snapshots. Export/restore must retain checked file manifests, new-destination publication and the separate 8 GiB total backup bound.
- Exercise checkpoints larger than 64 MiB and export/restore at the two T20 sizes on fresh copies/new volumes; verify complete record/vector digests and exact search against frozen references. Keep original volumes/captures untouched. No PostgreSQL timing rerun, GPU/model run or historical holdout use.
- Run relevant Rust tests, formatting/Clippy, container builds and CPU operational checks. Record results, remaining limits and compatibility before marking complete. Normal services remain unchanged unless separately requested.
- Acceptance: both former failing T20 sizes checkpoint and export/restore correctly; legacy and new recovery paths pass; corrupt/partial publication fails safely; bounded serialization is exercised; all exact data/retry/provenance contracts remain intact and reproducible evidence is retained.

Completion evidence:

- Replaced whole-state clone/serialization with numbered 1 MiB segments and strict header/footer integrity checks. Legacy snapshots remain readable; journal/job frames, sole-writer publication, exact values and backup envelope/limits remain unchanged.
- Fresh copies of T20's 401/1,601-document post-sentinel states produced 86.29/344.52 MiB checkpoints, survived SIGKILL with an additional acknowledged transaction, and exported/restored successfully. Full records/receipts/space and T20 vector digests match; all 768 exact queries passed. Independent inspection confirmed 87/345 segments and identical source/export/restored snapshot hashes. All 2,013 original-volume file hashes remain unchanged.
- Verified 132 Rust checks (full 131 plus the added >64 MiB regression), format/Clippy, core/release/app builds, actual T19 export migration with identical records and old-reader rejection, and four offline production API/UI/docs smoke routes. Existing future-compatibility notices remain; no GPU/model or historical-quality rerun.
- Compose selects built API/client/admin `:t21`; processor/generator stay unchanged. Normal app remains healthy on T19 until the next Start/Rebuild. All T21 test containers are stopped; new data/export/restored volumes and `data/t21/` reports/logs are retained. Old releases need an untouched pre-upgrade copy after new checkpoint publication. Next: scope filter profiling.

### T22 — Filter profiling and indexing

Status: complete (2026-10-15). Depends on T21. Architecture/plan updated before implementation. [Results](reports/t22-filters.md), [protocol](t22-protocol.md), [reproduction](../experiments/t22/README.md).

- Freeze a baseline binary/source identity and a fixed profiling workload before production edits. Use fresh copies/new capture paths; preserve historical stores and evaluation artifacts.
- Profile filter/tokenization, dense/keyword/ranking stages and complete query latency separately. Include 12,800/51,200 base-vector sizes, unfiltered, document, scalar equality/range, empty, Boolean, trust/unknown and fallback cases; record index construction and indexing budgets.
- Add immutable per-snapshot document/media postings and bounded top-level scalar attribute indexes. Preserve exact decimal/large-number comparisons, null/missing/type distinctions, generated-attribute trust, three-valued All/Any/Not behavior and full eligibility traces. Unsupported/over-budget columns use the original evaluator.
- Preserve API and storage contracts, exact cosine/tie ordering, BM25 statistics, default retrieval budgets and model identities. No ANN, GPU work or production service migration.
- Verify indexed versus scan decisions and complete search responses, boundary values, fallback/budget cases, compound filters, snapshot replacement/removal and concurrent readers. Run Rust regressions, formatting/Clippy and offline release checks.
- Acceptance: unchanged results across deterministic equivalence checks and the frozen profile; reproducible latency/build/memory-counter evidence demonstrates the targeted improvement or reports its limits honestly. Update retrieval documentation, README and handoff; retain all captures and stop isolated containers before marking complete.

Completion evidence: 135 Rust tests, formatting/Clippy, release/core/app builds and offline startup passed. The 4,224 profile requests match complete response hashes across 352 unique groups; large-corpus equality/empty/range medians improved from 16.302/16.693/25.177 ms to 0.252/0.059/1.024 ms. Build cost and fallback limits are reported. All 2,013 original T20 file hashes are unchanged; T22 captures/volume remain and isolated services are stopped. Normal app remains T19; Compose selects built T22.

### T23 — Fresh evidence-retrieval improvement experiment

Status: complete (2026-10-15). Depends on T22. Authorized after the filter work. [Protocol](t23-protocol.md), [results](reports/t23-evidence.md), [reproduction](../evals/evidence/README.md).

- Select fresh attributed public reference documents; freeze snapshots, source terms, questions and source-bound evidence labels before retrieval runs. Keep original holdout and all historical comparisons unused/unchanged.
- Use pinned real CPU embeddings/reranking, structural context and the existing ranked 30/20/5 baseline. Compare a fixed bounded field-focused candidate expansion in experiment tooling; retain original questions/scopes and record every auxiliary query.
- Keep gold labels out of runtime queries and prompts. Freeze per-variant candidate/rerank/final budgets and disclose extra retrieval/encoding work. Do not tune on measured outcomes or silently promote the variant into production.
- Measure source admission, candidate evidence recall, final evidence recall, complete-question coverage and latency, retaining failures and per-question captures. Include multi-source/detail questions and clearly scoped missing-evidence cases. No GPU/answer-generation quality claim.
- Validate fixtures/scoring and run paired comparisons on identical admitted source revisions/model identities. Preserve execution/input hashes and failed attempts. Publish results/limitations even if the proposed strategy does not improve retrieval.
- Acceptance: reproducible completed comparison on fresh data, source-linked scoring and honest conclusions, frozen artifacts and updated handoff. Agent-authored labels must not be described as independent human adjudication.

Completion evidence: all 12 sources admitted (188 chunks); 96/96 requests succeeded in baseline/expanded/expanded/baseline order, with identical paired ranking/score outputs. Fixed 20-input coverage improved 18/20 → 20/20 questions (31/34 → 34/34 fact requirements); final-five coverage stayed 16/20 and 28/34. Empty-cache medians were 624.6/619.0 ms; cached medians 1.52/3.35 ms. Five Python scorer tests, one experimental Rust test, Docker fixture validation, format/Clippy, release build and separate synthetic real-model smoke passed. Post-run alternative time support is documented without rewriting gold. Production defaults, historical evaluations and normal services are unchanged. New sources/code/image identities and all captures/volumes remain available.

### Later — Clarification and ambiguity evaluation

Scope a separate clarification workflow and clearly worded ambiguity evaluation after T23. Candidate-retrieval evidence does not establish answerability or ambiguity quality. Keep production defaults and historical freezes intact.

## Session handoff discipline

Keep the Current state and Next useful step sections accurate. For each meaningful work session, add one concise entry below with changed files/capabilities, task IDs, verification actually performed, unresolved issues, and the next step. Do not paste full chat transcripts or command logs.

### 2026-10-15 — T23 completed

- Froze twelve attributed NIST text sources, 24 question/hint requests and separate source-bound labels before inference. Built an isolated CPU candidate-expansion experiment, validation/scoring tests and reproducible runner; preserved all inputs, code/image identities and captures.
- All 96 requests succeeded. Expansion improves the shortlist but not final-five evidence coverage; retain production defaults. Recorded conservative source-label limitations and separate real-inference versus result-cache latency.
- Experimental containers exited; data/caches retained. Normal T19 app remains healthy, Compose selects built T22. Next scope final evidence selection with new data; no further implementation is started.

### 2026-10-15 — T22 completed; T23 next

- Updated architecture/plan first, froze and profiled T21, then implemented immutable bounded scalar/document/media indexes with the original scan evaluator as fallback. Added equivalence/revision/budget tests, paired profiling, reports and reproduction.
- Verified 135 Rust tests, format/Clippy, 4,224 complete response checks, image builds and four offline API/UI/docs routes. Recorded filter gains plus index-build costs; original stores and historical evaluation artifacts are unchanged.
- T22 containers stopped, captures and data retained; normal app stays on T19 while Compose selects T22. Next run the separately authorized fresh T23 evidence experiment, without GPU generation or production-default changes.

### 2026-10-15 — T21 completed

- Updated architecture/plan first, archived matching T20 execution sources, then implemented bounded checkpoint framing with legacy reads and unchanged journal/publication/backup contracts. Added format/upgrade documentation, regression tests, an isolated release drill, independent frame inspection and Markdown/JSON results.
- Both formerly failing T20 states passed checkpoint, forced-restart recovery, export/restore and all 768 exact queries. Verified 132 Rust checks, format/Clippy, builds and real old/new binary compatibility; preserved original source-volume/input hashes and all historical results. Failed early harness builds/smoke attempts remain in logs; only final checks are counted.
- New Compose API/client/admin image is `:t21`; the running normal app remains on T19, healthy and unchanged. All T21 containers stopped, data/reports retained. Preserve old store copies for rollback and the unchanged 8 GiB backup limit. Next: scope filter profiling before retrieval-quality experiments.

### 2026-10-15 — T20 completed

- Updated architecture and plan before implementation; added the isolated Rust supplied-vector adapter, pinned PostgreSQL/runner Compose tooling, frozen protocol, independent reference/scorer, recovery amendment, reproduction guide and Markdown/JSON results. README now includes the comparison and checkpoint/export limitation; its preceding technical expansion is preserved.
- Both corpus sizes completed the fixed four-configuration comparison. Exact correctness and journal recovery passed, PostgreSQL was faster in all exact warm groups, and larger-corpus HNSW recall was 99.0625%. VectorNext checkpointing failed at both sizes; do not hide this behind successful recovery or advertise backup at those states.
- Verified 123 Rust/eight Python checks, format/Clippy, builds, separate smoke, manifest integrity, summaries and stopped benchmark services. Retain `data/t20/20261015-fixed-v1`, `-v2`, `-v3`, all project volumes and earlier source archives. Normal app is healthy; no production code, GPU run, historical dataset or original holdout changed. Next: scope checkpoint/export repair before filter-performance and retrieval-quality work.

### 2026-10-15 — Technical README expanded

- Expanded the public README with the pinned Rust/Axum/Tokio/utoipa and frontend/worker stack, storage durability, format-specific ingestion, retrieval/answer pipeline, local models, API routes/contracts, scheduling, browser persistence and Docker resource/configuration details.
- Checked claims against manifests, Compose and the relevant implementation/contracts. Verified local links/anchors, Markdown fences, pinned versions, route coverage and whitespace. Documentation only; no application code, services, model runs or historical results changed. T19 remains complete; candidate retrieval and ambiguity evaluation remain the next work to scope.

### 2026-10-15 — T19 completed

- Updated architecture/plan first, captured the old server's 71-case HTTP baseline, and migrated only the HTTP boundary to Axum/Tokio with bounded blocking work. Added utoipa route definitions, explicit wire schemas and vendored Swagger documentation with exact raw response displays/downloads.
- Verified 122 Rust tests, 118 Python unit/regression checks, the 71-case baseline, five HTTP boundary/two OpenAPI schema checks, five frontend component checks and eleven offline browser scenarios. Rust format/Clippy, TypeScript/production builds, CLI reads, revision/restart/cancellation checks and normal startup passed. [Results and limitations](reports/t19-axum.md).
- Fixed a Swagger renderer registration that initially rounded displayed numbers, made legacy header checks case-insensitive, and corrected the worker test model mount. Launcher image checks now follow Compose. No production model/retrieval/storage behavior or historical evaluations changed; the original holdout remains unused.
- Normal API now runs `vectornext-app:t19` on localhost:8088; processor/generator container IDs and committed document listing are unchanged. Retained `vectornext-app:t18` for rollback and ignored `data/t19/` verification logs. T19 test containers stopped. No GPU quality rerun.
- Next: scope candidate retrieval and ambiguity evaluation separately on fresh data.

### 2026-10-15 — T16–T18 completed

- Updated architecture and sequence before code. Added the browser API, field-only Gemma planning, exact text projections, revision-safe document workflows, React/shadcn workspace with IndexedDB history, and Windows Setup/Start/Rebuild/Stop launchers. README now leads with the browser quickstart and an actual local-model screenshot.
- Verified 116 Rust checks, 90 Python regressions, 28 worker/planner checks, five live HTTP boundary checks, five frontend component/storage checks, nine offline browser scenarios and one production-browser scenario with local Gemma. Format/lint, type/build, all three upload formats, exact decimal/null/zero, missing evidence, source invalidation, offline browsing and launcher actions passed. See [the complete report](reports/t16-t18-local-app.md).
- Preserved the initial stage-casing harness failure and an automatic planning decline. Released only this session's stopped test networks after Docker pool exhaustion; retained test volumes/captures. Repeated normal Setup passed. The normal app remains running at localhost:8088; unrelated workloads were untouched.
- Limits: browser-local history/no tab merging, fallible planning and semantics, no failed-job cancellation, Chromium-only browser testing, reused model-download verification. Historical freezes/results and the original holdout remain unchanged. Next: separately scope candidate retrieval and ambiguity evaluation; no quality-default changes.

### 2026-10-14 — T15 completed

- Followed [architecture.md](architecture.md); repaired numeric prose proof handling without changing storage, JSON reads, model calls or retrieval defaults. Documented the strict English grammar and its conservative limitations in [answers.md](answers.md).
- Preserved the entire matching T14 source tree before edits. Archive and original data/execution manifests verified; historical T14 reports/captures remain unchanged. Current execution correctly differs at `src/answers.rs`; do not rewrite the old freeze.
- Verified 198 checks (108 Rust/90 Python), formatting/Clippy, before/after deterministic probe behavior and the rebuilt `vectornext-app:t15` release API liveness. Initial lint finding corrected. Temporary smoke container removed; no persistent services started or user data changed.
- Updated README, contracts, handoff and [T15 report](reports/t15-numeric-proofs.md). Next: independently scope candidate retrieval and ambiguity evaluation; keep the original holdout unused.

### 2026-10-14 — T14 completed

- Followed [architecture.md](architecture.md) and the pre-inference protocol. Added opt-in field selection, pointer constraints, exact-value/client/workflow compatibility checks, a separate v2 scorer and frozen new public corpus. No storage format, model identity or default strategy changed.
- Completed all six comparison blocks and retained every response/error: five 8/16, two 7/16, coverage 8/16 in both passes; coverage median 43.5–44.4% lower. Published the full report, source-review exception, readable successful/failure workflows and a deterministic numeric-boundary probe. This is an evaluated tradeoff, not a required quality improvement or broad superiority claim.
- 217 automated checks passed, plus format/lint/Compose and live JSON grammar/source-value checks. Fixed an initial pinned-compiler syntax issue and test invocation/environment mistakes before the freeze. New numeric proof defects remain explicit T15 scope, not silently repaired during measurement.
- All T14 services stopped; isolated volumes/cache, 96 raw responses and source downloads retained under `data/t14/20261014-coverage/`. T11/T14 freezes are unchanged; the original holdout is unused. Next: T15 numeric proof validation, then separately scoped candidate retrieval and clearer ambiguity evaluation.

### 2026-10-14 — T12 completed

- Added readable CLI workflow reports, exact-response capture and offline rendering; documented commands and published the fresh Voyager report plus retained failure examples. Followed the reporting scope in [architecture.md](architecture.md); no new service or inference narration was introduced.
- Verified 78 checks and one fresh Docker ingestion/search/answer run. The final report records the correct Voyager timeline and real supporting quotes. Original JSON output and exact numeric literals remain intact; missing timing/trace information is labeled unrecorded.
- All T12 services stopped; raw data and volumes retained. Published report: `docs/reports/t12-voyager-workflow.md`. Full verification and limitations: [T12 report](reports/t12-workflow.md). Next proposed work: T13 reliability/diagnostics, then T14 evidence coverage. Historical T11 reproduction requires its recorded pre-T12 code rather than changing the original freeze.

### 2026-10-14 — Workflow explanation prioritized as T12

- Added the user-requested T12: concise human-readable debug reports covering ingestion, search and answering from actual execution data, with readable steps, evidence, timings where available and outcomes.
- Moved the previous reliability and evidence-coverage tasks to the bottom of the work queue as T13 and T14; updated current priorities, dependencies and documentation references. Recorded the requirement in [architecture.md](architecture.md).
- Planning/documentation only; T12 implementation has not started. Checked task ordering, references, local links and whitespace; no application tests or GPU services were run. Next: implement T12 when requested.

### 2026-10-14 — T11 completed

- Added the attributed public-source dataset, explicit acquisition/authoring tools, frozen public requests/gold, isolated runner, comparison summaries, source review and reports. Replaced the fictional README example with a verified NASA Voyager timeline. Followed [architecture.md](architecture.md); no storage/search/model default or service boundary changed.
- Preserved the initial ingestion interruption and repaired only UTF-8 line counting before queries. The complete 112-request comparison retains all PDF admission and answer-validation failures: five 16/28 versus two 15/28 in each pass, despite two reducing median latency by 46–50%. Keep five; separate failure causes and annotation limitations are in [T11 results](reports/t11-independent.md).
- Verified 167 checks, format/lint, Compose, input hashes, source proofs and the standalone Docker CLI demo. Raw data remains under `data/t11/20261014-independent-fixed/`, the earlier attempt under `data/t11/20261014-independent/`, and the demo under `data/t11/readme-voyager-20261014/`. All T11 services stopped; volumes/caches retained, prior projects untouched.
- Follow-ups identified at completion: reliability/diagnostics, then evidence coverage on new frozen data (now T13 and T14 after the requested T12 insertion). Do not reuse the observed T11 cases as independent tuning validation or consume the six original holdout questions without a new explicit protocol.

### 2026-10-14 — Public repository README

- Reworked README.md for GitHub visitors: project pitch, exact fictional demo, implemented capabilities, three-service architecture, scoped measurements, fresh-install quickstart, source navigation and license. Preserved detailed setup, backup, lower-level experiments and verification commands in [development.md](development.md); updated working-instruction links.
- Checked local links/anchors, Markdown fences/whitespace, demo JSON against the actual request fixture and reported figures against the T10 archive. This was a documentation-only change; application tests and GPU benchmarks were not rerun, services were not started, and nothing was published. Architecture and implementation scope are unchanged. The next implementation step remains an independent corpus and explicit quality/latency targets.

### 2026-10-14 — T10 completed

- Added isolated end-to-end evaluation, source/answer scoring and review, stage/resource/queue measurements, answer budgets and independent keyword weights. Archived all six trials and the one-primary table failure; same fixtures/model prompts, no holdout use. See [T10 results](reports/t10-evaluation.md) for complete methods, numerators and limitations.
- Two-primary context passed both 13-question passes at roughly 12 seconds median versus 18 seconds with five; retain five as the general default. Generated context increased ingestion cost without final answer improvement. Exact search measured 9.946 ms for 12,800 supplied vectors; no new indexing or storage infrastructure is warranted by this test.
- Verified 90 Rust, 36 fixture/scorer and 22 worker/transport checks, formatting/Clippy, Compose and dataset integrity. Retained `vectornext-t10` volumes and ignored raw captures; stopped all three test services. Next: scope an independent corpus and quality/latency thresholds; the original T01–T10 queue is complete.

### 2026-10-14 — T09 completed

- Added the three-service application, shared sole database owner/API, short-lock snapshot/stage boundary, bounded interactive/background CPU lanes, source-exact client, capability readiness, and offline export/restore into a new destination. Preserved storage, model, PDF and answer contracts.
- Verified 89 Rust checks, six new checks on a Docker disk volume, 22 Python checks, Linux format/Clippy, Compose configuration, five source fixtures (TXT/two JSON/two PDF), actual Gemma answers, generation/CPU outages, concurrent committed reads, failed/interrupted job recovery after rebuild/recreation, and exact export/restore plus new writes. Fixed localhost publishing by giving only the API an ingress bridge. See [the report](reports/t09-deployment.md) for identities, measurements and limits.
- Retained isolated `vectornext-t09_data` with original generation 6 and restored generation 7, cache, ignored captures and `backups/20261014-t09`; stopped only the T09 services after checks. Existing T07 data is untouched. No holdout labels, source regeneration or prompt tuning.
- Next: T10 quality/performance comparison; avoid inferring retrieval quality from deployment smoke checks.

### 2026-10-14 — T08 completed

- Implemented local retrieval-to-answer flow, original-source expansion, CPU reranking, typed proofs/exact JSON reads, deterministic formatting and separate rewrites, complete filtered structured lookup, and bounded GPU priority. Preserved T07 storage/model identities and original evidence.
- Verified 83 Rust tests, 10 disk-volume answer tests, 18 Python checks, formatting/Clippy, 13/13 live development outcomes, an additional final prose check, real queue priority/health, and model-off source lookup/read integrity. Recorded earlier failures and final code/image/model/source identities in [T08 results](reports/t08-answers.md).
- Stopped only VectorNext's Gemma service. T07 corpus/cache volumes and ignored raw `data/t08/` reports remain available. Semantic correctness beyond these development examples remains unproven. T09 must provide shared application ownership, CPU admission, API/readiness, and exercised export/restore.

### 2026-10-14 — T07 completed

- Connected real CPU MiniLM embeddings, three context policies, separate Gemma 4 26B annotations with recorded source scope/configuration, bounded caches, durable failures/resume, and Docker ingestion/probe tools. Preserved source evidence, PDF metadata, exact JSON values, and old job serialization.
- Verified 73 Rust checks, seven context checks on disk, five Python model-worker checks, all five fixtures under each policy, exact cached replay with Gemma stopped, empty-cache recomputation, a real service outage/resume/retry, and reopening without models or caches. Final review added mandatory distant-heading provenance to bounded scopes. See [T07 results](reports/t07-model-ingestion.md).
- Retained T07 database/cache volumes and ignored raw reports; stopped Gemma after verification. Eight annotations included redundant summaries; retrieval improvement and factual entailment remain unproven. Next: T08 reranking, evidence assembly, supported answers, and model scheduling.

### 2026-10-14 — T06 completed

- Added the pinned offline CPU PDF/OCR adapter, explicit model setup, three synthetic PDF fixtures, source-linked table/section chunking, strict partial-quality policy, and artifact-bound Rust processor integration. Preserved the sole writer, original evidence, existing journal format, and old TXT/JSON request serialization.
- Verified all 66 core tests, 13 live/diagnostic processor checks, 8 disk-volume PDF checks, formatting/lint, Compose configurations, and T01 integrity. Reviewed all six source pages visually. The documented fresh-container CLI ingestion/retry produced 25 blocks/14 chunks and one publication. Exact evidence is in [T06 results](reports/t06-pdf.md).
- Retained downloaded CPU models under ignored `models/`, conversion artifacts under ignored `tmp/pdf/`, and the `vectornext-pdf-demo` volume. No GPU workload was started. English OCR, partial complex tables/graphics, synthetic embeddings, and the lack of a production API/scheduler remain explicit boundaries.
- Next: T07 embeddings and context policies; preserve quality/source metadata and T02's unresolved citation completeness when later implementing answers.

### 2026-10-14 — Initial repository handoff

- Captured confirmed requirements and the architecture proposal from the design conversation.
- Added AGENTS.md, this plan, and architecture.md; expanded README.md with navigation and resume prompts.
- Application code and implementation tasks remain untouched.
- Verification: all local Markdown links resolved; git diff --check passed; all four documentation files had no trailing whitespace. No application tests were run because no application exists yet.
- Next: continue the requested design discussion, or begin T01 when implementation is requested.

### 2026-10-14 — T01 completed

- Implemented `evals/` sources, generator, dataset/schema, validator, measurement contract, and tests; added the evaluation Dockerfile/Compose service and text-line-ending rules. Preserved existing ignore rules and added local artifact paths.
- Verified: five documents / 22 evidence references / 19 questions; 27 tests passed; all final PDF pages visually reviewed; Compose configuration validated. Tests run with network access disabled. Source hashes are recorded in `evals/dataset.json` (SHA-256 `69452ab10e1197d9d3a3a844d4ba596b48d91d462908dd3c6868780f212b0138`).
- Environment: Docker server 29.6.2; evaluation container Python 3.12.13, Poppler 25.03.0, ReportLab 4.4.9, pdfplumber 0.11.9, jsonschema 4.25.1. Python base image digest and package versions are pinned; Debian repositories are not a frozen snapshot.
- Limitations: small synthetic correctness corpus; scan is clean rasterized text; OCR transcription remains manually reviewed; no database/search/inference implementation or measured retrieval quality. Fixture regeneration may change raster hashes across Poppler/font environments and requires review.
- Next: T02 local GPU/model feasibility; storage and retrieval implementation follow in T03/T04.

### 2026-10-14 — T02 completed

- Added the model lock/downloader, official-release CUDA runtime image, CPU ONNX image, dedicated Compose experiment, bounded encoder wrappers, dev-only model smoke checks, host GPU/startup sampler, and five contract tests.
- Archived final and prior-run outcomes in `docs/reports/t02-local-models.json`; documented performance, quality failures, exact model conventions, offline reproduction, and runtime packaging. Updated architecture and instructions without introducing an existing vector database.
- Verification: five T02 tests passed; final GPU smoke exited 0; 14 artifacts verified offline; generation logged 36/36 CUDA layers; 27 responses completed; source/encoder length and server context overflow checks passed; T01 data validation passed. Models persisted across restart/recreation. Services stopped after testing.
- An initial larger-context probe exceeded the reserved input/output budget and was rejected before inference; corrected the test input and reran. The final 3,723-token probe executed but returned an incorrect answer, retained in the report. Earlier results were not discarded.
- Remaining: no database or end-to-end retrieval yet; Gemma E2B with the tested prompt is a hardware baseline with known correctness failures, not a final answer-quality selection.
- Next: T03 core contracts and durability using deterministic vectors; defer further GPU tuning until relevant integration/quality tasks.

### 2026-10-14 — Requested T02 Gemma 4 26B comparison completed

- Added a pinned 26B A4B QAT Q4_0 lock, optional Compose override, model-selection/run variant, request fingerprints and comparison verifier. Large model downloads now use bounded resumable ranges with final whole-file checksums. E2B remains the base configuration; both sets of weights persist locally.
- Two offline GPU runs completed: `20261014T143215Z` with 20 CPU expert layers and selected `20261014T143745Z` with 22. Every baseline request payload reproduced exactly apart from the model alias. Same CPU models/settings, no holdout questions, no prompt/schema tuning. Seven contract tests passed; comparison checks rejected changed prompts/settings, missing cases, and holdout usage.
- Both candidate placements returned correct outcome statuses on 13/13 dev questions, exact status/fields on 10/13, and the correct longer-context answer. Selected placement: 4.136 s median repeated short request, 18.079 s larger probe, 64.56 s startup, 6,889 MiB sampled device peak, 16.33 GiB container peak memory including file cache. All 27 responses schema-valid; overflow rejection passed; services stopped afterward.
- Remaining issues: non-answer fields are null-valued instead of empty objects; table/cross-page citations can omit necessary context. Strict citation completeness fell from 14/23 to 13/23, partly because of redundant JSON gold references and partly real context omissions. No answer postprocessing was used to improve scores. Dataset size remains too small for production-quality conclusions.
- Archived both runs, identities, responses, comparisons, and source hashes in `docs/reports/t02-gemma4-26b.json`; explanation in the matching Markdown report. The 26B profile is the preferred generation-quality experiment candidate, not a database dependency or final product selection.
- Next: T03 contracts/storage with deterministic vectors. Address status-specific schemas and complete evidence citations in T07/T08/T10; no further model benchmark is required for storage work.

### 2026-10-14 — T02 output-schema experiment completed

- Confirmed both generation baselines already used temperature 0. Added optional `--schema-mode status` with separate complete schema branches: supported outputs require all requested typed/nullable fields; non-answers require empty fields. Original prompts, model configuration, and legacy reproduction remain available.
- Added four contract tests (11 total) and schema-specific comparison verification. The original model comparison still validates all 27 archived requests; schema comparisons reject unrelated prompt, temperature, model, and dataset changes.
- First run `20261014T145123Z` was interrupted because another workload already occupied about 5.3 GiB at 97% GPU utilization before model startup. Zero answers completed. Stopped only our service and retained the error/evidence. Retried after the user requested it and GPU usage fell.
- Successful run `20261014T145846Z`: 13/13 exact status/fields in both passes; 27/27 including the larger probe; all responses schema-valid with valid source IDs; explicit zero and supported raw null preserved; overflow rejection passed. Repeated short median 4.389 s, longer request 18.507 s. Service stopped afterward.
- Citation completeness stayed 13/23. No output cleanup or gold-dependent constraints were used. Full evidence and limitations are in `docs/reports/t02-status-schema.md` and its JSON record, including the interrupted attempt.
- Next: T03. Transfer the tested status-dependent contract into T08 when the production answer pipeline exists; complete context/citation support remains unresolved.

### 2026-10-14 — T04 completed

- Added the retrieval contract, Rust exact/keyword/filter/fusion/dedup modules, independent ranking tests, and an offline source-coverage diagnostic example/report. Extended the core Docker build to include integration/example tests; preserved T03 storage format and all prior model/evaluation work.
- Verified 38 core tests, clean formatting/lint, eight recorded diagnostic cases, and archived source hashes. The controlled cases intentionally retain losses caused by candidate/final budgets and incorrect filters; no real-embedding or answer-quality claim follows from these results.
- Updated README, architecture, instructions, and evaluation metrics guidance. No model service ran and no holdout questions were used.
- Next: T05 TXT/JSON ingestion and durable jobs, with deterministic model substitutes and publication through existing storage contracts.
