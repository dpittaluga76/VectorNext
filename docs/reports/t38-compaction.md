# T38 — Safe offline compaction and garbage collection

Completed 2026-10-16. [Machine-readable verification](t38-compaction.json) · [Operator guide](../maintenance.md) · [Retention contract](../architecture.md#offline-compaction-and-retention).

VectorNext now provides explicit offline accounting and compaction through `storage-plan DB` and `compact DB --apply`. Architecture and task criteria were recorded before implementation. No retrieval, model, HTTP or storage-format contract changed. The normal library was not compacted, copied into tests or otherwise modified by verification.

## Retention and publication

The `preserve-history-v1` policy keeps complete current state, exact values, source mappings, vectors, embedding identities and generation. It retains every operation receipt and used revision ID indefinitely, plus every ingestion job byte-for-byte, including completed, failed and unfinished work. Current documents and saved jobs conservatively pin matching blob hash strings, including object keys and nested processing metadata. Available PDF artifacts remain reachable. Only unreferenced blobs are omitted.

Maintenance takes the existing exclusive lock, reads the source without repairing an incomplete journal tail, and writes a separate sibling candidate. It verifies copied files and a version-2 checkpoint through normal recovery before a single Linux directory exchange. The replacement shares the original lock inode, preserving exclusion even for a descriptor opened before the exchange. After parent-directory fsync and displaced-inventory verification, it unlinks only known old files. No sequential checkpoint/journal swap or recursive wildcard deletion is used.

The original state and retry history remain reopenable after an injected error or process death. Interrupted workspaces are reported, never automatically deleted. Unknown files, symlinks, corrupt data and insufficient free space cause refusal. Unsupported hard-link/atomic-exchange filesystems have no fallback sequence.

The sibling answer-job store, captured browser evidence, caches, models and external backups are outside GC. Historical ingestion can pin deleted documents' originals. There is no TTL, retry expiry or fixed disk-size guarantee; full jobs and receipt/revision metadata still grow.

## Reclamation measurement

The deterministic Rust integration fixture publishes eight documents through eight revisions, with 32 chunks of 128 supplied vector dimensions per revision, then deletes four documents. It creates no ingestion jobs, deliberately measuring reclaimable journal/original churn independently of retained ingestion history. Supplied vectors test search equality, not semantic quality.

| Measurement | Result |
| --- | ---: |
| Active-store logical bytes before | 4,513,752 |
| Compacted logical bytes | 288,558 |
| Logical bytes reclaimed | **4,225,194 (93.6%)** |
| Journal bytes before / after | 3,930,766 / 0 |
| Unreferenced blobs removed | 60 / 546,540 bytes |
| Remaining documents / chunks | 4 / 128 |
| Preserved receipts / reserved revision IDs | 68 / 64 |
| Generation before / after | 68 / 68 |

Serialized current documents and hybrid search results matched exactly. Export/restore passed; a second compaction reclaimed zero additional bytes. These are logical file lengths on an isolated fixture, not a claim about physical Docker virtual-disk shrinkage or expected savings in every user library.

## Verification

| Check | Result |
| --- | --- |
| Rust 1.87 all-target suite | **186 passed**; two existing subprocess helpers are ignored in ordinary enumeration and invoked by their parent tests. |
| Formatting / Clippy | Passed; existing dependency future-compatibility notices for `buf_redux` / `multipart` remain. |
| Fault and interruption recovery | Twelve injected I/O-error boundaries and twelve actual killed-process boundaries preserved complete logical state and original retry receipts. |
| Locking and paths | Live-writer refusal, lock-inode continuity, old-descriptor exclusion, missing paths, symlinks, unexpected files and corrupt blobs covered. |
| State and provenance | Exact large integer/decimal/null/zero JSON, complete state/search equality, byte-verified job copies, original sources, PDF artifact retention and pending PDF/TXT publication covered. |
| Retry and compatibility | Identical/conflicting operations and ingestion requests, deletion retries, reserved revision reuse, legacy checkpoints, subsequent commits/checkpoints and export/restore passed. |
| Release CLI, Linux Docker disk volume | Four checks passed: explicit apply/read-only dry run, atomic exchange/backup/repeat, read-only permissions, and actual low-space refusal on an 8 MiB filesystem before staging. |
| HTTP compatibility | All **71 frozen cases**, plus **five browser boundary checks**, passed offline without a processor or GPU. |
| Previous version-2 binary | Retained `:t37-hybrid` binary reopened/exported a new **empty** compacted store; current binary restored it identically. Nonempty legacy/state coverage is in Rust tests. |
| Packaging / launcher | Production image built; Compose configuration and mocked Windows launcher contracts passed. |

Core checks ran with current source mounted read-only in one reusable CPU container and network disabled. Crash/error fixtures used temporary memory-backed Linux storage. Release maintenance ran separately on a fresh Docker local volume; the low-space fixture used an independent 8 MiB tmpfs. This tests process/I/O recovery and Linux filesystem operations, not host power-loss behavior. No model benchmarks, original holdout, historical dataset edits or frontend behavior changes were involved.

Verification corrections are retained in local logs and their hashes in the JSON report. An initial test compile used the wrong PDF adapter field and was corrected before the passing checks. Docker stopped responding during a later core-image export while C: had about 3.6 GB free; pending commands were cancelled. After user cleanup, testing resumed using one container at a time. A broader OpenAPI module could not import `jsonschema` in the production image; the final selection contains the applicable CLI/HTTP checks. OpenAPI schemas did not change, and the model-backed docs fixture was not rerun. The previous-binary smoke initially hit container copy/no-exec restrictions before succeeding from the isolated disk volume. Failed invocations are not counted as passing checks.

## Reproduce without normal app data

Core verification uses the repository's standard commands (initial image builds may need network):

```powershell
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo fmt --check
docker compose run --rm core cargo clippy --locked --offline --all-targets -- -D warnings
```

Build the release, then use one isolated container with an automatically allocated scratch volume. These commands do not mount the normal application volume or publish a port:

```powershell
docker compose -f compose.app.yaml build vectornext
docker run -d --name vectornext-maintenance-check --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,size=268435456 --tmpfs /tight:rw,size=8388608 --mount "type=volume,destination=/scratch" --mount "type=bind,source=${PWD},target=/checks,readonly" -e VECTORNEXT_DATA=/tmp/check-db -e VECTORNEXT_PROCESSOR_URL=http://127.0.0.1:8090 vectornext-app:t38
docker exec -w /checks -e VECTORNEXT_MAINTENANCE_ROOT=/scratch -e VECTORNEXT_MAINTENANCE_TIGHT_ROOT=/tight -e VECTORNEXT_TEST_URL=http://127.0.0.1:8088 vectornext-maintenance-check python -m unittest deployment.test_maintenance deployment.test_http_compatibility deployment.test_browser_http -v
docker rm -f -v vectornext-maintenance-check
```

Wait for `/healthz` if starting tests immediately on a slow machine. Remove this specifically named test container and its anonymous scratch volume after checks, including after a failure; preserve logs outside it. No experiment Compose file or persistent test service is added.

## Delivery and limits

- API/client/admin configuration selects `vectornext-app:t38`, image `sha256:fafdb93ce19dae6f932dcf5c7717925bbcb7e3da26f4646cc8afa5f6a19fa60e`. Processor and generator remain on `:t37-hybrid`. The launcher reads image names from Compose; routine Start does not build or download.
- The running normal app was **not restarted** and remains on its previous healthy `:t37-hybrid` image. Both prior image and model files remain. A later normal Start/Rebuild selects the new API; use the maintenance guide for deliberate offline compaction after a verified backup.
- Both task-created verification containers and the anonymous scratch volume were removed. Raw captures remain under ignored `tmp/t38/`, with hashes and implementation identities in the versioned JSON report. No other containers, images, volumes or caches were deleted by this task.
- Maintenance needs a separate compacted copy plus a 64 MiB reserve, exclusive downtime and same-filesystem directory exchange. A directly mounted database root may be unexchangeable; the normal `/storage/db` subdirectory works. Filesystem availability can change after preflight.
- Unknown/corrupt leftover workspaces require explicit inspection. There is no automated interrupted-workspace reclamation, online compaction or history pruning. Existing 64 MiB journal/job frame and 8 GiB export bounds remain.

T38 is complete. Further ANN/storage novelty remains deferred until a representative workload establishes a need; model latency and broader semantic reliability remain separate work.
