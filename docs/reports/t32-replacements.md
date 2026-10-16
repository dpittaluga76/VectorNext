# T32 — small Nomic / Ettin replacement pilot

Measured 2026-10-16 (UTC). **Keep current MiniLM defaults.** All **24 scored requests** were attempted once: six fresh synthetic questions across four combinations. MiniLM embeddings with Ettin-17M reranking recovered one missing PDF answer and lost no baseline success. Nomic exposed a downstream token-budget incompatibility, producing four HTTP failures in each arm. This pilot supports further work on Ettin and pipeline budgets, not automatic promotion.

Architecture and task definitions were updated before implementation. The [frozen protocol](../../experiments/t32/protocol.md), [reproduction commands](../../experiments/t32/README.md), [machine-readable captures summary](t32-replacements.json) and [separate source review](t32-source-review.md) accompany this report.

## Answers and latency

| Embedding / reranker | Frozen correct | Separately reviewed correct | HTTP errors | Median / p95 end-to-end | Sampled processor peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| MiniLM / MiniLM | 4/6 | 5/6 | 0 | 12.80 / 19.97 s | 531 MiB |
| MiniLM / Ettin-17M | 5/6 | 6/6 | 0 | 9.68 / 10.98 s | 451 MiB |
| Nomic / MiniLM | 1/6 | 2/6 | 4 | 0.039 / 9.91 s **failure-dominated** | 1,881 MiB |
| Nomic / Ettin-17M | 1/6 | 2/6 | 4 | 0.047 / 10.44 s **failure-dominated** | 1,867 MiB |

The reviewed column credits one valid PDF correction-notice citation omitted by the frozen literal label. All four models returned 45 days with that valid original-source citation. **Frozen labels and scores remain unchanged.** The review affects all arms equally and does not change the relative gains/losses.

MiniLM/Ettin's all-request median was **24.4% lower** than MiniLM/MiniLM. On the four requests both arms passed under the frozen scorer, median latency was **11.55 → 8.58 s**, a **25.7%** reduction. Median reranking/preparation was **258 → 101 ms**; generation-call median was **12.06 → 9.03 s**. Most wall time is still Gemma work, and evidence/order/output differences also affect it. Do not attribute the full end-to-end improvement to CPU reranker speed. One pass on six questions cannot establish a stable performance advantage; p95 is simply the maximum of six observations.

Nomic's low medians reflect fast errors, **not speed gains**. Only one case was jointly correct under frozen scoring with the baseline: 7.72 s baseline versus 8.33 s with Nomic/MiniLM and 10.44 s with Nomic/Ettin. The two successful HTTP responses per Nomic arm have query-embedding medians 40–46 ms, versus 11–13 ms for the MiniLM embedding arms. Failed requests have no complete stage trace and stay in the denominator.

| Case | MiniLM / MiniLM | MiniLM / Ettin | Both Nomic arms |
| --- | --- | --- | --- |
| Approved pressure | Correct 17.5 bar | Correct 17.5 bar | Correct 17.5 bar |
| Facts from two route documents | Correct 12 piers / 48 tonnes | Same | Reranker token rejection |
| Exact long-record integer | Correct `9007199254740993` | Same | Reranker token rejection |
| Unknown count versus zero | Correct insufficient evidence | Same | Reranker token rejection |
| PDF corrected interval | 45 days; valid alternate citation | Same | Same |
| PDF passenger / lifeboat counts | Insufficient evidence; lifeboat fact missing | Correct 20 passengers / 12 per boat | Reranker token rejection |

## Evidence and the Nomic failure

Counts below require all labelled facts for a positive question. There are five positive questions; the unknown-count negative has no retrieval-recall denominator.

| Embedding / reranker | Raw candidates | Selected 20 | Ranked first five | Assembled evidence |
| --- | ---: | ---: | ---: | ---: |
| MiniLM / MiniLM | 5/5 | 5/5 | 3/5 | 4/5 |
| MiniLM / Ettin | 5/5 | 5/5 | 4/5 | 5/5 |
| Nomic / MiniLM | 2/5 recorded | 2/5 recorded | 2/5 recorded | 2/5 recorded |
| Nomic / Ettin | 2/5 recorded | 2/5 recorded | 2/5 recorded | 2/5 recorded |

The Nomic errors do not return a retrieval report, so those rows do **not** prove poor candidate recall. Missing traces count as no recorded support, while failed positive requests stay in the denominator. Ranked first-five coverage is distinct from budget-admitted/neighbor-expanded evidence. Ettin recovered the lifeboat sentence; both MiniLM embedding arms had that fact in their candidate lists.

Both embedding profiles admitted **10/10 sources** with unchanged structural policy and a 180-token target. MiniLM produced **49 chunks**, Nomic **42**. The only chunk-count difference was the long Aster JSON record: eight MiniLM subtrees versus one whole Nomic record. The JSON preparation policy admits a complete record when it fits the embedding space, even above the ordinary target. Nomic's complete embedding input was **557 tokens**, below its 1,024-token cap. Question/record pairs were **566–576 MiniLM-reranker tokens** or **519–530 Ettin tokens**, exceeding the fixed **512-token reranker cap**.

When that record enters the selected candidate list, the existing reranker rejects the whole operation with `503 capability_unavailable: Input exceeds 512 tokens ... split before inference`. This affected the same four questions in both Nomic arms, including questions about other documents. No truncation, larger reranker budget, skipped candidate, retry or changed fixture was introduced to hide the incompatibility. Token counts were confirmed after the run with tokenizer-only inspection; no extra quality calls were made. Both embedding profiles handled these sources, so this pilot does not demonstrate recovery of a MiniLM ingestion failure.

Ingestion wall time, including PDF preparation and job polling but excluding startup, was **29.33 s MiniLM / 30.72 s Nomic**. CPU service readiness took **7.11 / 18.42 s** for those ingestion processes. These PDF-dominated totals are not pure encoder-throughput measurements. The 768-dimensional Nomic vectors use twice the float32 bytes per vector; existing 384-dimensional vectors were never relabelled.

## Implementation and identities

- Added explicit CPU profiles `nomic-v1.5` and `ettin-17m`; defaults remain `minilm`. Embedding dimensions/document prefixes and reranker selection are profile-driven. Exact old MiniLM space and reranker identities pass compatibility checks; new profiles receive distinct spaces/caches. No Rust, public API, storage schema, launcher or normal Compose default changed.
- [Nomic's pinned publisher revision](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/tree/e9b6763023c676ca8431644204f50c2b100d9aab): FP32 ONNX, 768 dimensions, masked mean → layer normalization (epsilon 1e-5) → L2, `search_query: ` / `search_document: ` prefixes, tested 1,024-token limit. No claim that this export/profile works at 8K.
- [Ettin's pinned publisher revision](https://huggingface.co/cross-encoder/ettin-reranker-17m-v1/tree/9e4aa35321a6dd1a43ca313f500c4b4f7cfb5cc6): ONNX outputs token hidden states, not logits. The complete reranker also loads pinned scoring-head weights and applies CLS → Dense → exact GELU → learned LayerNorm → Dense. Raw scores are not confidence probabilities. Actual publisher padding ID 50283 is respected; the pair cap stays 512.
- [The lock](../../experiments/t32/models.lock.json) binds all model/tokenizer/config/head artifacts. The worker uses NumPy and `safetensors==0.8.0`; head/pooling outputs were checked against a separate PyTorch reference. Model files are ignored and inference is offline.

Same retained API image for all arms: `sha256:3c858fc267b0346c0cb3beeb32ea39d86aac32a3b4d9d4efa4acde65c2c87b86`. Candidate processor: `sha256:75725679ac2d6da6b901279e295c30e592436d9051e3a7cf794bb5fb1c421240`. The normal 12B generator remained `sha256:8f63ff90a6ff7fd762ebacde912b203b738cb93015005f11dc9003886bfcbd7c`, unchanged container/profile/entrypoint settings: 4,096 context, one slot, f16 KV, temperature 0, seed 42, two-call assessment/extraction, prompt caching off. This retained API predates the source-only numeric-range repair; it is the same deployed API in every arm.

Measured inputs/code/image IDs/container configuration were frozen before queries at `data/t32/pilot-v1/execution-freeze.json`. Its SHA-256 is `c21f5a8f67da7d240d7a5d079060181850d7a8595e3dff565151a57ff1dacc6a`; the source ZIP SHA-256 is `0512fee456bd52c4a18a8ebf83fe959ed38c1dee12ec4bdab8b635c853b30db1`. The reporting-only summarizer/README/source review were added afterward and do not replace the freeze.

Publication checks caught Git line-ending conversion in newly staged fixtures. An experiment-specific `.gitattributes` rule now preserves their original bytes; staged fixtures/requests/labels/source metadata are checked against every input-freeze hash. No source bytes, labels, recorded outcomes or frozen hashes were changed.

## Verification and boundaries

All 24 attempts have raw responses, status, elapsed time, hashes and pre-dispatch attempt markers. There are **16 HTTP successes and eight retained HTTP failures**. Four separate synthetic warmups are excluded from scoring/timing. Each embedder's two rerankers used the same committed documents/chunks/vectors/revisions, verified before and after each arm. Every arm recreated API/processor processes and used a separate query cache. OS caches were not isolated; execution order was fixed and only partially balanced, without repeated trials.

The final offline Python suite passed **60 checks**, including seven new profile checks, three scorer checks, legacy identities, exact values, missing/corrupt artifacts, token/padding bounds, head/pooling equivalence, worker cache isolation, scheduling/planning and transport. Four existing BGE profile regressions also passed, for **64 Python checks** in total. The first main-suite invocation had two harness errors because the legacy tests expect `/workspace/evals/dataset.json`; adding the read-only fixture mount fixed those errors without code changes. Both logs are retained. The Docker Rust run passed **163 top-level checks**, including the nested crash probe; no Rust source changed. Input hashes and `git diff --check` are verified separately.

The packaged processor was exercised directly by every arm without source overlays. Standalone ingestion and model-check images also built and each produced a 768-dimensional Nomic vector and an Ettin score with networking disabled, using packaged code and local models only. No browser/UI contract changed, no GPU quality suite or historical holdout was run, and no test source/label was regenerated during evaluation. Normal library/readiness snapshots match; only dedicated T32 API/processor containers stopped. Their volumes/caches and every failure remain available. Normal services still use `:t28-12b` and MiniLM.

Sampled processor memory is Docker container memory, not a precise process peak, host RAM or VRAM measurement; short CPU bursts can be missed. The generator was shared under its normal scheduler, with no unrelated workloads stopped. This is a small synthetic English pilot with explicit fields, not automatic-planner evaluation, multilingual proof, long-corpus capacity testing or an independently administered benchmark.

**Next recommendation:** make chunk/rerank admission compatible across stages, preserving original evidence and exact values, before retesting Nomic. Ettin is the more promising immediate candidate: a small fresh confirmation set should test its observed evidence gain and latency before any default switch. Neither follow-up nor production activation is started by this report.
