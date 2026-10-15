# T27 — Gemma 4 12B versus offloaded 26B

Read the [protocol](protocol.md) and operational amendments [01](protocol-amendment-01.md), [02](protocol-amendment-02.md), [03](protocol-amendment-03.md). These are current-runtime replays of observed T11/T14 regression sets, not historical reproductions or independent quality measurements. All original fixtures, scorers, freezes and scores remain unchanged. The original holdout is unused.

## Explicit setup

Run from the repository root in PowerShell, with Docker/NVIDIA ready and the existing verified CPU/PDF/26B models installed. The first commands download the official pinned 12B artifact (about 6.98 GB) and build optional model images. They do not promote it to default.

```powershell
docker compose -f compose.models.yaml -f compose.models.12b.yaml build model-download
docker compose -f compose.models.yaml -f compose.models.12b.yaml run --rm --no-deps model-download
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t27 .
docker build -f docker/app-llm.Dockerfile -t vectornext-app-llm:t27 .
docker build -f docker/app.Dockerfile -t vectornext-app:t27 .
```

The comparison packages the unchanged T26 API binary/UI with updated deployment files as T27; all three candidate images are identical across model arms. Keep the normal app's previous images for rollback. Prepare the dedicated Linux weight cache once (about 21.4 GB additional disk); it verifies copied bytes and refuses to overwrite corrupt/partial copies. Both models use the same cache during tests; normal models remain under `models/`.

```powershell
docker volume create vectornext-t27-generation-models
docker run --rm --network none --mount "type=bind,source=${PWD}/models,target=/source,readonly" --mount type=volume,source=vectornext-t27-generation-models,target=/cache --mount "type=bind,source=${PWD}/experiments,target=/experiments,readonly" vectornext-model-check:t27 python /experiments/t27/cache_models.py
```

Ensure ports 8097 and the dedicated subnets `10.254.27.0/24` / `10.254.28.0/24` do not conflict with other services/routes. Do not delete unrelated networks to make room. Preflight communicates with the generator over container loopback, not a published port.

## Preflight and paired run

Use Python 3.12+ for host orchestration. Choose fresh names; captures and volumes are retained. Preflight temporarily stops only `vectornext-llm-1`, leaves the normal library available, and restores the generator in its cleanup. It checks full GPU placement, context size, three constrained full-context requests and restart. Model loading/checksum time is separate from inference.

```powershell
python -m experiments.t27.preflight --run my-12b-preflight
python -m unittest experiments.t27.test_protocol -v
python -m experiments.t27.run --run my-paired-run --preflight data/t27/my-12b-preflight/result.json --freeze
python -m experiments.t27.summarize data/t27/my-paired-run --output data/t27/my-paired-run/summary.json
```

The runner refuses a failing preflight. It creates a new execution freeze, ingests each corpus once into its own fresh database, and runs all 416 calls without automatic inference retries. It restores the normal generator afterward. To resume unattempted requests, use the identical run/preflight arguments without `--freeze`; execution hashes must match. An interrupted request whose outcome is unknown becomes a recorded failure, never an automatic retry. Interrupted ingestion requires a fresh run name. Existing report paths cannot be overwritten.

Quality gates compare each case and cited support against current 26B; latency gates require >=20% improvement for ranked five in both suites/passes and on the common-success subset. Historical floors remain 8/16 and 16/28. Separate T26 planner/source/browser checks are required before promotion. A passing benchmark alone does not promote a model.

## Explicit application profiles

The verified normal default stays 26B with 22 CPU expert layers until every gate passes. To select an experimental profile explicitly, prepare its weights and images first, then use `-ModelProfile 12b`, `26b-offload22`, or `26b-gpu` with `deployment/VectorNext.ps1`. Selection is saved under ignored `data/launcher/model-profile.txt` after startup so subsequent Start/Setup/Rebuild use the same choice. `VECTORNEXT_GENERATOR_PROFILE` is an explicit environment override. Stop targets only the normal Compose project and preserves all storage. Start never builds/downloads.

```powershell
./deployment/VectorNext.ps1 -Action Setup -ModelProfile 12b
./deployment/VectorNext.ps1 -Action Start
# Restore the established profile after preparing its retained images/models:
./deployment/VectorNext.ps1 -Action Start -ModelProfile 26b-offload22
```

Direct Compose users apply `compose.app.models.yaml` after `compose.app.yaml` and set `VECTORNEXT_GENERATOR_PROFILE` consistently. The scheduler rejects aliases other than the selected profile, and the GPU launcher validates artifact and command. The full-GPU 26B model-tool override is `compose.models.26b-gpu.yaml`, applied after the base and existing 26B override. Its 16–24 GB target is unverified on this machine.

Changing generation profiles never re-embeds the library or changes stored annotations. Unfinished generated-context jobs remain bound to their original configuration: switch back to the matching profile before explicitly retrying them. Do not rewrite job policies or treat a new model's output as the old artifact identity.

Raw response text, samples and interrupted attempts are under ignored `data/t27/`. Repository reports must exclude user-library snapshots and local model weights. Neither 65–75% speedup nor a one-hour wall-clock completion is assumed.
