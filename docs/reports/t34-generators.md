# T34 — Ministral, Phi and Liquid versus Gemma

**Decision: keep Gemma 4 12B as the default.** Ministral was faster but lost four working cases. Phi and Liquid loaded on the existing runtime but failed mandatory synthetic checks before their scored questions. This is a small compatibility pilot under this application's fixed settings, not a general model ranking.

Date: 2026-10-16 UTC. [Frozen protocol](../t34-protocol.md) · [Machine-readable results](t34-generators.json) · [Setup](../../experiments/t34/README.md) · [Post-run reporting correction](../t34-reporting-addendum.md).

## Outcomes and latency

**24 requests were scheduled: 12 dispatched, 12 blocked by preflight.** The blocked cases remain in their six-case denominators with no fabricated response times. Ten of ten synthetic TXT/JSON/PDF documents committed into one shared 49-chunk corpus. The original historical holdout was not used.

| Model | Frozen literal-source score | With existing PDF citation review | Scored requests sent / blocked | Median / p95 of dispatched requests | Sampled peak GPU use |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Gemma 4 12B QAT Q4_0** | **5/6** | **6/6** | 6 / 0 | **10.44 / 12.03 s** | 7,838 MiB |
| Ministral 3 8B Instruct 2512 Q4_K_M | 2/6 | 2/6 | 6 / 0 | 4.57 / 5.66 s | 5,889 MiB |
| Phi-4-mini-instruct 3.8B Q4_K_M | 0/6, blocked | 0/6, blocked | 0 / 6 | Not measured | 3,541 MiB, preflight only |
| LFM2.5-1.2B-Instruct Q4_K_M | 0/6, blocked | 0/6, blocked | 0 / 6 | Not measured | 1,398 MiB, preflight only |

The blocked rows are operational outcomes, **not measured six-question accuracy estimates**. Ministral's all-request median includes three fast HTTP 400 failures and one incorrect insufficient-evidence result. On its **two common successful cases**, median latency was **4.38 s versus Gemma's 8.53 s**, a **48.6% reduction**. That pair consists of the large JSON integer and the correctly unknown count; it does not justify a general speed/quality replacement claim. There are no paired application timings for Phi or Liquid.

The unchanged [PDF review](t32-source-review.md) recognizes an alternate correct citation for the 45-day inspection interval. Gemma used that citation, so strict and reviewed scores differ. No labels or review rules were changed for these models. Six observations make p95 descriptive only. Fixed sequential order, Windows model bind mounts and OS caches limit timing comparisons; these six-case numbers are not directly interchangeable with T33's eight-case totals.

## What failed

| Case | Gemma | Ministral |
| --- | --- | --- |
| Approved pressure after revision | Supported: 17.5 bar | HTTP 400: altered source quote with added `**` markup |
| Exact large JSON integer | Supported: `9007199254740993` | Same exact value |
| Unknown JSON count | Insufficient evidence; no invented zero | Same correct outcome |
| Corrected PDF inspection interval | Supported: 45 days; reviewed citation | HTTP 400: quote includes added quotation marks and `**` markup |
| Ordinary pier-count question | Supported: 12 | HTTP 400: incorrectly asks for clarification |
| Follow-up asking authorized service load | Supported: 48 tonnes | Ready field plan, then incorrect insufficient-evidence assessment |

Ministral's follow-up saw the **same two assembled passages as Gemma**, including the explicit 48-tonne authorization. Its assessment nevertheless said only the pier count was available. This is an assessment failure, not missing retrieval. Its numeric prose drafts contained the right values, but exact-source proof validation correctly rejected altered quotations. The default was not weakened to accept them. Automatic planning itself passed one of two cases, but neither browser question produced a correct final answer.

**Phi:** the 3,300-token synthetic prompt stated that the token was yellow and requested a constrained JSON color. Phi returned schema-valid `{"color":"c"}` with finish reason `stop`. This fails the predeclared semantic preflight. Its six questions were blocked; restart and application warmup were not reached. The exact preflight response is retained in `commands.log` and the machine-readable report. No backend crash or OOM was observed.

**Liquid:** passed the same 3,300-token constrained check with `{"color":"yellow"}`, then passed restart. The separate application warmup, using the normal assessment/extraction worker, failed its requirement to return a supported yellow answer. Its six questions were blocked. The frozen warmup raises before printing a failed answer, so **the exact failed draft/reason is unavailable**; the exception and service logs are retained. The cause is not attributed to a particular output field or prompt defect without that evidence. No corrective inference, prompt tuning or retry was performed.

These are results for pinned Q4_K_M exports, the current runtime/templates, temperature zero and disabled reasoning. They do not establish that Phi or Liquid cannot work with another integration. Liquid's possible CPU-only planner role was not tested.

## Runtime and hardware

All arms used one retained API image (`:t28-12b`, excluding the unactivated range-parser change), one processor build and one generator build. Keep MiniLM/MiniLM, structural ingestion, ranked 30/20/5, two-call assessment/extraction, context 4,096, one inference slot, f16 KV, full GPU layers, batch 512 / ubatch 128, threads 4, temperature 0, seed 42, cache_prompt=false and existing output budgets/deadlines. All artifacts were checksum verified; actual backend commands matched the shared profiles. No runtime upgrade, projector, CPU-planner route or production activation occurred.

| Model | Startup | Restart | Peak generator container memory including file cache |
| --- | ---: | ---: | ---: |
| Gemma | 63.31 s | 64.51 s | 13.97 GiB |
| Ministral | 49.41 s | 47.73 s | 6.19 GiB |
| Phi | 24.58 s | Not reached | 2.30 GiB |
| Liquid | 8.06 s | 8.28 s | 0.91 GiB |

Startup/restart include artifact verification and Windows bind-mount loading. They are not comparable to historical Linux-volume startup figures. Device memory includes desktop allocations and is sampled, not a residency guarantee. Gemma's sampled peak left 350 MiB of the 8,188 MiB device. Candidate peaks cover different completed stages, especially the two preflight failures. No OOM/backend failure was observed; absence of WDDM paging is unverified. Only this RTX 4060 was tested.

New generator-only locks and profiles:

| Profile | Artifact provenance / revision | SHA-256 |
| --- | --- | --- |
| `ministral3-8b-q4km` | [Official Mistral GGUF](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF/tree/0102285ad796bd99af90f58de616092e5630e970) | `33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761` |
| `phi4-mini-q4km` | [Unsloth export of Microsoft's Phi](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF/tree/78eb92a46fc37e6b524df991ed9aca9bc6aa7b80) | `88c00229914083cd112853aab84ed51b87bdf6b9ce42f532d8c85c7c63b1730a` |
| `lfm25-12b-q4km` (**1.2B**) | [Official Liquid GGUF](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/tree/8ed288026e23958ad9dfa92d53ed773a8eee7125) | `b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5` |

Existing Gemma, embedding, reranker and saved generation identities are unchanged. These are experimental worker/Compose selections, not new Windows launcher choices. All use llama.cpp b11617 / `14310190cd0a0c831fe949ac8cbedd8abdc90695`. See publisher cards/licenses in the setup guide; Liquid uses its own license terms.

## Verification and preservation

- **42 focused offline Docker tests passed before inference**, covering profiles, aliases, legacy/artifact/cache identities, frozen inputs, exact scoring, workers, answers, planning, coverage and scheduler behavior.
- **Three reporting regression tests passed** after adding the offline correction. Its first test run exposed a missing browser-label adaptation; that was fixed before reporting. All nine captured HTTP 200 responses produce exactly the same score details as the frozen scorer. Non-200 outcomes remain failures, with unavailable coverage marked unknown.
- The initial frozen summary command raised `KeyError: 'text'` on rejected-answer metadata. The separate `report.py` handles this without changing original code, freezes, captures or quality criteria. See the [reporting addendum](../t34-reporting-addendum.md). There was **one measured run and no measured retries**.
- All 109 frozen execution files matched at run completion, alongside image IDs, original input hashes and actual backend commands. The setup README was subsequently updated only to point to the reporting correction; the original README is retained in the source ZIP. Historical T32/T33 inputs, captures, scores and the original holdout are unchanged.
- Normal document browsing returned HTTP 200 while generation readiness returned 503. The same normal generator container/configuration was restored; readiness is true and documents, revisions, library and jobs match the pre-run capture. Normal API/processor and unrelated workloads were left running.
- Experiment containers/networks are removed. Models, images, named data/cache volumes and exact raw captures remain under ignored `data/t34/pilot-v1/`. The report JSON contains only synthetic fixture results. No Rust/HTTP implementation changed, so no unrelated broad Rust or GPU suite was rerun.

Reproduction uses the [explicit setup and fresh-run guide](../../experiments/t34/README.md). Completed execution: `python -m experiments.t34.run --run pilot-v1`. Reporting performs no inference:

```powershell
python -m experiments.t34.report --run pilot-v1 --output data/t34/pilot-v1/summary.json
```

Base commit: `e55ae332a811967509c9eaf194a5a00c3006f09b`, plus archived uncommitted implementation. Retained identities:

| Item | SHA-256 / image ID |
| --- | --- |
| Execution freeze | `a272b7eebe5748339294b1199ff068b240dbba53a85bcbc77008215f485b2cb0` |
| Source ZIP | `824d41067cf0af3203eb92037c9dc11cc80389eff36becfb2dce7b7e106fa955` |
| Committed corpus capture | `91f5cf71977bda6a63743941c086dd1dbf047a133c9cecf8dad20a8903c06468` |
| Corrected reporter | `84ceb3d1471cc746e0a35a5c9279cd6f1be805521a8a523236be645cd7001da3` |
| API image | `3c858fc267b0346c0cb3beeb32ea39d86aac32a3b4d9d4efa4acde65c2c87b86` |
| Processor image | `7ebb178c91430fe6157321911c764676cb7fe6ced0a08348844e2f9a32bd5686` |
| Generator image | `032903ab708b6fdff16faa2c9789e6bb34096ca24474086f5eb2a381e1e510b2` |

Keep the deployed Gemma profile and all retrieval defaults. Among the earlier Qwen/Granite candidates, Granite remains the more promising separately scoped planner-compatibility follow-up. Nothing in this pilot authorizes another batch or automatic promotion.
