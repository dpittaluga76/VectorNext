# PDF ingestion (T06)

Design reference: [architecture.md](architecture.md). Extends the [T05 ingestion contract](ingestion.md); the Rust database remains the sole writer. Model inference and PDF conversion occur before accepting a processor stage.

## Boundary and identity

The CPU-only Python adapter produces a bounded, versioned JSON extraction artifact from a read-only PDF. The artifact binds the original SHA-256 and a processing profile SHA-256. The profile covers locked packages, model files, OCR data, adapter code, and conversion settings. Explicit setup downloads exact model revisions; conversion verifies local hashes and runs without networking. The file transport is an executable T06 integration boundary; T09 adds the [long-running processor/API](deployment.md) around the unchanged adapter.

Rust's `PdfProcessor` accepts the artifact at the Uploaded stage, validates identities, page geometry, source spans, structure, and quality policy, and returns the ordinary request-bound `StageResult`. `PdfConfig` binds the profile, canonical Rust serialization SHA-256 of the artifact (not its transport file bytes), and `allow_partial`. Recovery reconstructs the artifact from the stored blocks/units/report and verifies this identity. Later stages use the existing encoder interface, durable jobs, and atomic publication. The PDF configuration is optional and omitted from TXT/JSON serialization so existing request identities do not change. PDF parser/chunker versions are distinct. Real embeddings remain T07.

## Evidence and structure

Docling supplies reading order, labels, headings, tables, and native/OCR cell provenance. Coordinates are one-based pages and top-left PDF points. Each extracted item has UTF-8 byte ranges mapped to page regions; splitting a chunk retains only intersecting regions. A source region may cover more text than the split and is not a character-level PDF mapping.

Page headers/footers are retained as blocks but excluded from indexed evidence. Headings become structural context, with supporting source references. Paragraphs can combine across a page boundary within a section; page breaks never force a chunk boundary. Table containers preserve the full extracted grid. Row blocks keep their table identity and row number, with repeated headers, captions, units, and footnotes in structural context and attributed sources. Empty/merged cells and row/column coordinates remain in the extraction report. No generated prose or inferred numeric fact is substituted for source text.

The adapter uses Docling's PDF-aware OCR regions. Among returned overlapping identical items it prefers native text, never deduplicating globally by text. Docling can omit an invisible text layer and recover the visible scan with OCR; the searchable-scan fixture demonstrates this and retains `Ocr` provenance. Items containing both methods are conservatively labeled OCR. Confidence is an extraction diagnostic, not factual certainty. Chart/picture semantics are not extracted.

## Quality and bounds

The report records page dimensions, native/OCR cell counts, OCR confidence, conversion status, and warnings. Missing pages, empty pages, low-confidence OCR, omitted regions, and uninterpreted pictures make the artifact partial. Strict ingestion rejects partial artifacts; explicit `allow_partial` permits the recovered evidence while retaining warnings. Empty evidence always fails. A successful Docling status alone is insufficient to declare complete text extraction.

Initial profile: Docling Slim 2.139.0, Heron layout, accurate TableFormer, English Tesseract 5.5.0 at 216 DPI, CPU with two threads. Each CLI handles one conversion, limited to 16 MiB input/output, 32 pages, 1440 points per page dimension, 10,000 items, and 180 seconds wall time. Docker limits the processor to two CPUs, 4 GiB memory, 128 processes/threads, and 512 MiB temporary storage; it has no GPU or database mount. The CLI timeout terminates the process even if a library swallows exceptions. The in-process library must be hosted behind equivalent worker limits; T09 supplies shared admission and isolated subprocess deadlines with its documented service limits.

Merged/multi-page table items whose cell-to-page assignment is ambiguous are omitted with a partial diagnostic; cross-page prose remains supported. Tables use one row per initial group; oversized rows split with their headers retained. A source rectangle is a region citation, not a per-glyph alignment. Repeated titles/subtitles within the top 15% of later pages are treated as furniture when their normalized text matches an earlier page (allowing a `continued` suffix). This is a conservative fixture-tested heuristic, not universal document understanding.

The report lives in `DocumentRevision.processing["pdf"]`. Row geometry/text remains in the `pdf_table_row` attributed value, and heading/header/caption/footnote references in `pdf_context`. The artifact and trusted worker boundary provide provenance traceability, not cryptographic proof that an external parser transcribed a PDF correctly.

T13 also exposes the stored artifact's page report through `/v1/job` before publication, including strict partial-extraction failures. Inspection verifies source/profile/artifact identity and preserves the immutable partial policy. Warning previews include total counts and explicit limits; the saved artifact remains complete. Changing to `allow_partial` requires a new job ID, with warnings retained on publication. See [the recovery guide](reliability.md) and [real illustrated-PDF drill](reports/t13-reliability.md).

The small synthetic fixtures check extraction and source fidelity, not general PDF accuracy. Existing evaluation documents and labels are not regenerated by tests. New fixtures and adapter tests are independent of holdout answer tuning.
