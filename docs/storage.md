# Storage contract (journal format 1, checkpoint versions 1 and 2)

Status: adopted implementation specification; verification results are recorded in the build plan.
Design reference: [stored data and durability](architecture.md#stored-data-and-durability) and [operations](architecture.md#operations-caches-and-diagnostics).

## Scope and platform

The Rust core owns storage. Callers prepare complete records and supply vectors; no parser or model runs inside a transaction. Search, job persistence, HTTP endpoints and ingestion have separate contracts. Offline compaction follows the retention and publication rules below. Durable operation targets Linux local filesystems in Docker, with working file/directory fsync and atomic rename. Use a Docker volume for data. Native Windows storage is explicitly unsupported in this version; the Windows host runs the container. Filesystem or hardware failures that violate fsync are outside the guarantee.

## Records and visibility

Documents have a logical ID, immutable revision ID, content-addressed original, format, processing configuration, blocks, and complete chunks. Only published revisions enter the store. Source locators are revision-scoped TXT byte/line mappings, PDF page/region/extraction records, or JSON Pointers with optional record identity. Chunk spans use UTF-8 byte offsets into block text. Original bytes, derived evidence, structural context, generated context, and attributed typed values remain distinct. JSON uses arbitrary-precision numbers; absent attributes differ from explicit null. Source mappings are structurally validated here; their accuracy against parsed documents is an ingestion responsibility.

Embedding-space IDs are SHA-256 hashes of the complete serialized identity: model/revision/artifact, tokenizer, preprocessing, dimensions, limits, prefixes, and normalization. A changed identity creates a different space, even if dimensions match. Each document declares its required spaces; every chunk must supply exactly those vectors. Reject unknown spaces, dimension mismatches, nonfinite/zero vectors, and nonunit vectors in L2 spaces (norm tolerance 0.001). Spaces are immutable; no implicit conversion occurs.

A batch registers spaces and replaces/deletes documents atomically. Replacements use an expected current revision (null means currently absent); deletes require an existing expected revision. A revision ID may never be reused for the same logical document, including after deletion. One document may occur only once in a batch. Exact retries use the same operation ID and request bytes, returning the original generation; reusing an operation ID for different contents fails. Receipts and revision history persist across snapshots/restarts, without eviction in format 1.

Readers hold immutable shared snapshots. Committing swaps the current snapshot after durable flush. Existing readers retain the previous generation, including documents subsequently replaced or deleted. New readers see the complete new generation. One OS-held writer lock protects a directory across processes. A writer requires mutable access; model work is completed before calling it.

## Files and framing

`FORMAT` identifies the database version; a missing committed journal is an error. `writer.lock` holds an advisory exclusive lock for the database lifetime. `journal.bin` is append-only between recovery repairs. `snapshot.bin` is an optional checkpoint; `snapshot.pending` is disposable. `blobs/<sha256>` contains immutable originals. Temporary blob files are disposable and are never referenced by committed records. Interrupted first-time initialization may leave an invalid format marker and fails closed; no transactions are acknowledged before initialization finishes.

All frames use little-endian fields: magic `VNXFRAME` (8 bytes), frame format u16 (=1), kind u16, payload length u64, CRC32 of the preceding 20 header bytes (4 bytes), payload, CRC32 of header plus payload (4 bytes). Kinds 1 prepare, 2 commit, 3 legacy snapshot and 4 job have UTF-8 JSON payloads capped at 64 MiB per frame. T21 adds snapshot-only kinds 5/6/7 with tighter bounds below. CRCs detect accidental corruption, not hostile tampering. Complete invalid headers, checksums, unexpected kinds, sequence gaps, or invalid recovered records are errors, including at EOF; never silently discard a complete corrupt frame. A recognized kind is valid only in its designated stream.

T05 adds kind 4 only for separate `jobs/<sha256-of-job-id>.job` files, with `jobs/stage.pending` as the disposable write candidate. Document journal/checkpoint payloads are unchanged; kind 4 is never valid in either stream. Job files share the sole database writer lock and use file sync, rename, and directory sync. Opening the database also validates saved jobs and their original blobs. Embedded jobs may have an existing publication receipt while awaiting their completion marker; retry resolves that receipt. See [ingestion.md](ingestion.md). Backups/resumption must retain `jobs/` alongside the database and blobs; a document checkpoint does not include job state.

Prepare contains the next generation and full batch. Commit contains that generation and SHA-256 of the prepare payload. Frames are adjacent, with no interleaving. A partial final header/payload/checksum or a prepare without a complete matching commit is an uncommitted tail; recovery truncates to the last committed offset and fsyncs before accepting writes. Corruption within a complete frame is not classified as an interrupted write. The caller may not know whether an unacknowledged transaction survived; retry its operation ID.

## Commit order

1. Preserve originals: write a temporary file, fsync it, rename to its hash, fsync the blob directory. Verify existing blobs before reuse. Sync newly created directory entries, including the database directory's parent.
2. Validate the complete batch, references, vectors, expected revisions, and original checksums; construct the next immutable state. Nothing is visible yet.
3. Append prepare; fsync journal. Append matching commit; fsync journal.
4. Publish the new shared state and acknowledge its generation. Any journal write/flush failure poisons the writer; reads retain the previous state and further mutations require reopen/recovery. A complete but unacknowledged commit may survive recovery.

## Checkpoints and recovery

A checkpoint contains the complete state, receipt/revision history, journal byte offset, and SHA-256 of the journal prefix through that offset. Write `snapshot.pending`, fsync it, atomically rename over `snapshot.bin`, then fsync the database directory. Do not rotate or remove journal data in T03. Failure leaves the previous or new checkpoint; the journal covers both. Checkpoint errors also poison the writer to force recovery of uncertain publication.

### T21 bounded checkpoint stream

New checkpoints retain the same JSON state contract but stream its UTF-8 bytes across frames in one file. The checkpoint writer borrows the immutable state and uses a bounded segment buffer; it does not clone the complete state or serialize the whole checkpoint into a byte vector. Reads deserialize incrementally into the existing in-memory state model. Total state/record memory is not bounded by the segment size.

| Kind | Payload | Maximum payload |
| --- | --- | --- |
| 5 — header | JSON `{"version":2,"segment_bytes":1048576}` | 4,096 bytes |
| 6 — data | Zero-based contiguous u64 segment number, then raw JSON bytes | 8 + 1,048,576 bytes |
| 7 — end | JSON `{"segments":N,"json_bytes":B,"json_sha256":"…"}` | 4,096 bytes |

There must be at least one data frame. Every data frame contains 1–1,048,576 JSON bytes; only the final one may be short. A segment boundary may split a UTF-8 sequence or JSON token. The reader joins their logical byte stream before parsing. The terminal SHA-256 covers those JSON bytes in order, excluding sequence prefixes and frame envelopes. Counts and byte totals must match without overflow; footer CRC, aggregate hash and physical EOF are required. The reader enforces each kind's bound before payload allocation and rejects unknown stream versions/sizes, incorrect sequences, duplicate/gapped/reordered data, truncated frames, malformed/incomplete/extra JSON, missing or inconsistent footer, checksum errors and even one trailing byte. A corrupt published snapshot never triggers silent journal-only fallback.

The `VNXSTORE1` marker, prepare/commit JSON, job format and their 64 MiB per-frame limits do not change. Legacy kind-3 snapshot files remain readable under their original 64 MiB bound. Opening an old database does not rewrite its checkpoint. Calling `checkpoint()` or export writes version 2 using the existing publication/fsync sequence. The total snapshot is no longer subject to a single 64 MiB frame limit; filesystem capacity and the in-memory state model still apply.

Export remains lock-protected and creates a checked file manifest; restore validates both frame formats and publishes only into a new destination. Backup manifest `format:1` describes the unchanged file envelope, not the snapshot stream version. Keep its existing 8 GiB total-size, 16 MiB manifest-size and 100,000-file limits; T21 does not lift them or compact retained journals/blobs.

Compatibility is forward-read: T21 reads old and new checkpoints/backups. Older binaries reject new frame kinds rather than returning partial state. Before upgrading a store that must remain usable by an older release, retain an untouched offline copy or an old-release export. After the first version-2 checkpoint, rollback requires that copy; deleting/replacing a snapshot is not a supported downgrade procedure. Historical T20 stores and exports stay untouched by verification.

On open, lock first, validate a present checkpoint and its journal prefix, then replay committed pairs after the checkpoint offset. Verify published original files and reconstructed state before returning. A malformed checkpoint or missing/corrupt committed original fails closed. A stale temporary checkpoint is ignored. Prefix hashing reads the older journal but avoids deserializing it. A normal checkpoint does not reclaim files; the explicit offline operation below replaces the journal and removes only unreferenced blobs.

## Offline compaction and GC

`storage-plan DB` and `compact DB --apply` use the [maintenance contract and commands](maintenance.md). They require an existing database and exclusive writer ownership; stop the API and all other readers/writers. Inspection opens source files without writing or repairing an uncommitted tail. Invalid layouts, symlinks, unexpected files and corrupt committed data fail closed. The apply command validates and writes a separate sibling store before publishing anything.

The `preserve-history-v1` policy retains the complete recovered `State`, all receipts and used revision IDs, every ingestion-job file byte-for-byte, and every blob referenced by current documents or retained jobs/processing metadata. Matching hash strings are conservative retention roots, including available PDF artifacts. There is no TTL, job-history pruning or retry expiry. Thus retries after later replacement/deletion return the same receipt without resurrection; conflicting ID reuse and old revision reuse remain rejected. Generation, exact typed data, vectors, source mappings and embedding identities do not change.

The candidate contains a version-2 checkpoint with journal offset zero and the SHA-256 of an empty prefix, an empty journal, and copied retained files checked by size/SHA-256. It is reopened with normal recovery validation. The original writer-lock inode is linked into the candidate and remains locked across a same-filesystem Linux atomic directory exchange. After parent-directory fsync, the displaced inventory is verified before its known files are unlinked. The active path therefore contains an old or complete new checkpoint/journal pair; no sequential multi-file switch is used. Hard-link/exchange failure aborts without a fallback rename sequence. No format bump is needed; existing version-2 readers understand the resulting store.

Pending writes and unreferenced blobs are omitted from the candidate. The sibling answer-job namespace, browser history, caches, models and backups remain untouched. Original source files referenced by retained ingestion jobs remain even after a document is removed. Journal-only historical revisions are not a supported revision-read API; captured answer evidence retains its existing historical/stale behavior.

Errors and process termination can retain candidate/displaced sibling directories. Reports identify them but never automatically collect unknown leftovers. A verified backup and inspection are required before explicit cleanup. Reports count logical file bytes, not physical block reclamation. Temporary disk headroom is required, and history/receipt metadata still grows; this is not a fixed storage bound. See [recovery and limitations](maintenance.md#publication-interruption-and-recovery).

Tests must cover byte-by-byte interrupted writes, complete corruption, injected write/fsync/checkpoint failures, retry/revision conflicts, cross-process writer exclusion, old/new reader visibility, typed source/vector round trips, and recovery without model dependencies. These simulate process and I/O failures; they do not certify physical power-loss behavior of the host disk or Docker backend.
