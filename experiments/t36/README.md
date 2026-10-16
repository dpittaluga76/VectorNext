# Requested-field planning pilot

See [protocol](../../docs/t36-protocol.md). Eight fresh questions, three arms, 24 measured requests. Production defaults remain unchanged. The new profile only adds planner instructions separating requested properties from identifying constraints; it does not remove fields after generation.

From the repository root, with the already verified Gemma/NuExtract artifacts installed:

```powershell
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t36 .
docker build -f docker/app-llm.Dockerfile -t vectornext-app-llm:t36 .
docker run --rm --network none -v "${PWD}:/repo:ro" -w /repo --entrypoint /opt/model-env/bin/python vectornext-app-processor:t36 -m unittest experiments.t36.test_planning experiments.t36.test_score model_worker.test_planning -v
python -m experiments.t36.development --run development-v1
python -m experiments.t36.run --run pilot-v1
python -m experiments.t36.report --run pilot-v1 --output docs/reports/t36-planning.json
```

Use a new run name for every authorized repeat. These scripts temporarily stop only the normal generator, start isolated services on port 8105, restore the original container/library/jobs, and retain data and caches. Development invokes exactly two known planner probes before the fresh comparison. Failed probes are retained and block fresh inference. The full comparison uses original NuExtract, the fixed experimental profile and production Gemma at temperature zero. Do not run both scripts simultaneously; both use the same isolated network ranges and port.

`input-freeze.json` locks the five synthetic source files, source manifest, public requests, labels and development probes. Tests never regenerate them. `data/t36/<run>/` retains source ZIP/execution freeze, actual commands, corpus, exact raw responses, audits, resources and restoration checks. New fixtures contain fictional records; the PDF has been visually checked and is native text. The original historical holdout and evaluations are unused. No production profile switch is performed.
