# T33 — small generation-model comparison

Authorized: Qwen 3.5 9B and Granite 4.2 8B, standard Q4_K_M exports. Gemma 4 12B QAT Q4_0 is the fresh control. This is an application compatibility pilot, not a broad model ranking or promotion gate.

## Frozen inputs and scoring

Exactly **24 scheduled scored requests**, eight per model, one pass. Six requests, labels, ten synthetic TXT/JSON/PDF sources and literal-source scorer come unchanged from `experiments/t32/`. They are observed regressions. Two new browser requests test automatic count/measurement field planning and reference resolution. The follow-up uses the same fixed, source-verified preceding exchange in every arm; it does not depend on the previous measured answer and contains no answer to the follow-up. Freeze their public inputs and labels before inference. Labels are never sent to the API or model.

All eight use MiniLM embeddings/reranking, structural ingestion, ranked candidates/shortlist/primaries 30/20/5. Ingest once into a fresh isolated volume. Preserve ingestion failures and run all applicable questions without removing denominator cases; compare complete committed snapshots before and after each arm. The retained API image `:t28-12b` deliberately excludes the unactivated numeric-range repair. Build one processor and one generator image for all three arms. Fixed arm order: Gemma, Qwen, Granite; fixed case order. No cache-pass or statistical significance claim is supported by this small sequential sample.

Score status, exact values and citation support with the frozen literal-source scorer. Browser field names may differ: require exactly one field with the expected type and value, a ready plan, matching value-as-text projection and validated source support. HTTP, transport, validation and planning failures count as failures. A failed preflight leaves all eight cases explicitly blocked in the denominator with no fabricated latency. Record the previously documented T32 alternate PDF-citation exception separately; never rewrite gold. Publish raw responses and paired gains/losses. P95 on eight observations is descriptive only; compare common-success medians as well as all dispatched requests.

## Runtime and hardware

Pin model revisions, byte sizes and SHA-256 in new locks. IBM publishes Granite's GGUF; Unsloth publishes the Qwen conversion. Text-only use needs no multimodal projector. Use llama.cpp b11617 first, with unchanged 4,096 context, one slot, full GPU layers, f16 KV, batch 512 / ubatch 128, threads 4, temperature 0, seed 42, cache_prompt=false, no reasoning, two-call assessment/extraction and existing output budgets/deadlines. Both candidates explicitly set template `enable_thinking=false`, bound into runtime identities. These settings intentionally match this application; publisher recommended general sampling configurations are not being benchmarked.

Preflight verifies hashes, actual backend command, an almost-full 3,300-token synthetic input with a 768-token output reservation, closed/omitted thinking, schema output, offline startup and restart. One separate synthetic application warmup after restart is excluded from request latency. Keep preflight captures even on failure. No quantization/context/runtime substitution, prompt tuning, measured retries or post-result extra quality batch.

Use internal Docker networking for processor/generator. Only the API has local ingress. Store CPU caches separately per arm; recreate API/processor processes between arms. Observe startup/restart, stage/model timings, prompt/output token counts, sampled nvidia-smi device use and container RAM. Sampling does not prove absence of WDDM page-outs. Host model bind mounts and OS caches affect startup measurements. No nondefault embedding or reranker, speculative decoding, KV quantization or single-call experiment is combined here.

## Preservation and completion

Freeze source hashes/archive, model identities, image IDs, commands and inputs before measured requests. Fresh run names only; preserve interrupted attempts, never resume/retry into success. Verify existing normal jobs are committed before stopping only `vectornext-llm-1`; leave the normal API, document browsing and unrelated workloads alone. Restore the same generator container/configuration in a finally block, verify readiness and unchanged library/jobs, and stop experiment services while preserving storage/caches/captures. If externally interrupted, use the recovery command in the reproduction guide.

Complete after the 24 scheduled outcomes, focused unit/scorer tests, retained failures and restoration are accounted for in a report. Production defaults and launcher behavior remain unchanged, whatever the small pilot finds. Historical suites, freezes and original holdout remain untouched.
