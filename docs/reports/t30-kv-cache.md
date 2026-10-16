# T30 — Q8 KV cache experiment

Completed 2026-10-16 (UTC). **Retain f16 as the default.** Q8 reduced GPU KV allocation from 464 to 246.5 MiB, saving **217.5 MiB**, and passed full-context/repetition/restart preflight. However, the frozen 208-request replay lost the correct `unknown_count` abstention in both ranked-five and ranked-two passes. The `12b-kv-q8` profile remains experimental; it is not a Windows-launcher/default-profile change.

| Suite / block | f16 correct | Q8 correct | f16 median | Q8 median | Reduction | Q8 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| t14/five-cold | 13/16 | 12/16 | 11.164 s | 9.587 s | 14.1% | 18.140 s |
| t14/two-cold | 12/16 | 11/16 | 9.368 s | 7.859 s | 16.1% | 14.578 s |
| t14/coverage-cold | 12/16 | 12/16 | 8.289 s | 7.438 s | 10.3% | 14.703 s |
| t14/coverage-warm | 12/16 | 12/16 | 7.688 s | 6.828 s | 11.2% | 13.468 s |
| t14/two-warm | 12/16 | 11/16 | 8.609 s | 7.422 s | 13.8% | 14.125 s |
| t14/five-warm | 13/16 | 12/16 | 10.570 s | 9.453 s | 10.6% | 17.656 s |
| t11/five-cold | 18/28 | 18/28 | 10.351 s | 8.961 s | 13.4% | 15.266 s |
| t11/two-cold | 16/28 | 16/28 | 5.187 s | 4.820 s | 7.1% | 11.906 s |
| t11/two-warm | 16/28 | 16/28 | 4.773 s | 4.266 s | 10.6% | 11.140 s |
| t11/five-warm | 18/28 | 18/28 | 9.992 s | 8.539 s | 14.5% | 14.860 s |

All other blocks preserved per-case correctness. No previously validated source support was lost and no newly falsely supported negative appeared under frozen scoring. All 208 outcomes remain counted: 202 HTTP 200 responses and six rejections, with original PDF admission failures retained. Full case changes, common-success latency and source-support checks are in the [machine-readable results](t30-kv-cache.json).

All 202 comparable successful responses had identical assembled evidence; no single-call audit appeared. Assessment/extraction runtime audits included explicit q8_0 K/V identity. Peak sampled whole-device GPU use was 7635 / 8,188 MiB (553 MiB headroom). The 217.5 MiB KV saving is confirmed by allocation logs; whole-device peak differences include desktop/cross-run variation and do not prove absent WDDM page-outs.

Preflight: all 49 layers offloaded, 3,328 input-token constrained requests repeated three times including restart; startup 15.92 s, restart 7.39 s using the retained Linux weight volume. No OOM/backend failure was observed. All settings/weights/runtime binary stayed fixed apart from cache types and the validating alias/runtime identity. The two-call path and retained API exclude both the single-call experiment and new range validator.

Verification: 25 worker/profile/schema checks passed. Old identities and commands remain byte-compatible; partial/unknown KV types, wrong aliases and mismatched commands fail closed. Preflight and replay restored the normal generator and byte-identical library. The Q8 services are stopped; all captures, caches and volumes remain. Production remains 12B/f16/two-call. Historical scores and holdout are untouched.

This is a sequential comparison against retained T28, not independent quality or a fresh paired timing control. Do not attribute the full 10.6–14.5% ranked-five latency reduction to KV quantization alone. Use [reproduction commands](../../experiments/t30/README.md) and [the frozen protocol](../../experiments/t30/protocol.md). The exact source/image/input identities and source archive remain under `data/t30/replay-v1`; later source edits intentionally differ from that freeze.
