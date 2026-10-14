# T03 storage contract (format 1)

Status: adopted implementation specification; verification results are recorded in the build plan.
Design reference: [architecture.md](architecture.md), sections 3, 4, and 9.

## Scope and platform

The Rust core owns storage. Callers prepare complete records and supply vectors; no parser or model runs inside a transaction. Search, job persistence, HTTP endpoints, compaction, and ingestion belong to later tasks. Durable operation targets Linux local filesystems in Docker, with working file/directory fsync and atomic rename. Use a Docker volume for data. Native Windows storage is explicitly unsupported in this version; the Windows host runs the container. Filesystem or hardware failures that violate fsync are outside the guarantee.

## Records and visibility

Documents have a logical ID, immutable revision ID, content-addressed original, format, processing configuration, blocks, and complete chunks. Only published revisions enter the store. Source locators are revision-scoped TXT byte/line mappings, PDF page/region/extraction records, or JSON Pointers with optional record identity. Chunk spans use UTF-8 byte offsets into block text. Original bytes, derived evidence, structural context, generated context, and attributed typed values remain distinct. JSON uses arbitrary-precision numbers; absent attributes differ from explicit null. Source mappings are structurally validated here; their accuracy against parsed documents is an ingestion responsibility.

Embedding-space IDs are SHA-256 hashes of the complete serialized identity: model/revision/artifact, tokenizer, preprocessing, dimensions, limits, prefixes, and normalization. A changed identity creates a different space, even if dimensions match. Each document declares its required spaces; every chunk must supply exactly those vectors. Reject unknown spaces, dimension mismatches, nonfinite/zero vectors, and nonunit vectors in L2 spaces (norm tolerance 0.001). Spaces are immutable; no implicit conversion occurs.

A batch registers spaces and replaces/deletes documents atomically. Replacements use an expected current revision (null means currently absent); deletes require an existing expected revision. A revision ID may never be reused for the same logical document, including after deletion. One document may occur only once in a batch. Exact retries use the same operation ID and request bytes, returning the original generation; reusing an operation ID for different contents fails. Receipts and revision history persist across snapshots/restarts, without eviction in format 1.

Readers hold immutable shared snapshots. Committing swaps the current snapshot after durable flush. Existing readers retain the previous generation, including documents subsequently replaced or deleted. New readers see the complete new generation. One OS-held writer lock protects a directory across processes. A writer requires mutable access; model work is completed before calling it.

## Files and framing

`FORMAT` identifies the database version; a missing committed journal is an error. `writer.lock` holds an advisory exclusive lock for the database lifetime. `journal.bin` is append-only between recovery repairs. `snapshot.bin` is an optional checkpoint; `snapshot.pending` is disposable. `blobs/<sha256>` contains immutable originals. Temporary blob files are disposable and are never referenced by committed records. Interrupted first-time initialization may leave an invalid format marker and fails closed; no transactions are acknowledged before initialization finishes.

All journal and snapshot frames use little-endian fields: magic `VNXFRAME` (8 bytes), format u16 (=1), kind u16 (1 prepare, 2 commit, 3 snapshot), payload length u64, CRC32 of the preceding 20 header bytes (4 bytes), payload, CRC32 of header plus payload (4 bytes). Payloads are UTF-8 JSON, capped at 64 MiB per frame. CRCs detect accidental corruption, not hostile tampering. Complete invalid headers, checksums, unexpected kinds, sequence gaps, or invalid recovered records are errors, including at EOF; never silently discard a complete corrupt frame.

T05 adds kind 4 only for separate `jobs/<sha256-of-job-id>.job` files, with `jobs/stage.pending` as the disposable write candidate. Document journal/checkpoint payloads are unchanged; kind 4 is never valid in either stream. Job files share the sole database writer lock and use file sync, rename, and directory sync. Opening the database also validates saved jobs and their original blobs. Embedded jobs may have an existing publication receipt while awaiting their completion marker; retry resolves that receipt. See [ingestion.md](ingestion.md). Backups/resumption must retain `jobs/` alongside the database and blobs; a document checkpoint does not include job state.

Prepare contains the next generation and full batch. Commit contains that generation and SHA-256 of the prepare payload. Frames are adjacent, with no interleaving. A partial final header/payload/checksum or a prepare without a complete matching commit is an uncommitted tail; recovery truncates to the last committed offset and fsyncs before accepting writes. Corruption within a complete frame is not classified as an interrupted write. The caller may not know whether an unacknowledged transaction survived; retry its operation ID.

## Commit order

1. Preserve originals: write a temporary file, fsync it, rename to its hash, fsync the blob directory. Verify existing blobs before reuse. Sync newly created directory entries, including the database directory's parent.
2. Validate the complete batch, references, vectors, expected revisions, and original checksums; construct the next immutable state. Nothing is visible yet.
3. Append prepare; fsync journal. Append matching commit; fsync journal.
4. Publish the new shared state and acknowledge its generation. Any journal write/flush failure poisons the writer; reads retain the previous state and further mutations require reopen/recovery. A complete but unacknowledged commit may survive recovery.

## Checkpoints and recovery

A checkpoint contains the complete state, receipt/revision history, journal byte offset, and SHA-256 of the journal prefix through that offset. Write `snapshot.pending`, fsync it, atomically rename over `snapshot.bin`, then fsync the database directory. Do not rotate or remove journal data in T03. Failure leaves the previous or new checkpoint; the journal covers both. Checkpoint errors also poison the writer to force recovery of uncertain publication.

On open, lock first, validate a present checkpoint and its journal prefix, then replay committed pairs after the checkpoint offset. Verify published original files and reconstructed state before returning. A malformed checkpoint or missing/corrupt committed original fails closed. A stale temporary checkpoint is ignored. Prefix hashing reads the older journal but avoids deserializing it; snapshots are not yet a bounded-disk compaction mechanism. Old blobs, revision receipts, and old journal entries remain until a future safe reclamation design.

Tests must cover byte-by-byte interrupted writes, complete corruption, injected write/fsync/checkpoint failures, retry/revision conflicts, cross-process writer exclusion, old/new reader visibility, typed source/vector round trips, and recovery without model dependencies. These simulate process and I/O failures; they do not certify physical power-loss behavior of the host disk or Docker backend.
