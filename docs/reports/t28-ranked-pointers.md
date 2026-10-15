# T28 — Ranked JSON pointer constraints and 12B promotion

Completed 2026-10-15. **Promote the existing `12b` profile to default.** All 208 evaluation requests completed and every declared evaluation, fresh-fixture, application and hardware gate passed. The normal app now runs the `:t28-12b` release with its library unchanged. A separate activation check retained a known numeric-range rejection; it is described below, not counted as a successful answer.

Read the [machine-readable results](t28-ranked-pointers.json), [frozen protocol](../../experiments/t28/protocol.md), [original execution instructions](../../experiments/t28/README.md) and [answer contract](../answers.md#ranked-json-pointer-constraints-t28). T11/T14 are observed regression sets. This is a sequential comparison against retained T27 controls, not a new paired 26B run or independent quality assessment. Original sources, labels, scorers, execution freezes, captures and the unused six-question holdout remain unchanged.

## What changed

Rust's `answers::add_evidence` now enables the existing pointer constraints whenever a JSON record enters the proposed evidence. It does so **before token counting**, restoring the previous flag if the added evidence exceeds the budget. The existing Python worker builds its catalog and evidence-specific schema from admitted records, including admitted neighbors. Ranked two and five now share these validity rules with coverage modes. Pure-prose ranked messages and coverage behavior stay unchanged.

Each JSON proof binds an evidence ID to that record's existing RFC 6901 paths matching the requested type and any explicit caller pointer. The model still emits a null value placeholder; Rust reads the exact original value and validates the proof. Escaped keys, arrays, raw null, zero, absent fields and exact numeric syntax retain their existing distinctions. No extra model call, retry, pointer repair, relaxed validation or second grammar generator was added. Catalog limits remain 256 scalar/null leaves per record, depth 64, 2,048 bytes per pointer and 32,768 catalog bytes; exceeding them fails explicitly.

Constraints exclude invalid paths from accepted output. They do not prove that a valid path answers the question or guarantee correct abstention. Catalog tokens and grammar work have costs. The experiment measures those costs and preserves semantic failures.

## Complete regression results

Each score uses the original strict scorer. Every block retains its entire denominator, including missing-source questions and rejected responses. Times are end-to-end seconds; p95 is nearest rank. Common-success reductions compare requests returning HTTP 200 in both runs, including valid abstentions.

| Suite / block | T27 26B exact | T27 12B exact | T28 12B exact | T28 median / p95 | Median reduction vs 26B | Common HTTP 200 reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T14 five cold | 13/16 | 10/16 | **13/16** | 11.164 / 19.344 | 62.2% | 62.2% |
| T14 two cold | 11/16 | 10/16 | **12/16** | 9.368 / 16.954 | 48.0% | 48.0% |
| T14 coverage cold | 12/16 | 12/16 | **12/16** | 8.289 / 16.359 | 49.3% | 49.6% |
| T14 coverage warm | 12/16 | 12/16 | **12/16** | 7.688 / 15.203 | 51.6% | 51.8% |
| T14 two warm | 11/16 | 10/16 | **12/16** | 8.609 / 15.438 | 51.8% | 51.8% |
| T14 five warm | 13/16 | 10/16 | **13/16** | 10.570 / 17.703 | 62.8% | 62.8% |
| T11 five cold | 16/28 | 14/28 | **18/28** | 10.351 / 16.593 | 50.4% | 52.8% |
| T11 two cold | 15/28 | 12/28 | **16/28** | 5.187 / 14.234 | 53.6% | 53.7% |
| T11 two warm | 15/28 | 12/28 | **16/28** | 4.773 / 13.469 | 55.1% | 55.6% |
| T11 five warm | 16/28 | 14/28 | **18/28** | 9.992 / 15.625 | 52.9% | 57.9% |

No previously correct case or its validated source support was lost against **either T27 arm**, across any strategy/pass. Correct negative outcomes were preserved, with no new falsely supported negative under the frozen scoring. Ranked five meets T28's 13/16 and 16/28 targets and all four minimum 20% latency gates, both overall and on common HTTP successes. T14's original historical floor was 8/16; 13/16 is the fresh T27 control, not a rewritten historical score.

The recovered T14 cases are `nepal_record`, `sumatra_stations` and `raw_null`; T11 recovers `tohoku_json_magnitude_depth`, `raw_timezone_null` and `raw_tsunami_flag`. Maule also becomes correct where both T27 models rejected it. T14 ranked two retains 12B's earlier `three_mercury_ranges` gain. The JSON report publishes every case's score, support, response hash, error and latency, including unchanged failures.

There were **202 HTTP 200 and six HTTP 400 responses**. The retained rejections are T14 `three_launches` in both coverage passes and T11 `conflicting_instruments` in all four blocks. T11 still has two strict PDF admission failures and six dependent questions in every 28-question denominator. Historical source-review exceptions remain separate from strict scores. HTTP success does not mean factual correctness.

Ranked-five medians improve **50.4–62.8%** over retained 26B. This is not a uniform 55–60% improvement and does not establish the proposed 65–75% reduction. Against T27's already-faster 12B, T11 ranked-five medians increase from 9.860/9.484 to 10.351/9.992 seconds, approximately **5.0/5.4%**. The change is not free. T14 ranked-five medians decrease; all strategies and p95 are reported without selecting only favorable blocks.

## Corpus, execution and evidence accounting

Verified read-only copies of T27's committed corpora preserve document revisions, chunks and vectors. T14 admitted all eight sources; T11 retained 18 admitted sources / 658 chunks plus its two PDF failures. Snapshot identity was checked before each block. T14 ran five/cold → two/cold → coverage/cold → coverage/warm → two/warm → five/warm (96 requests), then T11 five/cold → two/cold → two/warm → five/warm (112). Question order stayed fixed. Each strategy/corpus has separate caches; API/processor processes were recreated between blocks. No measured failure was retried.

The run lasted **32 minutes 19 seconds**, from its execution freeze at 21:57:18 UTC to completion at 22:29:37 UTC, including startup, synthetic warmup and process/capture overhead. Model loading/warmup is excluded from request latency. Only one GPU model ran at a time, with the normal generator paused and browsing available. Unrelated workloads were untouched. Normal 26B capabilities and the unchanged library were restored before promotion was decided.

Admitted evidence keys match both retained T27 arms in **206/208 requests**. The exceptions are T11's Tohoku ranked-five cold/warm requests: the same three JSON bundles remain, while a neighboring Deep Impact prose bundle changes from chunk `c18` to `c16`. Catalog token accounting prevents that neighbor expansion; the omission is recorded. Total evidence bundles remain four; prompt size changes from 3,050 to 3,135 tokens. All 96 T14 evidence-key lists match. Therefore the Tohoku result cannot be attributed solely to decoding with identical evidence. Some historical rejected reports contain only keys/location/preview diagnostics, so complete text equality is not assumed for them.

Successful reports retain model/schema audits, usage and stage timings. Rejected envelopes omit some audit fields; raw drafts/evidence, processor/scheduler deltas and backend logs remain available. Missing token data is not treated as zero. Cold/warm refers to persisted application caches, not globally flushed OS/backend caches. These are 44 reused questions across strategies/passes, not 208 independent questions. Explicit-field suite timings exclude automatic planning.

## Hardware and application verification

The pinned official 12B QAT Q4_0 artifact and llama.cpp b11617 runtime are unchanged from T27. Full placement logged 49/49 layers; context stayed 4,096, one slot, batch 512/ubatch 128, temperature zero, seed 42 and reasoning disabled. Three synthetic constrained requests with 3,328 input tokens and a 768-token output allowance passed, including restart. They produced tiny fixed outputs and test capacity/functionality, not long-output throughput.

The Linux model-volume preflight reached readiness in 38.34 seconds and restarted in **7.48 seconds**. Query blocks captured 928 GPU samples, peaking at **7,880/8,188 MiB**, leaving **308 MiB sampled headroom**. Generator cgroup memory peaked at **10.192 GiB**, processor at 0.781 GiB and API at 0.062 GiB. Whole-device GPU measurements include desktop workloads; cgroup memory includes file cache and is not process RSS. No OOM or backend failure was observed. Windows shared/dedicated adapter counters were captured, but **WDDM page-outs remain unverified**. This is narrow headroom on one tested 8 GB RTX 4060; 12 GB cards and full-GPU 26B on 16–24 GB cards remain unverified.

Verification completed:

- **160 top-level Rust tests**, formatting and all-target Clippy. A subprocess helper adds one line to summed test output; it is not an extra top-level test. Existing multipart dependency future-compatibility notices remain.
- **81 Python checks**, covering worker/profile/schema/scheduler/processor/reporting and T28 contracts. After default selection, 35 focused release tests passed, including both directions of saved-generator rejection before HTTP and unchanged embedding/cache identity separation.
- **71 frozen HTTP cases**, five browser API boundaries, two OpenAPI checks, five components, ten offline workspace scenarios and two real-adapter/docs browser scenarios.
- Original T26 **12/12 planner**, **8/8 source-backed**, **5/5 observed-regression** cases, with unchanged fixtures/scorers. Existing facet browser follow-up/exact-value/export passed.
- Separately frozen T28 **8/8 fixed-evidence and 8/8 real-ingestion ranked source checks**, covering paths/types, missing evidence, ambiguity and exact values. The ranked live browser passed automatic planning, follow-up, scope reset, citations, exact decimal `9007199254740997.00000000000003`, zero/null, IndexedDB reload and diagnostic export. Screenshot reviewed.
- Wrong model alias rejection, stopped-generator unavailability with browsing still available, restart and restoration of 26B. Offline artifact verification, packaged worker initialization, all three profile configurations and **eight launcher contracts under both PowerShell variants** passed. Start performs no builds/downloads; Stop retains data.

Preserved engineering failures include an initial synthetic test vector missing normalization, a redundant cast found by Clippy, a Python test-module typo, a docs test started without its required processor stub, a configuration-inspection helper omitting Compose profiles, and a profile-switch test that assumed 26B was always the default. Corrected engineering checks passed; no measured answer, model setting or frozen label was changed. The fresh harness's `DocumentIds` wire spelling was corrected before any candidate inference; original scorer/freeze bytes remain retained.

## Activation and remaining limitation

The measured `:t28` images were preserved. Release images use **`:t28-12b`**; the shared catalog, app Compose, model tools, standalone ingestion and Windows default now select `12b`. Existing explicit saved selections remain respected. `26b-offload22` keeps its old artifact/runtime identity; `26b-gpu` remains an optional, unverified larger-card placement. No public API or storage format changed. Saved jobs reject incompatible generation identities instead of silently switching models. Both models still reject unsupported aggregation.

Before activation, every normal job was committed. The normal services were stopped and all six storage files copied to `backups/vectornext-before-t28-default12.zip`, with ZIP-entry hashes verified against the unchanged source. Archive SHA-256: `5b02cf356603a9985b9977fededc35044179f6cc0b7a44cf7974a6c3bcca50f1`. The real Windows Start action activated the selected release and reached all-capability readiness in **67.33 seconds**. This includes the normal Windows bind-mounted loading/checking path and is not comparable to a bare Linux-volume restart. Library metadata remained byte-identical.

A normal-library browser question requesting the start year of a printed year range was rejected by the existing conservative numeric validator, even though the draft selected the correct endpoint. No answer value was shown as validated; that request and its diagnostics are retained privately. T28 does not change range interpretation. A distinct text-fact question returned a supported, source-linked answer with the correct 12B artifact/runtime audit and ranked 30/20/5 settings. The browser harness initially looked for a server alias in the artifact audit; after correcting that assertion, it replayed the **same captured successful response**, without another inference, to verify citation display and persisted history. Both attempts remain recorded. Private document names, contents and screenshots are excluded from this report and Git.

The range limitation prevents a general claim that ordinary questions always succeed. It does not change the frozen 208-request scores or the predeclared promotion gates. Future numeric-range and ambiguity work needs separate scope and fresh cases, rather than relaxing T28's proof checks.

## Reproduction, profiles and rollback

The post-evaluation default/configuration edits intentionally differ from the measured execution freeze. **Do not overwrite that freeze or run the current release as if it were the frozen candidate.** Restore the retained source bytes and image IDs before reproducing the original experiment, then follow the [original reproduction guide](../../experiments/t28/README.md). Use new output/run names and isolated volumes; never overwrite historical captures. The original guide is itself frozen.

| Retained artifact | SHA-256 |
| --- | --- |
| Full pre-T28 tree: `backups/t27-source-before-t28.zip` | `ab55ee2d280cd58791d9711b2b274cb21b9846918b55c7bea0ad64f335a55de8` |
| Exact 209-file execution snapshot: `data/t28/replay-v1/source.zip` | `6123a9499d7e07af41314040161f280a794a7c8fd7387fc399bacf06a5efda26` |
| Full pre-promotion tree: `backups/t28-source-before-default12.zip` | `e5d7b53f09b1ae21523445d7e16cc4b6757f12f752c65e2a90ca425a3f8e3084` |

The execution ZIP's complete file set and individual hashes were verified against its freeze before promotion. Measured images remain `vectornext-app:t28` (`e999c1fc…`), `vectornext-app-processor:t28` (`6d9fd702…`) and `vectornext-app-llm:t28` (`bcf3f8ea…`); full IDs, source identities, startup records and scoring rules are in the JSON report. Processor/generator matched T27's retained images. Models, corpora, caches, interrupted engineering attempts and raw responses remain under ignored local storage. T28 test services are stopped; the normal three-service app is running on localhost:8088.

Final packaging checks confirm that the release API executable and bundled UI index are byte-identical to the measured candidate: SHA-256 `9a18bc9ff921a1f38d74ef7a1b521b268229935755ed37bb8473d2be41259f96` and `36720db1ebf80a3188ed647502155b312516ac0058a7d2ef988fe0f17609f258`, respectively. Packaged worker production files match the release source. All 209 execution-archive entries, the fresh input freeze, unchanged published gate calculations and 333 local documentation links passed final checks. The shared default catalog is intentionally different from the measured candidate; its selected 12B model/runtime settings are unchanged.

Publication verification caught Git's default line-ending normalization changing the eight fresh input hashes. `.gitattributes` now preserves the T28 experiment and browser fixture bytes; every frozen input hash was verified directly from the staged Git tree. The manifest and evaluated source bytes were not rewritten. This packaging correction does not change application behavior or the frozen scores.

For a fresh installation or explicit migration from a saved 26B selection:

```powershell
powershell -File deployment/VectorNext.ps1 -Action Setup -ModelProfile 12b
```

When release images and verified model files are already installed, use `-Action Start -ModelProfile 12b`. Ordinary subsequent Start reuses the saved selection offline. To choose the retained 26B model with the new pointer contract:

```powershell
powershell -File deployment/VectorNext.ps1 -Action Setup -ModelProfile 26b-offload22
# After its files/images are installed, switching is offline:
powershell -File deployment/VectorNext.ps1 -Action Start -ModelProfile 26b-offload22
```

Use `26b-gpu` only as an explicitly selected larger-card configuration; it was not tested here. The corresponding model-tool overrides are `compose.models.26b.yaml` (offload22) and `compose.models.26b-gpu.yaml` (full GPU). Direct application selection is:

```powershell
$env:VECTORNEXT_GENERATOR_PROFILE = '26b-offload22'
docker compose -f compose.app.yaml -f compose.app.models.yaml up -d --no-build --pull never
```

Set the variable to `12b` to return. Resolve unfinished generated-context jobs with their saved profile first; never edit their saved policy. Before a whole-code/storage rollback, stop the normal project, restore the retained archive into a **new** storage volume, and use its matching prior source/images. Keep current storage intact; a pre-activation copy does not contain later documents. Prior normal images and both model files were retained. This task does not add automatic Git publication or storage reclamation.
