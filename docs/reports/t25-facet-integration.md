# T25 — Facet coverage in the local application

Implemented and activated on 2026-10-15 against [the architecture](../architecture.md). Architecture and plan were updated before runtime edits. T24 is preserved in commit `a4efed3`; its frozen examples, sources, labels and results were not changed. [Machine-readable verification](t25-facet-integration.json).

## Delivered

`facet_coverage_v1` is an opt-in strategy in the browser's **Advanced answer controls → Evidence selection**, the CLI and both answer APIs. Ranked 30/20/5 remains the default; `coverage_v1` is unchanged. The mode derives 1–4 queries from requested field names/descriptions, runs additional scoped searches, merges at most 20 candidates round-robin, and applies the tested T24 selector to at most five primaries. It excludes heading-only and substantially overlapping source spans and records every selection decision. The production copy leaves the historical experimental implementation frozen.

Source bundles, full extraction history, exact JSON materialization, pointer/type/numeric validation, immutable revisions and context-token admission remain authoritative. Facets never become evidence, filters or answer values. Unsupported budgets/field counts fail explicitly; context exclusions are recorded and neighbor expansion is disabled. The main retrieval response remains separate from auxiliary searches and the merged shortlist. [Detailed contract](../answers.md#facet-coverage-t25-opt-in).

Recorded facet queries and planned/admitted counts appear under “How did you find this?” and survive IndexedDB reloads. The complete selection audit is preserved in opaque JSON export, including on proof rejection. Browser numeric values still render as exact text. OpenAPI documents the new enum, constraints and optional workflow text fields. The strategy control resets to Ranked on reload; saved answers retain the actual recorded mode.

## Verification

| Check | Result |
| --- | --- |
| Rust | 156 checks passed across all targets, then 29 answer checks passed after adding the final null/zero/ambiguity regression: **157 total checks available**, two ignored subprocess helpers exercised by parent tests. Thirteen new checks cover the copied selector and integrated scope/history, context omissions, exact decimals, malformed reranking, unsupported budgets/fields/scope, no matches, rejected values and null/zero/ambiguity. |
| Formatting / Clippy | Rust formatting and all-target Clippy with warnings denied passed. Existing dependency future-compatibility notices for `buf_redux`/`multipart` remain. |
| Python | 62 workflow/client, reliability, processor, worker, answer, planning and scheduler checks passed offline with read-only local model files. |
| HTTP / schemas | All 71 frozen compatibility cases and five browser-boundary tests passed against an isolated API. Two OpenAPI checks validated schemas/references and real envelopes, including facet answers with exact decimals. |
| Browser / components | Type/build checks and five component tests passed. Ten offline workspace scenarios, two real-adapter/docs scenarios and one local-model browser scenario passed. Facet selection reaches the API, recorded workflow survives reload, citations open, and raw diagnostics export. Screenshot reviewed. |
| Real local models | Four fresh synthetic TXT/PDF/JSON files ingested. Six successful checks and **three automatic-planning failures** across nine distinct requests/controls; details below. |
| Activation | Built API/UI/client/admin `vectornext-app:t25`; normal app now serves it on port 8088. UI asset and OpenAPI contain the new strategy; liveness and every capability are ready. Processor/generator remain `:t18`; no model download or new service added to the normal deployment. |

The first browser test had an ambiguous locator matching both visible summary and hidden diagnostic text; the locator was narrowed, and all ten scenarios then passed. The first Python invocation omitted the model mount, causing two setup errors; the corrected offline run passed 62 tests. Initial logs are retained. No production code was changed to mask those harness failures.

## Local inference results and limits

The frozen fixtures in `tests/fixtures/facets/` describe fictional stations; they are integration controls, not a public factual benchmark. Source hashes were saved before inference, the native-text PDF was rendered and visually checked, and the original holdout and all previous evaluation captures were untouched.

| Request | Automatic field planning | Explicit-field control |
| --- | --- | --- |
| Aster opening year | Supported: 2017 | Not needed |
| Follow-up: who directs that station? | Planner declined; HTTP 400 clarification/unsupported error before retrieval | Supported: Maya Chen, same question/history |
| Aster panels and Boreal antennas, two documents | Planner declined before retrieval | Supported: 17 and 29 with separate cited documents |
| Cobalt sensor count, PDF | Planner declined before retrieval | Supported: 7, cited PDF passage/page |
| Exact JSON amount / zero / raw null | Explicit fields by protocol | Supported: `9007199254740993.00000000000001`, `0`, `null` |
| Unknown Aster builder | Explicit fields by protocol | Insufficient evidence, no factual fields |

The first attempt stopped at the follow-up planning failure. Continuations replayed already captured asks without inference and completed the remaining requests, then added explicit-field diagnostic controls. They retain all three automatic failures in their summaries and exit nonzero; controls do not replace failed outcomes. The original six checks yielded three successful outcomes and three planning failures; all three separately declared explicit-field controls succeeded. A seventh successful browser request repeated the simple opening-year workflow with actual local models.

The existing Gemma field planner is still unreliable for some follow-ups/counts. Its prompt, schema, model and decoding were not tuned on these fixtures. Explicit fields are a documented workaround, not an automatic fallback. Facet descriptions may be generic, extra CPU work costs latency, and selected passages can still be excluded by the context budget. These tests establish integration and fail-closed behavior, **not** broader answer-quality improvement or semantic completeness. T24's coverage gains do not transfer automatically to this field-derived application mode.

## Reproduction and retained artifacts

Standard Rust and frontend checks are in README. The new opt-in live check is:

```sh
python -m deployment.facet_smoke --url http://localhost:8095 --output data/t25/new-run
```

Use a fresh **isolated** API database and processor cache, the current API image and existing local models. Never point it at the normal library. It refuses existing documents unless `--resume` is explicitly supplied; the output directory must be new. The fixtures are verified, never regenerated. As measured, automatic planning failures make the command exit nonzero. `--resume data/t25/previous-run` continues that same isolated library and replays captured asks without retrying inference. It does not erase failures. The browser scenario needs that prepared library and `VECTORNEXT_FACET_URL`, then `npm run e2e -- facets-live.spec.ts` inside the Docker UI-test image.

This session used `vectornext-t25-live` and `vectornext-t25-processor` on the existing internal network, dedicated `vectornext-t25-data`/`vectornext-t25-cache` volumes, and the already running local GPU generator. The isolated processor received no database mount. The separate `vectornext-t25-contract` had networking disabled and a synthetic processor for HTTP/docs checks. All test containers are stopped/exited; volumes and every capture remain. Logs, three linked live capture directories, raw browser export, reviewed PDF render and browser screenshot are under ignored `data/t25/`.

The final app image is `sha256:f5453a0967c120747224d3987423f8488bd9a713053a14198ba52b5676646f16`. The earlier verification image differs only in packaged auxiliary files; both verified binaries have SHA-256 `1eec00897f9e280ceda2ba2907eeb30f5daceb5ecc12f58cda63373a5ad457a6`. The final UI-test image is `sha256:2281590f2a7e45c6beb1b6274d33e61a7524018652b2e7673f922decf92a6d05`.

Before upgrading the normal T19 API, its empty generation-0 storage was copied while stopped to ignored `backups/vectornext-before-t25.zip` (SHA-256 `aab64b57b1710a75d5412c3ca028874183c6316999c7d99e5cf371faed0d159c`). The previous API images remain available. T25 includes T21 checkpoints: older binaries require an untouched pre-upgrade storage copy, not just changing the image tag. Restore that copy to a **new** volume for rollback; never overwrite newer documents. See [storage compatibility](../storage.md#t21-bounded-checkpoint-stream).

The exact pre-T25 T24 execution tree is retained in `backups/t24-source-before-t25.zip`, SHA-256 `9eac7131ecdd04c1f768e1fc0bdb58431dbab4451ab06ad3d1cd7349d9d9eaf6`, including the original CRLF worker file. Current runtime sources intentionally differ from historical freezes; do not update those manifests.

Next proposed work: field-planning reliability and clear clarification outcomes, evaluated separately with new data. The selector remains opt-in while those limits and broader semantic quality are unresolved.
