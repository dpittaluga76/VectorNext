# Ministral / Phi / Liquid generation pilot

[Protocol](../../docs/t34-protocol.md): six cases per model, including a fresh Gemma 4 12B control; 24 scored requests total, no promotion. All sources and requests reuse observed regressions from [T32](../t32/) and [T33](../t33/).

Pinned artifacts:

| Candidate | Export | Provenance |
| --- | --- | --- |
| Ministral 3 8B Instruct 2512 | Q4_K_M, 5.20 GB | [Official Mistral GGUF](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF/tree/0102285ad796bd99af90f58de616092e5630e970), Apache-2.0 |
| Phi-4-mini-instruct, 3.8B | Q4_K_M, 2.49 GB | [Unsloth GGUF](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF/tree/78eb92a46fc37e6b524df991ed9aca9bc6aa7b80) of [Microsoft's model](https://huggingface.co/microsoft/Phi-4-mini-instruct), MIT |
| LFM2.5-1.2B-Instruct | Q4_K_M, 0.73 GB | [Official Liquid GGUF](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/tree/8ed288026e23958ad9dfa92d53ed773a8eee7125), LFM Open License v1.0; review publisher terms |

The profile `lfm25-12b-q4km` means **1.2B**, not 12B. Its CPU-planner potential is not measured here: every candidate uses the same complete GPU generation pipeline. This preserves the application's sampling settings, rather than benchmarking publisher-specific recommendations.

Explicit PowerShell setup (approximately 8.42 GB of additional downloads; SHA-256 verified):

```powershell
$env:VECTORNEXT_MODELS_LOCK='experiments/t34/models.ministral.lock.json'
python -m experiments.t02.fetch_models --models models
$env:VECTORNEXT_MODELS_LOCK='experiments/t34/models.phi.lock.json'
python -m experiments.t02.fetch_models --models models
$env:VECTORNEXT_MODELS_LOCK='experiments/t34/models.lfm.lock.json'
python -m experiments.t02.fetch_models --models models
Remove-Item Env:VECTORNEXT_MODELS_LOCK
docker build -f docker/app-llm.Dockerfile -t vectornext-app-llm:t34 .
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t34 .
```

Keep the retained `vectornext-app:t28-12b` image and existing Gemma/MiniLM/PDF artifacts. No API rebuild or normal activation is part of this pilot. Experimental selection uses `T34_PROFILE` in `compose.t34.yaml`; never start a second GPU service alongside the normal generator.

Run from the repository root with a **fresh** run name. The runner stops only the normal generator, performs the comparison, and restores it:

```powershell
python -m experiments.t34.run --run pilot-v1
python -m experiments.t34.report --run pilot-v1 --output data/t34/pilot-v1/summary.json
```

The completed results and preflight failures are in the [report](../../docs/reports/t34-generators.md). The original frozen `score.py` fails on text-free rejected-answer metadata; use `report.py`, as documented in the [reporting addendum](../../docs/t34-reporting-addendum.md). This README command was corrected after the run; the execution ZIP preserves its original text.

After a hard external interruption, stop only the actual test project, restore the existing normal generator and check readiness; retain volumes:

```powershell
docker compose -f compose.t34.yaml -p vectornext-t34-pilot-v1 down
docker start vectornext-llm-1
python -m deployment.client ready
```

Offline checks:

```powershell
docker run --rm --network none -v "${PWD}:/repo:ro" -v "${PWD}/models:/models:ro" -w /repo --entrypoint /opt/model-env/bin/python vectornext-app-processor:t34 -m unittest experiments.t34.test_profiles experiments.t34.test_score experiments.t34.test_report model_worker.test_generator_profile model_worker.test_answers model_worker.test_coverage model_worker.test_planning model_worker.test_scheduler model_worker.test_worker -v
```

Ignored `data/t34/<run>/` retains exact responses, request attempts, immutable source ZIP/execution freeze, committed corpus, startup/restart/preflight, actual commands, sampled resources, failures and normal before/after state. Reporting invokes no inference. Containers/networks are removed on completion, but volumes are retained. Release an interrupted project's fixed subnets before a fresh run. Preserve frozen scoring separately from the pre-existing alternate PDF-citation review; never regenerate source/labels during checks.
