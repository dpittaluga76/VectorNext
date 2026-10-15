# Development and operations guide

Detailed setup, backup, verification and lower-level experiment commands for VectorNext. For the project overview and shortest demo, start with the [README](../README.md). Run all commands from the repository root. The integrated application is the normal entry point; the earlier CLI examples are isolated development tools.

## Run the integrated local application

Use Docker Desktop with Linux containers/WSL 2 and NVIDIA GPU support. Setup needs network access and disk space for images plus the pinned Gemma 4 26B weights (about 14.44 GB), CPU models and PDF assets. Normal operation uses local files. If T02/T06 models already exist, the setup tools verify and reuse them:

```sh
docker compose -f compose.models.yaml -f compose.models.26b.yaml build model-download
docker compose -f compose.models.yaml -f compose.models.26b.yaml run --rm --no-deps model-download
docker compose -f compose.processor.yaml build processor
docker compose -f compose.processor.yaml run --rm pdf-setup
docker compose -f compose.app.yaml build
docker compose -f compose.app.yaml up -d
docker compose -f compose.app.yaml run --rm client ready
```

Readiness initially returns a nonzero exit code while models load; retry until all capabilities are ready (the T10 model restart took about 137 seconds on this host; startup varies). The API is available at `http://127.0.0.1:8088`; the CPU processor and GPU runtime have no published ports. Only the GPU runtime requests NVIDIA access. Avoid running the older experiment GPU service concurrently.

Ingest the supplied fictional TXT/JSON/PDF examples and ask the original Pele question:

```sh
docker compose -f compose.app.yaml run --rm client ingest /app/evals/fixtures/fictional_matches.txt --document fictional_matches --job fictional_matches-v1 --wait
docker compose -f compose.app.yaml run --rm client ingest /app/evals/fixtures/nested_matches.json --document nested_matches --job nested_matches-v1 --record-pointer /matches --wait
docker compose -f compose.app.yaml run --rm client ingest /app/evals/fixtures/scanned_note.pdf --document scanned_note --job scanned_note-v1 --wait
docker compose -f compose.app.yaml run --rm client search "Pele Argentina 1954"
docker compose -f compose.app.yaml run --rm client ask /app/tests/fixtures/answers/pele.json
docker compose -f compose.app.yaml run --rm client jobs
```

Structural context is the default; add `--policy generated` for local Gemma contextual enrichment. Failed jobs stay inspectable: `client job JOB_ID`, then `client retry JOB_ID` and `client wait JOB_ID` after the dependency recovers. Identical uploads with the same job ID reuse the original receipt. Replace a document with a new job ID and `--expected-revision CURRENT_REVISION`. Busy model lanes return a retryable error; source inspection/keyword search can continue during ingestion.

For your own files, use the standard-library host client (`python -m deployment.client ingest path/to/file.pdf --document my-file --job my-file-v1 --wait`) or mount an input directory read-only into the containerized client. `client document DOCUMENT_ID` inspects the complete revision and source locations. The CLI preserves exact JSON numeric literals. This initial interface is intended for a local single user and has no web UI/authentication. See [the deployment contract](deployment.md) for API schemas, limits and failure behavior.

Data and cache use separate persistent Docker volumes; weights stay in ignored `models/`. Configure `VECTORNEXT_MODELS_DIR`, `VECTORNEXT_PORT`, `VECTORNEXT_BACKUPS_DIR` or `VECTORNEXT_DATA` before invoking Compose when different paths/ports are needed. Rebuilding images and recreating containers preserve these mounts. Do not use `down -v` on data you want to keep.

To export and restore, use new directory names each time. The API must be stopped for export; the admin tool has no network or model dependency:

```sh
docker compose -f compose.app.yaml stop vectornext
docker compose -f compose.app.yaml run --rm admin export /storage/db /backups/my-backup
docker compose -f compose.app.yaml run --rm admin restore /backups/my-backup /storage/restored
docker compose -f compose.app.yaml run --rm admin inspect /storage/restored
```

The export appears under the host's ignored `backups/my-backup/`. Restore verifies the complete file manifest, exact records, jobs and receipts, and refuses to overwrite an existing database. Set `VECTORNEXT_DATA=/storage/restored` in your shell (PowerShell: `$env:VECTORNEXT_DATA='/storage/restored'`) before `docker compose -f compose.app.yaml up -d vectornext` to serve the restored copy. Retain that setting for subsequent recreations. Without it, `/storage/db` remains the default. Keep a separate copy of the backup outside the original disk when protecting against disk failure.

Stop this stack with `docker compose -f compose.app.yaml stop`; volumes and models remain. The earlier Compose files below are lower-level development tools. Their database-owning CLIs should not open the application volume while its API is running.

## Run the evaluation checks

With Docker Desktop running Linux containers, run from the repository root:

```sh
docker compose build evals
docker compose run --rm evals
docker compose run --rm evals python -m unittest evals.test_validate -v
```

The first build downloads dependencies. Validation then runs offline, without a GPU or local model. Rebuild after changing evaluation files. The suite checks five synthetic TXT/PDF/JSON documents, 22 evidence references, and 19 questions; these fixture checks validate integrity; the separate T10 runner measures retrieval and answer outcomes. See the [evaluation guide](../evals/README.md) for coverage, regeneration, and limitations.

## Run the storage and retrieval checks

With Docker Desktop running Linux containers, from the repository root:

```sh
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo fmt --check
docker compose run --rm core cargo clippy --locked --offline --all-targets -- -D warnings
```

The first build acquires a digest-pinned Rust 1.87.0 image and locked Cargo dependencies. Checks then run offline with no GPU, ports, or model files. The container filesystem is read-only; Cargo and test databases use disposable `/tmp` space, which permits execution of compiled tests. Rebuild after code changes. The ignored `child_process` test is a helper invoked automatically by the forced-termination test, not skipped recovery coverage.

T07 adds seven context-policy/recovery tests, T08 adds ten answer tests, T09 adds six service/backup tests, T10 adds one answer-options check, and T11 adds one UTF-8 source-mapping regression to the previous 66 checks, for 91 passing Rust checks. Two ignored test functions are subprocess helpers invoked by the termination tests. The default core command includes all targets, so the example's source-coverage tests run too.

The public library exposes `Database::open`, `put_original`, `commit(Batch)`, `snapshot`, and `checkpoint`. A `ReadSnapshot` exposes committed documents and embedding spaces. Supply complete prepared records and vectors to a batch; retries keep the same operation ID. See [the contracts](../src/contracts.rs) and [storage specification](storage.md). Native Windows durable storage is deliberately unsupported; run it on Linux in Docker with a data volume. This is a library verification service, not an HTTP application.

For retrieval, build `SearchIndex::build(snapshot, space_id, KeywordConfig::default())`, then call `search` with `SearchRequest::keyword(...)` or `SearchRequest::hybrid(..., QueryVector { ... })`. Responses include each ranking stage, filter counts, keyword score explanations, and duplicate mappings. Resolve hits through the same index to get their original chunks/source references. Build a fresh index after a new database generation; old indexes remain consistent old readers.

Run just the retrieval tests or print the deterministic source-coverage report:

```sh
docker compose run --rm core cargo test --locked --offline --test search
docker compose run --rm core cargo run --locked --offline --example search_eval
```

The example creates six synthetic documents/eight chunks in a temporary database and reports eight controlled cases. It uses supplied vectors and prepared source locations; it does not test a parser, real embeddings, or answers. All report settings and limitations are included in its JSON. [Archived results](reports/t04-retrieval.md) include exact source hashes and the image identity.

To exercise test databases on a Docker disk volume instead of memory-backed `/tmp`:

```sh
docker volume create vectornext-core-checks
docker compose run --rm -e TMPDIR=/storage -v vectornext-core-checks:/storage core
```

During T03, all 18 storage tests passed both in memory-backed temporary storage and on a Docker disk volume. The suite creates and removes its own temporary databases inside that volume. Full truncation testing is slower on disk because it performs thousands of durable flushes. The volume can be reused. These are crash/I/O simulations, not a host power-loss certification. Journal/job frames still have a 64 MiB cap. T21 writes checkpoints as a [version-2 stream of bounded frames](storage.md#t21-bounded-checkpoint-stream), while accepting old snapshots. Export still has an 8 GiB total bound; the journal, old originals and retry history remain until future compaction work. Older binaries cannot read a new checkpoint: retain an untouched pre-upgrade copy for rollback. [Large-state verification commands](../experiments/t21/README.md).

## Ingest with real local models

First acquire the pinned models using the [T02 setup instructions](../experiments/t02/README.md), including the optional **26B** model for generated context. Normal inference stays on an internal Docker network without published ports. The CPU worker has a four-CPU/4-GiB limit; Gemma uses the RTX 4060 and CPU expert offload.

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml build ingest
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest /storage/structural fictional evals/fixtures/fictional_matches.txt fictional-v1 structural
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest probe /storage/structural "fictional soccer match records" structural
```

Select `plain`, `structural`, or `generated`. For the generated policy, start Gemma and wait for its checksum verification/loading to finish:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml --profile generation up -d --wait --wait-timeout 300 llm
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest /storage/generated fictional evals/fixtures/fictional_matches.txt fictional-v1 generated
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest /storage/generated nested evals/fixtures/nested_matches.json nested-v1 generated - /matches
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest /storage/generated equipment evals/fixtures/equipment_guide.pdf equipment-v1 generated tests/fixtures/pdf/equipment_guide.json
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm ingest inspect /storage/generated
docker compose -p vectornext-t07 -f compose.ingestion.yaml stop llm
```

PDF ingestion consumes the validated T06 extraction artifact; the bundled captures match the bundled originals. Use the [PDF workflow](pdf-ingestion.md) to produce an artifact for a new PDF. Mount new sources/artifacts read-only into the ingest container. `probe` is a diagnostic call to existing exact/BM25 search, with real query embeddings and explicit policy field weights; it does not generate answers. `inspect` opens committed data and durable job status without loading models.

Repeat the exact ingest command to resume a failed job. Reusing a job ID with changed bytes/configuration fails deliberately: use a new job ID for a replacement. Databases live in the `vectornext-t07_ingestion-data` Docker volume; the separate `vectornext-t07_ingestion-cache` volume is disposable. A committed retry does not recompute stages, though the ingestion CLI still validates/loads the encoder at startup. The worker shares CLI filesystem permissions and never receives a database handle; the integrated T09 service isolates it from the database volume. T08 adds priority admission inside the GPU container.

CPU model checks and the optional three-policy fixture smoke run:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m unittest model_worker.test_worker -v
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m model_worker.verify_ingestion --root /storage/policy-check --output /storage/policy-check.json
```

The smoke run requires Gemma for uncached generation, indexes all five source fixtures, and checks one technical retrieval probe. It does not load evaluation questions/answers or measure answer quality. Use a fresh database root to exercise ingestion again; matching inputs may reuse cached results. See [T07 results](reports/t07-model-ingestion.md) for actual verification and limitations.

## Ask questions with local models

After indexing the fictional TXT document above, start Gemma and run the bundled request:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml build ingest
docker compose -p vectornext-t07 -f compose.ingestion.yaml up -d --wait --wait-timeout 300 llm
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint ask ingest /storage/generated tests/fixtures/answers/pele.json
```

The JSON report contains the original question, candidate scores, expanded original evidence, source references, assessment/model identities, validated typed fields and formatted text. The example returns `Match year 1954, Pele goals: 3, rival: Argentina` from explicitly fictional data. To supply another request in PowerShell, mount its folder read-only:

```powershell
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint ask -v "${PWD}/requests:/requests:ro" ingest /storage/generated /requests/question.json
```

A request supplies `question` and `fields` (names with `kind`: `string`, `integer`, `number`, or `boolean`). Optional inputs are `history` (`role`/`text`), `filter`, `template` with `{field}` placeholders, and `prose: true` for a separate presentation draft. `nullable: true` explicitly permits a stored raw JSON null. Missing values remain insufficient evidence. `scope: structured_lookup` requires an explicit filter and a relative JSON `pointer` for every field; it scans complete eligible records without Gemma. `scope: corpus_aggregate` is rejected. See [the answer contract](answers.md) for limits and semantics.

Generation requests from questions take priority over waiting enrichment. Active generation is not preempted; overload/expired waits fail explicitly. This is a development CLI, not the T09 application server. It releases its writer lock before inference, but cannot open its initial snapshot while an ingestion CLI holds that lock. The output's mechanical schema/source checks do not certify semantic correctness.

CPU/model/scheduler checks and an optional live queue check:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m unittest model_worker.test_worker model_worker.test_answers model_worker.test_scheduler -v
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m model_worker.verify_scheduler
```

The live queue check requires an idle, healthy Gemma service and generates three short responses. It verifies interactive priority and responsive health checks. Development answer checks use the five-source corpus created by `model_worker.verify_ingestion`:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m model_worker.verify_answers /storage/policy-check/generated /storage/t08-check
docker compose -p vectornext-t07 -f compose.ingestion.yaml stop llm
```

Keep Gemma running for those live checks. The answer check writes separate raw outputs, errors and correctness results; it does not use the T01 holdout labels. Cold CPU-model startup is included in each CLI timing. See [T08 results](reports/t08-answers.md) for observed quality and latency.

## Ingest a TXT or JSON file with the synthetic test encoder

The T05 inspector uses an explicitly synthetic encoder to exercise parsing, durable stages, and publication. It does not provide semantic embeddings or answers. Create a persistent Docker volume, then ingest a bundled synthetic fixture:

```sh
docker volume create vectornext-ingestion-demo
docker compose run --rm -v vectornext-ingestion-demo:/storage core cargo run --locked --offline --example ingest -- /storage/db fictional evals/fixtures/fictional_matches.txt fictional-v1
docker compose run --rm -v vectornext-ingestion-demo:/storage core cargo run --locked --offline --example ingest -- /storage/db nested evals/fixtures/nested_matches.json nested-v1 /matches
```

Repeat either command to verify its completed receipt without another publication. An interrupted job resumes from its saved stage. A new job ID replaces the current revision of the same document; reusing an ID with changed bytes/configuration fails. To ingest your own files, add a read-only input bind mount and pass the corresponding container path. Input extensions must be `.txt` or `.json`; TXT is strict UTF-8 with optional BOM. The volume retains originals, jobs, and published data across containers.

Both commands were verified in fresh containers: TXT produced 6 blocks/4 chunks, and nested JSON produced 7 blocks/7 chunks. Retrying the TXT job reused its first receipt while the database remained at generation 2. All 20 ingestion/durability checks also passed on a Docker disk volume.

Library entry points are `submit_ingestion`, `ingestion_job(s)`, and `advance_ingestion`. `ingestion_stage_request`/`accept_ingestion_stage` expose the serializable processor boundary. See [the ingestion contract](ingestion.md) for mappings, record pointers/IDs, exact typed attributes, budgets, recovery, and limitations. Test only ingestion on a Docker disk volume with:

```sh
docker compose run --rm -e TMPDIR=/storage -v vectornext-core-checks:/storage core cargo test --locked --offline --test ingestion
docker compose run --rm -e TMPDIR=/storage -v vectornext-core-checks:/storage core cargo test --locked --offline --lib ingestion::jobs::tests
```

## Ingest a PDF locally

T06 adds a CPU-only Docling/Tesseract processor. Build/setup require network access; normal conversion and verification run offline. Setup downloads about 367 MiB of checksum-pinned layout/table models into the ignored `models/` directory. It reuses valid files. No GPU is used by this processor.

```sh
docker compose -f compose.processor.yaml build processor
docker compose -f compose.processor.yaml run --rm pdf-setup
docker compose -f compose.processor.yaml run --rm processor
docker compose -f compose.processor.yaml run --rm processor python -m processor.pdf /app/evals/fixtures/equipment_guide.pdf /output/equipment.json
```

The last command writes `tmp/pdf/equipment.json`. It contains text, structural context, table rows/cells, page rectangles, extraction methods, and diagnostics. The processor only reads PDFs/models and writes artifacts; it cannot access the database. Convert your own file by adding a read-only input bind mount and passing its container path.

In PowerShell on the target Windows host, publish the artifact through the Rust job coordinator:

```powershell
docker compose build core
docker volume create vectornext-pdf-demo
docker compose run --rm -v vectornext-pdf-demo:/storage -v "${PWD}/tmp/pdf:/input:ro" core cargo run --locked --offline --example ingest_pdf -- /storage/db equipment evals/fixtures/equipment_guide.pdf equipment-v1 /input/equipment.json
```

Repeat the ingestion command to reuse its completed receipt. The original PDF passed to Rust must match the artifact's hash. New bytes, parser profile, or partial-extraction policy require a new job ID. The inspector still uses `TestEncoder`; semantic models and generated context are T07.

Partial extraction is rejected by default. Inspect the artifact warnings, then explicitly append `--allow-partial` to the inspector command if retaining the recovered text is appropriate. The committed document retains those warnings. Blank/unsupported evidence never becomes a fabricated answer. English OCR is the initial profile; diagrams/charts are not interpreted and ambiguous multi-page tables are reported as partial. See [PDF contracts](pdf-ingestion.md) and [T06 results](reports/t06-pdf.md).

The processor is bounded to two CPUs, 4 GiB RAM, 32 pages, 16 MiB input/output, 20-inch page dimensions, and a 180-second CLI timeout. It runs one conversion per CLI; the integrated T09 processor adds shared admission and an API around this adapter. Run PDF ingestion tests on a Docker disk volume with:

```sh
docker volume create vectornext-core-checks
docker compose run --rm -e TMPDIR=/storage -v vectornext-core-checks:/storage core cargo test --locked --offline --test pdf_ingestion
```

## Evaluate context policies and retrieval budgets

T10 adds an isolated local comparison on port 8089, source-coverage/answer scoring, original-source review, stage timings, resource sampling, offline query replays and a separate supplied-vector capacity probe. Read the [protocol](evaluation.md), [results](reports/t10-evaluation.md) and [reproduction guide](../evals/README.md). All inference stays in the existing three containers; the standard-library host runner orchestrates them and measures API latency. Models must already be set up. Holdout questions are excluded.

The runner's `--run` selects fresh captures/caches; use a fresh `--database-root /storage/<name>` as well for a new corpus comparison. Run policies and variants sequentially. It refuses existing ingestion/captures and retains volumes. Source labels and generated annotations are scored separately; exact output format alone does not establish factual support.

`POST /v1/ask` accepts an optional `options` object beside `request` and `space_id`: `{"candidates":30,"rerank_limit":20,"primary_limit":5,"rerank":true}`. The default remains 30/20/5. A smaller `primary_limit` is an explicit experiment, not an automatic speed mode. `VECTORNEXT_STRUCTURAL_WEIGHT` and `VECTORNEXT_GENERATED_WEIGHT` configure keyword fields at application startup (both default to 1, range 0–10); selecting plain embeddings alone does not disable structural keywords. `GET /v1/metrics` exposes cumulative process counters; each answer includes bounded options and monotonic stage timings. See [API details](deployment.md).

On the 13-question development seed, two primaries preserved all answers in both cache passes and reduced median response time from about 18 seconds to 12 seconds; one primary missed the table answer. Five remain the general default. Generated context added ingestion cost without final answer improvement. Exact hybrid search over 12,800 supplied vectors took about 10 ms median; this capacity probe does not establish quality on 400 real documents.

T11 adds a separate [public-source dataset and reproduction guide](../evals/independent/README.md), using an isolated project on port 8091. All 112 requests completed across four blocks: five scored 16/28 and two 15/28 in each cache pass. Two reduced median latency by 46–50% but lost required evidence. Both PDF admission failures remain in the denominator; read [the report](reports/t11-independent.md) for failures, source-review exceptions, the retained pre-query UTF-8 repair and verification commands. Do not overwrite its frozen inputs or reuse its captures for a new run. Services are stopped; volumes and caches remain available.

## Resuming with Codex

Open this repository and describe the work you want to do. For example:

> Read AGENTS.md, docs/architecture.md, and docs/plan.md. Summarize the current state and the most important unresolved design choice. Continue the architecture discussion without implementing code yet.

When ready to build:

> Read the project instructions and design, then implement the next ready task in docs/plan.md. Verify its acceptance criteria and update the handoff with the results.

The T01–T13 queue is complete. T12's [workflow reporting guide](workflow-debugging.md) covers readable CLI output, saved Markdown and offline captures; see the [fresh Voyager example](reports/t12-voyager-workflow.md). T13 adds [recovery and diagnostics](reliability.md), verified in a fresh CPU drill. Remaining proposed work is T14 evidence coverage. Read [T11 results](reports/t11-independent.md) before changing defaults. Preserve the six existing holdout questions and retain T11 as observed regression evidence; these results do not establish broad retrieval quality.
