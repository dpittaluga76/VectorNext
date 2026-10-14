# TXT/JSON ingestion and durable jobs

T05 implementation contract. Design reference: [architecture.md](architecture.md).

## Boundaries

The Rust library owns deterministic TXT/JSON preparation and the job coordinator. This adopts the existing serialization/type system for source fidelity and keeps the Python adapter independent. `Processor` accepts serializable stage requests and returns serializable stage results; it has no database handle. `LocalProcessor` uses an `Encoder` interface for exact input token counting and embeddings. Parsing/inference finish before a result is saved or a revision is committed. T06 adds the [PDF/OCR adapter](pdf-ingestion.md). T07 adds [real embeddings and generated context](model-ingestion.md) through an optional configuration and a persistent Python child. Production network transport and scheduling remain future work.

T05 supplies an explicitly synthetic character-token/hash encoder with its own embedding-space identity. It measures plumbing, not semantic retrieval. Token counting includes special tokens, document prefixes, structural context, and serialization separators. Context that leaves no room for evidence fails explicitly. No silent truncation. Chunk/parser/input-format versions and the exact encoder identity belong to each job's immutable configuration.

## Durability and publication

Stages are uploaded, parsed, chunked, contextualized, embedded, committed. Contextualized is an explicit structural-only pass in T05. A job retains the last successful stage and durable failure details; retry repeats that stage's work. Stable job IDs bind document ID, expected prior revision, source hash, media type, and complete configuration. Reusing an ID with different input is rejected. Revision IDs derive from this full request, including job ID.

Original bytes are durably stored first. The sole database writer saves one checksummed versioned job file under `jobs/`, using temporary-file write, file sync, rename, and directory sync. Pending files are disposable. Job writes do not change query generations or the version-1 document journal. A failed/uncertain job write poisons further writes until reopen. Job filenames hash user IDs; IDs never become filesystem paths. Recovery validates committed job files and source blobs without invoking a processor.

Stage results are tied to a digest of the entire input; stale or mismatched results cannot overwrite newer work. An acknowledged result retry is idempotent. Only a fully embedded draft is submitted to the existing atomic `Batch` contract, with a stable operation ID and compare-and-swap revision. Publication precedes the committed job marker. If interrupted between those operations, retry recovers the original publication receipt without another generation or resurrecting a later deleted/replaced document. No partial draft is searchable.

## TXT

Strict UTF-8 (optional BOM); unsupported/invalid bytes fail explicitly and originals remain available. CRLF and CR normalize to LF. Compact mappings use whole-normalized-document UTF-8 coordinates and original byte spans; splits clip identity runs while keeping normalized newline/source CRLF relationships intact. Line numbers are one-based.

Markdown ATX headings define explicit sections; list markers and blank lines define blocks. Other text remains prose, without speculative heading inference. Preserve internal line breaks. Combine neighboring blocks only within the same section and budget. Oversized prose prefers sentence/word boundaries, then Unicode scalar boundaries accepted by the encoder. T05 uses zero overlap; all evidence is retained. Heading blocks and chunk neighbors support later expansion. Structural heading labels are separate from evidence.

## JSON

Strict UTF-8 JSON, exact arbitrary-precision numbers, duplicate object keys rejected. The storage serializer's reserved object key `$serde_json::private::Number` is rejected explicitly (including escaped spellings) to prevent it being misread as a numeric value. The root array is records by default; a configured JSON Pointer can select a nested record array. Sibling metadata outside the selected array is also indexed with its original paths. Empty containers/scalars are supported. An explicit relative ID pointer (default `/id`) preserves string/numeric IDs; missing/null IDs remain absent. Duplicate IDs within the selected records fail instead of guessing identity. ID identity uses its typed JSON serialization; use string IDs for identifiers whose numeric spelling could vary.

Small records stay together. Oversized containers split recursively at child boundaries. Long string leaves split as decoded narrative passages with field/record links. Non-string scalar values are never truncated; oversized indivisible scalars fail. JSON search evidence is a deterministic serialization/decoded-string representation, not a claim to unchanged source bytes. Pointers always include the revision; array indexes alone are not durable record identities.

Each record chunk carries the exact full `record` attribute with provenance, including nulls, nested objects, arrays, and numeric precision. Its `value` attribute identifies the selected subtree. Metadata chunks outside a selected record array carry `value` only. This intentional small-workload duplication supports exact record filters across narrative chunks; chunks must never be counted as independent records for aggregates. Escape `/` and `~` per RFC 6901. Keep full field paths in structural context rather than conflating similarly named nested keys.

## Limits and verification

Job and document frames retain the existing 64 MiB cap. Original ingestion is bounded to 16 MiB; configuration to 32 KiB; IDs to 1024 bytes; parsed/derived blocks and selected records to 10,000. Chunk/embedding preparation accounts for serialized growth and rejects excessive expansion while building it, before producing an unbounded list of copied record attributes. The final frame check remains authoritative. Drafts and stage messages are in memory; this is for the initial small-document workload. Job history, originals, and journal receipts are retained; cleanup, cancellation, parallel leases and streaming are not implemented. T09 exposes the durable stages through a [local HTTP API](deployment.md) with stricter admission limits. Unsupported encodings/formats and malformed/oversized input produce visible failures rather than partial publication.

Processor requests/results are an internal trusted-worker contract, not an adversarial plugin sandbox. The coordinator validates identities, permitted stage transitions, unchanged evidence during embedding, and the storage schema. `LocalProcessor` verifies original hashes and actual token counts; schema validation alone cannot certify an arbitrary external parser's source fidelity. The splitter checks each chosen serialized prefix and uses bounded lookahead for nonmonotonic tokenizer counts; it may conservatively reject pathological inputs instead of finding every possible split.

Tests must cover source mapping, type fidelity, token overhead, deterministic identities, stale results, persisted failures, retries at every boundary, publication/marker interruption, replacement visibility, corruption, and offline ingest-to-search recovery. These checks do not establish model or answer quality.
