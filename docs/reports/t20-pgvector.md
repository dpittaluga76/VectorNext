# T20 — VectorNext versus PostgreSQL + pgvector

Completed 2026-10-15. [Machine-readable measurements and hashes](t20-pgvector.json) · [Frozen protocol](../t20-protocol.md) · [Recovery amendment](../t20-protocol-amendment-01.md) · [Reproduction commands](../../experiments/t20/README.md).

PostgreSQL exact search was faster in every tested warm query group. Both exact implementations passed **2,048/2,048 timed exact requests**, with 100% recall on nonempty results. HNSW reduced unfiltered latency substantially, with 100% recall at 12,800 vectors and 99.0625% at 51,200 vectors. This is a synthetic CPU vector-storage/search comparison, not a semantic retrieval or RAG-quality evaluation.

**The most consequential finding is a VectorNext checkpoint capacity limit.** Both corpora ingested and searched successfully, but their complete snapshot exceeded the existing 64 MiB frame limit. PostgreSQL checkpointed successfully. VectorNext recovered all acknowledged data from its journal after reopening and after forced process interruption. Checkpoint support at these sizes did not pass. Offline export also calls checkpoint, so this limit blocks export of these states; that implication comes from code inspection, not a separate export run.

## Workload and measurement boundaries

The architecture and task plan were updated before implementation. No production storage, search, API or model code was changed or tuned for this comparison. PostgreSQL is isolated experiment tooling; normal deployment remains three services with VectorNext's own database.

| Property | Fixed setup |
| --- | --- |
| Corpora | 400 / 1,600 synthetic documents; 32 chunks each; 12,800 / 51,200 vectors |
| Data | Approximately 20 KiB original text per document; identical chunk text, IDs, bucket attributes and 384-dimensional float32 coordinates in both engines |
| Geometry | PCG64 seed 20261015; 128 Gaussian cluster centers, noise scale 0.35, normalized then converted to float32 |
| Queries | 32 separately sampled vectors per corpus, each under four scopes; top 10 |
| Scopes | All chunks; first 5% of document IDs; bucket 0 matching 1% of documents; bucket -1 matching none |
| Passes | One initial pass and three warm passes; rotated/reversed configuration order and deterministic shuffled requests |
| Limits | Each database: 2 CPUs, 4 GiB RAM; driver: 2 CPUs, 2 GiB RAM |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg12+2), pgvector 0.8.7; 512 MiB shared buffers, 32 MiB work memory, 512 MiB maintenance memory; query/maintenance parallel workers disabled |
| Durability | Normal fsync/synchronous_commit/full_page_writes; one acknowledged transaction per document |
| Host | Ryzen 5 7600, 6 cores / 12 threads, 67,802,910,720 bytes RAM (about 63.1 GiB); Windows/Docker Desktop/WSL2; Docker server 29.6.2 |

VectorNext uses a benchmark-only supplied-vector HTTP adapter around the existing `SearchIndex::search`, with keyword retrieval and deduplication disabled. It still constructs its complete index, including keyword structures. PostgreSQL receives SQL over a persistent native connection. Its exact query sorts by cosine distance plus zero and ID to prevent HNSW satisfying the ordering. Ordinary B-tree filter indexes remain available. Actual plans confirm no ANN index in exact queries.

Reported latency is client wall time, including vector serialization, transport and response decoding. Different wire protocols and request/response shapes are part of this measurement. It is not the production text-query API, and it excludes embedding, parsing, reranking and answer generation. Rust's inner search timings and PostgreSQL's untimed EXPLAIN ANALYZE samples have different boundaries and remain diagnostics, not directly comparable engine-time results.

The independent NumPy float64 reference uses the stored float32 coordinates. Checks cover result count, unique eligible IDs, cosine scores within 1e-5, descending order, required above-boundary hits and allowed ties. Strict ID recall is reported separately. Empty-result correctness is checked; recall is undefined for an empty reference. Input files, reference results and 39 execution-source files were hashed before measurement and reverified afterward.

## Exact-search results

Warm client latency in milliseconds. Each cell contains **p50 / p95 / p99**, from 96 observations: 32 query vectors repeated in three passes.

| Vectors | Scope | VectorNext exact | PostgreSQL exact |
| ---: | --- | ---: | ---: |
| 12,800 | All | 8.818 / 11.023 / 13.130 | 5.673 / 6.931 / 7.497 |
| 12,800 | 5% document scope | 1.495 / 1.899 / 2.106 | 0.738 / 0.892 / 1.153 |
| 12,800 | 1% attribute filter | 4.196 / 5.063 / 7.097 | 0.469 / 0.590 / 0.732 |
| 12,800 | Empty attribute filter | 4.416 / 5.240 / 7.751 | 0.414 / 0.553 / 0.649 |
| 51,200 | All | 43.862 / 48.260 / 51.091 | 22.729 / 27.019 / 30.664 |
| 51,200 | 5% document scope | 5.146 / 6.723 / 7.710 | 1.923 / 2.338 / 2.664 |
| 51,200 | 1% attribute filter | 16.420 / 19.262 / 22.052 | 0.736 / 1.017 / 1.086 |
| 51,200 | Empty attribute filter | 17.053 / 19.270 / 20.777 | 0.487 / 0.745 / 1.005 |

For each corpus, each exact configuration passed all **512/512** requests across both initial and warm phases and all scopes. There were no query errors. The JSON report retains initial-pass distributions and every filtered configuration, rather than presenting only the favorable groups. The initial pass is not a cold disk-cache measurement: setup and prior configurations can warm pages.

PostgreSQL's unfiltered exact median was approximately 1.55 times faster at the smaller size and 1.93 times faster at the larger size. The larger filter gap warrants profiling VectorNext's eligibility checks and candidate selection. These timings alone do not isolate a particular internal bottleneck.

## Approximate search and planner choices

HNSW uses `m=16`, `ef_construction=64`, `ef_search=40` or `200`, `iterative_scan=strict_order` and `max_scan_tuples=20000`. These settings were fixed before timed queries.

| Vectors | ef_search | Unfiltered warm p50 / p95 / p99, ms | Mean recall@10 | Exact-correct requests |
| ---: | ---: | ---: | ---: | ---: |
| 12,800 | 40 | 0.586 / 0.765 / 1.403 | 100% | 96/96 |
| 12,800 | 200 | 0.928 / 1.172 / 1.235 | 100% | 96/96 |
| 51,200 | 40 | 0.843 / 1.034 / 1.207 | 99.0625% | 87/96 |
| 51,200 | 200 | 1.073 / 1.320 / 1.528 | 99.0625% | 87/96 |

The larger search budget did not improve recall on these queries. The misses repeat across passes; 96 observations are not 96 independently sampled queries. Across all scopes/phases, each HNSW configuration passed 512/512 exact checks at the smaller size and 500/512 at the larger size. All **4,096/4,096 timed requests** completed without transport/query errors.

At both sizes, the actual unfiltered HNSW plan used `chunks_hnsw`. Every filtered HNSW-labelled configuration instead used an exact filter/index/sort plan: `chunks_document` for document scope, bitmap access through `chunks_bucket` for the 1% filter, and `chunks_bucket` index access for empty results. Filtered recall was 100%, but this is **not evidence of HNSW filtered-search recall**. Exact unfiltered SQL used sequential scan plus sort. All plan trees, buffers and EXPLAIN timings are retained.

## Loading, indexing and resources

Loading times sum acknowledged per-document client times, alternating insertion order between engines. They exclude index construction and corpus generation. VectorNext stores its full provenance model; PostgreSQL stores normalized document/chunk rows and uses COPY inside each document transaction. This is a comparison of the two implemented paths, not matched internal write work.

| Documents | VectorNext load | PostgreSQL load | VectorNext index | PostgreSQL filters / ANALYZE | Additional PostgreSQL HNSW build / ANALYZE |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 400 | 10.282 s | 2.620 s | 216.908 ms | 113.213 ms | 1.673 s |
| 1,600 | 42.351 s | 10.359 s | 875.167 ms | 306.864 ms | 8.817 s |

VectorNext index timing is measured inside the adapter; PostgreSQL preparation times are client wall times. Index responsibilities also differ. Per-document p50/p95/p99 and all counters are in the JSON report.

Resource samples below were taken after timed searches, before checkpoint attempts. MiB means 1,048,576 bytes.

| Vectors | VectorNext database bytes, MiB | PostgreSQL relations including HNSW, MiB | PostgreSQL cluster WAL, MiB | VectorNext cgroup current / peak, MiB | PostgreSQL cgroup current / peak, MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 12,800 | 93.70 | 50.95 | 64 | 193.96 / 208.11 | 257.75 / 295.57 |
| 51,200 | 374.81 | 203.43 | 192 | 749.95 / 774.91 | 626.43 / 715.91 |

PostgreSQL relation bytes before HNSW were 27,189,248 and 108,437,504. Its WAL is cluster-wide, including prior work, and is not added to per-corpus relation bytes as a comparable total. VectorNext's logical database bytes include originals and journal; no successful snapshot was produced. Text is intentionally repetitive, and storage formats, compression opportunities and provenance schemas differ.

Cgroup memory includes page cache and setup, not just resident vector data. Peaks are cumulative within each container lifetime; the larger run follows the smaller corpus's recovery, and PostgreSQL retains earlier schemas. These are neither isolated per-corpus memory requirements nor a memory-efficiency ranking. Sampled CPU counters are retained; both database samples reported zero throttled periods. Normal app services and an unrelated service remained running, so this was not a dedicated benchmark machine. No GPU work was requested.

## Checkpoint failure and recovery

Both VectorNext checkpoint calls returned `invalid record: frame exceeds 64 MiB limit`. [Database::checkpoint](../../src/storage.rs) serializes the complete state into one frame; [frame encoding](../../src/frame.rs) bounds that frame at 64 MiB. Failure poisons the writer until it is reopened. This is a serialized-state limit, **not a universal maximum document count**. Smaller or differently chunked documents may reach it at different counts.

The original protocol expected successful checkpoints. The first completed 400-document query run exposed this limitation. [Amendment 01](../t20-protocol-amendment-01.md) preserved that failure and changed only subsequent recovery reporting: record rejection, reopen and verify data, acknowledge a separate 32-chunk sentinel, then perform the kill/restart drill. No engine code or query settings changed.

| Documents before sentinel | VectorNext checkpoint | PostgreSQL checkpoint | VectorNext reopen after rejection | VectorNext post-kill open + index | Exact queries after restart, both engines |
| ---: | --- | ---: | ---: | ---: | ---: |
| 400 | Failed: frame limit | 124.659 ms | 573.153 ms | 824.696 ms | 256/256 correct |
| 1,600 | Failed: frame limit | 243.590 ms | 2,710.845 ms | 4,040.676 ms | 256/256 correct |

Each engine acknowledged the sentinel before its dedicated container was killed with SIGKILL. After restart, both engines matched the complete digest over all chunk IDs, text, bucket values and float32 vector bits, including the sentinel; counts were 401/1,601 documents. All **512/512 recovery queries** passed. VectorNext recovered through journal replay; PostgreSQL had a successful checkpoint followed by post-checkpoint work. Restart timings above exclude container startup; no equivalent PostgreSQL readiness latency was measured.

[Database::export](../../src/backup.rs) calls `checkpoint()` before writing an export, so the observed state-size limit also prevents that export path. The test demonstrates acknowledged-data recovery after process interruption. It does not certify physical power-loss behavior, interrupted commits, replication or a working large-state backup. The adapter's ordinary `stats` response contains an uncomputed empty digest; integrity evidence is `preparation.verified_digest` and the explicit recovery digest, not that stats field.

## Retained attempts and reproducibility

All attempts remain under ignored `data/t20/`, with separate Compose projects and volumes:

- `20261015-fixed-v1`: both engines loaded/verified 400 documents. A PostgreSQL WAL counter was a Python Decimal, which failed preparation-report serialization before any timed queries. The counter conversion was repaired; the matching source archive and partial report remain.
- `20261015-fixed-v2`: all 2,048 small-corpus timed requests completed; the checkpoint failure stopped the recovery phase. Captures and the matching source archive remain.
- `20261015-fixed-v3`: the final run reported here. Both corpora, checkpoint outcomes and recovery drills completed under amendment 01. Corpus, query, reference and sentinel hashes are identical across all three attempts. This was not a search-parameter tuning exercise.

Initial Docker startup also encountered exhausted automatic network pools. Only new benchmark projects received explicit unused private subnets; existing networks were not removed. Setup failures/logs remain. All three benchmark projects are stopped, with volumes and networks retained. The normal app remained healthy on localhost:8088.

The base production tree is commit `9e3831f`; the manifest pins every production source and benchmark execution file. The versioned JSON includes that manifest, hashes of raw captures and earlier source archives, full aggregate measurements and plan-node summaries. Raw query responses, load timings, recovery results, SQL plans, resources and logs remain locally under `data/t20/20261015-fixed-v3/` and `data/t20/`. Fresh reproduction requires a new project, unused subnet and new run name; never overwrite a retained attempt.

Image identities used:

| Image | SHA-256 |
| --- | --- |
| VectorNext benchmark | `bf7d34608b21aa4dce4e4a4bf1a473c793c47aa54ac403fcf88ebd4bc0890ca9` |
| Python runner | `ea664b4fc4fabbea033787597dc004869b956e9d81e4b9624e575b9b14e056dd` |
| PostgreSQL runtime image | `55141572004e92a39edfdc2d16e821c214b64ca4fba50c1f7e408a09a3d04aff` |
| pgvector pinned image index | `2358fcba361ed2233a5ed81b5fe4ca779ccb304120ce531a3bf51c0ed7e2bc11` |

Rust uses 1.87 and the repository lockfile. The runner pins Python's base image, NumPy 2.5.4 and psycopg 3.2.10. [Compose](../../compose.benchmark.yaml) pins PostgreSQL/pgvector; Dockerfiles pin their base images. All runtime benchmarking uses an internal Docker network without published ports, model mounts or GPU access.

## Verification and next work

- **123 Rust tests passed**, including the new benchmark scope/filter check; two intentional subprocess helpers remain ignored in ordinary enumeration and are exercised by parent tests.
- **Eight Python benchmark checks passed**, including float32 transport, independent cosine examples, filter selectivity, boundary ties, mandatory better hits, duplicate/ineligible results, empty results and errors. They never regenerate a measured corpus.
- Rust formatting, Clippy with warnings denied, release/runner builds and the separate two-document smoke check passed. Existing `buf_redux`/`multipart` future-compatibility notices remain.
- Final source/input hashes, capture denominators, summary counts, recovery digests and identical inputs across attempts were independently checked from retained files. No historical fixture, manifest, score or original holdout was modified or consumed. Production code and the frontend were unchanged; GPU and browser-quality reruns were unnecessary.

T20's benchmark acceptance is met, including explicit reporting of failures. This does not make the checkpoint defect acceptable. The next work to scope is a bounded, crash-safe checkpoint/export format that preserves journal and revision contracts, followed by profiling/filter candidate selection. Approximate indexing should be considered against fresh workloads and an explicit recall requirement. Candidate-retrieval and ambiguity experiments remain separate quality work.

This single-host, single-client, clustered synthetic experiment does not establish broad database superiority, sustainable concurrent throughput, real embedding relevance, or better answers. It provides a reproducible baseline and identifies a concrete storage limitation to fix before making stronger capacity claims.
