# Nomic / Ettin replacement pilot

**Historical deployment:** `compose.t32.yaml` has been removed from the current checkout. Deployment commands and the runner below require the recorded experiment source environment. See [configuration history and prior revision](../../docs/tasks-done.md#experiment-compose-cleanup). Frozen fixtures, manifests and results are unchanged; this pilot does not change supported application defaults.

Six fixed questions × four embedding/reranking combinations = **24 scored requests**, one pass. Read the [protocol](protocol.md) and [results](../../docs/reports/t32-replacements.md). These fictional fixtures are an author-created engineering pilot, not independent quality validation. Do not change the input freeze or extend the batch based on observed answers.

| Arm | Embedding | Reranking |
| --- | --- | --- |
| `minilm-minilm` | Current MiniLM | Current MiniLM |
| `nomic-ettin` | Nomic v1.5 | Ettin-17M |
| `nomic-minilm` | Nomic v1.5 | Current MiniLM |
| `minilm-ettin` | Current MiniLM | Ettin-17M |

Nomic uses the publisher's FP32 ONNX, 768 dimensions, masked mean → layer normalization → L2, `search_query: ` / `search_document: ` prefixes, and a tested 1,024-token cap. Ettin's ONNX is a token backbone: the pinned scoring-head weights are also required. Its published CLS → Dense → GELU → LayerNorm → Dense head runs in NumPy with raw logits. Both rerankers reject pairs above 512 tokens. Profiles, identities, preprocessing and all artifact hashes are checked; no truncation or fallback.

Publisher sources: [Nomic](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5), [Ettin](https://huggingface.co/cross-encoder/ettin-reranker-17m-v1). All weights remain under ignored `models/`. The model lock pins revisions and hashes, including Ettin's head/configuration.

## Explicit setup and checks

Run from the repository root in PowerShell. Setup downloads are explicit; subsequent inference is offline. This does not change production profiles.

```powershell
$env:VECTORNEXT_MODELS_LOCK = 'experiments/t32/models.lock.json'
python -m experiments.t02.fetch_models --models models
Remove-Item Env:VECTORNEXT_MODELS_LOCK
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t32 .
docker run --rm --network none --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/models,target=/models,readonly" -w /checks --entrypoint /opt/model-env/bin/python vectornext-app-processor:t32 -m unittest experiments.t32.test_profiles experiments.t32.test_score -v
```

## Isolated run

The original run uses retained API image `vectornext-app:t28-12b` and an already running normal `vectornext` Compose project with its 12B/f16/two-call generator. The normal network must be `vectornext_local`; the generator container must be `vectornext-llm-1`. The test processor uses a unique service alias to avoid interfering with normal processor DNS. No normal services are recreated. Readiness/library and generator/image identities are captured before execution. Close other app answer requests while measuring to avoid shared-scheduler contention.

```powershell
python -m experiments.t32.run --run fresh-pilot-name
```

Only the dedicated API/processor start, using port **8101**, fixed private subnets in `compose.t32.yaml`, fresh project volumes and no external inference network. Each embedding profile ingests the same ten sources once; its two rerankers share the exact committed snapshots. Every arm has a new process and query cache. Four separate synthetic warmups are excluded from the 24 requests and timing.

The runner refuses existing output/volumes. It never retries measured failures and does not implement automatic resume. After an interruption, preserve the entire attempt; continuation requires accounting for attempted/uncertain requests under the frozen identities, not rerunning the batch. Raw responses, attempt markers, source ZIP, execution freeze, snapshots, ingestion failures, resource samples and summary remain under `data/t32/<run>/`. Small result tables are published in the report; do not put weights or databases in Git.

Normal completion stops experiment containers and retains all volumes. If manual cleanup is needed, target the exact recorded project, without `-v`:

```powershell
docker compose -f compose.t32.yaml -p vectornext-t32-fresh-pilot-name stop
```

Frozen execution uses the saved source archive and image IDs. Git attributes preserve the exact experiment bytes, including original line endings, so a fresh checkout retains the input-freeze checksums. Later documentation or shared worker changes do not rewrite that freeze. No promotion, production re-embedding, historical quality replay or original holdout use is authorized by this runner.
