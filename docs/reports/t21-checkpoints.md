# T21 — Bounded checkpoints and large-state export

Completed 2026-10-15. [Machine-readable evidence](t21-checkpoints.json) · [Storage format](../storage.md#t21-bounded-checkpoint-stream) · [Reproduction](../../experiments/t21/README.md).

The complete-state 64 MiB checkpoint bottleneck is removed. Fresh copies of **both T20 databases** now checkpoint, recover after SIGKILL, export and restore successfully. Their complete record/vector digests and **768/768 exact-query checks** match before checkpoint, after interruption and after restore. The original T20 volumes, manifests, inputs and reported results remain unchanged.

Architecture and T21's task/acceptance criteria were updated before implementation. The matching T20 source files were archived and verified before storage edits. No model, retrieval algorithm, HTTP contract, journal payload or job format changed.

## Implementation and compatibility

`src/storage/checkpoint.rs` streams the existing checkpoint JSON directly from borrowed immutable state into **1 MiB segments**. It adds a version-2 header, contiguous numbered data frames and a terminal manifest containing segment count, JSON byte length and SHA-256. Every frame has the existing CRC protection. The reader applies kind-specific limits before allocation, reconstructs the logical JSON stream, and requires a valid terminal manifest and exact physical EOF.

Missing/duplicate/reordered/gapped segments, invalid lengths, altered checksums or aggregate hashes, malformed JSON, unknown versions and trailing data fail closed. The complete checkpoint is never cloned or collected into a serialized byte vector by the new path. The database itself still resides in memory; deserialized records and JSON fields are not limited to a 1 MiB resident footprint.

Publication remains `snapshot.pending` → file fsync → atomic rename → directory fsync, under the existing writer lock. Failures retain the old or new published checkpoint and poison the writer until reopening. Recovery validates the retained journal prefix before replaying its suffix. No journal truncation/compaction or silent fallback from a corrupt published snapshot was introduced.

New readers accept old kind-3 snapshots and new kind-5/6/7 streams. Opening alone does not rewrite old checkpoints; explicit checkpoint/export writes version 2. The journal marker stays `VNXSTORE1`, and the backup file manifest stays `format:1`. Its file envelope has not changed. **Older binaries cannot read a new checkpoint.** Keep an untouched pre-upgrade offline copy or old-release export if rollback is required; deleting a checkpoint is not a supported downgrade.

The existing **64 MiB journal/job frame limit, 8 GiB total backup limit, 16 MiB backup-manifest limit and 100,000-file bound remain**. This fixes the aggregate checkpoint constraint exposed by T20, not every database capacity limit.

## Verification on the former failing states

The stopped `vectornext-t20-v3_vector_data` volume was mounted read-only and copied into fresh `vectornext-t21-data`. All **2,013 copied/source files** matched by SHA-256. The test copies contain T20's existing 32-chunk sentinel, so the measured states have 401/1,601 documents and 12,832/51,232 chunks.

The release drill uses 2 CPUs / 4 GiB per container, no network or GPU. It verifies all records and 128 frozen T20 exact queries, writes a checkpoint, then acknowledges an additional journal transaction that re-registers the same embedding space. That transaction adds a receipt/generation without changing document/query expectations. The process stays alive until explicitly killed. A fresh process must recover that receipt, retry it idempotently, repeat the queries, export, restore into a new destination, and verify all records/queries again.

| T20 base corpus | Snapshot before suffix | Data segments | Checkpoint | Open after SIGKILL | Export | Restore | Exact checks across 3 stages |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 400 documents | 90,483,871 bytes (86.29 MiB) | 87 | 0.456 s | 1.009 s | 2.368 s | 3.071 s | 384/384 |
| 1,600 documents | 361,257,185 bytes (344.52 MiB) | 345 | 1.858 s | 4.287 s | 9.370 s | 11.267 s | 384/384 |

The export includes the additional receipt, increasing each snapshot slightly: **90,483,997 / 361,257,312 bytes**. Export manifests cover **404 / 1,604 files**, totaling **188,983,337 / 754,517,678 bytes**. The retained full journal and originals are included.

The independent Python frame inspector confirmed CRCs, sequence numbers, aggregate SHA-256, footer counts and physical EOF. Largest data-frame payload: **1,048,584 bytes** (1 MiB JSON plus eight-byte sequence). The live-copy, exported and restored snapshot files have identical hashes. Full document/provenance/typed-value/vector/receipt/embedding-space digests match across all stages, and the original T20 chunk digest matches its frozen post-sentinel reference. The additional receipt survives at generations 402/1,602 and exact retries do not advance them.

These are one-pass operational durations, not a new comparative benchmark. They include filesystem/page-cache effects and ran on the existing Windows/Docker/WSL2 Ryzen 5 7600 host. Cgroup peaks during recovery/export/restore were 718,790,656 / 2,877,030,400 bytes; these include page cache and multiple open states and do not measure serialization-buffer size. Container startup is excluded from open time. Process interruption is not physical power-loss certification.

## Regression and real legacy checks

**132 Rust checks passed:** the full 131-test suite, then one added >64 MiB regression; both stages passed formatting and Clippy. The final core image includes all 132 tests. Nine new checks cover stream framing/corruption, exact segment boundaries, partial I/O, legacy migration, incomplete segment publication, and large export/restore. Existing tests cover exact numeric/null/zero values, revision tombstones, retry conflicts, source mappings, unfinished jobs, prefix/blob corruption and all fsync/rename publication faults. The expanded fault loop also fails after the first data segment. Two subprocess helpers remain intentionally ignored in ordinary enumeration and are invoked by parent tests.

The large regression builds a valid state from 33 individually valid transactions with 2 MiB metadata payloads. It exports/restores a checkpoint above the old limit and compares complete documents plus idempotent receipts, including arbitrary-precision integers/decimals, null and zero. It does not regenerate any historical corpus or gold labels.

A retained **T19 binary** exported the copied two-document smoke store using the actual legacy format. T21 restored it, rewrote a new checkpoint through export and produced byte-identical `inspect` output. T19 then rejected that upgraded copy with `corrupt storage: unknown frame kind`. The legacy export itself remains untouched and usable by the old reader.

The release drill and production app images built successfully with Rust 1.87. The isolated production image returned HTTP 200 for `/healthz`, `/`, `/docs` and `/openapi.json` with external networking disabled. UI/model behavior was not changed, so browser/GPU quality suites were not rerun. Existing `buf_redux`/`multipart` future-compatibility notices remain.

Early verification corrections are retained in the logs: the new drill initially missed a receipt reference required by `serde_json::to_writer`; this compile error was fixed before operational runs. A test launch against the previous core image was stopped and not counted. The first API smoke requested nonexistent `/health/live`; the corrected check uses the existing `/healthz`. Only final successful checks are counted above.

## Artifacts, deployment and next work

- Reports/logs: ignored `data/t21/`; the versioned JSON records source hashes, capture hashes, image identities, exact results and aggregate measurements. Raw backup manifests and query checks remain locally available.
- Data: `vectornext-t21-data` retains both test databases, exports, restored copies and the legacy exercise. `vectornext-t21-api-data` retains only the isolated empty API smoke store. All T21 containers are stopped. No T20 container was started or original volume written.
- Matching T20 source archive: `backups/t20-source-before-t21.zip`, SHA-256 **`32e41ca95f4a86f4bd4c5fcd6bd2150449cb16fb521a3348c40cd3550da9d1fc`**. All 39 original execution-source hashes were checked in the archive. To reproduce T20, use a separate checkout of base `9e3831f` and overlay this archive there; do not rewrite its freezes to match T21.
- Built images: `vectornext-checkpoint:t21` = `sha256:51ad30026af57e130b8314c117aba5dc91e68edb3b5af02e782793c95402bc51`; `vectornext-app:t21` = `sha256:ec10b62e5221051edc67b005ff8cf65f5714b6a5f57cc04a9d45f9df92308850`. Core image and complete source/capture identities are in the JSON report.
- Compose now selects `vectornext-app:t21` for API/client/admin; processor and generator stay on their existing images. The launcher reads image names from Compose. **The already-running normal app was not restarted and still uses T19.** Its services remain healthy, and the T19/T18 images remain retained. A later normal Start/Rebuild applies the new API image; preserve a pre-upgrade store copy before writing new checkpoints if old-binary rollback matters.

T21's acceptance is met. Next scope filter eligibility/candidate profiling on fresh measurements. Storage compaction, a larger backup envelope, approximate indexing and retrieval/ambiguity quality experiments remain separate work. No historical evaluation score or original holdout was changed or consumed.
