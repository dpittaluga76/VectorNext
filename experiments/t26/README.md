# T26 — Automatic field planning

Read the [original protocol](protocol.md), [type-repair amendment](protocol-amendment-01.md), and [results](../../docs/reports/t26-planning.md). These are agent-authored integration checks, not independently administered quality measurements. Neither runner uses historical holdouts. Expected answers and labels never enter model requests.

`cases.json` and `input-freeze.json` preserve the first 15-case comparison. `cases-v3.json`, `live-v3.json` and `input-freeze-v3.json` preserve the separate final verification. The two manifests hash the protocols and source/question fixtures; validation never regenerates them. The synthetic one-page PDFs were generated once and visually reviewed. Their statements describe fictional equipment.

## Reproduce the final candidate

Build `vectornext-app:t26` with `docker/app.Dockerfile` and `vectornext-app-processor:t26` with `docker/app-processor.Dockerfile`. Use the existing pinned local Gemma service and verified model files. Start an **isolated** API/processor pair with new data/cache volumes; only the API mounts its database. Do not run the live check against your normal library. Example, while the normal generator is available on `vectornext_local`:

```powershell
docker run -d --name t26-check-processor --network vectornext_local --read-only --tmpfs /tmp:rw,size=1073741824 --cpus 4 --memory 6g --mount "type=bind,source=${PWD}/models,target=/models,readonly" --mount type=volume,source=t26-check-cache,target=/cache vectornext-app-processor:t26
docker run -d --name t26-check-api --network vectornext_local --read-only --tmpfs /tmp:rw,size=67108864 --cpus 2 --memory 4g --mount type=volume,source=t26-check-data,target=/storage --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/data/t26,target=/out" -e VECTORNEXT_DATA=/storage/db -e VECTORNEXT_PROCESSOR_URL=http://t26-check-processor:8090 vectornext-app:t26
docker exec t26-check-api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8088/readyz').read().decode())"
```

Create the output parent `data/t26` first. Wait for every capability to be ready, then run the two checks sequentially, with unused output paths:

```powershell
docker exec -w /checks t26-check-api python -m experiments.t26.planner_check --url http://t26-check-processor:8090 --output /out/new-planner --cases experiments/t26/cases-v3.json --freeze experiments/t26/input-freeze-v3.json
docker exec -w /checks t26-check-api python -m experiments.t26.live_check --url http://localhost:8088 --output /out/new-live --cases experiments/t26/live-v3.json --fixtures tests/fixtures/planning-v3 --freeze experiments/t26/input-freeze-v3.json --version field-planning-v3
```

The live runner requires an empty library and no existing jobs. It uploads TXT/PDF/JSON sequentially, polls acknowledged jobs, then submits each question once without fields. It keeps raw HTTP bodies, questions, durations, audit/version checks, citation/scope checks and failures. No inference retries, fallback fields, silent resume, label changes or answer-value repair. JSON values are compared as exact browser text; raw diagnostic text is retained verbatim. Aggregate refusals may come from the existing Rust guard or the local planner. The first v2 run's narrower message expectation is documented in the amendment, not retroactively changed.

For actual browser history/export verification, build `docker/ui-test.Dockerfile` as `vectornext-ui-test:t26`, then run against that prepared isolated library:

```powershell
docker run --name t26-check-browser --network container:t26-check-api -e VECTORNEXT_PLANNING_URL=http://localhost:8088 vectornext-ui-test:t26 npm run e2e -- planning-live.spec.ts
docker cp t26-check-browser:/tmp/t26-browser-diagnostics.json data/t26/browser-diagnostics.json
docker cp t26-check-browser:/tmp/t26-browser.png data/t26/browser.png
docker stop t26-check-api t26-check-processor
```

The browser test repeats integration questions to exercise real UI history, scope changes, citations, IndexedDB reload and exact export. It does not add independent quality cases. Test containers/volumes and all failed attempts are retained; stop only the explicitly named test containers. Keep outputs outside Git. Committed results preserve compact summaries and identities; original raw captures remain under ignored `data/t26/` on the measurement machine.

To debug browser assertions without repeating inference, mount a completed `live_check` capture directory and set `VECTORNEXT_PLANNING_REPLAY` to its container path. This explicitly replays captured answer bodies while retaining real library/source reads; report it separately from live-model verification. Live T26 checks use the API's bundled UI and do not start a redundant Vite preview server. The test retains raw answer attachments and applies bounded UI waits.

`regressions.json` / `regression-freeze.json` contain five previously observed T25/v2 questions for the final candidate. They use the same planner runner with `--cases` / `--freeze`, but their results are regression checks, not fresh evaluation cases.
