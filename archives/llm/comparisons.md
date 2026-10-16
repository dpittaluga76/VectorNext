# Historical model comparisons

These are retained historical measurements. Their runtime switches and runners were archived during Hybrid integration; they are not supported app options. Use the [source archive](README.md) for exact reproduction.

### Gemma 12B vs 26B

**12B became the default after pointer constraints recovered its JSON-answer failures while retaining most of its speed advantage.** The original comparison evaluated Gemma 4 26B A4B QAT Q4_0 with Gemma 4 12B QAT Q4_0 in 416 requests and initially rejected 12B's promotion. The follow-up changed the application's extraction constraints, kept the model weights unchanged, and completed a separate 208-request 12B evaluation against the retained baseline results.

Answer scores and latency below use the default **five primary passages**. The evidence-coverage suite contains 16 questions; the NASA/USGS suite contains 28 questions. Accuracy was identical in both cache passes. Resource peaks cover all query blocks, including the other passage-selection strategies.

| Measurement | 26B — baseline | 12B — before pointer constraints | **12B — current** |
| --- | ---: | ---: | ---: |
| Evidence coverage: correct outcomes | **13/16** | 10/16 | **13/16** |
| NASA/USGS: correct outcomes | 16/28 | 14/28 | **18/28** |
| Evidence-coverage median latency, cold / warm | 29.51 / 28.44 s | 11.59 / 11.16 s | **11.16 / 10.57 s** |
| NASA/USGS median latency, cold / warm | 20.86 / 21.23 s | **9.86 / 9.48 s** | 10.35 / 9.99 s |
| Previously correct 26B cases | Baseline | Some lost | **All preserved, including source support** |
| Model placement | Experts from 22 layers on CPU | All layers on GPU | All layers on GPU |
| Peak whole-device GPU use | **6,706 MiB** | 7,864 MiB | 7,880 MiB |
| Peak generator memory, including file cache | 19.81 GiB | 11.82 GiB | **10.19 GiB** |
| Decision | Previous default | Failed promotion gates | **Current default** |

Cold/warm refers to persisted application caches; OS/backend caches were not globally flushed. Latencies include errors and abstentions, exclude model loading/warmup, and use explicit answer fields. Ordinary browser questions add a separate automatic field-planning call. Whole-device GPU measurements include desktop workloads; generator memory is container accounting including file cache, not process RSS.

**What pointer-constrained extraction changed:**

| Area | Before pointer constraints | With pointer constraints |
| --- | --- | --- |
| JSON path selection | Ranked extraction allowed unconstrained path strings. | The schema permits only existing, type-compatible RFC 6901 paths from admitted evidence records. |
| Example failure | The model could emit `properties.mag`. | It must select an allowed pointer such as `/properties/mag`. |
| Evidence association | Invalid record/path combinations could reach validation and be rejected. | Schema branches bind each permitted pointer to its specific evidence record. |
| Actual answer value | Rust read the original JSON value and validated it. | **Unchanged.** The model does not transcribe the numeric value; exact values, zero, raw null and missing fields retain their distinctions. |
| Prompt budgeting | Ranked extraction lacked the pointer catalog. | Catalog tokens count toward the budget and can displace other evidence. Rejected additions restore the prior constraint state. |
| Inference calls | Existing assessment/extraction calls. | **No additional calls or repair retries.** |
| Other settings | Pinned models and runtime, existing context and retrieval configuration. | **Unchanged:** model weights, embeddings, reranker, 4,096-token context, temperature zero, seed 42 and ranked 30/20/5. |

**Limitations and tradeoffs:**

- **Comparison scope:** The follow-up reran 12B only. **26B with the new pointer constraints remains unmeasured.** These results compare application configurations on one RTX 4060, including 26B's CPU expert offload; they do not establish that 12B is intrinsically more capable. Full-GPU 26B on larger cards remains unverified.
- **Speed and overhead:** current 12B reduced ranked-five median latency by **50.4–62.8%** versus retained 26B, exceeding the 20% promotion gate. The proposed 65–75% overall reduction was not achieved. NASA/USGS medians increased about **5%** versus the earlier 12B run. Catalog token accounting changed a prose neighbor in two of 208 requests, so evidence was not identical in every case.
- **GPU headroom:** full GPU placement uses less system memory here but more VRAM than offloaded 26B. The current sampled peak was **7,880/8,188 MiB**, leaving only **308 MiB**. No OOM/backend failure was observed; Windows GPU page-outs remain unverified. Only this 8 GB card was tested, not the whole intended 8–12 GB range.
- **Quality evidence:** these are 44 reused questions across strategies and passes, not independent proof of broad quality. The NASA/USGS suite retains two PDF admission failures and their six dependent questions in every 28-question denominator. The follow-up's 208 requests include six rejected responses; HTTP success is not the accuracy score. Original strict labels and separate source-review exceptions remain unchanged.
- **Remaining failures:** a valid pointer can still select a semantically irrelevant field. PDF extraction failures and semantic mistakes remain; the measured release also rejected year-range endpoints. Separate planner/source/browser checks passed, but their success does not guarantee correct answers to every ordinary question.

26B remains available as an optional compatibility and rollback profile. [Original model comparison and promotion failure](../../docs/reports/t27-model-comparison.md) · [Pointer-constrained results, p95, case changes and rollout](../../docs/reports/t28-ranked-pointers.md) · [Pointer and proof contract](../../docs/answers.md#ranked-json-pointer-constraints-t28).

### Qwen and Granite generation pilot

A **24-request local pilot** compared two Q4_K_M alternatives with Gemma while keeping the same corpus, MiniLM retrieval and two-call answering. Both candidates fit the tested RTX 4060 and were faster, but lost automatic-planning successes.

| Model | Correct cases with the existing PDF citation review | Automatic question/follow-up cases | Median of the same six explicit-field requests | Sampled peak GPU use |
| --- | ---: | ---: | ---: | ---: |
| **Gemma 4 12B QAT Q4_0 — default** | **7/8** | **2/2** | 9.20 s | 7,774 MiB |
| Qwen 3.5 9B Q4_K_M | 5/8 | 0/2 | 6.14 s | 5,740 MiB |
| Granite 4.2 8B Q4_K_M | 6/8 | 1/2 | 5.08 s | 6,361 MiB |

Frozen literal-source scores were 6/8, 4/8 and 6/8; the separately recorded valid PDF-citation alternative explains the reviewed counts above. Both candidates preserved exact JSON values and explicit-field outcomes. Qwen incorrectly declined the ordinary count question and its follow-up; Granite declined the follow-up. On paired successful cases, Qwen was **37.8% faster** and Granite **46.1% faster**, using different common-success sets. **Gemma remains the default.** These are eight synthetic cases per model, not broad quality proof; sampled memory does not establish Windows GPU residency. Experimental profiles use pinned artifacts and the existing runtime, with thinking disabled. [Results, limitations and case changes](../../docs/reports/t33-generators.md) · [Explicit setup and reproduction](../../experiments/t33/README.md).

### Ministral, Phi and Liquid generation pilot

A second bounded pilot scheduled **24 requests across four models** on the same ten-document corpus. Gemma remains the default. Twelve requests ran; the other twelve stayed blocked after mandatory synthetic checks failed.

| Model | Correct cases with the existing PDF citation review | Median answer-request time | Result |
| --- | ---: | ---: | --- |
| **Gemma 4 12B QAT Q4_0** | **6/6** | **10.44 s** | Both ordinary-question cases passed |
| Ministral 3 8B Instruct Q4_K_M | 2/6 | 4.57 s, including failures | Altered source quotes, false clarification and missed supplied evidence |
| Phi-4-mini-instruct Q4_K_M | Six cases blocked | Not measured | Long-prompt check returned the wrong color |
| LFM2.5-1.2B-Instruct Q4_K_M | Six cases blocked | Not measured | Passed long-context JSON, failed application-answer warmup |

Frozen literal-source scores were **5/6 for Gemma and 2/6 for Ministral**; the same previously recorded PDF citation exception explains Gemma's reviewed count. On the two requests both answered correctly, Ministral took **4.38 s versus 8.53 s**, but lost four Gemma successes. Phi/Liquid's blocked cases are operational failures, not measured question accuracy; their low preflight memory use does not establish application reliability. No prompts, validators or defaults were changed to rescue failures. These small, reused synthetic cases test compatibility with this app, not general model capability. [Full results, hardware and limitations](../../docs/reports/t34-generators.md) · [Setup and reproduction](../../experiments/t34/README.md).

### Published temperatures and an extraction specialist

A 24-request follow-up used the publishers' non-thinking **temperatures** while keeping other sampler/runtime settings unchanged. It also tested **NuExtract3** with its native extraction template and the same hard JSON constraints and source validation.

| Model | Temperature | Correct cases with the existing PDF citation review | Median request time | Sampled peak GPU use |
| --- | ---: | ---: | ---: | ---: |
| Gemma 4 12B QAT Q4_0 | 1.0 | **6/6** | 10.27 s | 7,725 MiB |
| Qwen 3.5 9B Q4_K_M | 0.7 | 4/6 | 4.73 s | 5,646 MiB |
| Granite 4.2 8B Q4_K_M | 1.0 | 5/6 | 5.16 s | 6,182 MiB |
| NuExtract3 Q4_K_M | 0.2 | 5/6 | **3.48 s** | **3,368 MiB** |

Gemma/Qwen/Granite retained exactly the same correctness outcomes as their corresponding temperature-zero cases. Qwen and Granite still declined follow-ups; their medians include fast failures. NuExtract passed all four explicit-field cases and the follow-up, but added three unrequested fields alongside the correct pier count. On its five common successful cases it was **66.7% faster than Gemma** (3.41 vs 10.23 s). Frozen literal-source scores were 5/3/5/4 of six; reviewed scores above preserve the existing alternate PDF citation separately.

**Production stays on Gemma at temperature zero.** NuExtract remains experimental. One seed, six reused cases per model and a model-specific template adapter do not establish broad reliability; this is not the full publisher sampling recipe. All four profiles passed full-context/restart checks, with no observed OOM, but sampled memory does not prove Windows GPU residency. [Results, case changes and limitations](../../docs/reports/t35-temperatures.md) · [Explicit setup and reproduction](../../experiments/t35/README.md).

### Repairing the specialist's extra fields

A separate **24-request fresh comparison** added a versioned NuExtract planner instruction that separates requested outputs from supplied subject/date/location constraints. The new experimental `nuextract3-requested-facts-v1` profile keeps explicitly requested multiple fields and follow-ups. It does not trim outputs, change the extraction schema or add a model call.

| Model/profile | Frozen correct | Correct after source/API review | Median, all eight requests | Sampled peak GPU |
| --- | ---: | ---: | ---: | ---: |
| Production Gemma 4 12B, temperature 0 | 6/8 | **8/8** | 10.15 s | 7,728 MiB |
| Original NuExtract3, temperature 0.2 | 4/8 | 5/8 | 3.47 s | 3,402 MiB |
| NuExtract3 with requested-field repair, temperature 0.2 | 6/8 | **8/8** | **3.59 s** | **3,390 MiB** |

The fix recovered two extra-field failures and an unresolved-subject clarification failure, preserving the three-field request, follow-up, exact large integer and missing-data abstention. On the **five common source-supported answers**, the fixed profile was **64.7% faster than Gemma** (3.74 vs 10.59 s). The original NuExtract median includes incorrect outcomes; the fixed prompt adds tokens and is slightly slower on their previously shared successes.

Reviewed scores separately correct a frozen scorer's rejection of an original PDF heading and its expectation of a later aggregation-error message. The application rejects that aggregation before calling any model. All original labels/scores remain intact. Eight synthetic questions, one seed and this author-administered review do not establish broad reliability or guarantee requested-field semantics. **Gemma remains the production default; the repaired NuExtract profile is experimental.** [Results, case table and reproduction](../../docs/reports/t36-planning.md) · [Exact review rules](../../docs/reports/t36-source-review.md).

### Single-call answering experiment

A separate 208-request comparison removed the preliminary assessment while keeping the extraction prompt, pointer schema, evidence and prompt caching unchanged. Ranked five preserved **13/16** and **18/28** correct outcomes, with **35.6–40.7% lower median latency**. Coverage mode fell from **12/16 to 10/16** in each pass, so the production **two-call default remains**. All 202 comparable successful responses had identical assembled evidence; failures stayed in the denominator. These are sequential comparisons on reused regression questions. [Results and case changes](../../docs/reports/t29-single-call.md) · [Reproduction](../../experiments/t29/README.md).

### Memory and embedding experiments

An independent 208-request Q8 KV-cache comparison saved **217.5 MiB** of GPU allocation, but lost a correct unknown-count classification in four ranked blocks. The default keeps **f16 KV storage**. Full-context/restart checks passed; sampled GPU use does not establish absence of Windows paging. [Memory results and limitations](../../docs/reports/t30-kv-cache.md) · [Reproduction](../../experiments/t30/README.md).

The experimental **BGE-small-en-v1.5** CPU profile supports 512 tokens with CLS pooling and a query instruction included in its embedding-space identity. Across 192 retrieval requests, it improved NIST selected-20 coverage **18/20 → 19/20**, while final-five coverage stayed **16/20** on both NIST and NASA. Ingestion was **34–40% slower** at the unchanged 180-token chunk target. **MiniLM remains the default**; existing vectors are preserved. These TXT regression sets do not establish answer accuracy or long-record gains. [Embedding results](../../docs/reports/t31-embeddings.md) · [Explicit setup and reproduction](../../experiments/t31/README.md).

A separate **24-request TXT/PDF/JSON pilot** compared Nomic embeddings and Ettin-17M reranking in four combinations. MiniLM embeddings with Ettin improved frozen correctness **4/6 → 5/6**, recovered the missing lifeboat evidence and reduced median end-to-end latency **12.80 → 9.68 s**. A separately reviewed valid PDF citation raises both counts to **5/6 → 6/6**; frozen labels remain unchanged. Nomic admitted a 557-token JSON record, but it exceeded the existing 512-token reranker budget and caused four failures in each Nomic arm. This exposes a pipeline compatibility gap, not a reliable Nomic quality comparison. **Both MiniLM defaults remain** pending further evidence. The new CPU profiles are experimental and require compatible fresh ingestion; six synthetic questions do not justify promotion. [Four-combination results and limitations](../../docs/reports/t32-replacements.md) · [Setup and reproduction](../../experiments/t32/README.md).
