# T07 model ingestion results

Verified 2026-10-14 on Docker Desktop Linux and the local RTX 4060. Design: [model ingestion contract](../model-ingestion.md). Exact receipts, model/input identities, source/code hashes, cache statistics, and probes are in the [machine-readable report](t07-model-ingestion.json).

T07 is complete. TXT, PDF, and JSON ingestion now uses real MiniLM tokenization and 384-dimensional normalized embeddings. Optional Gemma 4 26B A4B QAT context generation runs at temperature zero with CPU expert offload. Original evidence stays intact; generated annotations, their source scope, prompt, model configuration, and input digests persist separately. Complete revisions still publish through the existing sole Rust writer.

## Verification

- **73 core tests passed:** the previous 66 plus seven policy/provenance/recovery tests. They cover permitted context mutations, forged input/model/scope rejection, failure persistence, restart, exact retry, long-source scope bounds, JSON bypass, and token-overflow publication prevention. All 73 also passed on the retained Docker disk volume in the final image, including mandatory distant-heading provenance. Final formatting and Clippy with warnings denied passed.
- **Five Python worker tests passed**, using the actual pinned CPU MiniLM and injected generator responses. Coverage includes real vector shape/normalization, exact no-truncation limits, cache corruption/size bounds, heading/scope invalidation, configuration mismatch, generator outage, over-budget prompts, malformed responses, and successful retry.
- **Five source fixtures × three policies** committed successfully into separate databases, each with **28 chunks** and generation 5. TXT has 1 chunk, root-array JSON 2, nested JSON 7, native PDF 14, and scanned PDF 4. PDF extraction reused the verified T06 artifacts and originals; this task did not rerun OCR or regenerate source/answer fixtures.
- Generated mode considered nine prose chunks: **eight annotations and one abstention**. Headings/tables/JSON used structural context without generation. One initial TXT annotation was already cached when the full fixture run began.
- The diagnostic query `equipment temperature and pressure limits` used a real query embedding and returned the equipment document first under each policy. This is an integration check, not a scored retrieval benchmark; no evaluation questions or answers were loaded by the T07 verification scripts.
- A second run into fresh databases completed all 15 ingestions **with Gemma stopped**, with **zero new embedding or generation inference calls**. All receipts matched the first run. A separate empty-cache TXT run recomputed its embedding and reproduced the exact publication receipt.
- An uncached generated job with Gemma stopped saved a `Chunked` failure and left **zero committed documents / generation 0**. After restarting Gemma, a fresh CLI resumed at that stage, committed generation 1, and another retry reused the same receipt without inference.
- A fresh container with networking disabled and **no model or cache mounts** reopened the generated corpus and all five committed documents. Recovery required only the database volume.

The full fixture pass took **64.85 seconds** including repeated CLI/model initialization and diagnostic probes; it reused some earlier/cross-policy caches. The cache-only pass took **24.88 seconds**. The equipment document's six generation calls took **34.66 seconds** within its ingestion stages; the scan's two calls took **6.15 seconds**. These are single observations, not cold-start benchmarks or latency percentiles. During verification, one whole-device sample showed 6,262 MiB VRAM used; no continuous memory-peak measurement was performed.

## Quality observations and remaining boundaries

The eight annotations were inspected alongside their source excerpts. They included a useful subject description for the H2 high-temperature exception and several redundant summaries, such as repeating that the table gives nominal flow rather than the high-temperature limit. The prompt's request to abstain on self-contained excerpts is not reliably followed. No quality tuning was performed against holdout answers. Source scope and schema checks do not establish factual entailment or retrieval improvement.

Generated keyword weight remains zero in the library default; the diagnostic CLI explicitly uses policy-specific field weights. The first selection policy covers prose/list chunks and skips all JSON, including narrative fields. The fixed 64-token embedding reservation and 8,000-byte source-scope bound can reject difficult inputs; required evidence is never silently truncated. The general parser's larger file limit does not bypass the model worker's per-message bounds.

The CLI and Python child share a container and filesystem permissions, though only Rust opens the database. This is not the final production service isolation, API, scheduler, or interactive priority system. The worker processes one text/request at a time; larger-corpus throughput remains unmeasured. Cache values are disposable and bounded to 64 MiB. Annotation cache keys include revision-scoped sources and may conservatively regenerate equivalent text in a new revision.

Retained local data: `vectornext-t07_ingestion-data` contains `/storage/t07-corpus/{plain,structural,generated}`, the cache replay, empty-cache check, and outage/resume demonstration. `vectornext-t07_ingestion-cache` contains disposable inference results. Raw run outputs are under ignored `data/t07/`. The GPU service was stopped after verification.

Next: T08 reranking, evidence assembly, source-supported answer extraction, rendering, and scheduling. Preserve T02's distinction between schema validity and citation completeness; no answer-quality or state-of-the-art claim follows from T07.
