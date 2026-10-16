# Qwen 3.5 9B and Granite 4.2 8B on VectorNext

Completed 2026-10-16. **Keep Gemma 4 12B as the default.** Both Q4_K_M candidates run on the existing runtime and RTX 4060, use less sampled GPU memory and answer explicit-field questions faster. Both lose browser-planning successes that Gemma preserves. Granite is the stronger follow-up candidate in this small application pilot; neither is ready for automatic promotion.

[Protocol](../t33-protocol.md) · [Setup/reproduction](../../experiments/t33/README.md) · [Machine-readable measurements](t33-generators.json)

## Results

Exactly **24 scored HTTP requests**, eight per model, one pass; no retries. The ten synthetic sources admitted **49 chunks** once in **28.94 s**, and every model used the same committed documents, revisions and vectors. Six explicit-field requests reuse observed T32 regressions; two additional requests exercise automatic field planning and a fixed-history follow-up. This is not an independent quality benchmark.

| Measurement | Gemma 4 12B QAT Q4_0 | Qwen 3.5 9B Q4_K_M | Granite 4.2 8B Q4_K_M |
| --- | ---: | ---: | ---: |
| Frozen literal-source correctness | 6/8 | 4/8 | 6/8 |
| Correct with existing PDF support review | **7/8** | **5/8** | **6/8** |
| Explicit-field cases, reviewed | 5/6 | 5/6 | 5/6 |
| Automatic planning + answer cases | **2/2** | **0/2** | **1/2** |
| Median, same six explicit-field requests | 9.20 s | 6.14 s | **5.08 s** |
| Median, all eight requests | 10.36 s | 4.65 s | 5.08 s |
| P95, all eight requests | 13.16 s | 6.73 s | 6.53 s |
| HTTP failures / preflight-blocked cases | 0 / 0 | 2 / 0 | 1 / 0 |
| Sampled peak whole-device GPU use | 7,774 MiB | **5,740 MiB** | 6,361 MiB |
| Apparent headroom at sampled peak, of 8,188 MiB | 414 MiB | 2,448 MiB | 1,827 MiB |
| Generator peak container memory, including file cache | 14.30 GiB | 7.17 GiB | 6.61 GiB |
| Startup to application readiness | 63.44 s | 55.25 s | 49.36 s |
| Generator restart to readiness | 63.38 s | 52.58 s | 48.83 s |
| GGUF artifact size, decimal GB | 6.98 | 5.68 | 5.35 |

**Fast refusals lower the all-request candidate medians.** On the five cases Qwen and Gemma both pass after the fixed source review, medians are **6.34 vs 10.20 s: 37.8% lower**. On the six cases Granite and Gemma both pass, they are **5.59 vs 10.36 s: 46.1% lower**. Pair sets differ; use the same-six explicit-request row for a direct three-way latency comparison. P95 with eight observations is effectively the maximum and does not establish tail reliability.

The frozen PDF label recognizes only one literal schedule passage. Gemma and Qwen correctly cite the previously reviewed correction notice instead; Granite cites the original labelled passage. Applying the **unchanged, already documented [support exception](t32-source-review.md)** adds one success to Gemma and Qwen only. Keep frozen and reviewed scores distinct; labels and original scores were not rewritten.

## Paired case outcomes

| Case | Gemma | Qwen | Granite |
| --- | --- | --- | --- |
| Approved pressure after revision | Supported: 17.5 bar | Same | Same |
| Route piers and service load across two sources | Supported: 12 and 48 | Same | Same |
| Exact large JSON integer | Supported: `9007199254740993` | Same exact value | Same exact value |
| Unknown JSON count | Insufficient evidence; no invented zero | Same | Same |
| Corrected PDF inspection interval | Supported: 45; reviewed alternative citation | Same | Supported: 45; frozen citation |
| PDF passenger and per-lifeboat capacities | Insufficient evidence; fails expected answer | Same | Same |
| Ordinary question: accepted route's pier count | Supported: 12 | **HTTP 400: falsely classified as unsupported aggregation** | Supported: 12 |
| Follow-up: its maximum authorized load | Supported: 48 | **HTTP 400: asks for clarification despite supplied history** | **Same incorrect clarification refusal** |

All six explicit-field requests have **identical assembled evidence across all three models**. Their prompt token counts differ by tokenizer, but no source-support success was gained or lost on those requests after the existing PDF review. The two-count PDF failure remains a final-evidence selection limitation; none of these generator substitutions repairs it. For the browser questions, rejected plans stop before retrieval, as the current contract requires.

The follow-up supplies an identical, source-verified preceding exchange to every model. It tests reference resolution and planning without making the input depend on whether the previous measured request succeeded. It does not include the expected load value in history.

## Runtime, artifacts and safety

The test uses the same API, processor and generator images for every arm. The API is the retained `:t28-12b` binary, excluding the unactivated numeric-range change. MiniLM embeddings/reranking, structural ingestion, ranked 30/20/5, two-call assessment/extraction, temperature 0, seed 42, cache_prompt=false, 4,096 context, one slot, f16 KV, GPU layers 99, batch 512, ubatch 128 and existing deadlines remain fixed. No prompt or retrieval tuning was performed.

New experimental profile names are `qwen35-9b-q4km` and `granite42-8b-q4km`. Each binds `enable_thinking=false` into the actual launch command and runtime/cache identity. Existing Gemma identities and defaults remain unchanged. These are experimental worker/Compose selections, not additional Windows launcher choices.

| Artifact | Pinned revision | SHA-256 |
| --- | --- | --- |
| [Unsloth export of Qwen3.5-9B](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5), `Qwen3.5-9B-Q4_K_M.gguf` | `3885219b6810b007914f3a7950a8d1b469d598a5` | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| [IBM Granite4.2-8B GGUF](https://huggingface.co/ibm-granite/granite-4.2-8b-GGUF/tree/93f3f6a8938ee922b784cf4e5b4203cd3428df8f), `granite-4.2-8b-Q4_K_M.gguf` | `93f3f6a8938ee922b784cf4e5b4203cd3428df8f` | `16a9369d0805f80b7377d25d87f937a90c05dc04ad79173a52001e42c9aab311` |

The existing Gemma lock is unchanged. All three use **llama.cpp b11617 / `14310190cd0a0c831fe949ac8cbedd8abdc90695`**, with no runtime upgrade. Publisher instructions confirm the candidates' `enable_thinking=false` mode: [Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), [IBM](https://huggingface.co/ibm-granite/granite-4.2-8b). This pilot tests the app's fixed non-thinking/temperature-zero settings, not the publishers' recommended general-purpose sampling recipes.

Each model passed a **3,300-token synthetic prompt with a 768-token output reservation**, constrained JSON output, explicit non-thinking template inspection, offline startup, restart and repeated application requests. Separate synthetic warmup after restart is excluded from answer latency. No OOM or backend failure was observed. GPU values are sampled whole-device `nvidia-smi` observations, **not proof of WDDM residency or absence of page-outs**. Container memory includes file cache and is not a minimum host-RAM requirement. This tests one 8 GB RTX 4060 only.

Startup includes artifact verification and loading from a **Windows bind mount**. Do not compare these 49–63-second restarts directly with historical measurements using other storage/cache conditions. Fixed sequential arm order and OS caching are additional limitations.

## Verification and retained attempts

- **42 focused Python tests passed offline in Docker:** legacy/candidate profiles, strict aliases/options, artifact/cache identity, answers, planning, coverage, scheduler, worker and exact scorer/projection behavior. The initial test invocation lacked its model mount; the documented corrected invocation passed.
- Compose validation and whitespace checks passed. No Rust or HTTP implementation changed; the same retained API binary ran all arms. No broad Rust/GPU regression suite, historical evaluation rerun or original holdout was used.
- Ten of ten sources committed; the corpus snapshot was identical before/after each arm. Raw response hashes, actual backend commands, profiles, image IDs and frozen execution sources were verified.
- The normal library endpoint returned HTTP 200 while generation was paused; readiness accurately returned 503. The **same normal generator container/configuration** was restored afterward, with readiness true and documents, revisions, library and jobs unchanged. API/processor and unrelated workloads were left running.
- Experiment containers/networks were removed after logs were captured; named storage/cache volumes, models, prior images and all attempts remain. No production promotion or deployment occurred.

`data/t33/pilot-v1/` retains a pre-query interruption to fix a scorer edge case: `48.0` must be checked against the exact report projection, not the label's spelling `48`. It contains zero measured requests. `pilot-v2/` retains a startup failure caused by v1's occupied fixed Docker subnet, also with zero measured requests; normal restoration succeeded. Releasing only those stopped experiment containers/networks fixed setup. **`pilot-v3/` contains the complete 24-request run.** No failed measured request was retried or replaced.

Available stage audits suggest lower generation cost as well: extraction medians were 5.10 / 3.00 / 2.53 s for Gemma / Qwen / Granite. Those operation sets differ, so this is diagnostic, not a paired speedup estimate. Raw successful responses retain model identity, exact values, token usage and timings. Existing HTTP 400 planner-decline envelopes do not retain the underlying planner token/audit payload; their exact error responses and end-to-end times are captured, and this limitation was not bypassed by changing the API.

## Reproduction and decision

Run the [explicit setup and fresh-run commands](../../experiments/t33/README.md). The completed invocation was `python -m experiments.t33.run --run pilot-v3`; choose a new name for a separately authorized repeat. Summarization is read-only:

```powershell
python -m experiments.t33.score --run pilot-v3 --output data/t33/pilot-v3/summary.json
```

Base commit: `e55ae332a811967509c9eaf194a5a00c3006f09b`, plus the archived uncommitted implementation. Retained identities:

| Item | SHA-256 / image ID |
| --- | --- |
| Execution freeze | `4c72e3e96ec3fdd1c93d0c82ddbf2b06d7a533d7a936e8d3a3602a8551a7a802` |
| Source ZIP | `f84d01c3624cd83938787220fc4f1041563631a5bc9dcfdafaad1682a2a8b457` |
| Committed corpus capture | `78014496c5601d8b42b20b8953b811aa971c74d09924ae9bba87650d7d6c5415` |
| API image | `3c858fc267b0346c0cb3beeb32ea39d86aac32a3b4d9d4efa4acde65c2c87b86` |
| Processor image | `1123ab441da0e98acb864b1ff7d7ed77aecbed40d17519edd437a48a77c31b1d` |
| Generator image | `0ee7a009ced0a1b7cd2ff488d25331f3e041a933d5bf98aa9f1948937761838e` |

Retain Gemma and all current retrieval defaults. Granite merits a separately scoped planner/follow-up compatibility experiment; Qwen is promising when fields are supplied explicitly, but has a larger planner gap here. Eight cases per model cannot establish broad factuality, ambiguity handling, multilingual quality or long-document reliability. No further batch, prompt changes or activation is implied by this recommendation.
