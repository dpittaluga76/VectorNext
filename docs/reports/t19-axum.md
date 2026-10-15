# T19: Axum API and local OpenAPI documentation

Implemented and verified 2026-10-15 against [the architecture](../architecture.md). Architecture and plan were updated before code. The migration changes the HTTP adapter; storage, retrieval, worker protocols, model configuration and historical evaluation records are unchanged. [Machine-readable verification record](t19-axum.json).

## Delivered

- Axum routes share the existing synchronous `Application`. Tokio collects bounded request bodies; `spawn_blocking` performs application work. Immediate admission remains 16 requests, and running work owns its permit after cancellation of its HTTP future. Processor lanes, deadlines, durable jobs and retry reconciliation remain unchanged.
- Explicit adapters preserve legacy routing, method failures, origin checks, required headers, body limits, multipart parsing and error envelopes. GET routes explicitly reject HEAD instead of inheriting Axum's success behavior. Unknown methods and paths retain the previous responses. Header names are compared case-insensitively, as required by HTTP.
- `utoipa-axum` registers the 18 API/health routes and collects their definitions. Schema-only definitions describe existing serialization without changing domain types. Arbitrary source data remains unconstrained; stable envelopes, field types, defaults, limits and errors have explicit schemas.
- `/openapi.json` and `/docs` serve locally. Vendored Swagger assets, a local initialization script and the existing CSP require no CDN or validator. Try it out uses this origin and the existing client header. A custom response renderer and raw download preserve exact JSON text, including `9007199254740993.00000000000001`, null and zero. The workspace links to the documentation.
- Axum 0.8.9, Tokio 1.48.0, utoipa 5.4.0, utoipa-axum 0.2.0 and utoipa-swagger-ui 9.0.2 are pinned and compiled with Rust 1.87. `tiny_http` is now a development dependency for processor stubs. The existing multipart parser is retained to preserve its field handling and rejection behavior.
- The API/client/admin image is `vectornext-app:t19`; processor and generator remain `:t18`. The Windows launcher resolves required image names from Compose instead of hard-coding the previous API version.

## Verification

| Check | Result |
| --- | --- |
| Frozen HTTP compatibility | **71 cases passed**, captured from the previous T18 release before replacing the server. Exact response bodies/status and relevant headers match. Covers routes, methods, queries, origins, malformed JSON, 64-KiB/23-MiB limits, multipart limits/duplicates/missing fields and PDF query errors. |
| Rust regressions | **122 passed**, plus two intentionally ignored subprocess helpers exercised by parent tests. Six new adapter tests cover saturation/cancelled callers with retained permits, lost upload acknowledgement/reconciliation/reopening, all answer outcomes and exact numbers, revision-checked PDFs/removal, documentation/methods, and replacement guards/atomic publication/restart identity. |
| Rust formatting / Clippy | Passed with `-D warnings`, Rust 1.87. Existing future-compatibility notices remain for multipart/buf_redux. |
| Existing Python regressions | **90 passed** for evaluation integrity, scoring, workflow reports and reliability. No fixture regeneration or model evaluation. |
| CPU worker/planner/scheduler/transport | **28 passed**, using existing local model files and synthetic generation. No GPU inference. |
| Release HTTP / OpenAPI | **5 browser boundary checks and 2 schema checks passed**. All 18 paths and schema references validated, plus actual health/readiness, library, document/job/source, search, legacy/UI answer and error envelopes. CLI health/document reads passed. |
| Frontend | Type check/production build and **5 component/history checks passed**. |
| Offline browser | **9 existing workspace scenarios passed**. **2 additional real-API scenarios passed** against the release adapter with a deterministic processor: Swagger JSON/multipart requests, exact decimal filters sent without rounding, exact displayed/downloaded response, workspace upload/planning/citation and reload. |
| Normal application | API-only recreation passed. Health and readiness passed; `/docs` returned 200 and OpenAPI contained 18 paths. Committed document listing was unchanged. Processor/generator container IDs were unchanged. Windows Start with `-NoBrowser` and Status passed without building/downloading. |

The frozen baseline is `tests/fixtures/http/t18-boundaries.json`, from commit `ae0abc41233dc194c6431d81f2478da296ca445f`. Tests never overwrite it. Isolated APIs used `--network none`, temporary databases and synthetic processor identities. Browser containers shared only that isolated network namespace, with external requests checked in the documentation test. The separate schema check used the already installed processor image. No normal documents were used for write tests.

## Observed failures and limitations

- The first documentation test exposed Swagger's numeric reformatting because the custom renderer used the wrong component name. Correcting it to `responseBody` fixed display; repeated tests verified request text, both response displays and the downloaded JSON. Authoritative data is never reconstructed from Swagger's parsed response object.
- One older HTTP test assumed title-cased header names. It now normalizes names while comparing values; the API contract itself did not change. An initial worker regression invocation omitted the read-only model mount and failed setup; the corrected invocation passed all 28 checks.
- Browser verification uses Chromium on this machine. Workspace scenarios retain their existing HTTP fixtures; the two added scenarios exercise the actual adapter and deterministic processor. PDF adapter tests use the existing frozen extraction fixture. New real OCR/Gemma quality measurements, other browser engines and a second PC were not tested.
- Disconnect ownership is tested by cancelling active router request futures while processor replies are delayed. Existing processor deadline/outage and durable recovery regressions also passed. This is not an exhaustive network fault campaign or a new performance benchmark.
- JSON schemas are maintained separately from application types to avoid changing legacy wire serialization. Coverage/reference and actual-response checks guard drift; arbitrary diagnostic/source payloads cannot be fully enumerated. Schema validation does not establish answer correctness.
- No complete slow-client connection deadline, authentication, remote hosting, streaming, storage-format change or retrieval-quality experiment was introduced. The previous browser limitations still apply. Historical T11/T14 freezes/scores and the original unused holdout remain untouched.

## Reproduce without models or GPU

Run the standard core, Python and frontend commands in README. For the isolated HTTP/browser checks, build the API and frontend test images, then run the following from the repository in PowerShell. Use an unused container name; these commands intentionally do not target the normal application or its volume.

```powershell
docker build -f docker/app.Dockerfile -t vectornext-app:t19 .
docker build -f docker/ui-test.Dockerfile -t vectornext-ui-test:t19 .
docker run -d --name vectornext-t19-check --network none --read-only --tmpfs /tmp:rw,size=268435456 --mount "type=bind,source=${PWD},target=/checks,readonly" -e VECTORNEXT_DATA=/tmp/t19-db -e VECTORNEXT_PROCESSOR_URL=http://127.0.0.1:8090 vectornext-app:t19
docker exec -e VECTORNEXT_TEST_URL=http://127.0.0.1:8088 -w /checks vectornext-t19-check python -m unittest deployment.test_http_compatibility deployment.test_browser_http -v
docker exec -d vectornext-t19-check python -u /checks/tests/http_processor.py
docker run --rm --network container:vectornext-t19-check -e VECTORNEXT_HTTP_URL=http://localhost:8088 vectornext-ui-test:t19 npm run e2e -- docs.spec.ts
docker run --rm --network container:vectornext-t19-check -e VECTORNEXT_TEST_URL=http://127.0.0.1:8088 --mount "type=bind,source=${PWD},target=/app,readonly" -w /app vectornext-app-processor:t18 /opt/model-env/bin/python -m unittest deployment.test_openapi -v
docker stop vectornext-t19-check
```

Run boundary checks on the empty database before the browser fixture. Schema checks follow the browser test, which creates `exact.json`. The last check requires the existing processor image for its JSON Schema library, but mounts no model weights and runs no inference. The temporary test database is disposable; source fixtures and logs are the reproducible evidence.

## Retained state and rollback

Final verification logs, browser screenshot and deployment checks are under ignored `data/t19/`. T19 test containers are stopped. Normal VectorNext remains running at `http://localhost:8088`, using the same storage volume and unchanged processor/generator containers. The previous API image is retained:

- T18: `sha256:7c810d751081151e7cdc71441e34c837f533df74300666e7ebe256aaff44f7e5`.
- T19: `sha256:8c0a2f04f5e3e5711194e99579ed6fa336e8987324a508cc5d6b598d39fae163`.

The browser/HTTP checks exercised the same release binary and assets as the final image; the final packaging rebuild additionally copied the launcher correction. Rollback requires only selecting `vectornext-app:t18` for the API in a Compose override and recreating that service with `--no-deps --no-build --pull never`. No storage migration is required. Retain the override while using the old API; normal Start otherwise resolves the current Compose image.

The next work to scope is candidate retrieval and clearer ambiguity evaluation on fresh data; it was not started here.
