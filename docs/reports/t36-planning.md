# T36 — NuExtract requested-field repair

Completed 2026-10-16. The versioned NuExtract planner repair fixes the original extra-field failure and recovers three failures in a fresh 24-request comparison. Production stays on Gemma 4 12B at temperature zero; this small pilot does not authorize promotion.

## Results

Eight fresh browser requests per arm, one seeded pass, identical committed evidence. The reviewed column includes two separately documented scorer exceptions; frozen scores are preserved.

| Arm | Temperature | Frozen correct | Correct after review | Planner contracts | Median, all requests | p95, all requests | Sampled peak GPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 12B QAT Q4_0 | 0 | 6/8 | **8/8** | **7/7** | 10.15 s | 17.95 s | 7,728 MiB |
| Original NuExtract3 Q4_K_M | 0.2 | 4/8 | 5/8 | 4/7 | 3.47 s | 6.55 s | 3,402 MiB |
| NuExtract3, requested-facts-v1 | 0.2 | 6/8 | **8/8** | **7/7** | **3.59 s** | **6.09 s** | **3,390 MiB** |

The aggregate request is rejected by an existing application guard before the planner runs, so the planner denominator is seven. All-request timings include correct declines and failures. On the **five source-supported answers both Gemma and fixed NuExtract answered correctly**, median latency was **10.59 → 3.74 seconds (64.7% lower)**. Across all eight reviewed common-correct outcomes, it was 10.15 → 3.59 seconds (64.7% lower). No loading, preflight or warmup time enters request latency.

The fix is not a universal NuExtract speedup: among the original NuExtract's five reviewed successes, median latency rose **3.33 → 3.48 seconds**; among its three common positive answers, **3.61 → 3.74 seconds**. The additional planner instruction adds 258 input tokens. Avoiding unrequested output fields reduced the count and PDF request times from **5.94 → 3.69** and **6.55 → 3.83 seconds** respectively. Original NuExtract's lower all-request median does not account for its three incorrect outcomes.

| Fresh case | Gemma | Original NuExtract | Fixed NuExtract |
| --- | --- | --- | --- |
| Berths at a named terminal/month/year | One integer, 18 | Correct 18 **plus three unrequested fields** | One integer, 18 |
| PDF pressure for named valve/cycle/plant | One number, 6.25 | Correct 6.25 **plus three unrequested fields** | One number, 6.25 |
| Explicit depot name, year and bay count | Northbank; 2036; 7 | Same three requested facts | Same three requested facts |
| History-dependent vessel draft | One number, 11.75 | Same | Same |
| Exact JSON sequence | Integer 9007199254741237 | Same | Same |
| Missing manual reset count | Insufficient evidence | Same | Same |
| Unresolved subject, no history | Requests clarification | Plans a generic count, then returns ambiguous | Requests clarification |
| Compute sum across records | API rejects before planning | Same | Same |

There are no lost reviewed Gemma successes. The unchanged NuExtract and fixed arm differ only in the planner variant/profile identity: same weights, native template, temperature, assessment/extraction prompts, runtime and hard schema. The original NuExtract ambiguity reply did not fabricate a factual answer, but it failed the expected pre-retrieval clarification contract.

## What changed

`model_worker/planning.py` adds a NuExtract-only instruction distinguishing **requested output properties** from **supplied identifying constraints**. It keeps identifying details in descriptions and preserves explicitly requested names, years, multiple properties and history-dependent requests. The new `nuextract3-requested-facts-v1` profile selects it; `field-planning-v3;requested-facts-v1` and the runtime/cache identity record it.

There is no extra model call, output pruning, forced single-field schema, answer generation in planning or automatic retry. Original question/history, public API, exact JSON pointer materialization, source validation, embedding spaces and saved generator identities remain intact. All 13 existing profiles, their runtime identities, the default and the original planner prompt/version are unchanged. The original NuExtract profile remains available for comparison and rollback.

Before fresh inference, two separate development planner calls passed: the exact T35 Norhaven count now produces only `pier_count`, retaining route/month/year in its description; a three-property contrast preserves route name, acceptance year and pier count. Both raw replies remain in `data/t36/development-v1/`. No failed model attempts or prompt revisions were needed. The production application itself was not rebuilt or switched.

## Scoring review, kept separate

The frozen scorer produced two false-negative categories. The PDF evidence includes an original heading prepended to its cited body chunk; the scorer incorrectly demanded that the whole assembled passage fit inside that single chunk. The aggregate request correctly hits an earlier Rust rejection than the planner rejection text expected by the label.

The [source/API review](t36-source-review.md) verifies those exact cases while preserving all field/value/type/citation requirements. It accepts Gemma/fixed NuExtract's valid PDF replies and all three upstream aggregate declines. It does not excuse the original NuExtract's extra fields or unclear-subject behavior. The frozen scorer, labels, execution archive and all 24 responses remain unchanged. `review.py` is an explicitly post-run sidecar with its own hash; it is not part of the original execution freeze.

## Hardware and verification

Five synthetic TXT/JSON/PDF documents ingested once into six chunks; all admissions committed. The PDF was reviewed visually and by extracted text before input freezing. Six comparable retrieval requests have identical assembled evidence and original-question/history hashes across all arms. Each arm used separate query caches and recreated processes. No measured retries, replacement successes, ingestion failures, blocked preflights or backend/OOM failures occurred.

All three passed 3,300-token constrained-input checks, offline startup, restart and synthetic application warmup. Startup/restart wall times include local checksum validation and loading:

| Arm | Compose startup | Generator restart to readiness | Peak generator container RAM |
| --- | ---: | ---: | ---: |
| Gemma | 63.33 s | 65.61 s | 8,386.56 MiB |
| Original NuExtract | 26.94 s | 27.41 s | 3,103.74 MiB |
| Fixed NuExtract | 28.09 s | 28.61 s | 3,100.67 MiB |

Tested RTX 4060 reports 8,188 MiB. The fixed arm's sampled device peak leaves approximately 4,798 MiB of reported headroom, versus 460 MiB for Gemma. Samples include desktop/other allocations and do not prove absence of WDDM paging. Startup timings are observations on this machine, not guaranteed cold-start costs.

Verification: **58 focused offline Python checks**, seven final scorer rechecks after adapting to the existing Rust error prefix, and two post-run review checks passed. All **144 frozen execution files**, source ZIP entries, three image IDs, actual launch commands, artifact hashes and **53 available operation audits** matched. Short-circuited extraction has only an assessment audit; planner-decline envelopes do not expose their raw model audit. No audit was invented for unrecorded calls. The unchanged Rust/API image excludes unrelated source-only changes; no Rust build or historical quality rerun was needed.

Only the normal generator was stopped; its library endpoint remained HTTP 200 while answering readiness correctly returned 503. After both development and fresh runs, the same normal generator container/configuration was restored, readiness passed and library/revisions/jobs were unchanged. Unrelated workloads were untouched. Experiment containers/networks are removed; volumes, caches, raw replies and logs remain. Production is still the three-service `:t28-12b` deployment with Gemma/temperature zero, two-call answering, f16 KV, structural context, MiniLM/MiniLM and ranked 30/20/5. Original holdout and historical scores remain unused/unchanged.

## Reproduction and retained artifacts

Use the [pre-query protocol](../t36-protocol.md) and [build/run commands](../../experiments/t36/README.md), with fresh run names for any authorized repeat. No additional model download was needed. The retained API and candidate processor/generator image IDs are recorded in the execution manifest. Preserve its source ZIP to reproduce the exact measured code, including any previously uncommitted work.

Offline reports for the completed run:

```powershell
python -m experiments.t36.report --run pilot-v1 --output data/t36/pilot-v1/frozen-summary.json
python -m experiments.t36.review --run pilot-v1 --output docs/reports/t36-planning.json
docker run --rm --network none -v "${PWD}:/repo:ro" -w /repo --entrypoint /opt/model-env/bin/python vectornext-app-processor:t36 -m unittest experiments.t36.test_review -v
```

- [Machine-readable measurements](t36-planning.json), retaining frozen and reviewed results and paired changes.
- `data/t36/pilot-v1/`: 24 attempts/raw responses/rows, corpus, image/profile/command freeze, source ZIP, resources, logs, preflights and restoration records.
- `data/t36/development-v1/`: two known-case planner replies and source/operational captures.
- `data/t36/verification.json`, `offline-tests.txt`, `scorer-final-tests.txt`, `review-tests.txt`: local verification records. Model files, volumes and raw operational data remain ignored by Git.

| Retained artifact | SHA-256 |
| --- | --- |
| Input freeze | `4fa9df616bbc3f9139422532661a3c70bd9111f0a660bb63d30c54f7b99dc74f` |
| Execution freeze | `34ef0bafff30e3ad23959c7a1586e7c48c2ac3fc0cc1a2435772d1fbb20b4449` |
| Exact source ZIP | `71c82f492fce94454fdbceee164cce5a412042ee9d1ece6c9a778cdb58dae3b7` |
| Committed corpus capture | `6c4cdedba50ed1422d5781c39e4658030e7b861b2b624572ac8267d4b86fe146` |

## Limits and next decision

Eight internally authored cases, a fixed arm order, one seed and two author-reviewed scorer exceptions do not establish broad reliability or stochastic robustness. These cases are now observed regressions. Requested-field semantics are prompted, not mathematically guaranteed by the JSON schema. The pilot does not cover long histories, multilingual requests, larger/more ambiguous evidence collections, enrichment or a full historical suite. T35's earlier assessment inconsistency remains an observed issue; the fresh missing-count case passed all arms without changing assessment.

The result supports a separately scoped confirmation/activation decision for the fixed experimental profile, not an automatic default change. Improve the next frozen scorer to account for original-heading assembly and upstream guards before running another authorized comparison. Preserve this run's original scoring and review rather than rewriting it.
