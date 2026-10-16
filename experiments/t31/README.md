# CPU embedding profile benchmark

Read [the protocol](protocol.md). The default remains MiniLM. BGE is an explicit experimental profile with CLS pooling, L2 normalization, 512-token capacity and a query-only instruction. Its model/tokenizer/pooling/prefix/limit identity is distinct; old vectors are never relabelled or mixed.

Artifacts are pinned to [the publisher revision](https://huggingface.co/BAAI/bge-small-en-v1.5/tree/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a), which documents CLS pooling, the query instruction and ONNX use. The seven artifact hashes are in [the lock](models.bge.lock.json). The existing checksum-verified setup is explicit:

```powershell
$env:VECTORNEXT_MODELS_LOCK = 'experiments/t31/models.bge.lock.json'
python -m experiments.t02.fetch_models --models models
Remove-Item Env:VECTORNEXT_MODELS_LOCK
docker build -f experiments/t31/Dockerfile -t vectornext-embedding:t31 .
docker run --rm --network none --mount "type=bind,source=${PWD},target=/checks,readonly" --mount "type=bind,source=${PWD}/models,target=/models,readonly" -w /checks --entrypoint /opt/model-env/bin/python vectornext-embedding:t31 -m unittest experiments.t31.test_embedding model_worker.test_worker model_worker.test_answers model_worker.test_generator_profile -v
python -m experiments.t31.run --run comparison-v1
```

Choose a new name for each attempt. The runner refuses existing output/volumes and freezes source, image and input identities before measurement. It performs fresh ingestion per model/corpus, then 192 requests with counterbalanced model order and separate cold/warm caches. All inference runs offline on CPU with 2 CPUs/4 GiB; it never stops the normal app or invokes Gemma. Dataset labels are absent from the inference mount. Original source attribution, labels, scorers, freezes, captures and holdout remain unchanged.

Outputs live in `data/t31/<run>/`: source archive, manifest, per-document ingestion, exact source snapshots/vectors, per-query rankings/timings/errors, process commands and exit codes, and `summary.json`. All volumes/caches are retained. Reports distinguish literal source coverage from answer accuracy; missing-fact questions have no recall score. Model loading/worker creation is outside the per-query clock and separately recorded.

`minilm-space-before.json` is a one-time compatibility capture from the retained `vectornext-app-processor:t30` image before embedding changes. Tests only read it; they never regenerate it. A passing test verifies exact legacy space fields as well as cache separation. Query prefixes are applied by existing Rust callers before embedding; the worker must not add the prefix a second time. The 180-token target is unchanged, but actual chunk/token boundaries are recorded per profile. Larger chunks, other formats and production migration are separate experiments.
