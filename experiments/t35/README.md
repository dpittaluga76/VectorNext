# Published temperatures and NuExtract3

[Protocol](../../docs/t35-protocol.md): 24 scheduled requests, six per model. Experimental profiles: `12b-temp1`, `qwen35-9b-temp07`, `granite42-8b-temp1`, `nuextract3-q4km`. Production defaults stay unchanged. Temperatures are 1.0 / 0.7 / 1.0 / 0.2; this does not apply every publisher sampler recommendation.

Official [NuExtract3 GGUF](https://huggingface.co/numind/NuExtract3-GGUF/tree/28a1aae6288c5d50bdf999ca2e572240966d669b), Apache-2.0, requires one additional 2.78 GB checksum-verified download. Existing Gemma/Qwen/Granite/MiniLM/PDF artifacts are reused. PowerShell, repository root:

```powershell
$env:VECTORNEXT_MODELS_LOCK='experiments/t35/models.nuextract.lock.json'
python -m experiments.t02.fetch_models --models models
Remove-Item Env:VECTORNEXT_MODELS_LOCK
docker build -f docker/app-llm.Dockerfile -t vectornext-app-llm:t35 .
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t35 .
docker run --rm --network none -v "${PWD}:/repo:ro" -v "${PWD}/models:/models:ro" -w /repo --entrypoint /opt/model-env/bin/python vectornext-app-processor:t35 -m unittest experiments.t35.test_profiles experiments.t35.test_score experiments.t34.test_report model_worker.test_generator_profile model_worker.test_answers model_worker.test_coverage model_worker.test_planning model_worker.test_scheduler model_worker.test_worker -v
python -m experiments.t35.run --run pilot-v1
python -m experiments.t35.report --run pilot-v1 --output data/t35/pilot-v1/summary.json
```

Use a fresh run name. The runner stops/restores only the normal generator and owns isolated services on port 8104. Never manually start a second GPU model alongside the normal generator. Normal data is not mounted by the experiment; captures and corpus/cache volumes remain after cleanup. Reporting uses no inference. The NuExtract adapter supplies native template guidance while retaining the application's hard schema and validation; see protocol limitations.

After a hard interruption, retain volumes and restore the normal generator:

```powershell
docker compose -f compose.t35.yaml -p vectornext-t35-pilot-v1 down
docker start vectornext-llm-1
python -m deployment.client ready
```
