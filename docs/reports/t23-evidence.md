# T23 — Candidate expansion improves the shortlist, not final evidence

Completed 2026-10-15. **Keep the production ranked 30/20/5 defaults.** Field-focused expansion recovered three missing fact requirements before reranking, but did not improve the final five passages. This is a fresh, agent-authored CPU retrieval experiment, not an independent benchmark or a generated-answer evaluation.

## What ran

The [protocol](../t23-protocol.md), [public requests](../../evals/evidence/requests.json), [separate labels](../../evals/evidence/gold.json), [source attribution](../../evals/evidence/NOTICE.md) and [input freeze](../../evals/evidence/input-freeze.json) preceded measured inference. Twelve NIST reference text snapshots total 62,334 bytes. All twelve ingested successfully into **188 chunks** using structural context, the existing 180-token target, pinned real MiniLM embeddings and the normal encoder limit.

Twenty answerable questions contain 34 fact requirements; four additional questions deliberately lack supporting data. Ten positive questions concern one topic and ten combine topics/details. There are 19 distinct labeled facts, so observations are correlated. Each support has a source hash, literal quote and UTF-8 byte offsets. No historical evaluation or original holdout input was used.

Both arms use dense/keyword top 30, existing fusion/deduplication, the same 20 reranker inputs and five primary passages. Expansion adds the frozen question-derived hints, merges top-20 lists round-robin and reranks against the original question. Hints are authored decompositions; this does not test automatic planning. The baseline tests the retrieval/reranking portion of production behavior, stopping before neighboring evidence assembly and answer generation.

Four offline Docker processes ran **baseline / expanded / expanded / baseline** on the same committed database, with 2 CPUs / 4 GiB, no GPU/network, and separate per-arm result caches. All **96 requests succeeded**. Paired repeats returned identical raw/selected/primary keys and reranker scores. The [execution freeze](../../evals/evidence/execution-freeze.json) binds runtime source, model locks, image and settings; the [JSON report](t23-evidence.json) includes per-question results and capture hashes.

## Coverage

Results are identical in each arm's first and cached pass. “Complete” means every frozen fact requirement has a matching original source quote in that stage's chunks.

| Stage | Baseline complete questions | Expanded complete questions | Baseline facts | Expanded facts |
|---|---:|---:|---:|---:|
| Raw deduplicated candidate union | 20/20 | 20/20 | 34/34 | 34/34 |
| Fixed 20 reranker inputs | 18/20 | **20/20** | 31/34 | **34/34** |
| Final five primary passages | 16/20 | 16/20 | 28/34 | 28/34 |

Macro fact recall at the fixed shortlist rises from **94.17% to 100%**; final macro recall remains **88.33%**. Final single-topic coverage is 10/10, multi-part coverage 6/10. No positive question gains or loses final frozen fact coverage between arms.

Expansion recovers time for M01 and time/length for M04 into the reranker inputs. The final selector still loses the complete length/time definitions for M01, length/time for M04, and the temperature definition for M05 and M06. Broad overview passages and a resource paragraph mentioning many base units rank highly. This supports investigating evidence coverage during final selection, rather than assuming a larger upstream pool will improve answers.

**Post-run source review, not a label revision:** M01 and M04 include a different time paragraph with the cesium cycle count. That paragraph was not enumerated in the frozen gold, so the literal scorer does not credit it. It is potentially useful alternate time support, but both questions still lack the required length value in their final five. Preserve the official 28/34 fact score as conservative; do not interpret it as a complete semantic adjudication. No gold, source or score was rewritten. The broad overview passages do not supply the missing exact length/temperature values.

All four missing-evidence requests return five candidates, as expected for a retrieval stage. Their recall is undefined. This experiment makes no claim about abstention or supported answers from those candidates.

## Cost

End-to-end per-query timing includes query embedding, search, passage construction and reranking. It excludes process/model startup, index construction, report serialization and HTTP. All 24 requests contribute to each latency distribution.

| Result-cache condition | Baseline median / p95 | Expanded median / p95 |
|---|---:|---:|
| Initially empty per-arm cache | 624.6 / 713.8 ms | 619.0 / 719.0 ms |
| Repeated cached requests | 1.52 / 2.49 ms | 3.35 / 4.89 ms |

The similar first-pass latency does not establish a speed gain: reranking dominates, workloads differ and the host is shared. Median first-pass embedding cost rises from 10.58 to 24.14 ms; search from 0.37 to 0.77 ms. Reranking medians are 610.58 and 592.08 ms. Baseline issues 24 embedding probes; expansion issues 62, with 54 actual embedding inferences and eight intra-pass cache hits. Both perform 24 reranker inferences in the first pass and zero in the cached pass. No generation call occurs.

Raw candidate counts have median/p95 51/56 for baseline and 62/86 for expansion. Every request still reranks exactly 20 and returns five. “Initially empty” describes the application result cache, not OS caches, model files or within-pass reuse. Cached results must not be advertised as inference latency.

## Verification and disposition

- Separate synthetic smoke fixture: real offline ingestion and both retrieval arms passed before measured execution.
- Five scorer tests passed in the offline image: alternative quotes, whitespace, exact source/revision identity, original evidence only, missing/error denominators and partial coverage. Frozen fixture/hash/span validation passed separately in Docker.
- Experimental round-robin Rust regression, release build, formatting and all-target Clippy passed. The preceding T22 core suite passed 135 tests; T23 adds one experimental test. Existing dependency future-compatibility warnings remain for `buf_redux`/`multipart`.
- All execution-input hashes still match; input/execution freezes and original captures are retained. Historical T11/T14/T20/T21 artifacts are unchanged. All experimental containers exited; fresh database/cache volumes remain.
- Publication verification found one existing worker file with CRLF working-tree bytes versus LF in Git; normalized content is identical. The original execution hash remains intact, and the reproduction guide explains this expected checkout difference. Frozen evaluation input bytes are unchanged.
- The normal three-service app remains healthy on its previous T19 API image. Compose selects the built T22 API for a later normal restart; this experiment changes no production retrieval or model defaults.

Limits: twelve small, related English TXT snapshots; no fresh PDF/JSON quality measurements, no GPU/LLM answers, no automatic hint planner, no independent human adjudication, and conservative literal source coverage. Some navigation/resource text survives extraction. The new corpus is now observed regression data, not a future holdout. These results support a separately scoped, freshly evaluated final-selection experiment; they do not justify shipping expansion as a default.

Reproduce with [the experiment guide](../../evals/evidence/README.md). Local complete captures are under ignored `data/t23/final-v1/`; the synthetic smoke and initial acquisition failure are retained separately.
