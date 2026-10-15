# T22 — Filter profiling and immutable indexes

Completed 2026-10-15. [Protocol](../t22-protocol.md) · [Machine-readable results](t22-filters.json) · [Reproduction](../../experiments/t22/README.md) · [Filter contract](../retrieval.md#filter-execution-indexes-t22).

Architecture and plan were updated before implementation. A release baseline from `c7427f3` was profiled first. Scalar equality and range evaluation dominated selective queries, so T22 adds bounded, disposable filter indexes without changing storage, HTTP contracts or search ranking.

## What changed

`src/search/filter_index.rs` builds document/media postings and bounded top-level scalar attribute columns in each immutable `SearchIndex`. Exact decimal ordering coalesces numerically equivalent representations without converting through floating point. Equality/range/existence and generated-attribute trust produce complete three-valued decisions; All/Any/Not preserve unknowns. The existing scan evaluator handles nested pointers, containers, absent/unindexed columns and budget exclusions. Complete responses retain their original rankings, counts and optional eligibility traces.

Construction considers 32 lexicographic attribute names, at most 4,096 distinct values per column, 16 KiB per scalar key, 1 MiB total retained attribute key/name bytes and 1,000,000 attribute posting slots. Generated-trust postings count separately. An incomplete column is discarded. Document/media postings scale with rows. These counters bound retained attribute index work/data, not byte-exact allocator or total database memory. No query is rejected solely because its field cannot be indexed.

## Paired measurements

Fresh copies of the stopped T20 v3 stores contain 401/1,601 documents including the sentinel, or 12,832/51,232 vectors. One baseline pilot per size preceded implementation. Final blocks run baseline/indexed/indexed/baseline using fresh sequential processes, identical formatted profiler source, 2 CPUs / 4 GiB, no network/GPU and the same existing synthetic vectors. Each block has one initial and two warm passes across 11 scopes, trace on/off and eight query vectors.

All **4,224 requests completed**. Complete response hashes agree in every one of 352 size/scope/trace/query groups, giving 3,872 comparisons against each group's first response. This covers scores/order, eligible/unknown counts, all intermediate rankings and detailed traces, not only top IDs.

Warm in-process complete-query median milliseconds, tracing disabled (32 observations per cell):

| Base documents | Scope | Baseline | Indexed |
| ---: | --- | ---: | ---: |
| 400 | Unfiltered | 6.945 | 7.019 |
| 400 | 5% document scope | 0.575 | 0.290 |
| 400 | Scalar equality | 3.028 | 0.068 |
| 400 | Empty scalar result | 2.505 | 0.021 |
| 400 | Numeric range | 4.646 | 0.292 |
| 1,600 | Unfiltered | 34.467 | 32.396 |
| 1,600 | 5% document scope | 3.094 | 1.044 |
| 1,600 | Scalar equality | 16.302 | 0.252 |
| 1,600 | Empty scalar result | 16.693 | 0.059 |
| 1,600 | Numeric range | 25.177 | 1.024 |

At the larger size, median filter-stage equality/range costs fell from 15.907/23.641 ms to 0.027/0.058 ms. Unfiltered vector scoring is unchanged; do not attribute its smaller timing variation to a faster distance algorithm. Fallback timing variations likewise do not establish an optimized nested-JSON path. Full first/warm/trace-on distributions and p95 values are in the JSON report.

Index construction costs more. Two baseline builds took 195.5–201.9 ms at the smaller size and 838.2–1,026.5 ms at the larger size; indexed builds took 242.0–249.2 and 1,001.9–1,027.7 ms. The corpus has one scalar attribute column with 12,832/51,232 postings and 198 key/name bytes; document and media postings each add one entry per row. Whole-process final RSS was roughly 100 MiB/374 MiB baseline and 100–101 MiB/375 MiB indexed. Only two build observations per variant and shared-host variation limit conclusions about overhead.

These timings exclude HTTP transport, response serialization/hashing and report writing. They cannot be compared directly to T20's PostgreSQL client latencies. The first pass is not a cold filesystem cache. Eight query vectors repeated across scopes/passes are not independent samples; no broad throughput, semantic quality or PostgreSQL superiority claim follows.

## Verification and retained state

- All 135 regular Rust tests (plus the invoked subprocess helper), format check and Clippy with warnings denied passed. Three new integration tests compare scalar/Boolean/trust/trace outputs against scan evaluation, exercise cardinality/key-size/column-count/key-byte fallback, and retain revision-scoped indexes across replacement, deletion and concurrent readers. Existing tests cover independent exact-cosine/BM25 references, nested values, invalid filters and storage recovery.
- Thousands of full-response comparisons include arbitrary-precision integers/decimals, equivalent numeric spellings, extreme exponents, negative zero, strings, null, missing values, generated trust and compound unknown logic. The 4,224 release requests independently compare the previous core and optimized core.
- Release profiler/core/production images built. The isolated production image returned 200 for `/healthz`, `/`, `/docs` and `/openapi.json` with external networking disabled. No frontend or model behavior changed, so GPU/browser-quality suites were not rerun. Existing dependency future-compatibility notices remain.
- All 2,013 original T20 volume file hashes were rechecked unchanged. T22 data/captures live in `vectornext-t22-data` and ignored `data/t22/`; its API smoke volume/container is retained and stopped. Profilers remove their completed containers. Original benchmarks and holdout remain untouched.
- The initial profiler was rustfmt-formatted after the pilot. Final baseline context uses the same formatted profiler as the optimized image, with unchanged `c7427f3` production sources. Both manifests and pilot captures remain. An early unused test import was removed before final checks. Historical freezes were not rewritten.
- Compose selects the built `vectornext-app:t22` for API/client/admin; processor/generator stay unchanged. The normal application was not restarted and still runs T19. Existing T19/T21 images remain available. No storage-format change is introduced by T22.

T22 acceptance is met. Next execute T23's fresh evidence-retrieval experiment separately. Nested-field indexes, incremental indexing, ANN and general performance claims remain outside this result.
