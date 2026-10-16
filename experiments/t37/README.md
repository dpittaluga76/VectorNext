# Hybrid answer integration

This bounded application check uses the eight retained cases and five source files from the NuExtract planning comparison. It does not rerun the historical large suites or use the original holdout. See the [frozen protocol](../../docs/t37-protocol.md), [results](../../docs/reports/t37-hybrid.md) and [answer-job contract](../../docs/answer-jobs.md).

## Reproduction

Prepare the two supported models through normal Setup first. Run from the repository root with Python 3.12 and Docker Desktop. The isolated project uses port 8097 and its own data/cache volumes. Stop only the normal generator before starting this project; leave its API/processor available for browsing. Do not run another GPU model alongside it.

```powershell
docker compose -f compose.app.yaml stop llm
docker compose -f compose.t37.yaml up -d --no-build --pull never
python -m experiments.t37.run freeze --run pilot-v1
python -m experiments.t37.run ingest --run pilot-v1
python -m experiments.t37.run run --run pilot-v1
python -m experiments.t37.run verify --run pilot-v1
python -m experiments.t37.run report --run pilot-v1
```

The recorded `pilot-v1` already exists locally. Never overwrite it or reuse its database for a fresh run. A repeat needs a fresh project/volumes/run name and an explicit matching runner URL/project configuration, frozen before inference. The historical source ZIP in `data/t37/pilot-v1/` preserves the exact 150-file implementation and scorer used for this run; later reporting/operational scripts are additions, not changes to that freeze. The final release has a documented two-file browser readiness/layout amendment. The original API image remains at `vectornext-app:t37-measured`; its immutable ID, unchanged processor/generator IDs and source ZIP are required for exact historical verification. Do not rewrite the old freeze to accept the current release tag. The runner sends original public requests, preserves raw response bytes and does not retry failed measurements. Resuming reconciles acknowledged IDs and skips completed captures.

The overnight PC sleep interrupted observation of Hybrid's clarification result. The original result and timing remain in the frozen summary. `python -m experiments.t37.review` creates a separate public report with that one turn excluded only from derived timing summaries; all eight cases remain in each correctness denominator. It also reads the completed drill/activation/backup captures. This post-run reporter does not alter scoring or raw captures. Summary/backup key mismatches in its first implementation were corrected without inference or capture changes.

## Separate operational drill

```powershell
python -m experiments.t37.drill
```

This explicitly kills a backend and the API **only in `vectornext-t37`**, after recording its own source hash and the candidate freeze. It checks three model transitions, queued cancellation, backend-failure fallback and interrupted API recovery without replay. It creates a separate synthetic document and records process counts. The fixed `drill-v1` output directory must be absent; retain an existing attempt and use an explicitly named new attempt if repeating. These operational questions are outside the 24 scored cases.

After capturing results, stop the isolated project without removing volumes and restore the previous normal generator until rollout is decided:

```powershell
docker compose -f compose.t37.yaml stop
docker start vectornext-llm-1
```

Model files, prior images, isolated data/caches, exact captures and interrupted attempts are retained. Follow the rollout report for backup and activation; starting the experiment does not authorize overwriting the normal database.
