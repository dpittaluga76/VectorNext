# VectorNext build plan and handoff

Last updated: 2026-10-14.
Design reference: [architecture.md](architecture.md).

## Current state

- Phase: T01 through T10 complete.
- Implemented: Rust storage/retrieval and TXT/JSON/PDF ingestion, durable jobs, and 66 foundation tests (18 storage, 20 TXT/JSON/job durability, 8 PDF, 18 retrieval, 2 diagnostic); offline CPU Docling/Tesseract adapter with 13 tests; synthetic fixtures/schema/validator and 27 T01 tests; an offline Docker local-model experiment with pinned downloads, GPU generation, CPU embeddings/reranking, 11 T02 contract tests, optional status-dependent output constraints, and archived measurements.
- T07 implemented: real MiniLM embeddings, three context policies, separately attributed Gemma 4 26B annotations, bounded caches, Docker ingestion/inspection/probe tools, seven additional Rust tests and five Python worker tests. Total core checks: 73.
- T08 implemented: snapshot-scoped hybrid retrieval/CPU reranking, budgeted source evidence assembly, two-stage Gemma answers, exact JSON pointer reads, source/type checks, deterministic templates, separate prose drafts, complete filtered structured lookup, and bounded generation priority. Ten additional Rust tests bring the core total to 83; Python worker/answer/scheduler coverage totals 18. All 13 source-authored development cases passed; see [T08 results](reports/t08-answers.md) for qualifications and prior failures.
- T09 implemented: shared Rust API/database owner, isolated CPU service with bounded lanes, local client, capability readiness, three-service Compose, and offline checksummed export/restore. Six new Rust checks bring the total to 89; four CPU transport checks bring Python worker coverage to 22. Integrated TXT/JSON/PDF ingestion, actual GPU answers, full model outages, restart/rebuild, interrupted work and exact restoration passed; see [T09 results](reports/t09-deployment.md).
- T10 complete: isolated evaluation runner, source-coverage/answer scorer, independent keyword weights, bounded answer budgets and stage/resource/queue measurements. Six configurations produced 156 responses on the same 13 development questions, cold/warm; only one-primary context failed the table question in both passes. Two primaries passed 26/26 and reduced median response time by 30–32%, but five remain the general default. Generated context added ingestion cost without final answer gain. The 400-document/12,800-vector capacity probe measured 9.946-ms median hybrid search; this is supplied-vector capacity, not corpus quality. Verified 90 Rust, 36 fixture/scorer and 22 worker/transport checks, Linux formatting/Clippy and Compose. See [T10 results](reports/t10-evaluation.md). Six holdout questions remain unused.
- Not implemented: web UI, public authentication/multi-user service, corpus aggregates, approximate indexing, or a broad independent-corpus quality benchmark.
- Available: public project overview and quickstart in the [README](../README.md), detailed [development/operations commands](development.md), repository instructions, architecture, this task plan, the [storage specification](storage.md), [retrieval specification](retrieval.md), [source-coverage diagnostics](reports/t04-retrieval.md), and [evaluation guide](../evals/README.md).
- User-confirmed scope: our own vector database; local models and GPU; Docker; TXT/PDF/JSON; approximately 400 files of 10–30 KB; MinIO/Redis optional.
- Adopted: Rust storage/retrieval and deterministic TXT/JSON preparation, CPU Python Docling/Tesseract PDF artifacts, source-preserving PDF chunking and partial-quality policy, serializable processor stages, separate durable jobs, version-1 journal/checkpoint contracts, Linux/Docker durability, immutable per-space indexes, exact cosine, BM25, typed filters, RRF, and conservative evidence deduplication. T07 adopts a persistent Python child in the CLI container and a separate GPU generation service. T08 adds CPU reranking, source-linked typed answers, and bounded GPU priority. T09 adds shared application ownership, CPU admission, isolated services and verified backups.
- Exact model artifacts are pinned as T02 feasibility baselines; final quality selection, stable public API compatibility, and quality/latency thresholds remain open. The initial evaluation dataset contract is implemented; broader benchmark data remains future work.
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

Agree on quality/latency targets and add an independent corpus with realistic distractors, distant multi-passage evidence, conflicting records and harder tables/OCR. Compare the default five-primary and opt-in two-primary settings there before changing defaults. Keep the existing six holdout questions separate. Read [T10 results](reports/t10-evaluation.md) first: the current seed is saturated, and generation dominates measured latency. T10 services are stopped; databases/caches and ignored `data/t10/20261014` captures are retained under the dedicated `vectornext-t10` project. T07/T09 data remains untouched. The numbered T01–T10 queue is complete; scope the next task from this evidence rather than automatically adding infrastructure.

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

## Session handoff discipline

Keep the Current state and Next useful step sections accurate. For each meaningful work session, add one concise entry below with changed files/capabilities, task IDs, verification actually performed, unresolved issues, and the next step. Do not paste full chat transcripts or command logs.

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
