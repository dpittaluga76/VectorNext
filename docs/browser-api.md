# Browser API and local workspace

The Rust service serves the React build and API at `http://localhost:8088`. The production image contains local JavaScript/CSS assets, system fonts and no frontend server or CDN. The three normal Compose services remain unchanged in responsibility.

All POST requests require `X-VectorNext-Client: 1` and a bounded Content-Length. JSON bodies use `application/json` and are limited to 64 KiB. A browser Origin must exactly match the request's loopback Host (`localhost` or `127.0.0.1`, including the port); unrelated, null and cross-site browser origins are rejected. No wildcard CORS is enabled. CLI requests without browser headers continue to work on the existing routes. This is local single-user operation, without public authentication.

## Additive endpoints

| Method/path | Contract |
| --- | --- |
| `GET /v1/ui/library` | Compact current document metadata, filenames, revision, format, passage count, processing flag and unfinished jobs; no vectors. |
| `POST /v1/ui/upload` | Multipart with exactly one `metadata` JSON field and one `file`. Metadata: `upload_id` (browser-generated UUID), `filename`, optional replacement `document_id` and `expected_revision`, `record_pointer` (default root), `allow_partial` (default false). Structural context is used. Returns a durable job with 202. |
| `POST /v1/ui/upload-status` | `{"upload_id":"..."}` returns `preparing`, `acknowledged` with job, or `absent`. Check before every retry. |
| `POST /v1/ui/remove` | `{"document_id":"...","revision":"..."}` removes only the matching current revision from search. Historical jobs and retained blobs remain. |
| `POST /v1/ui/source` | Same document/revision body; returns current revision's passage text, exact location metadata as text, and processing metadata as opaque JSON text. Stale/removed revisions return 409. |
| `GET /v1/ui/original?document_id=...&revision=...` | Current revision's original PDF bytes. Stale/removed revisions return 409; no arbitrary filesystem paths are accepted. |
| `POST /v1/ui/ask` | `question`, nonempty `document_ids`, optional `history`, explicit `fields`, `template`, `prose`, `options`. Returns the browser answer projection described below. |

Existing `/v1/` request/response shapes remain available. A new guard prevents concurrent unfinished ingestion for the same document, including legacy uploads. Replacement/removal check revisions under the same processing lane as upload preparation and publication. They fail while any unfinished job for that document exists, including saved failures. Explicitly retry the job first. New document IDs and job IDs are derived from the upload UUID, never entered by the user. Optional `source_name` is part of new ingestion configuration; absent metadata is omitted during serialization so old job hashes remain unchanged.

Original files require 1 byte to 16 MiB, supported extensions TXT/PDF/JSON, filenames up to 255 UTF-8 bytes without path separators/control characters, and metadata up to 8 KiB. The multipart envelope allows at most 16 MiB + 16 KiB. Existing 64-unfinished-job admission and parser/model limits still apply. PDF CPU preparation happens before durable acknowledgement; an in-memory preparation registry distinguishes it from saved work. After a restart, a saved job is authoritative; otherwise the same retained identity can be explicitly retried. Same-ID changes to content or ingestion options are rejected.

The frontend sends files sequentially. Explicit busy admission gets at most three retries (2/4/8 seconds), each preceded by reconciliation. A transport error triggers reconciliation; an absent/uncertain outcome waits for an explicit user retry. The file, UUID and options are retained in IndexedDB until acknowledgement. A lost response never intentionally creates a fresh ID or duplicate document. Saved stage failures require explicit processing retry.

## Simple questions and exact results

Ordinary questions run one additional schema-constrained Gemma `plan_fields` operation. It receives only the original question and bounded history, and proposes names, types, nullable flags and descriptions. No answer values, query rewrites, JSON pointers or hard filters are accepted. Rust validates names, counts, duplicate fields and the complete answer request again. Invalid plans fail with a readable message; clarification and unsupported aggregation are explicit. Advanced explicit fields bypass planning. The selected document IDs alone become the document filter. Existing retrieval, extraction and proof validation remain authoritative, using ranked 30 candidates / 20 reranked / 5 primary passages by default.

Browser responses have `outcome`, `fields`, `evidence`, `workflow`, optional `formatted`/`draft_text`, and `raw_report`. Each factual field contains `name`, `value_text`, `kind`, `evidence_id`, `quote` and `pointer`. Null uses text `null` and kind `null`; zero remains text `0` and its numeric kind. Values, JSON records and original location metadata are never parsed through JavaScript numbers. `raw_report` is the exact serialized Rust diagnostic report as a **string**; export writes it directly without parsing. Rejected results expose no factual fields; diagnostic previews are explicitly marked if truncated. Mechanical support does not establish semantic correctness.

History allows at most four complete user/assistant exchanges, each turn at most 4 KiB, from supported factual answers only. The frontend limits new questions to 4 KiB so they can fit a later history turn. It shows the context window, refuses oversized turns rather than shortening them, and starts a new conversation when document scope changes. Combined model prompts also have the existing 3,328-token input budget; oversized prompts fail explicitly.

## Browser persistence and operations

IndexedDB stores conversations, captured evidence, exact raw reports, upload recovery state and theme in this browser/origin. There is no server chat store or cross-device sync. `localhost` and `127.0.0.1`, different ports and different browser profiles have separate histories. Clearing browser data/private browsing can erase history. Export conversations before switching profiles or clearing data; diagnostic exports preserve raw numeric literals. One active tab is recommended; concurrent tabs do not merge workspace edits. Storage errors are visible, and the in-memory session remains usable with export.

Captured passages remain historical after replacement/removal. Source inspection/opening never silently substitutes another revision. PDF evidence shows extracted text and page locations; native/OCR details and warnings are available, while an integrated PDF overlay viewer is deferred. Processing shows real saved stages, preparation/acknowledgement states and elapsed answer time. It does not stream internal stages or invent percentages. Workflow details are derived from recorded diagnostics; function references describe implementation, not instrumented execution or model reasoning.

Use `VectorNext.cmd` for Setup, Start, Rebuild, Stop and Status; `Start VectorNext.cmd` starts directly. Setup downloads/checks the pinned models and builds images. Start uses `--no-build --pull never`, checks installed model sizes, and opens the browser when the API is live, before all models are necessarily ready. Model processes retain their checksum checks. Stop targets only project `vectornext`, keeps volumes and never prunes Docker resources. Use Rebuild after code changes. Docker Desktop/WSL 2, Linux containers and NVIDIA GPU support remain prerequisites.
