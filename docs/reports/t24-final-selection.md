# T24 — Facet selection recovers final evidence at extra CPU cost

Completed 2026-10-15. The experimental selector improves **complete frozen evidence coverage from 16/20 to 18/20 positive questions**, using the same expanded candidate shortlists and five primary slots. It recovers three labeled fact requirements with no measured coverage regressions. First-pass median latency increases from **685 ms to 1,437 ms**. Keep production ranked 30/20/5 and coverage_v1 unchanged; this small agent-authored retrieval experiment supports an opt-in integration proposal, not a default switch or answer-quality claim.

## Design and execution

Architecture and plan were updated before implementation. The [protocol](../t24-protocol.md), [input freeze](../../evals/selection/input-freeze.json), [public requests](../../evals/selection/requests.json) and [separate gold labels](../../evals/selection/gold.json) were frozen before measured inference. Ten new [NASA reference snapshots](../../evals/selection/sources.json), with [source attribution](../../evals/selection/NOTICE.md), contain 97,810 bytes of transformed TXT. All ten ingested successfully into **388 chunks**, with structural context, actual encoder budgets and the existing 180-token target. No historical evaluation questions or original holdout were used.

Twenty positive questions contain 37 fact requirements from 22 distinct facts; ten are single-topic and ten are multi-part. Four other questions ask for explicitly fictional, absent data. Facets are authored decompositions of the original questions, not automatic model plans. Labels preserve original quotes, UTF-8 offsets and source hashes. They are not independently adjudicated or exhaustive semantic annotations.

Both arms use the T23-style expanded candidate pool: original question plus facets, 30/30 dense/keyword search per probe, and round-robin merging to at most 20 candidates. Both rerank those candidates against the original question. **The ranked arm is a selection baseline on expanded candidates, not the complete current production pipeline.**

The candidate additionally reranks each facet alone, chooses the best eligible result for each facet, reuses already-selected exact keys, then fills from the general ranking. It excludes heading-only chunks and suppresses at least 80% original non-heading span overlap within the same document revision. It never suppresses across documents/revisions or treats a score as factual proof. Five remains the maximum; exclusions can produce fewer passages. The pure selector and audit live in `examples/support/final_selection.rs`, driven by `examples/final_passages.rs`; production source modules are unchanged.

Four processes ran ranked/facets/facets/ranked with real pinned CPU MiniLM embeddings and the existing cross-encoder, no network/GPU, 2 CPUs / 4 GiB and separate per-arm result caches. **96/96 requests succeeded.** All 72 cross-run shortlist/general-score comparisons and 48 within-arm repeated selection comparisons matched. The original snapshot documents also match across all four captures. No Gemma/generation call occurred. The [execution freeze](../../evals/selection/execution-freeze.json) and [machine-readable report](t24-final-selection.json) retain code/image identities, per-question results and capture hashes.

## Evidence results

Both repeated passes produce the same results. Coverage requires frozen literal quotes in original, revision-bound chunk bodies after whitespace normalization; added headings and generated annotations do not count.

| Stage | Ranked complete | Facets complete | Ranked facts | Facets facts |
|---|---:|---:|---:|---:|
| Raw candidate union | 20/20 | 20/20 | 37/37 | 37/37 |
| Fixed shortlist | 19/20 | 19/20 | 36/37 | 36/37 |
| Final five primaries | 16/20 | **18/20** | 32/37 | **35/37** |

Final macro fact recall rises from 93.33% to 97.08%. Single-topic complete coverage stays 10/10; multi-part coverage improves from 6/10 to 8/10. No question loses frozen final evidence coverage.

- **M07:** recovers Earth's atmospheric nitrogen percentage alongside the Mercury/Venus/Mars facts; the question becomes complete.
- **M08:** recovers Neptune's orbital period alongside the Jupiter/Saturn/Uranus facts; the question becomes complete.
- **M10:** recovers the Moon's radius in the frozen score; the question remains incomplete under that literal contract.
- **M09:** remains incomplete under the frozen intended-source label for Earth's axial tilt.

All requests return five primaries in this run. Audits record 120 selections per pass, 42 exact-key reuse decisions and 87 heading-only exclusions; no substantial-overlap exclusion fired on this corpus. Overlap behavior is therefore demonstrated by deterministic tests, not by a measured quality contribution here. This is a combined facet/eligibility selector comparison, not an ablation isolating each component.

The four missing-evidence queries also return five candidates. Their recall is undefined; no abstention, answerability or factual-answer success is claimed.

## Source-review limits

Post-run review found two alternate-support issues; [exact keys, quotes and source offsets](t24-source-review.json) are preserved separately. **No gold, source, original score or protocol was revised.**

M09 returns a Mars passage explicitly stating Earth's 23.4-degree tilt in both arms. The frozen question asks for values in the individual bodies' facts pages and its Earth label points to the Earth source. The literal metric does not credit the cross-document statement, even though it may be useful factual support.

M10's facet-selected Sun passage explicitly gives the polar rotation period of 36 Earth days. The frozen label uses an alternate sentence beginning “At its poles”; this passage uses that clause within a longer sentence. The literal scorer does not credit it. Thus its missing frozen quote from the shortlist is **not evidence that all semantic support was absent**. The facet output also supplies the Moon radius, so this case is more useful than its strict score suggests. No broader semantic rescore or answer-generation test was performed. Report 18/20 as the frozen metric, not a complete judgment of factual usefulness.

## Cost and boundaries

Per-query latency includes embedding, search, passage construction, all reranking and selection, excluding startup, index build, capture serialization and HTTP. All 24 requests contribute to each distribution.

| Per-arm result cache | Ranked median / p95 | Facets median / p95 |
|---|---:|---:|
| Initially empty | 685.1 / 764.2 ms | 1,437.0 / 2,800.2 ms |
| Repeated cached requests | 3.77 / 7.19 ms | 4.29 / 8.71 ms |

The first-pass median rises about 2.10×. Facet reranking alone has median 632.9 ms / p95 2,111.5 ms; the deterministic selector costs about 0.041 ms median. General-reranker medians are 612.3/602.4 ms. Both arms issue 66 embedding probes with 51 actual embedding inferences and 15 within-pass cache hits. Ranked requests 480 query/passage pairs (24 reranker batches); facets requests 1,320 (66 batches, including 42 facet batches). The capture field `pair_evaluations` counts requested pairs, including cache hits; repeated passes perform **zero** embedding/reranker inferences. Do not advertise cached timings as inference performance.

Raw candidate counts have median/p95 62/150 in both arms. Every query reranks the same 20 candidates; each facet adds a batch over those same candidates, up to 100 pairs total per query. Shared-host variation, related English TXT documents, correlated questions, authored facets and literal labels limit generalization. No new PDF/JSON quality, automatic planner, production context assembly, GPU or end-to-end answer result is established.

## Verification and retained state

Eight targeted Rust tests, formatting and all-target Clippy passed in Docker. Tests cover facet recovery/shared-best reuse, heading-only/empty results, exact-key ties, limits/invalid scores, merged span unions, the 80% boundary, large offsets, block/document/revision separation and pair-token rejection. Nine Python scorer/comparison regressions and frozen source/span validation passed offline. A separate two-document synthetic fixture exercised real ingestion and both selectors before measurement. Production code is unchanged, so historical GPU/browser/full storage suites were not rerun.

The final release image is `sha256:d1ac1189a16525b461cdae2afd181ba1f717a7b2f02c0b9c44d12c1a1b0695c5`. The initial build and final rebuild after adding a validation regression are retained; no measured attempt was discarded. All execution-input hashes match. As with T23, the existing worker's CRLF bytes differ from Git's LF representation; the original freeze is preserved and reproduction documents this.

All experiment containers exited; `vectornext-t24-final-v1-*` and smoke volumes/caches remain. Complete logs/captures are under ignored `data/t24/`. The normal T19 API/three-service app remains healthy and unchanged; Compose still selects the built T22 image for a later startup. Historical freezes, scores, source snapshots and the original holdout remain untouched. New data is now observed regression material, not a future holdout.

Next: scope opt-in application integration with bounded facet generation and end-to-end answer/context-budget verification on separately frozen data. Do not turn this experiment into an automatic production default. [Reproduction guide](../../evals/selection/README.md).
