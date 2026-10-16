# Published temperatures and NuExtract3

**Decision: retain Gemma 4 12B at temperature zero as the production default.** Published temperatures did not improve any of the six selected outcomes for Gemma, Qwen or Granite. NuExtract3 is the strongest new extraction candidate: substantially faster and smaller in this pilot, with one automatic-planning contract failure. No profile was promoted.

Completed 2026-10-16 UTC. [Frozen protocol](../t35-protocol.md) · [Machine-readable results](t35-temperatures.json) · [Setup/reproduction](../../experiments/t35/README.md).

## Results

All **24 requests ran**, with no preflight blocks, measured retries, backend failures or observed OOM. Ten synthetic TXT/JSON/PDF documents committed into one shared 49-chunk corpus. Every model received identical assembled evidence for the four explicit-field requests, including admitted neighbors. The two browser questions additionally exercise automatic planning and a fixed source-verified preceding exchange.

| Model / answer temperature | Frozen score | Reviewed score | Explicit fields | Browser questions | All-request median / p95 | Sampled peak device memory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 12B QAT Q4_0 / 1.0 | 5/6 | **6/6** | 4/4 | **2/2** | 10.27 / 12.06 s | 7,725 MiB |
| Qwen 3.5 9B Q4_K_M / 0.7 | 3/6 | 4/6 | 4/4 | 0/2 | 4.73 / 6.22 s | 5,646 MiB |
| Granite 4.2 8B Q4_K_M / 1.0 | 5/6 | 5/6 | 4/4 | 1/2 | 5.16 / 6.81 s | 6,182 MiB |
| NuExtract3 Q4_K_M / 0.2 | 4/6 | 5/6 | 4/4 | 1/2 | **3.48 / 6.22 s** | **3,368 MiB** |

Explicit/browser columns use reviewed scoring. The unchanged [PDF support exception](t32-source-review.md) adds one success to Gemma, Qwen and NuExtract, which cite the valid correction notice. Granite cites the original labelled passage. Frozen labels, scores and review rules were not rewritten.

Qwen's median includes two fast HTTP 400 planning refusals; Granite's includes one. Compare successful pairs separately:

| Candidate | Common successes with fresh Gemma | Gemma median | Candidate median | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Qwen | 4 | 9.22 s | 5.98 s | 35.2% |
| Granite | 5 | 10.23 s | 5.56 s | 45.7% |
| NuExtract3 | 5 | 10.23 s | **3.41 s** | **66.7%** |

Pair sets differ. On the same four explicit-field cases, medians are 9.22 / 5.98 / 5.16 / 3.34 seconds respectively. Six observations make p95 descriptive only, not a tail-latency estimate suitable for deployment guarantees.

## What the temperature change did

Compare only the six matching requests from the retained temperature-zero runs, not T33's eight-request totals:

| Model | Reviewed at temperature 0 | Reviewed at published temperature | Historical / current median | Changed correctness cases |
| --- | ---: | ---: | ---: | --- |
| Gemma | 6/6 | 6/6 | 10.44 / 10.27 s | None |
| Qwen | 4/6 | 4/6 | 4.62 / 4.73 s | None |
| Granite | 5/6 | 5/6 | 5.08 / 5.16 s | None |

These are sequential comparisons with [T33](t33-generators.md) and [T34](t34-generators.md), not a fresh paired temperature-zero control. Higher-temperature sampling used one fixed seed (42); the absence of a change here does not establish equivalence across seeds or broader inputs. Only temperature follows the publisher recommendation, not the full top-p/top-k/penalty recipe. Background context-generation temperature remains zero under the unchanged durable-job contract; structural ingestion makes no generation calls.

## Case findings

- All models correctly returned **17.5 bar**, the exact integer **9007199254740993**, the **45-day** PDF interval and an insufficient-evidence outcome for the unknown count. No unknown count became zero.
- Qwen again rejected the ordinary pier-count question as aggregation and the follow-up as needing clarification. Granite again answered the count but declined the follow-up.
- NuExtract answered the follow-up with **48 tonnes**. For the pier-count question it returned the correct **12**, but its planner added route, month and year as unrequested fields. This fails the frozen requirement to plan only the requested fact. It is **not an incorrect count or fabricated source value**, and the failure is not rescored into success.
- NuExtract's unknown-count assessment incorrectly chose `supported` while its reason described the missing total. Its subsequent extraction correctly returned `insufficient_evidence`. The final answer passes, but this internal classification inconsistency remains a limitation.

All six NuExtract HTTP responses were 200; status-code success alone would have missed the planning failure. The unchanged source-proof validator and exact browser projection remain authoritative.

## Integration and hardware

Experimental profiles are `12b-temp1`, `qwen35-9b-temp07`, `granite42-8b-temp1` and `nuextract3-q4km`. Validated answer temperature is enforced by the worker and scheduler and recorded in audits/runtime identities. All nine previous profiles, their default/runtime selection and saved generation configurations remain unchanged. Background requests still require temperature zero.

NuExtract uses the official [Q4_K_M GGUF](https://huggingface.co/numind/NuExtract3-GGUF/tree/28a1aae6288c5d50bdf999ca2e572240966d669b), revision `28a1aae6288c5d50bdf999ca2e572240966d669b`, SHA-256 `7ee3c0ee9e5699a4391624ae758487f583f73b3242aa4e73dc2bb33e508d703e`, 2,783,445,984 bytes. No projector was downloaded. Existing Gemma/Qwen/Granite artifacts were reused unchanged.

Its native template receives a projection of the output schema for guidance; the **original JSON Schema** still constrains decoding and validation. The projection cannot express every dependent union/null-only leaf; it merges guidance without changing hard constraints. Prompt admission counts the actual native template, and audits bind its identity. Original system instructions and source text are unchanged. This adapter is an additional variable and does not establish the specialist's best possible integration. No prompt tuning followed observed outputs.

All arms use the same API/processor/generator images, pinned llama.cpp b11617, context 4,096, one inference slot, full GPU layers, f16 KV, batch 512/ubatch 128, disabled reasoning, cache_prompt=false, two-call answering and unchanged output budgets/deadlines. MiniLM/MiniLM, structural ingestion and ranked 30/20/5 are unchanged. The API remains the retained T28 binary, excluding the unactivated numeric-range change.

| Model | Startup / restart | Peak generator container memory, including file cache |
| --- | ---: | ---: |
| Gemma | 63.47 / 64.66 s | 13.99 GiB |
| Qwen | 55.22 / 51.28 s | 6.63 GiB |
| Granite | 50.53 / 50.08 s | 6.38 GiB |
| NuExtract3 | 28.03 / 27.38 s | 4.21 GiB |

Every profile passed a **3,300-token constrained synthetic prompt**, with a 768-token output reservation, restart and application warmup. The NuExtract check also confirmed that its native structured template was applied. Startup includes checksum verification and Windows bind-mount loading; do not compare it directly with earlier Linux-volume restart numbers. Device memory includes desktop allocations and leaves sampled headroom of 463 MiB for Gemma versus 4,820 MiB for NuExtract. WDDM residency/page-outs are **not verified**; one RTX 4060 is not a hardware compatibility matrix.

## Verification and preservation

- **49 focused offline Docker tests passed**, covering temperature/profile/alias enforcement, template bounds, original schema preservation, token counting, old identities, exact numbers, planning, scoring, workers and scheduler behavior. Compose validation and whitespace checks passed.
- All **124 frozen execution files** and image/command identities matched at completion. All **44 available scored-operation audits** use the selected temperature. Existing HTTP 400 planner-decline envelopes omit underlying planner audits; exact errors and end-to-end times are retained.
- Same corpus before and after each arm, unchanged source/label bytes, no measured retries or additional quality batch. The original holdout remains unused. Historical freezes/captures and all prior model files/images remain retained.
- Normal library browsing returned HTTP 200 during the generator pause; readiness correctly returned 503. The **same original generator container/configuration** was restored, readiness is true, and documents/library/jobs are unchanged. Unrelated workloads were left running.
- Experiment containers/networks were removed; corpus/cache volumes, models and exact captures remain in ignored `data/t35/pilot-v1/`. No production activation, commit or push was performed. No Rust/HTTP code changed, so no unrelated broad Rust or GPU regression suite was run.

The only measured run was `python -m experiments.t35.run --run pilot-v1`. Read-only summary: `python -m experiments.t35.report --run pilot-v1 --output data/t35/pilot-v1/summary.json`. The published JSON additionally records matching-case historical comparisons and verification; those additions do not change frozen scoring. Full setup is in the [reproduction guide](../../experiments/t35/README.md).

| Retained identity | SHA-256 / image ID |
| --- | --- |
| Execution freeze | `fa02fb2528a502644551bed075913c19232c85cf60a0f4e9aaa675cf08fccf2d` |
| Source ZIP | `9ee201661b25ac3ecd804c35242c6da71161455d66151e3af4346db619a6bb16` |
| Corpus capture | `bbabd16a409644ee0c22d4129545f3c3ebb56a360171f42808674bc2e192aab9` |
| API image | `3c858fc267b0346c0cb3beeb32ea39d86aac32a3b4d9d4efa4acde65c2c87b86` |
| Processor image | `33c65f611dacceef50a92b301d76d238575a1f5b4c267820a6f1074d3279bf01` |
| Generator image | `4692c23e3655785b13466b4eb56573f729941c0dee63fb718435731e99051a7b` |

Keep the production default at Gemma/temperature zero. NuExtract merits a separately scoped, fresh planning/assessment confirmation before any broader replacement decision. This observed six-case pilot does not test broad ambiguity, multilingual or long-document reliability and authorizes no further batch or automatic promotion.
