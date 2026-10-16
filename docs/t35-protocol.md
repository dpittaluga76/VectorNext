# T35 — Published-temperature generation pilot

Authorized 2026-10-16. Design: [architecture](architecture.md). This protocol is frozen with code and images before scored requests.

## Question and arms

Does using publisher-recommended non-thinking temperature improve compatibility under the existing VectorNext pipeline? Does NuExtract3 work as an additional candidate?

| Arm | Temperature | Published reference |
| --- | ---: | --- |
| Gemma 4 12B QAT Q4_0 | 1.0 | [Google](https://huggingface.co/google/gemma-4-12B-it) |
| Qwen 3.5 9B Q4_K_M | 0.7 | [Qwen, general non-thinking](https://huggingface.co/Qwen/Qwen3.5-9B) |
| Granite 4.2 8B Q4_K_M | 1.0 | [IBM](https://huggingface.co/ibm-granite/granite-4.2-8b) |
| NuExtract3 Q4_K_M | 0.2 | [NuMind, non-thinking extraction](https://huggingface.co/numind/NuExtract3) |

Only answer/planning temperature changes for the existing models; all other sampler settings inherit the unchanged pinned runtime. This is **not the full publisher sampling recipe**. Background annotation temperature remains zero under the existing durable-job contract; structural ingestion does not call generation. Experimental temperature and adapter identities do not change existing identities or the default.

## Inputs and scoring

Six cases per arm, 24 scheduled total: unchanged T34 pressure revision, large JSON integer, unknown count, PDF correction, ordinary pier-count question and history-dependent load question. Source snapshots, labels and requests are the same bytes; no holdout or new gold generation. The follow-up receives the same source-verified history regardless of the previous result. Fixed model order: Gemma, Qwen, Granite, NuExtract. Fixed question order, one sample/seed 42; no confidence or stochastic-reliability claim.

Ingest the ten T32 synthetic sources once into isolated storage using structural context. Every model sees identical committed source/revision/vector data. Separate caches and recreated processes per model; retrieval remains MiniLM/MiniLM, ranked 30/20/5. Record ingestion failures, HTTP errors and preflight-blocked requests in the denominator; blocked requests have no latency. No failed measured request is retried or replaced.

Reuse the corrected T34 reporter's exact-value, citation and browser-projection checks, preserving the already documented alternate PDF citation separately from frozen literal-source scores. Compare all six cases with fresh Gemma and the corresponding retained temperature-zero captures (T33 Qwen/Granite, T34 Gemma). Those historical comparisons are sequential, not a contemporaneous temperature-zero control. Report all-request and common-success medians/p95, per-case changes and available stage audits. Six observations cannot rank broad model quality.

## NuExtract integration

Pin official GGUF revision `28a1aae6288c5d50bdf999ca2e572240966d669b`, file `NuExtract3-Q4_K_M.gguf`, SHA-256 `7ee3c0ee9e5699a4391624ae758487f583f73b3242aa4e73dc2bb33e508d703e`, 2,783,445,984 bytes. Explicit setup verifies this hash. No projector is required for text input.

Use its embedded native template with `enable_thinking=false` and a per-request `template` projected from the unchanged output JSON Schema. Projection merges object/enum branches for prompt guidance; null-only leaves use string guidance because native templates do not represent the app's null placeholder. The original schema remains the decoding/validation authority, including dependent evidence/pointer pairs, status-specific empty fields and null-only JSON values. Quote guidance uses `verbatim-string`. Unsupported mixed primitive unions fail clearly. No schema constraint, Rust proof check, source value or absent/null distinction is relaxed. The original system instructions and user content are unchanged. Template bytes are included in prompt admission and audit hashes. This adapter is an additional experimental variable, not a claim of optimal specialist integration or equivalent expressiveness.

## Operations and verification

Retain the T28 API binary, existing runtime b11617, 4,096 context, f16 KV, one slot, batch 512/ubatch 128, full GPU layers, disabled reasoning, cache_prompt=false, two calls, existing budgets/deadlines and background temperature zero. Freeze all execution sources, images, model hashes/commands/profiles before measured calls. Capture startup, actual launch command, near-full-context constrained synthetic output, restart and a synthetic application warmup outside scored latency. Preserve raw failing warmups and logs. A failed required preflight blocks that arm's six requests; never silently change runtime, quantization or budgets.

Pause only the normal generator; leave library browsing and unrelated workloads available. Restore the same container/configuration and verify readiness, library, revisions and jobs afterward, including failure cleanup. Retain volumes/captures and remove only experiment containers/networks. Sample GPU/container memory; nvidia-smi does not prove WDDM residency. Run focused offline profile, scheduler, worker, answer, planning and scorer regressions; no Rust/API implementation changes or GPU historical suites. Keep the production default unchanged regardless of pilot outcome.
