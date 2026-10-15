# T16–T18: local browser application

Implemented and verified 2026-10-15. The architecture and build plan were updated before implementation. [Browser contract](../browser-api.md) · [Verification record](t16-t18-local-app.json) · [Actual local-model browser capture](../assets/workspace.png).

## Delivered

- **T16:** additive same-origin browser API, bounded multipart TXT/PDF/JSON uploads, UUID-derived identities, optional filename metadata with unchanged absent-field serialization, pre-acknowledgement reconciliation, revision-safe changes, compact library/source projections and original PDF access. Automatic Gemma field planning feeds the existing extraction/validation pipeline; explicit fields bypass it. Exact values and raw reports cross the browser boundary as text. Existing CLI contracts remain available.
- **T17:** React/TypeScript/Vite with locally generated shadcn/ui Button/Dialog components. Library, conversation and evidence panels; drag/drop, explicit retries, replace/remove confirmation, passage browsing, source links, light/dark themes, recorded workflow details, advanced controls and browser-only IndexedDB history/export/clear. Four complete supported exchanges form the visible context window. Captured evidence retains its original revision. The Docker API image contains all runtime frontend assets.
- **T18:** Windows menu and direct-start command files plus PowerShell Setup/Start/Rebuild/Stop/Status. Setup invokes existing verified model preparation. Start reuses local artifacts with `--no-build --pull never` and opens the browser after API liveness, while capability readiness remains visible. Stop targets only the normal Compose project and keeps volumes. README and repository handoff now describe browser use.

## Verification

| Check | Result |
| --- | --- |
| Rust regressions | **116 passed**, plus two intentionally ignored subprocess helpers invoked by parent tests. Includes eight new browser-contract checks. |
| Rust formatting / Clippy | Passed; lint uses `-D warnings`. The existing pinned toolchain accepts the multipart parser; Cargo reports future-compatibility notices for multipart/buf_redux. |
| Existing Python evaluation/report/reliability checks | **90 passed**. |
| Model-worker/planner/scheduler/transport checks | **28 passed**, including two new planner checks. |
| HTTP boundary checks against the running Docker API | **5 passed**, including origins/rebinding headers, old CLI reads, static paths, custom headers, oversized JSON/multipart, missing files and invalid question/history/scope inputs. |
| Frontend | Type check and production build passed; **5 component/history/storage checks passed** in Docker. |
| Browser workflows without external networking | **9 Playwright tests passed**: sequential three-format upload, replacement/removal confirmation, exact rendering/export, reload, history clear, all-passage browsing, delayed PDF preparation, bounded busy retry identity, lost acknowledgement, model outage, storage failure, keyboard interaction, narrow layout and safe untrusted text rendering. |
| Production browser with actual local Gemma | **1 end-to-end scenario passed**: multipart TXT upload, ordinary launch-year question, follow-up, citations, reload/history, advanced exact decimal/null/zero question and current PDF source access. No browser API mocks in this scenario. |
| Windows launcher | Setup with reused/checksummed model files, Start, Rebuild, Stop, Status and command-file Start all completed. Direct Start issued the browser-open action. Stop preserved normal/test volumes and left unrelated workloads running. |

The GPU/API checks used a fresh `vectornext-t18` project on port 8098. Real TXT, generated text PDF and JSON versions of attributed Apollo 11 facts were ingested. Real Gemma returned **1969**, **Neil Armstrong**, **1969** from PDF, and crew count **3** from JSON using automatic fields. Explicit fields preserved `9007199254740993.00000000000001`, stored null and zero. Browser rendering and reload preserved those literals. A missing launch-mass field returned `insufficient_evidence`. Revision mismatch, replacement/removal, old source rejection and original-PDF rejection after removal passed. With Gemma stopped, document browsing stayed available and the library was unchanged.

## Observed failures and limits

- The first smoke harness expected a lowercase job stage; the existing contract uses `Committed`. The harness was fixed, and its initial capture was retained. No model answers ran in that attempt.
- Automatic planning declined “What was the ticket price for Apollo 11?” with a readable 400 response. It did not fabricate a value. The harness had incorrectly required an evidence-stage abstention for that question. Its capture remains; a separate explicit-field missing-mass check verified evidence abstention without changing prompts to fit the example. Planning can decline questions before retrieval; Advanced fields provide a bypass.
- Docker's network address pool was exhausted during the first normal startup. Only this session's stopped `vectornext-t18` containers/networks were removed to release two ranges; its data/cache volumes and all captures were retained. Normal startup and a complete repeated Setup then passed. No global prune or historical evaluation cleanup was used.
- Setup was exercised with previously downloaded artifacts and checksum verification, not a new 14.44-GB transfer. Existing download paths were already tested in T02/T06. Browser tests use Chromium; other browser engines and a different PC were not tested. Offline browser checks disable container networking; production GPU/processor services retain their internal-only networks. The host network adapter was not disabled.
- Conversations are local to a browser origin/profile; private mode, clearing site data or quota failures can remove/prevent persistence. Concurrent tabs do not merge workspace saves. Export before clearing or moving profiles.
- A saved failed ingestion job remains unfinished and blocks changes to that document until resolved. There is no cancellation/abandonment endpoint; a permanently invalid replacement needs a future recovery feature. This preserves the approved unfinished-job guard and existing job semantics.
- The model remains fallible. These small operational fixtures are not a fresh quality benchmark. Mechanical source validation does not prove semantic correctness. Corpus aggregation, remote authentication, token streaming, integrated PDF highlighting, automatic schema/pointer inference beyond field definitions and retrieval-quality experiments remain outside this work.

## Reproduction and retained state

Use the standard core build/test instructions in README. Frontend checks:

```sh
docker build -f docker/ui-test.Dockerfile -t vectornext-ui-test:t18 .
docker run --rm --network none vectornext-ui-test:t18 npm test
docker run --rm --network none --ipc=host vectornext-ui-test:t18 npm run e2e -- workspace.spec.ts
```

Live checks are explicit opt-in: `deployment.ui_smoke` needs an isolated running deployment and a new capture directory; `e2e/live.spec.ts` needs `VECTORNEXT_LIVE_URL` and the `tests/fixtures/ui` directory mounted at `/fixtures`. The live browser test uses a loopback proxy inside its test container to reach the production API. Its requests and assets reach only that local app. Fixtures are never regenerated by tests. The smoke runner's `--resume` continues the final integrity checks from the retained five successful answers, without repeating those inference calls.

Local captures are retained under `data/t18/20261015-live-01`, `-02`, `-03`, `frontend/test-results-live`, and `data/t18/launcher-*.log`. The verification JSON records image identities, source/capture hashes, live answer outcomes and test totals. `vectornext-t18_data` and `vectornext-t18_cache` remain; its containers/networks were removed as described above. The normal `vectornext` application is running at `http://localhost:8088` after launcher verification, ready for the user. Normal user-facing data starts empty.

Historical T11/T14 datasets, protocols, scores, manifests and captures were not edited. The pre-T15 source archive still hashes to `dc1d839dd53a226cfbee820cfe45aa4e773a9845be13f8d4c211b1c6cadcedca`. Historical execution freezes intentionally differ from this new runtime. The original six holdout questions remain unused.
