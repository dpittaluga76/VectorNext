# Single-call answering experiment

Read [the frozen protocol](protocol.md). Production stays on two calls. The API/generator images are aliases of the retained T28 measured images; only the processor gains the explicit experimental mode. No KV quantization or new numeric validator is used in this comparison.

```powershell
docker image tag vectornext-app:t28 vectornext-app:t29
docker image tag vectornext-app-llm:t28 vectornext-app-llm:t29
docker build -f experiments/t29/processor.Dockerfile -t vectornext-app-processor:t29 .
docker volume create vectornext-t29_data
New-Item -ItemType Directory -Force data/t29
docker run --rm --network none --mount type=volume,source=vectornext-t27_data,target=/original,readonly --mount type=volume,source=vectornext-t29_data,target=/destination --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/data/t29,target=/out" -w /checks --entrypoint python vectornext-app:t29 -m experiments.t28.copy_corpus --run replay-v1
python -m experiments.t29.run --run replay-v1 --freeze --preflight data/t28/preflight-v1/result.json
python -m experiments.t29.summarize data/t29/replay-v1 --output data/t29/replay-v1/summary.json
```

Choose new names for repeated experiments; never overwrite historical captures. The old preflight is accepted only for the identical generator image/command. Port 8099 and dedicated Docker subnets are isolated from the normal app. The runner restores the idle normal generator after evaluation and checks library preservation. Resume only unattempted work under the same execution freeze by omitting `--freeze`.

Offline worker checks (existing model files mounted read-only):

```powershell
docker run --rm --network none --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/models,target=/models,readonly" -w /checks --entrypoint /opt/model-env/bin/python vectornext-app-processor:t29 -m unittest experiments.t29.test_single_call model_worker.test_answers model_worker.test_coverage -v
```
