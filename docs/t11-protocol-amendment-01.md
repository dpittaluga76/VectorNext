# T11 amendment 01: UTF-8 line mapping before comparison

Date: 2026-10-14. Written before the first T11 answer request.

The first ingestion attempt, `data/t11/20261014-independent/`, committed Voyager 1 and Voyager 2, then crashed the Rust background worker while preparing Pioneer 10. `src/ingestion/prepare.rs:122` sliced a UTF-8 string at `end - 1` to count newlines. That byte was inside the ellipsis `…` at bytes 8905–8908. The queued job stayed `Uploaded`, the coordinator stopped progressing, and HTTP readiness remained available. The runner was interrupted; no T11 answer queries were issued. Logs, partial job captures, runtime image identities and the untouched database are retained.

This is a general source-handling defect that prevents the remaining queue from running, not an ingestion rejection of one document or a measured answer-quality failure. Continuing would mark every later document unavailable for the same dead worker. Repair it before the comparison rather than rewrite the source or remove documents.

The repair counts newline bytes using a byte iterator in both paragraph and forced-chunk source mapping, without constructing a string slice at an arbitrary byte. It changes neither chunk selection nor original bytes, token counts, search, prompts, models or answer validation. A new regression uses ellipsis, accented characters, CJK and emoji at paragraph/chunk endings, with BOM/CRLF input, and checks source line numbers, character boundaries, reconstructed text and preserved originals. It fails against the old code and passes with the fix. General worker-panic supervision/readiness is separate follow-up work.

Use a rebuilt `vectornext-app:t11` API for **both** passage limits. Keep the T10 CPU processor and generator images unchanged. Preserve the [original freeze](../evals/independent/freeze.pre-parser-fix.json) and [original protocol](t11-protocol.pre-parser-fix.md); record a replacement execution freeze before the comparison and use the fresh `20261014-independent-fixed` database/cache path. Every source byte, public request, expected field, source location and scoring rule remains identical to the original freeze. The rebuilt image also packages the new README source/request; that does not affect inference.

Report this failed attempt alongside the successful comparison. Do not use any subsequent answers to change this dataset or tune the pipeline.
