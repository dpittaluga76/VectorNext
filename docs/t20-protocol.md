# T20: VectorNext / PostgreSQL + pgvector protocol

Frozen design before timed queries, 2026-10-15. This is a synthetic CPU storage/vector-search comparison, not a retrieval-relevance or RAG-quality evaluation. PostgreSQL is experiment tooling only. No historical corpus or holdout is consumed.

## Fixed workload

- Two independent databases/schemas: 400 and 1,600 documents, 32 chunks per document, 384 float32 coordinates. Each document has about 20 KiB of synthetic source text. Both engines receive the same original text, chunk text, identities, numeric bucket attributes and vector coordinates.
- NumPy PCG64 seed 20261015, 128 normally distributed cluster centers, cluster assignment uniformly random, independent normal noise at scale 0.35, L2 normalization then float32 conversion. Queries are separately sampled from the same distribution; none is copied from a stored vector. This artificial geometry is not representative of every embedding model.
- 32 independent query vectors, each issued under four scopes: all rows, the first 5% of document IDs, numeric bucket 0 (document index modulo 100, exactly 1%), and bucket -1 (empty). Top-k=10. No BM25, model inference, parsing, reranking or answer generation.
- The generated files, query order/reference results and source/configuration files receive SHA-256 manifests before the run. Existing captures are never overwritten. Smoke/unit fixtures are separate from the measured runs.

## Correctness and approximate search

The independent oracle computes cosine in NumPy float64 from the supplied float32 coordinates, sorts by descending cosine then stable chunk key, and retains all scores within 1e-5 of the kth score for boundary-tie assessment. Strict recall@10 and tie-tolerant exact correctness are reported separately. Results must contain unique eligible IDs, the expected count, and scores within 1e-5 of the oracle. Empty results must be empty. Query failures score zero and remain in planned denominators; empty-query correctness is separate from nonempty recall.

VectorNext uses its existing `SearchIndex` dense branch with keyword search/deduplication disabled. PostgreSQL exact SQL orders by cosine distance plus zero, then ID, preventing the approximate index from satisfying that ordering. Store EXPLAIN plans and verify exact queries do not use HNSW. PostgreSQL retains ordinary B-tree filter indexes.

HNSW is an additional competitor configuration, not a substitute for exact results: `m=16`, `ef_construction=64`, `ef_search=40` and `200`, iterative scanning `strict_order`, `max_scan_tuples=20000`. Capture the actual planner choice for each scope; filtered SQL may legitimately use an exact filter/index/sort plan instead of HNSW. Do not force a worse plan or claim ANN acceleration when no ANN plan was used. Never tune these settings after observing results.

## Measurement boundaries

Both database services receive 2 CPU / 4-GiB memory limits and independent Docker volumes. PostgreSQL uses 512-MiB shared buffers, 32-MiB work memory, 512-MiB maintenance memory, parallel query/maintenance workers disabled, and normal fsync/synchronous-commit/full-page-write settings. VectorNext retains its actual index build, including keyword structures even though only dense search is queried. Pin images and record versions/configuration/hardware.

Measure one first pass per configuration, followed by three warm passes with rotated/reversed engine order and deterministic shuffled query order. There are four configurations: VectorNext exact, PostgreSQL exact, and PostgreSQL HNSW at each search budget. Initial-pass data is not described as cold disk cache: setup, reference computation and prior configurations can warm operating-system pages.

Primary latency is client wall time through persistent connections: HTTP supplied-vector adapter for VectorNext, PostgreSQL wire protocol for pgvector. Both receive the vector and return up to ten IDs/scores. This includes differing protocol/serialization costs, not production text-query latency. VectorNext's inner `SearchIndex::search` timing and untimed PostgreSQL EXPLAIN ANALYZE samples are diagnostics only; they are not interchangeable engine-time measurements. Report p50/p95/p99, planned/succeeded counts and every raw result/error. Single-client measurements do not establish multi-user throughput.

Ingestion acknowledges one durable transaction per document. VectorNext constructs its actual source/provenance records; PostgreSQL stores originals in a document table and chunks/vectors/buckets in related rows, using COPY within each transaction. It does not duplicate every VectorNext internal provenance structure. Record this schema difference when comparing cost/storage. Time index preparation separately: VectorNext's full snapshot index; PostgreSQL's filter indexes/ANALYZE; additional HNSW build. The benchmark does not exercise PDF/model ingestion.

Record cgroup memory.current/memory.peak (whole service including page cache), CPU counters, VectorNext logical database bytes, PostgreSQL relation/index bytes and cluster WAL bytes separately. Peaks include ingestion/setup and are cumulative for the container lifetime; these are not isolated query working-set or physical disk-allocation measurements. Do not silently add PostgreSQL shared-memory RSS across processes.

## Recovery, retention and acceptance

After acknowledged data is loaded, verify a digest over every stored chunk ID, text, bucket and float32 vector coordinate. Save checkpoints, then write an additional independent sentinel document so recovery must include post-checkpoint work. Kill only the two benchmark database containers, restart with the same volumes, rebuild the VectorNext index, and verify counts/digests plus all exact test queries. This checks acknowledged-data recovery after process interruption, not an interrupted commit, physical power failure or replication.

Retain manifests, raw query responses/timings, ingestion samples, resource/planner records, failures and recovery reports under a new ignored `data/t20/` run directory. Summarize results in versioned Markdown/JSON, including limitations and any protocol amendment. Stop benchmark services and retain volumes; do not stop or modify the normal VectorNext application. No performance-driven code tuning occurs in T20. Correctness/harness defects may be repaired with the failed attempt retained and a fresh run identity.

References: [pgvector search/index behavior](https://github.com/pgvector/pgvector#readme), [PostgreSQL EXPLAIN caveats](https://www.postgresql.org/docs/current/using-explain.html), [VectorNext retrieval contract](retrieval.md).
