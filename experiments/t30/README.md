# Q8 KV cache experiment

Read [the protocol](protocol.md). The experimental `12b-kv-q8` profile changes only the K/V cache types, validated alias and runtime identity. Production remains `12b`/f16 and **two-call** answering. This experiment also uses two calls, independently of the single-call experiment.

```powershell
docker image tag vectornext-app:t28 vectornext-app:t30
docker build -f experiments/t30/processor.Dockerfile -t vectornext-app-processor:t30 .
docker build -f experiments/t30/generator.Dockerfile -t vectornext-app-llm:t30 .
New-Item -ItemType Directory -Force data/t30
python -m experiments.t30.preflight --run preflight-v1
docker volume create vectornext-t30_data
docker run --rm --network none --mount type=volume,source=vectornext-t27_data,target=/original,readonly --mount type=volume,source=vectornext-t30_data,target=/destination --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/data/t30,target=/out" -w /checks --entrypoint python vectornext-app:t30 -m experiments.t28.copy_corpus --run replay-v1
python -m experiments.t30.run --run replay-v1 --freeze --preflight data/t30/preflight-v1/result.json
python -m experiments.t30.summarize data/t30/replay-v1 --output data/t30/replay-v1/summary.json
```

Proceed to the replay only after a passing preflight. Both runners temporarily stop only the idle normal generator and restore it/library afterward. They retain all captures, errors and volumes; choose new names for repetitions. The isolated API uses port 8100. Resume unattempted work only under the matching freeze, omitting `--freeze`; never retry failed measured requests into success. All original datasets/scorers/holdout remain unchanged.

Offline checks:

```powershell
docker run --rm --network none --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/models,target=/models,readonly" -w /checks --entrypoint /opt/model-env/bin/python vectornext-app-processor:t30 -m unittest experiments.t30.test_kv model_worker.test_generator_profile model_worker.test_answers model_worker.test_coverage -v
```

Do not select this experimental profile through the Windows launcher. The normal installed profile and artifact files are unchanged. The new runtime identity separates generated annotations/caches and refuses an old launch command. Larger cards and absent WDDM page-outs are not established by this test.
