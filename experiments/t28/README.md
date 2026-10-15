# T28 reproduction

Read [the protocol](protocol.md) before running. Historical T27 inputs/results remain immutable; T28 uses 12B only, 208 requests. A passing evaluation does not by itself promote the model. Results and rollout decisions belong in `docs/reports/t28-ranked-pointers.md` after execution.

Build `vectornext-app:t28` from `docker/app.Dockerfile`. Processor and generator tags `:t28` alias the unchanged, retained `:t27` image IDs; verify them against the execution manifest. The existing verified `vectornext-t27-generation-models` volume supplies both pinned artifacts read-only, with only 12B loaded. Use the existing explicit setup flow if artifacts are missing; never substitute a model. Build browser checks with `docker/ui-test.Dockerfile` as `vectornext-ui-test:t28`.

Run these commands from the repository with Python available. Choose fresh run names/output directories for repetitions; never remove old volumes or overwrite captures. The commands below reproduce the original named run and intentionally reject existing output.

```powershell
docker volume create vectornext-t28_data
docker run --rm --network none --mount type=volume,source=vectornext-t27_data,target=/original,readonly --mount type=volume,source=vectornext-t28_data,target=/destination --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/data/t28,target=/out" -w /checks --entrypoint python vectornext-app:t28 -m experiments.t28.copy_corpus --run replay-v1
python -m experiments.t28.preflight --run preflight-v1
python -m experiments.t28.application
python -m experiments.t28.run --run replay-v1 --freeze --preflight data/t28/preflight-v1/result.json
python -m experiments.t28.summarize data/t28/replay-v1 --output data/t28/replay-v1/summary.json
```

Create `data/t28` before copying. `application` uses its explicit fresh `application-v1` directory and separate T26/fresh/ranked-browser databases. To repeat it, preserve the original script/capture and declare fresh names before freezing the new execution. A fixed API port8098 and dedicated subnets10.254.29.0/24 and10.254.30.0/24 are used; resolve conflicts explicitly before running. Never change unrelated projects.

The runners check that the normal generator is idle before stopping it and restore it afterward; browsing remains available. Preflight checks full-context constrained requests/restart. The application driver runs original T26 planner/source/regression/facet-browser checks, new fixed/source checks and ranked-browser history/export, wrong-alias and outage recovery checks. Outputs retain all errors. Inspect each exit code and `result.json`; an orchestrator process exiting does not imply every nested check passed.

The regression runner refuses changed execution files/images/baseline captures and checks document snapshots before each block. It preserves original source admission failures. Completed/attempted requests are not rerun; an unknown interrupted attempt is recorded failed. To resume unattempted work under the same freeze, omit `--freeze`. Do not edit execution inputs while it runs. The source archive and raw responses remain under ignored `data/t28`.

CPU contracts:

```powershell
docker run --rm --network none --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/models,target=/models,readonly" -w /checks --entrypoint /opt/model-env/bin/python vectornext-app-processor:t28 -m unittest experiments.t28.test_contract model_worker.test_answers model_worker.test_coverage -v
docker run --rm --network none vectornext-core:t28
docker run --rm --network none vectornext-ui-test:t28 npm test
docker run --rm --network none vectornext-ui-test:t28 npm run e2e -- workspace.spec.ts
```

The fresh source fixtures are synthetic, authored for this task. They are not real station measurements or independent human adjudication. `input-freeze.json` binds their bytes, requested fields, expected answers, scorer and separate browser scenario. A pre-inference harness correction changed the legacy filter spelling to `DocumentIds`; the initial scorer/freeze are retained under `data/t28/*before-wire-fix*`. No candidate response was used for that correction.
