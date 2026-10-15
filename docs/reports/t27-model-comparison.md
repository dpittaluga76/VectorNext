# T27 — Gemma 4 12B versus offloaded 26B

Status: complete, 2026-10-15. **Keep 26B with 22 CPU expert layers as the default.** The 12B candidate is faster, but loses correct answers and source support. It remains an explicitly experimental option. Read the [machine-readable results](t27-model-comparison.json), [protocol](../../experiments/t27/protocol.md) and [reproduction guide](../../experiments/t27/README.md). T11/T14 are observed regression sets, not independent quality validation. No historical holdout was used.

## Decision and paired results

The new run used identical candidate API, processor and generator images for both arms; only the selected generation profile changed. Each corpus was ingested once with structural context. T14 admitted all eight documents; T11 admitted 18 documents / 658 chunks and retained both strict PDF extraction failures. Their six dependent questions remain in every 28-question denominator. Every block checked the same committed document revisions, chunks and vectors.

Each table row contains a complete paired block. Scores use the unchanged original labels and scorers. Times are end-to-end seconds; p95 uses nearest rank. Common-success reductions use only requests returning HTTP 200 in both arms, including valid abstentions. No failed measured request was retried.

| Suite / block | 26B exact | 12B exact | 26B median / p95 | 12B median / p95 | Median reduction | Common HTTP 200: count / reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T14 five cold | 13/16 | 10/16 | 29.508 / 38.953 | 11.586 / 19.829 | 60.7% | 13 / 60.2% |
| T14 two cold | 11/16 | 10/16 | 18.032 / 22.735 | 8.805 / 16.922 | 51.2% | 14 / 48.5% |
| T14 coverage cold | 12/16 | 12/16 | 16.336 / 31.297 | 9.251 / 17.812 | 43.4% | 15 / 43.6% |
| T14 coverage warm | 12/16 | 12/16 | 15.898 / 31.250 | 8.203 / 16.000 | 48.4% | 15 / 48.0% |
| T14 two warm | 11/16 | 10/16 | 17.844 / 22.188 | 8.399 / 16.531 | 52.9% | 14 / 50.0% |
| T14 five warm | 13/16 | 10/16 | 28.438 / 38.546 | 11.164 / 18.906 | 60.7% | 13 / 59.3% |
| T11 five cold | 16/28 | 14/28 | 20.860 / 38.609 | 9.860 / 15.532 | 52.7% | 23 / 64.2% |
| T11 two cold | 15/28 | 12/28 | 11.180 / 23.672 | 5.383 / 13.468 | 51.8% | 23 / 57.1% |
| T11 two warm | 15/28 | 12/28 | 10.640 / 23.203 | 4.751 / 12.485 | 55.4% | 23 / 58.3% |
| T11 five warm | 16/28 | 14/28 | 21.234 / 37.297 | 9.484 / 15.125 | 55.3% | 23 / 66.0% |

All four ranked-five speed gates passed the required 20% threshold, both overall and on common HTTP successes. The proposed 65–75% reduction was **not achieved for overall ranked-five medians**: measured reductions were 52.7–60.7%. One common-success subset reached 66.0%; that does not establish the broader proposed reduction.

The no-loss accuracy/source-support gate failed in eight paired blocks. Ranked-five 12B passed T14's historical floor of 8/16, but missed T11's 16/28 floor in both passes. No new falsely supported negative case appeared under the frozen scoring comparison. Existing incorrect/ambiguous outcomes remain in the results. Historical scores stay separate: T14 originally scored five/two/coverage 8/7/8 of 16; T11 originally scored five/two 16/15 of 28. These fresh results do not rewrite those runs.

## Case changes and retained failures

Cold and warm passes produced the same exact-score case changes:

| Strategy | Correct control cases lost by 12B | Cases gained by 12B |
| --- | --- | --- |
| T14 ranked five | `nepal_record`, `sumatra_stations`, `raw_null` | None |
| T14 ranked two | `nepal_record`, `sumatra_stations` | `three_mercury_ranges` |
| T14 coverage | None | None |
| T11 ranked five | `tohoku_json_magnitude_depth`, `raw_timezone_null`, `raw_tsunami_flag` | `galileo_orbits` |
| T11 ranked two | `tohoku_json_magnitude_depth`, `raw_timezone_null`, `raw_tsunami_flag` | None |

The lost cases returned rejected structured answers. For example, 12B emitted `properties.mag` and `properties.nst` instead of RFC 6901 pointers; one depth selection also used the wrong hierarchy (`properties.geometry.coordinates[2]`). Rust withheld those drafts. They were not normalized, retried, scored as successful or displayed as validated facts. Coverage's actual-record pointer constraints avoided these losses in T14; retrieval defaults were not changed to exploit that observed result.

Shared failures also remain visible: both models rejected T11's Maule and conflicting-instrument cases in all four blocks, and both rejected T14's three-launch case in coverage mode. Two unavailable PDFs remain ingestion failures. The [T14 alternate interpretation](t14-source-review.md) and [T11 source-review exceptions](t11-source-review.json) remain separate from strict scores; no gold label was changed.

## Hardware preflight

The official Google 12B QAT Q4_0 artifact was downloaded and verified against its pinned size and SHA-256. It loaded on the RTX 4060 under unchanged llama.cpp b11617 with 49/49 layers offloaded, 4,096-token context, one slot, batch 512/ubatch 128, temperature zero, seed 42 and reasoning disabled. Three synthetic constrained requests with 3,328 input tokens and a 768-token output allowance passed, including a generator restart. They returned a tiny fixed JSON value; these are capacity/functionality checks, not a throughput or answer-quality benchmark.

The complete preflight sampled 184 whole-device memory observations, peaking at 7,841 of 8,188 MiB (347 MiB sampled headroom). Background desktop applications remained untouched. Allocation logs show 6,637.69 MiB CUDA model buffers, 464 MiB KV buffers, 31.32 MiB CUDA compute buffers and CPU-mapped buffers. Layer placement logs and sampled device memory do not establish exact residency or exclude driver-managed paging on Windows. No OOM or backend failure occurred.

With the verified Linux weight cache, readiness took 9.09 seconds and restart 8.80 seconds. The three preflight HTTP calls took 4.09, 3.78 and 3.73 seconds including `docker exec` transport. Normal bind-mounted 26B restoration took 149.39 seconds, including checksum/loading time; this is not an inference-speed comparison. The normal library matched its captured bytes before/after restoration.

Measured query-block resources:

| Profile | GPU samples | Whole-device peak | Generator cgroup RAM peak | Processor / API cgroup RAM peaks |
| --- | ---: | ---: | ---: | ---: |
| 26B offload22 | 1,958 | 6,706 MiB | 19.805 GiB | 0.772 / 0.057 GiB |
| 12B | 912 | 7,864 MiB | 11.816 GiB | 0.790 / 0.058 GiB |

The candidate's measured-query peak leaves **324 MiB sampled GPU headroom**. Cgroup RAM includes file caches and is not process RSS; these query samples do not measure PDF ingestion's peak. No OOM/backend failure occurred in the paired run. Only this 8 GB RTX 4060 was tested; 12 GB cards and the optional full-GPU 26B profile on 16–24 GB cards remain unverified.

The 416-request run spanned **105 minutes 7 seconds**, from 19:17:14 to 21:02:21 UTC, including ingestion, process/model switches, warmups and capture work. Loading and synthetic warmup were excluded from per-request latency. Across all strategies, median answer-RPC time was 17.12 seconds for 26B and 8.02 seconds for 12B; detailed per-block stage, token, startup and resource records accompany the result JSON. These aggregate RPC times are descriptive, not additional promotion gates.

Preserved harness failures: the first attempt exhausted Docker's automatic network address pool before loading any candidate; the second loaded 12B but timed out reaching a host port on an internal-only network. Explicit non-overlapping test subnets and container-loopback preflight transport resolved these. A shell-quoted cache-copy command failed before copying; a checked-in script now verifies copies. The separate operational amendments retain all attempts without changing model settings or scoring.

## Application and engineering verification

- 158 top-level Rust checks, formatting and all-target Clippy passed. Existing multipart dependency future-compatibility notices remain.
- 68 Python worker/profile/planner/scheduler/processor/workflow/reliability checks passed; four new protocol/scoring checks passed.
- 71 frozen HTTP cases, five browser API boundary checks and two OpenAPI checks passed. Five component tests, ten offline workspace scenarios and two real-adapter/docs browser scenarios passed.
- Three resolved Compose profiles matched their validated model commands and processor/generator selections. Six launcher contracts passed under both current PowerShell and Windows PowerShell: offline Start, saved selection, selected setup, rebuild, non-destructive Stop and switching back. The first launcher harness assertion failure is retained; it was corrected without changing application behavior.
- Model-download and standalone-ingestion images built. Offline checks verified the packaged 12B lock and initialized the real CPU worker with the selected 12B generation identity. The standalone tool now uses `vectornext-ingestion:t27`, preserving its prior image.
- T27's API executable and bundled UI index are byte-identical to the tested T26 artifacts: API `489808457d46ca2de6ef6eb25a09a244cf574e4387f85a048d0dd27c2d9c3d9e`; UI index `36720db1ebf80a3188ed647502155b312516ac0058a7d2ef988fe0f17609f258`.
- Historical T11/T14 data/scorer checks passed. Their execution freezes and recorded scores were not rewritten.

The separate 12B replay passed **12/12 final T26 planner cases, 5/5 observed regressions and 8/8 source-backed cases**, using their original fixtures/scorers with no retries or prompt changes. The live browser scenario passed in 38.25 seconds: automatic count, real follow-up history, scope reset, source selection, exact `9007199254740995.00000000000009` / `0` / `null`, IndexedDB reload and diagnostic export. Its screenshot was reviewed. These source/browser checks retain T26's opt-in `facet_coverage_v1`; they do not establish default ranked retrieval correctness.

Live wrong-alias rejection passed. During a stopped-generator outage, readiness and answering returned 503 while library browsing returned 200. Restart restored readiness in 9.78 seconds. Unit checks covered missing/corrupt artifacts, placement/cache identity separation and refusing a saved job's mismatched generator. The previous normal generator then restored in 132.02 seconds; all normal capabilities were ready and the library remained byte-identical. T27 services are stopped; their data, caches, logs and images remain.

The unchanged application drivers used `experiments.t26.planner_check` with `cases-v3.json` / `input-freeze-v3.json`, then `regressions.json` / `regression-freeze.json`; `experiments.t26.live_check` used `live-v3.json`, `tests/fixtures/planning-v3`, `input-freeze-v3.json` and `--version field-planning-v3`. See [T26 reproduction commands](../../experiments/t26/README.md) for the original drivers. T27 selected 12B with `compose.app.models.yaml` plus `compose.t27.yaml`, a fresh `/storage/application-v1` database and `/cache/application-v1/12b` cache. The client ran on `vectornext-t27_local`, mounting this repository read-only at `/checks` and `data/t27` at `/out`; each output directory was new. The browser command was:

```sh
docker run --name vectornext-t27-browser --network container:vectornext-t27-vectornext-1 -e VECTORNEXT_PLANNING_URL=http://localhost:8088 vectornext-ui-test:t26 npm run e2e -- planning-live.spec.ts
```

Keep the normal generator paused only while the isolated GPU checks run, verify it is idle before stopping it, and restore it in cleanup. The retained `data/t27/application_check.py` records the exact orchestration; captures/results are under `data/t27/application-v1/`. Use fresh names/paths for any repeat.

## Reproduction, profiles and rollback

The [setup and execution commands](../../experiments/t27/README.md) use fresh names, isolated storage, one GPU generator and explicit checksum-verified downloads. The official [12B artifact](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf/tree/29d097773436b69ff9feafd636ab4cf873786537) is pinned in [its new lock](../../experiments/t27/models.12b.lock.json): 6,975,879,296 bytes, SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`. Historical E2B/26B locks and embedding/reranker identities are unchanged. No projector was downloaded.

The normal default remains `26b-offload22`. Explicit experimental application selection uses `deployment/VectorNext.ps1 -Action Setup -ModelProfile 12b`; subsequent ordinary Start reuses that saved selection without building or downloading. Restore the established profile with `deployment/VectorNext.ps1 -Action Start -ModelProfile 26b-offload22`. Direct Compose selection applies `compose.app.models.yaml` after `compose.app.yaml`, with `VECTORNEXT_GENERATOR_PROFILE` set consistently. `26b-gpu` is the unverified larger-card option. The historical T02 base model-tools configuration remains available unchanged; separate overrides select 12B or full-GPU 26B.

The shared catalog controls artifact, alias and placement. The launcher verifies the artifact and exact command; the scheduler accepts only its selected alias; worker audits and generated-context caches include the selected model/runtime identity. The legacy offload22 identity remains byte-for-byte compatible with saved jobs. Unfinished enrichment requiring another generator must be explicitly retried with its matching profile; its saved policy is never reassigned.

No promotion was activated. The normal app retains its previous API/processor `:t26` and generator `:t18` containers; prepared repository Compose images are `:t27` with the same 26B default for the next Start/Rebuild. Prior images and all model files remain available. No storage schema changed. The conditional promotion/storage-copy rollout was not needed because the quality gate failed.

Retained local artifacts include `data/t27/paired-v1/`, all earlier preflight/cache/launcher attempts, and the dedicated storage/cache/model volumes. The exact 148-file execution snapshot is `data/t27/paired-v1/source.zip`, SHA-256 `b93468c842f41649def7838ca36df66ea2d0181e889aa36ec79e821e957c5ce7`; every entry was checked against the execution freeze. Preserve its original line endings. The full pre-T27 source archive is `backups/t26-source-before-t27.zip`, SHA-256 `37ba46b6b378df1a39e485edcbf3e8f3a59fbb1487a34c44a2dbbf7771a84888`. Original T11/T14 manifests, scores, sources and holdout remain unchanged.

## Interpretation limits

- T11/T14 use explicit fields. Their timing excludes automatic field planning; separate T26/browser checks test that functionality, not paired ordinary-browser latency.
- These are observed regression sets, with repeated questions across strategies/passes. They are not 416 independent questions or proof of broad semantic quality.
- Cold/warm describe isolated persisted application caches. OS and backend internal caches were not globally flushed. Both arms used the same verified Linux model-volume arrangement; normal Windows bind-mounted startup was measured separately.
- Successful responses retain model audits, usage and stage timings. Rejected envelopes omit those fields; their original drafts/evidence, per-request RPC/scheduler deltas and backend token/timing logs are retained. Token aggregates cover available successful-response audits only. Missing audit fields are not counted as zero.
- A future JSON-pointer/output-contract improvement needs a separately scoped test with fresh validation data. This experiment made no prompt repair, retrieval change, model substitution, speculative-decoding change or runtime upgrade.

Raw logs, source snapshots, local library captures and runtime data remain under ignored `data/t27/`; weights remain excluded from Git. The pre-T27 source archive and exact model pins are recorded in the protocol. Normal services are restored after each isolated run; the test volumes and failed attempts are retained.
