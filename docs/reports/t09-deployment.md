# T09 integrated local deployment

Date: 2026-10-14. Design reference: architecture sections 2 and 7–9. **T09 acceptance passed** on the existing Windows/WSL Docker host with an RTX 4060 8 GB. Exact image/model/source identities, responses, manifests, timings and limitations are in [the JSON report](t09-deployment.json). Setup and backup commands are in the [README](../../README.md); API and operational details are in [deployment.md](../deployment.md).

## What is implemented

`compose.app.yaml` runs three services: the sole Rust database owner/API, a CPU processor without a database mount, and the pinned Gemma 4 26B A4B QAT Q4_0 runtime with T08's generation-priority wrapper. Only the generation service requests GPU access. The API alone publishes localhost port 8088; processor and generation stay on an internal Docker network. The API also has an ingress bridge to make localhost publishing work on Docker Desktop. Normal inference requires no external calls.

The Rust owner takes short locks for snapshots, durable stage acceptance and atomic publication. Slow deterministic parsing/chunking, CPU model requests and GPU inference occur outside that lock. Independent interactive/background CPU lanes admit bounded work, and the PDF subprocess shares background admission. Separate Python environments preserve the existing PDF/model dependency identities. The small client supports ingestion, inspection, retry, keyword/hybrid search and typed answers. Exact JSON numeric response bytes are preserved through the client.

The offline admin command checkpoints under the sole writer lock and exports all durable state with a complete size/SHA-256 manifest. Restoration verifies the export in a new staging directory before atomic publication and never overwrites an existing destination. Models and disposable caches are excluded. No external vector database, MinIO, Redis, web UI or new answer-quality tuning was introduced.

## Verification

| Check | Result |
| --- | --- |
| Rust all-target suite | 89 passed; two ignored functions are invoked subprocess helpers |
| Six new deployment/backup checks on Docker disk volume | 6 passed |
| Existing Python worker/answer/scheduler suite | 18 passed with local CPU weights and no network |
| New CPU service transport/admission suite | 4 passed, including deadline kill/restart, independent lanes and invalid/oversized frames |
| Formatting, Linux Clippy with warnings denied, Compose configuration | Passed |
| Fresh application data/cache volumes | Five source fixtures, 28 chunks, generation 5 |
| GPU answers through the shared API | Correct fictional Pele fields/template and scanned J2 torque |
| Generation outage and full processor/model outage | Explicit 503s for dependent operations; keyword/source reads remain usable |
| Failed job, rebuild/recreation and interrupted-stage restart | Progress retained; resumed once to generation 6 |
| Offline export/restore | 17 files, 749,829 payload bytes; identical document/job/receipt inspection bytes |
| Live export / existing restore destination | Both refused |
| Write after restore | New exact-number JSON document committed at generation 7 |

The fresh-volume seed ingested the existing fictional TXT, array JSON, nested JSON with `/matches`, native equipment PDF and scanned note PDF under structural context. Repeating each exact upload kept its publication receipt. Timings including upload preparation and 0.5-second job polling were approximately 0.55, 0.53, 0.55, 14.38 and 11.17 seconds respectively. These are one warm-runtime smoke pass, not a throughput benchmark.

Actual local GPU calls returned:

- `Match year 1954, Pele goals: 3, rival: Argentina` from the synthetic TXT source, in 24.25 seconds through the API.
- Torque `6`, unit `N m`, with scanned PDF evidence, in 14.86 seconds.

The runtime logged CUDA layer placement while retaining 22 CPU expert layers, matching the pinned model profile. Docker inspection confirmed that only `llm` had GPU device requests. One loaded-idle whole-device observation was 6,182 MiB; this is not a peak-memory measurement. The API binary was identical across the initial live drill and final image rebuild; the last rebuild added the final verifier/client packaging. The final image reopened restored generation 7 successfully.

## Outage and recovery drill

With Gemma stopped, exact JSON lookup returned goals `0` and the original assists `null`; keyword search worked; a passage answer failed explicitly. A new generated-context job failed durably at `Chunked`, leaving generation 5 visible. Rebuilt API/processor images were recreated against the same mounts; document summaries, complete revisions and the saved failed job remained unchanged. The failure required an explicit retry after generation recovered.

During resumed background work, ten keyword queries saw the previous generation and completed within the host timer's roughly 15–16 ms resolution. Zero recorded samples mean below timer resolution, not zero cost. The API and CPU service were then stopped during the active stage. After CPU warming and owner restart, the unfinished job resumed automatically, retained its single earlier failure, and published generation 6 exactly once. An identical upload returned the original receipt.

With both processor and generation stopped later, readiness returned 503 and hybrid search failed explicitly. Source-only lookup still returned the exact decimal `9007199254740993.00000000000001`; keyword reads and inspection remained available. The client preserved the same literal after restoration. Invalid uploads, changed input under an existing job ID, missing client headers and browser Origin requests were rejected without changing generation 7.

## Backup and retained state

Attempting export while the API owned the database returned the writer-lock error. After stopping that owner, export and restoration completed without model/network dependencies. Complete `inspect` output before export and after restore was byte-identical, including vectors, source values, processing metadata, jobs and retry receipts. The manifest and inspection hashes are in the JSON report. Restoring into the existing destination was refused. The restored copy could search, repeat a committed job receipt without republishing, and commit a new exact-number JSON record.

The Rust checks additionally cover corrupt/missing/extra/traversal/symlink export entries, an unfinished PDF's canonical artifact surviving backup/restart, stale stage-failure rejection, and immutable old indexes while slow model work proceeds. They do not certify physical power-loss behavior or adversarially modified manifests as authentic.

All T09 services were stopped after verification. Retained artifacts:

- `vectornext-t09_data`: `/storage/db` at generation 6 and `/storage/restored` at generation 7 (seven documents, 31 chunks).
- `vectornext-t09_cache`, the existing ignored host `models/`, and host backup `backups/20261014-t09`.
- Raw captures under ignored `data/t09/20261014-t09` and the compact committed report.

Existing T07 volumes were not changed. To reopen the final restored test copy, set `VECTORNEXT_DATA=/storage/restored`, then run `docker compose -f compose.app.yaml -p vectornext-t09 up -d`. The README's default project creates a separate application volume.

## Corrections and limits

Initial Docker inspection showed a configured host port with no published binding when the API used only an internal network. Adding the API ingress bridge fixed host access; processor/model isolation stayed intact. An initial Python regression invocation omitted its model mount and failed setup; all 18 checks passed with the required read-only local weights. Review also caught lossy client-side JSON reserialization; CLI output now prints exact response bytes and the decimal check passes.

This is a local single-user API with no authentication or complete slow-client connection deadline. CPU overload returns an explicit busy error; active GPU inference cannot be preempted. PDF conversion precedes durable upload acknowledgment. Stored failures need retry; a startup dependency race can create such a failure. Exports require API downtime and are initially limited to 8 GiB/100,000 files. Journal/blob cleanup and approximate indexes remain unimplemented. Base images, model files, Rust and Python dependencies are pinned; Debian package repositories are not frozen snapshots.

No holdout labels were read, no sources were regenerated, and no prompt/retrieval settings were tuned in T09. Two successful smoke answers on a small synthetic corpus do not establish retrieval or answer quality. T10 should compare context policies and measure evidence recall, supported answer accuracy, abstention, ingestion costs, queue-inclusive latency and memory with separate cold/warm runs.
