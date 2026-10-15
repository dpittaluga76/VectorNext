# Filter profiling and indexing

Read the [frozen protocol](../../docs/t22-protocol.md), [filter contract](../../docs/retrieval.md#filter-execution-indexes-t22) and [results](../../docs/reports/t22-filters.md). No GPU, model calls, PostgreSQL timing run or normal-service upgrade is required.

Requirements: Docker Desktop, Git history containing `c7427f3`, and Python 3.12 (standard library only) for host orchestration. All database work runs in Linux containers. The paired run uses stopped T20 fixture stores and existing synthetic input files. Preserve them; recreate T20 in its historical checkout if those local artifacts are unavailable.

Build a fresh baseline context and the optimized image from the repository root:

```powershell
python experiments/t22/prepare_baseline.py data/t22/baseline-repeat01
docker build -f data/t22/baseline-repeat01/docker/filter-profile.Dockerfile -t vectornext-filter:t22-baseline-final data/t22/baseline-repeat01
docker build -f docker/filter-profile.Dockerfile -t vectornext-filter:t22-indexed .
```

Before the first run, create the dedicated copy (only when the destination volume is new and empty):

```powershell
New-Item -ItemType Directory -Force data/t22
docker volume create vectornext-t22-data
docker run --rm --network none --entrypoint python -v vectornext-t20-v3_vector_data:/old:ro -v vectornext-t22-data:/work -v "${PWD}/experiments/t21:/tools:ro" -v "${PWD}/data/t22:/reports" vectornext-checkpoint:t21 /tools/copy_data.py copy /old /work /reports/source-volume-hashes.json
python experiments/t22/run.py run data/t22/repeat01
```

Check every exit status. Copy and report creation refuse overwrite; the runner refuses an existing capture directory. Repeats may reuse the unchanged T22 fixture copy sequentially; never run two profilers against its writer lock at once. Images are resolved to immutable IDs before execution. Source/input hashes are checked after each block. Eight processes perform baseline/indexed/indexed/baseline at two sizes, with 528 requests each. All complete response hashes must agree. Timings exclude response hashing and report writing.

Run regressions and inspect construction counters:

```powershell
docker compose build core
docker run --rm --network none vectornext-core:latest cargo test --locked --offline --all-targets
docker run --rm --network none vectornext-core:latest cargo fmt --all -- --check
docker run --rm --network none vectornext-core:latest cargo clippy --locked --offline --all-targets -- -D warnings
docker run --rm --network none -v vectornext-t22-data:/work vectornext-core:latest cargo run --locked --offline --example filter_index_info -- /work/1600
docker run --rm --network none --entrypoint python -v vectornext-t20-v3_vector_data:/old:ro -v vectornext-t22-data:/work:ro -v "${PWD}/experiments/t21:/tools:ro" -v "${PWD}/data/t22:/reports:ro" vectornext-checkpoint:t21 /tools/copy_data.py check-source /old /work /reports/source-volume-hashes.json
```

Retain images, the T22 volume and captures. Every profiler container exits and is removed automatically; there are no persistent benchmark services. Full core checks include independent cosine/BM25 references, exact typed filtering, revision/recovery checks and the new scan/index equivalence suite. No measured corpus is generated during tests.
