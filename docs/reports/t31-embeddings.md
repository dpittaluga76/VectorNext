# T31 — CPU embedding profile comparison

Completed 2026-10-16 (UTC). **Retain MiniLM as the default.** BGE-small-en-v1.5 passed profile isolation, CLS pooling and 512-token admission checks, and completed all **192 retrieval requests without errors**. It improved selected-20 evidence coverage but did not improve final-five coverage. Ingestion took 33.6% longer on NIST and 39.6% longer on NASA. BGE remains an explicit experimental worker profile; no existing vectors or user library were migrated.

## Source coverage

Counts are questions with every labelled fact present. Each corpus has 20 positive questions and four missing-fact questions; the latter have undefined recall, are retained in captures, and are not counted as automatic successes. Both cold/warm passes produced the same coverage and case outcomes.

| Corpus | Profile | Raw candidates | Selected 20 | Final five | Final facts found | Final macro recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| NIST | MiniLM | 20/20 | 18/20 | 16/20 | 28/34 | 88.3% |
| NIST | BGE | 20/20 | 19/20 | 16/20 | 28/34 | 88.3% |
| NASA | MiniLM | 20/20 | 17/20 | 16/20 | 32/37 | 93.3% |
| NASA | BGE | 20/20 | 17/20 | 16/20 | 32/37 | 93.3% |

BGE added NIST `M01/time` and `M04/time` to selected evidence, completing M01. It added NASA `M10/sun_poles` without completing that question. No final-stage fact set changed in either pass, and no complete case was lost. This is literal source-retrieval coverage with question-only ranked 30/20/5, not generated-answer correctness, facet selection or independent quality validation. The existing source-review exceptions remain separate from frozen labels.

## Cost

All measured processes ran offline on CPU with two CPUs and a 4 GiB memory limit. Per-query clocks include embedding, search and reranking but exclude model loading/process startup. Warm results are embedding/reranker cache hits, not model inference speed.

| Corpus / profile | Ingestion | Chunks | Cold median / p95 | Warm median / p95 | Cold embedding median | Cold rerank median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NIST / MiniLM | 5.92 s | 188 | 641 / 791 ms | 1.68 / 2.08 ms | 9.75 ms | 609 ms |
| NIST / BGE | 7.91 s | 188 | 628 / 760 ms | 1.60 / 2.05 ms | 12.40 ms | 611 ms |
| NASA / MiniLM | 9.73 s | 388 | 603 / 770 ms | 1.71 / 2.04 ms | 10.81 ms | 591 ms |
| NASA / BGE | 13.59 s | 388 | 613 / 725 ms | 1.80 / 2.12 ms | 14.82 ms | 597 ms |

All 12 NIST and 10 NASA sources admitted in each profile. Ingestion worker startup was 1.33–1.42 s for MiniLM and 1.76 s for BGE, excluded from the ingestion totals above. Exact process commands/wall times remain beside captures. The small overall query differences are mixed and dominated by the unchanged reranker; a single counterbalanced run does not establish a speed advantage.

The 180-token target produced identical chunk evidence, structural text, spans and source locators in both profiles: 188/388 chunks. Revisions and vector spaces differ intentionally. Actual embedding inputs were 5–179 tokens on NIST (median 92.5) and 4–179 on NASA (median 36.5) for both tokenizers. Retrieved question/passage pairs reached 206 tokens on NIST and 220 on NASA, below the unchanged 512-token reranker bound. There were no truncation or token-admission failures. These corpora do **not** demonstrate recovery of previously rejected long JSON/PDF records or benefits from larger chunks; only the separate boundary test exercises the new 512-token capacity.

## Identity and verification

The [publisher model revision](https://huggingface.co/BAAI/bge-small-en-v1.5/tree/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a) is pinned with seven SHA-256-verified artifacts in [the lock](../../experiments/t31/models.bge.lock.json). FP32 ONNX SHA-256 is `828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35`. Pooling uses the first CLS hidden state followed by L2 normalization, with 384 dimensions. Query-only prefix `Represent this sentence for searching relevant passages: `, including its trailing space, is applied once by existing Rust callers and included in the embedding-space identity along with pooling/version, artifact, tokenizer and token limit. Documents receive no instruction prefix.

MiniLM's pre-change space fields remain exactly compatible. Captured space IDs were `6ca04c7e667b1b04520b78dea672c578bc93ff15ce7076b9e7362c1a609f0996` (MiniLM) and `0fb3eccc7efec339da12b1622caacd11a41a33397ae32478ae0e0f99d9acc11b` (BGE). Existing vectors are not relabelled; model selection requires a compatible space and fresh ingestion.

Verification passed: 49 final worker/answer/planner/scheduler/transport/profile checks, 11 legacy model-contract checks, actual ONNX CLS/padding equivalence, 512-token acceptance/513-token rejection, prefixed-query budget rejection, shared-cache isolation, unknown-profile failure and exact default-space compatibility. Processor, standalone model-check and ingestion images build; both profiles produce offline vectors from the packaged processor without a source overlay. The earlier full Rust suite passed 163 checks plus format/Clippy; no Rust changed during this embedding work. The normal three-service app stayed available; this experiment never invoked a GPU generator.

## Reproduction and limitations

Use [the commands and frozen protocol](../../experiments/t31/README.md). The measured image is `sha256:f4ac0d3835a5f708908cf1e63e6884569a2edee0dc493a76ff338152e79108d1`. `data/t31/comparison-v1/` retains its source ZIP, execution freeze, public inputs, per-document results, complete committed source/vector snapshots, exact rankings, timings, cache stats and process exit codes. All experiment processes exited; volumes/caches remain. [Machine-readable results](t31-embeddings.json) include per-case scores, token counts, chunk comparison, artifact spaces and freeze/archive hashes. The reporting-only `summarize.py` was added after measurement and runs without inference; it does not replace the frozen runner or original captures.

Final code review added rejection of non-finite CLS norms, including overflow from finite float32 hidden values, with an adversarial unit check. The worker already rejected resulting zero vectors; this moves rejection to pooling. No measured output or score changed and no inference replay was needed. The final encoder/test sources therefore intentionally differ from the measured freeze; use its retained source ZIP/image for exact reproduction.

Both corpora are observed regression sets. There are no generated-answer, PDF/JSON, multilingual, larger-chunk or production-migration claims. No original holdout was used, no labels/sources/historical scores were rewritten, and no prompts were tuned. The next decision is whether to authorize a separate longer-record/independent-recall experiment; this result alone does not justify a default change.
