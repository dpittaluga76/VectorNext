# T06 PDF ingestion results

Verified 2026-10-14 on the local Docker Desktop Linux environment. Design: [PDF ingestion](../pdf-ingestion.md). Exact images, profile, code/source hashes, diagnostics, timings, and demo receipt: [machine-readable report](t06-pdf.json).

T06 is complete: native PDFs, scanned text, and mixed pages now feed the durable ingestion pipeline with original-file hashes, page rectangles, native/OCR provenance, table headers/units, and explicit extraction quality. Rust remains the sole database writer. Conversion uses the CPU; no GPU workload or generation benchmark was started. Embeddings remain synthetic until T07.

## Fixture observations

| Source | Observed result |
| --- | --- |
| Native equipment guide, two pages | 25 blocks; table rows retain Model / Flow (L/min) / Water (C), cell coordinates, and heading support. The C7 sentence spans both pages in one chunk. Repeated page furniture is preserved but excluded from indexed evidence. |
| Scanned inspection note | OCR recovered the J2/6 N m and J3/9 N m text with OCR provenance and confidence. Native cell count is zero. |
| Mixed native/scanned page | V8/24 kPa remains native; V9/31 kPa is OCR on the same page, with separate rectangles. The batch identifier and closing note remain readable. |
| Searchable scan with invisible text layer | The V5/19 kPa line occurs once. Docling omits the invisible layer and recovers the visible line with OCR; the adapter records that actual method. |
| Uninterpreted diagram | Readable title/caption are recovered. Picture semantics remain unavailable, the artifact is partial, and default ingestion rejects it. Explicit partial opt-in retains both recovered evidence and warnings. |

All six source pages were rendered and visually inspected, including the scanned digits and units. Existing evaluation PDFs were reused unchanged. The three new documents are separate synthetic fixtures. Capture updates changed only the profile hash compared with the first extraction pass; the five extracted document payloads were otherwise identical.

The converter logs orientation-detection warnings on some short regions. The tested text still recovered correctly; these warnings do not establish reliable rotated-text handling. Confidence/missing-page/unmapped-text diagnostic tests inject controlled failures; they do not replace evaluation on degraded real scans.

## Verification

- All **66 Rust tests** passed in the final offline image: 18 storage, 20 TXT/JSON/job durability, 8 PDF ingestion, 18 retrieval, and 2 diagnostics. Two ignored helper functions are invoked by process-termination tests.
- All **13 Python processor tests** passed with networking disabled, read-only application/model mounts, two CPUs, and 4 GiB memory. They exercise the five real fixture conversions plus diagnostic/resource-limit checks.
- All 8 PDF tests also passed on the retained `vectornext-core-checks` disk volume. Coverage includes restart after each stage, checkpoint recovery without the parser, exact retry receipts, changed/stale artifacts, invalid geometry/UTF-8 mapping/hierarchy, multi-page source clipping, and partial-quality policy.
- Final Rust formatting and Clippy with warnings denied passed. Initial lint failures (a Boolean expression and an unnecessary test borrow) were fixed before the final full check. Base/processor Compose configurations validated; the existing T01 integrity validator still passed.
- The documented CLI converted the native guide in a fresh offline processor container, then published 25 blocks/14 chunks into `vectornext-pdf-demo`. A separate fresh core container reused the same receipt and kept generation 1. The volume and ignored output artifact remain available for inspection.
- All model/runtime hashes and locked Python package versions verified. Explicit setup was rerun against the retained models and reused them successfully. No database files are mounted in the processor.

Final images:

- Core: `sha256:efbcc6931ca4c2a7fcc72a7cd40c66e76ea97960f4ebb6edb28f68d5ae817f6b`.
- Processor: `sha256:e16c8229c11353560b8eaae14cab6c651fd22180d3b16d4b5725c74b7be0dee8`.
- Processing profile: `eba773878b43b30647ae9cc447b45a591401a226ca0757e6902b3ebe49fdd19d`.

## CPU measurements and limits

The final 13-test processor run took 45.69 seconds. Individual conversion calls, including local hash verification, measured 15.045 s for the native guide, 7.188 s for the scan, 4.545 s for the searchable scan, 5.265 s for the mixed page, and 4.679 s for the diagram. The first conversion includes lazy model initialization; later calls reuse the converter. These are single observations, not latency percentiles or end-to-end service measurements.

Python process peak RSS was 1,314,572 KiB (about 1.25 GiB). This excludes some child-process/container memory and is not a whole-machine peak. Docker enforced a 4 GiB memory cap, two CPUs, 128 processes/threads, and 512 MiB temporary storage. Models occupy approximately 367 MiB outside the image. The runtime has no GPU device access.

Input/output is limited to 16 MiB, 32 pages, 1440 points per page dimension, and 10,000 extracted items. CLI work has a 180-second hard process timeout. The timeout/library limits are not a production scheduler; that remains T09. Python packages and model revisions/files are pinned, with OCR binary/library/data hashes checked at runtime. Debian repositories are not a frozen snapshot; a future incompatible rebuild must fail verification and require deliberate revalidation.

## Remaining boundaries

English OCR and small clean synthetic layouts are the tested scope. No claim covers handwriting, arbitrary multi-column layouts, rotated scans, all merged-cell tables, or other languages. Ambiguous multi-page table cell coordinates are reported as partial; their cells are not assigned to guessed pages. Page rectangles identify source regions and are not glyph-level alignments. Table rows split with header context if needed; complex caption/footnote linking still depends on Docling's associations.

`complete` means no tracked extraction warning was found, not that every fact or visual was understood. Strict mode fails on partial extraction; explicit partial mode is reviewable through persisted diagnostics. Unrecognized omissions remain possible. No holdout answers were used for tuning or changed. No semantic retrieval, generated context, answers, server, or integrated GPU deployment was added here.

Next: T07 connects actual embeddings and plain/structural/generated-context policies while preserving source evidence, immutable identities, token budgets, and durable publication.
