# T02 follow-up: Gemma 4 26B A4B QAT

Measured on 2026-10-14 at the user's request. **The 26B A4B model is the stronger generation candidate on this small development set, with a substantial latency and memory cost.** It fixes E2B's outcome-classification errors and the longer-context failure. Three output-shape failures and incomplete citations remain; this is not end-to-end retrieval validation or production-quality acceptance.

The selected configuration is `compose.models.26b.yaml`, using 22 CPU-resident expert layers. The base Compose file still provides E2B for reproduction. [Run instructions](../../experiments/t02/README.md), [complete measured evidence](t02-gemma4-26b.json), and the [original E2B report](t02-local-models.md) are retained.

## Controlled comparison

- Same PC: RTX 4060 with 8,188 MiB, approximately 64 GB system RAM, Ryzen 5 7600, Docker 29.6.2, NVIDIA driver 616.92.
- Same official llama.cpp b11617/CUDA 12.8 image, 4,096-token context, maximum 256 requested output tokens, thinking off, temperature 0, seed 42, one slot, four CPU threads, flash attention on, and prompt-cache reuse disabled.
- Same 13 dev questions twice, plus one larger-context probe. Same supplied source excerpts, requested fields, JSON schema, and generation settings. No holdout questions were used.
- All **27 request payloads were verified against E2B's archived hashes**, allowing only the model alias to differ. The model's chat template/tokenization adds four input tokens: the longer probe is 3,727 tokens here versus 3,723 for E2B.
- The pinned CPU embedding/reranking identities and package versions are unchanged. The comparator rejects mismatched prompts, settings, datasets, CPU identities, missing/duplicated cases, and holdout use.
- These are supplied-excerpt experiments, without a vector index, retrieval, parsing, or OCR. Thirteen development questions are too few to establish broad reliability; repeated passes are not independent new questions.

## Results

| Measurement | E2B baseline | 26B, 20 CPU expert layers | Selected 26B, 22 CPU expert layers |
| --- | --- | --- | --- |
| Run ID | `20261014T135900Z` | `20261014T143215Z` | `20261014T143745Z` |
| Correct outcome status, each 13-question pass | 10/13 | 13/13 | 13/13 |
| Exact status and typed fields, each pass | 8/13 | 10/13 | 10/13 |
| Correct larger-context answer | No | Yes | Yes |
| Exact outputs including repeats and larger probe | 16/27 | 21/27 | 21/27 |
| Schema-valid responses / valid source IDs | 27/27 | 27/27 | 27/27 |
| Strict gold citation-set completeness | 14/23 | 13/23 | 13/23 |
| Median first-pass short request | 0.789 s | 3.992 s | 4.283 s |
| Median repeated short request | 0.764 s | 3.864 s | 4.136 s |
| Larger-context request | 1.334 s, incorrect | 16.992 s | 18.079 s |
| Process startup to healthy | 19.62 s | 66.77 s | 64.56 s |
| Sampled whole-device peak GPU memory | 2,857 MiB | 7,702 MiB | 6,889 MiB |
| GPU memory before run | 1,302 MiB | 1,343 MiB | 1,342 MiB |
| Generation-container peak memory, including file cache | 3.84 GiB | 16.44 GiB | 16.33 GiB |

The selected configuration is approximately **5.4 times slower** than E2B for the repeated short requests. Moving two additional expert layers to system RAM reduced the observed GPU peak by 813 MiB for a roughly 7% increase in median repeated latency. It left 1,299 MiB of observed device headroom, versus 486 MiB with 20 CPU expert layers. Desktop activity and context/concurrency changes can alter this margin.

Startup is process-cold with already-downloaded, checksum-verified weights and an unflushed OS file cache. It includes warmup and readiness polling. These are individual measurements, not statistically established latency guarantees. GPU figures include the desktop; the 22-layer run collected 684 samples with a maximum observed interval of 0.357 s and no sampling errors. Shorter spikes can be missed. Container peak memory includes file cache and must not be interpreted as isolated model RSS.

## What improved, and what remains

The larger model correctly recognizes that an omitted match year is ambiguous, accepts an explicit zero as a known count, and distinguishes a request for a raw JSON null from a request for an unknown numeric count. Its longer-context answer preserves the requested year, opponent, and goal count and cites the correct passage. Both CPU-placement configurations produced the same status/field scores.

The three exact-output failures are:

| Question | Correct outcome recognized | Remaining contract failure |
| --- | --- | --- |
| Ambiguous Pelé/Argentina match | `ambiguous` | Returns `{"goals": null}` instead of `{}` |
| Missing match | `insufficient_evidence` | Returns `{"goals": null}` instead of `{}` |
| Unknown assist count | `insufficient_evidence` | Returns `{"assists": null}` instead of `{}` |

These are shape/semantic-contract failures, not fabricated numeric answers. They remain failures in the recorded strict score; no response was normalized after generation to improve that score. The current schema permits optional nullable fields without encoding status-dependent requirements. T08 should enforce that contract explicitly while preserving the distinction between supported raw nulls and unsupported counts.

Citation completeness **did not improve**. Some strict gold sets require a complete JSON record and a separate leaf reference even when one contains the other. There are also substantive context omissions: the table answer cites `table_h2` (`H2 12 20`) without the units/heading, and the cross-page answer cites `c7_end` without the beginning that identifies the pump. Valid source IDs and correct fields do not establish complete citation support. Context assembly and citation validation remain necessary.

The larger probe used 3,727 input and 54 output tokens with no cached tokens. In the selected run, prompt processing accounted for approximately 16.20 of its 18.08 seconds. This suggests that assembling only necessary evidence will matter for interactive latency. It does not establish reliability for arbitrary long documents or adversarial contexts.

## Model and placement

Model: [Google Gemma 4 26B A4B instruction-tuned QAT Q4_0 GGUF](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf), revision `d1c082be9cf3c8a514acf63b8761f4b41935842e`.

- Text weight file: `gemma-4-26B_q4_0-it.gguf`, 14,439,363,584 bytes.
- SHA-256: `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d`.
- [Candidate lock](../../experiments/t02/models.26b.lock.json) includes the model card and reuses the baseline's 12 CPU model/configuration artifacts. The projector was not downloaded.
- `--n-gpu-layers 99 --n-cpu-moe 22`: first 22 layers' expert tensors stay on CPU; attention and remaining eligible tensors use CUDA. The runtime reports 31/31 layers offloaded, **but this is hybrid CPU/GPU execution**, not all weights fitting in VRAM.
- Selected runtime buffers: CUDA model 4,771.15 MiB; CPU-mapped model buffers total approximately 9,561.86 MiB; CUDA KV 80 + 250 MiB; CUDA compute 284.94 MiB. These named buffer totals are not directly additive process-resident-memory measurements.
- The CPU benchmark process peaked at 446,888 KiB RSS. Normal inference used the internal Docker network, read-only models, and no published service ports. No remote inference was used.

Both generation runs completed successfully and rejected a 5,013-token request with HTTP 400 at the 4,096-token limit. The embedding and reranking input-limit checks also passed. The generation service was stopped afterward, and device use returned to 1,342 MiB. Weights remain under ignored `models/generator-26b/` for reuse.

## Repository handoff

Prefer this 26B configuration for further **generation-quality experiments** when its latency is acceptable, while retaining E2B as the low-resource comparison. Do not hard-code either into the database or mark answer quality accepted. JSON values should still be read deterministically. T03 remains the next implementation task and requires no running generation model.

The comparison added an optional model/lock selection, a separate Compose override and run variant, model-independent prompt fingerprints, a comparison verifier, and bounded resumable downloads for large artifacts. All seven contract tests passed. The original 27 E2B request hashes were reproduced; negative comparison checks rejected changed prompts/settings, missing cases, and holdout usage. Both candidate runs, all responses, runtime identities, and measured source hashes are preserved in the JSON report. Historical E2B hashes describe its original measured source; its evidence has not been rewritten.
