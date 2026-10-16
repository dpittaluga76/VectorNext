# Qwen / Granite generation pilot

Protocol: [T33](../../docs/t33-protocol.md). Eight cases per model, including Gemma control; no promotion. Synthetic sources and six original requests are reused byte-for-byte from [the previous pilot](../t32/).

Artifacts: [Unsloth Qwen3.5-9B Q4_K_M](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5) and [IBM Granite4.2-8B Q4_K_M](https://huggingface.co/ibm-granite/granite-4.2-8b-GGUF/tree/93f3f6a8938ee922b784cf4e5b4203cd3428df8f). Both are Apache-2.0; see publisher licenses/cards. Thinking controls: [Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), [IBM](https://huggingface.co/ibm-granite/granite-4.2-8b). This test preserves the app's temperature-zero non-thinking settings, not each publisher's recommended sampling recipe.

Explicit PowerShell setup (Python standard library; downloads approximately 11 GB):

```powershell
$env:VECTORNEXT_MODELS_LOCK='experiments/t33/models.qwen.lock.json'
python -m experiments.t02.fetch_models --models models
$env:VECTORNEXT_MODELS_LOCK='experiments/t33/models.granite.lock.json'
python -m experiments.t02.fetch_models --models models
Remove-Item Env:VECTORNEXT_MODELS_LOCK
docker build -f docker/app-llm.Dockerfile -t vectornext-app-llm:t33 .
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t33 .
```

Keep the retained `vectornext-app:t28-12b` image and existing MiniLM/PDF model artifacts. No API source rebuild is part of this comparison. Select experimental profiles through `T33_PROFILE` in `compose.t33.yaml`; never start it alongside the normal GPU generator.

The runner checks artifacts/frozen inputs, records normal state, stops only the normal generator, runs the comparison and restores it. Use a **fresh** run name; there is no retry/resume mode:

```powershell
python -m experiments.t33.run --run pilot-v1
python -m experiments.t33.score --run pilot-v1 --output data/t33/pilot-v1/summary.json
```

For a hard external interruption, stop only the named test project, restore the existing normal generator, then check readiness. Do not delete volumes:

```powershell
docker compose -f compose.t33.yaml -p vectornext-t33-pilot-v1 down
docker start vectornext-llm-1
python -m deployment.client ready
```

Offline focused checks (mount the repository read-only):

```powershell
docker run --rm --network none -v "${PWD}:/repo:ro" -v "${PWD}/models:/models:ro" -w /repo --entrypoint /opt/model-env/bin/python vectornext-app-processor:t33 -m unittest experiments.t33.test_profiles experiments.t33.test_score model_worker.test_generator_profile model_worker.test_answers model_worker.test_coverage model_worker.test_planning model_worker.test_scheduler model_worker.test_worker -v
```

Captures under ignored `data/t33/<run>/` retain exact responses, immutable execution freeze/source ZIP, committed corpus, preflight/startup/restart, actual backend commands, resources, failures and before/after normal state. The runner removes only its containers/networks on completion, retaining named volumes. Release an interrupted project's networks before a fresh run; the fixed isolated subnets cannot be used by two projects simultaneously. Reporting never invokes inference. Preserve frozen scores separately from the pre-existing alternate PDF-citation review. Do not regenerate source/labels during verification.
