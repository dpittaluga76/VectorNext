# T29 — Single-call assessment/extraction experiment

Completed 2026-10-16 (UTC). **Do not adopt globally:** all 208 requests completed, but coverage mode lost two correct abstention classifications in each pass. The two-call production default remains unchanged. Ranked five preserved its correct cases/source support in both suites and was 35.6–40.7% faster in median end-to-end latency. This is a sequential comparison against retained T28 captures, not a fresh paired timing trial or independent quality evaluation.

| Suite / block | Baseline correct | Single-call correct | Baseline median | Single-call median | Reduction | Single-call p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| t14/five-cold | 13/16 | 13/16 | 11.164 s | 7.031 s | 37.0% | 13.453 s |
| t14/two-cold | 12/16 | 12/16 | 9.368 s | 5.469 s | 41.6% | 9.562 s |
| t14/coverage-cold | 12/16 | 10/16 | 8.289 s | 5.929 s | 28.5% | 10.766 s |
| t14/coverage-warm | 12/16 | 10/16 | 7.688 s | 4.758 s | 38.1% | 9.141 s |
| t14/two-warm | 12/16 | 12/16 | 8.609 s | 5.344 s | 37.9% | 8.672 s |
| t14/five-warm | 13/16 | 13/16 | 10.570 s | 6.633 s | 37.2% | 12.750 s |
| t11/five-cold | 18/28 | 18/28 | 10.351 s | 6.664 s | 35.6% | 11.172 s |
| t11/two-cold | 16/28 | 16/28 | 5.187 s | 4.735 s | 8.7% | 9.766 s |
| t11/two-warm | 16/28 | 16/28 | 4.773 s | 4.211 s | 11.8% | 9.984 s |
| t11/five-warm | 18/28 | 18/28 | 9.992 s | 5.922 s | 40.7% | 11.172 s |

The regressions are `unknown_count` and `absent_fact` in both coverage passes. No previously validated source support was lost and no new falsely supported negative appeared under the frozen scorer. All other blocks preserved per-case correctness. Failures remain in denominators: 202 HTTP 200 responses, six rejections, and the original two unavailable PDFs/six dependent questions. Common-HTTP-success latency, every changed case and source-support checks are in the [machine-readable results](t29-single-call.json).

All 202 comparable successful responses retained identical assembled evidence. 202 returned single-call audits; observed cached-token counts were [0]. Peak sampled whole-device GPU use was 7810 MiB. Resource sampling does not establish WDDM residency.

Only the assessment generation was removed. Extraction prompt/schema, pointer constraints, temperature/seed, false prompt caching, context/output budgets and evidence admission stayed unchanged. API and generator image IDs exactly matched T28; the new numeric validator was deliberately excluded. Input/source/image/capture freezes and `source.zip` are retained in `data/t29/replay-v1`; interrupted/failed responses were not retried. Corpus copies preserved exact revisions/vectors and old volumes.

Verification: 17 focused worker/schema tests passed, including one-call count, unchanged budget accounting, exact pointer schemas, abstentions, invalid modes and no retry of malformed output. Prerequisites passed 163 Rust checks, formatting/Clippy and README link/table preservation. The normal generator was restored and its library matched byte-for-byte. Test services are stopped; data/caches remain. No production activation, historical score rewrite or holdout use.

Reproduce with [the commands](../../experiments/t29/README.md) and [pre-inference protocol](../../experiments/t29/protocol.md). Later task edits intentionally differ from this execution freeze; use its archived tree and retained image IDs. A ranked-only follow-up could be considered separately, but these results do not authorize changing default classification behavior.
