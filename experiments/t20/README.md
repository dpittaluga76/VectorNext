# VectorNext / PostgreSQL + pgvector benchmark

**Historical deployment:** `compose.benchmark.yaml` has been removed from the current checkout. Deployment commands and the runner below require the recorded experiment source environment. See [configuration history and prior revision](../../docs/tasks-done.md#experiment-compose-cleanup). Frozen protocols, manifests and results are unchanged.

This CPU-only experiment compares the existing Rust storage/search implementation with PostgreSQL 18 + pgvector 0.8.7. It does not use model inference, user documents, semantic labels or historical evaluation data. Read [the frozen protocol](../../docs/t20-protocol.md) and [checkpoint/recovery amendment](../../docs/t20-protocol-amendment-01.md) before interpreting timings.

Two deterministic corpora contain 400 / 1,600 documents and 12,800 / 51,200 supplied 384-dimensional vectors. An independent float64 oracle checks top-10 cosine results. Exact results and pgvector HNSW profiles are reported separately, including filtered queries, recall, errors, latency, ingestion, resources and process-interruption recovery.

## Build and check

From the repository root, with Docker Desktop running:

```powershell
docker compose -f compose.benchmark.yaml build
docker run --rm --network none --entrypoint python vectornext-benchmark-runner:t20 -m unittest experiments.t20.test_benchmark -v
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo fmt --all -- --check
docker compose run --rm core cargo clippy --locked --offline --all-targets -- -D warnings
```

Builds require network access for pinned dependencies/images. Experiment containers use an internal network with no published ports or GPU/database-model mounts. Each database gets 2 CPUs and 4 GiB RAM; the driver has its own limit. The dedicated subnet avoids Docker's exhausted automatic address pool on the test host; choose a different unused subnet if it conflicts with your environment.

## Run a fresh comparison

Every repeat needs a **new Compose project, unused subnet and new run directory**. Never reuse an existing measured schema/database or overwrite an existing capture. The following PowerShell example uses distinct names; change them for another run. The output directory is `data/t20/my-comparison-01` and is ignored by Git.

```powershell
$benchmarkProject = 'vectornext-t20-repeat01'
$benchmarkRun = 'my-comparison-01'
$env:T20_SUBNET = '10.219.21.0/28'
docker compose -p $benchmarkProject -f compose.benchmark.yaml up -d --wait vectornext postgres
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps --entrypoint python -w /source runner -m experiments.t20.smoke
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner prepare --run $benchmarkRun
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner run --run $benchmarkRun --size 400
docker compose -p $benchmarkProject -f compose.benchmark.yaml kill -s SIGKILL vectornext postgres
docker compose -p $benchmarkProject -f compose.benchmark.yaml up -d --wait vectornext postgres
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner recover --run $benchmarkRun --size 400
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner run --run $benchmarkRun --size 1600
docker compose -p $benchmarkProject -f compose.benchmark.yaml kill -s SIGKILL vectornext postgres
docker compose -p $benchmarkProject -f compose.benchmark.yaml up -d --wait vectornext postgres
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner recover --run $benchmarkRun --size 1600
docker compose -p $benchmarkProject -f compose.benchmark.yaml run --rm --no-deps runner summarize --run $benchmarkRun
docker compose -p $benchmarkProject -f compose.benchmark.yaml stop vectornext postgres
```

Check every exit code before continuing. The two explicit kills target only the selected benchmark project and exercise acknowledged-data recovery. Normal VectorNext is unaffected. Stop retains volumes; do not use `down -v` or prune them. The two-document smoke corpus lives separately under `/storage/2` and PostgreSQL schema `t20_2`.

## Captures and interpretation

- `manifest.json`: exact corpus/query and execution-source hashes. Runner commands refuse changed source/input files after preparation.
- `<size>/documents.jsonl`, `vectors.npy`, `queries.json`, `sentinel.json`: frozen generated inputs, independent reference results and separate recovery sentinel.
- `<size>/run/ingestion.jsonl`: acknowledged per-document timings, with alternating engine order.
- `preparation.json`, `plans.json`, `final.json`: index costs, actual SQL plans, versions/settings, storage and whole-service cgroup memory/CPU counters.
- `queries.jsonl`: every first/warm request, returned IDs/scores, error, correctness and recall. Summary refuses incomplete/duplicated captures.
- `recovery-pending.json`, `recovery.json`: sentinel acknowledgement after the checkpoint attempt, complete data digests and all exact query results after interruption.
- `checkpoint.json`: checkpoint success/failure and any reopening required after rejection. A rejected VectorNext checkpoint is reported as journal recovery, never successful checkpoint recovery.
- `summary.json`: fixed-group p50/p95/p99 and quality/ingestion/resource summaries. Empty-query correctness is separate from recall, which is undefined for an empty expected set.

Archive image IDs/digests, resolved Compose configuration and host hardware/load alongside the run. The versioned report records these for the original execution. Large generated corpora, volumes and raw captures stay outside Git; tests never regenerate a measured corpus.

The comparison uses a benchmark-only HTTP adapter for supplied vectors and PostgreSQL's wire protocol. Client timing includes request serialization and response decoding; inner Rust timings and PostgreSQL EXPLAIN samples have different boundaries. VectorNext stores richer internal provenance; PostgreSQL uses a normalized document/chunk schema. HNSW-labelled configurations may choose exact plans for selective filters. Memory includes page cache and setup; WAL bytes are cluster-wide. The protocol and results must disclose these differences rather than treating any single latency as an overall database ranking.
