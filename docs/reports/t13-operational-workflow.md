# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **apollo-t13**; file: apollo11\_pdf.pdf; format: Pdf.

**Outcome: Failed.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — failed.** invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial
  Code: `PdfProcessor::process()`.

- **Create chunks — not reached.** No completed result recorded for this step.

- **Prepare context — not reached.** No completed result recorded for this step.

- **Create embeddings — not reached.** No completed result recorded for this step.

- **Publish document — not reached.** No completed result recorded for this step.

Recorded failure: invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial

Saved failed attempts: 1.

## PDF diagnostics before publication

Extraction: partial; partial text allowed: false; pages: 2; warnings: 48.

- Page 1: low\_ocr\_confidence — —

- Page 1: low\_ocr\_confidence — w

- Page 1: low\_ocr\_confidence — Oe

- Page 1: low\_ocr\_confidence — ete

- Page 1: low\_ocr\_confidence — tae

- Page 1: low\_ocr\_confidence — Pe

- Page 1: low\_ocr\_confidence — we

- Page 1: low\_ocr\_confidence — ‘

Additional warnings remain in the structured job response.

Review page warnings. To accept recovered text explicitly, submit a new job ID with --allow-partial; the existing job policy is immutable.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

- **Admission attempt 1 — rejected.** admission busy: processing lane busy; retry later Retrying in 1 s.

- **Admission attempt 2 — rejected.** admission busy: processing lane busy; retry later Retrying in 2 s.

- **Admission attempt 3 — rejected.** admission busy: processing lane busy; retry later Retrying in 4 s.

- **Admission attempt 4 — rejected.** admission busy: processing lane busy; retry later Retrying in 4 s.

- **Admission attempt 5 — rejected.** admission busy: processing lane busy; retry later Retrying in 4 s.

Document: **queued-t13**; file: queued.txt; format: Txt.

**Outcome: Stored and searchable.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Read UTF-8 text and its structure.
  Code: `ingestion::prepare::parse()`.

- **Create chunks — completed.** Prepared 1 blocks and 1 searchable chunks.
  Code: `ingestion::prepare::chunk()`.

- **Prepare context — completed.** Context policy: structural.
  Code: `ContextProcessor::process()`.

- **Optional generated context — skipped.** This format or policy does not request generated annotations.

- **Create embeddings — completed.** Embedding model: sentence-transformers/all-MiniLM-L6-v2.
  Code: `ingestion::configured_input()` → `RemoteModels::embed()`.

- **Publish document — completed.** Published the complete document revision for search.
  Code: `Database::commit_ingestion()`.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **apollo-t13**; file: apollo11\_pdf.pdf; format: Pdf.

**Outcome: Stored and searchable.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Processed PDF text and available OCR/layout evidence.
  Code: `PdfProcessor::process()`.

PDF details: partial; 2 pages; extraction methods: Native.

- **Create chunks — completed.** Prepared 28 blocks and 14 searchable chunks.
  Code: `ingestion::pdf::chunk()`.

- **Prepare context — completed.** Context policy: structural.
  Code: `ContextProcessor::process()`.

- **Optional generated context — skipped.** This format or policy does not request generated annotations.

- **Create embeddings — completed.** Embedding model: sentence-transformers/all-MiniLM-L6-v2.
  Code: `ingestion::configured_input()` → `RemoteModels::embed()`.

- **Publish document — completed.** Published the complete document revision for search.
  Code: `Database::commit_ingestion()`.

## Extraction warnings

- —

- w

- Oe

- ete

- tae

- Pe

- we

- ‘

40 additional warnings remain in the structured capture.

## PDF diagnostics before publication

Extraction: partial; partial text allowed: true; pages: 2; warnings: 48.

- Page 1: low\_ocr\_confidence — —

- Page 1: low\_ocr\_confidence — w

- Page 1: low\_ocr\_confidence — Oe

- Page 1: low\_ocr\_confidence — ete

- Page 1: low\_ocr\_confidence — tae

- Page 1: low\_ocr\_confidence — Pe

- Page 1: low\_ocr\_confidence — we

- Page 1: low\_ocr\_confidence — ‘

Additional warnings remain in the structured job response.

Review page warnings and extraction coverage; illustrations are not interpreted.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **perseverance-t13**; file: perseverance\_pdf.pdf; format: Pdf.

**Outcome: Failed.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — failed.** invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial
  Code: `PdfProcessor::process()`.

- **Create chunks — not reached.** No completed result recorded for this step.

- **Prepare context — not reached.** No completed result recorded for this step.

- **Create embeddings — not reached.** No completed result recorded for this step.

- **Publish document — not reached.** No completed result recorded for this step.

Recorded failure: invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial

Saved failed attempts: 1.

## PDF diagnostics before publication

Extraction: partial; partial text allowed: false; pages: 2; warnings: 4.

- Page 1: low\_ocr\_confidence — SPVPRVSVN

- Page 1: uninterpreted\_picture — Picture/diagram semantics are not extracted

- Page 1: uninterpreted\_picture — Picture/diagram semantics are not extracted

- Page 2: uninterpreted\_picture — Picture/diagram semantics are not extracted

Review page warnings. To accept recovered text explicitly, submit a new job ID with --allow-partial; the existing job policy is immutable.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **perseverance-t13**; file: perseverance\_pdf.pdf; format: Pdf.

**Outcome: Stored and searchable.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Processed PDF text and available OCR/layout evidence.
  Code: `PdfProcessor::process()`.

PDF details: partial; 2 pages; extraction methods: Native, Ocr.

- **Create chunks — completed.** Prepared 36 blocks and 18 searchable chunks.
  Code: `ingestion::pdf::chunk()`.

- **Prepare context — completed.** Context policy: structural.
  Code: `ContextProcessor::process()`.

- **Optional generated context — skipped.** This format or policy does not request generated annotations.

- **Create embeddings — completed.** Embedding model: sentence-transformers/all-MiniLM-L6-v2.
  Code: `ingestion::configured_input()` → `RemoteModels::embed()`.

- **Publish document — completed.** Published the complete document revision for search.
  Code: `Database::commit_ingestion()`.

## Extraction warnings

- SPVPRVSVN

- Picture/diagram semantics are not extracted

- Picture/diagram semantics are not extracted

- Picture/diagram semantics are not extracted

## PDF diagnostics before publication

Extraction: partial; partial text allowed: true; pages: 2; warnings: 4.

- Page 1: low\_ocr\_confidence — SPVPRVSVN

- Page 1: uninterpreted\_picture — Picture/diagram semantics are not extracted

- Page 1: uninterpreted\_picture — Picture/diagram semantics are not extracted

- Page 2: uninterpreted\_picture — Picture/diagram semantics are not extracted

Review page warnings and extraction coverage; illustrations are not interpreted.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **recovery-t13**; file: recovery.txt; format: Txt.

**Outcome: Failed.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Read UTF-8 text and its structure.
  Code: `ingestion::prepare::parse()`.

- **Create chunks — failed.** capability unavailable: processor /rpc/background: http://processor:8090/rpc/background: Dns Failed: resolve dns name 'processor:8090': failed to lookup address information: Name or service not known
  Code: `ingestion::prepare::chunk()`.

- **Prepare context — not reached.** No completed result recorded for this step.

- **Create embeddings — not reached.** No completed result recorded for this step.

- **Publish document — not reached.** No completed result recorded for this step.

Recorded failure: capability unavailable: processor /rpc/background: http://processor:8090/rpc/background: Dns Failed: resolve dns name 'processor:8090': failed to lookup address information: Name or service not known

Saved failed attempts: 1.

---

# VectorNext workflow — ingestion

Fresh T13 CPU operational drill; no generation model was used.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/job → Application::job()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **recovery-t13**; file: recovery.txt; format: Txt.

**Outcome: Stored and searchable.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Read UTF-8 text and its structure.
  Code: `ingestion::prepare::parse()`.

- **Create chunks — completed.** Prepared 500 blocks and 500 searchable chunks.
  Code: `ingestion::prepare::chunk()`.

- **Prepare context — completed.** Context policy: structural.
  Code: `ContextProcessor::process()`.

- **Optional generated context — skipped.** This format or policy does not request generated annotations.

- **Create embeddings — completed.** Embedding model: sentence-transformers/all-MiniLM-L6-v2.
  Code: `ingestion::configured_input()` → `RemoteModels::embed()`.

- **Publish document — completed.** Published the complete document revision for search.
  Code: `Database::commit_ingestion()`.

Saved failed attempts: 1.
