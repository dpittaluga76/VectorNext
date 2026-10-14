# T02: local model feasibility

This experiment checks model execution and resource use before the database is built. Generation runs in a CUDA container. Embedding and reranking run in a separate CPU container. All inference uses local files on a Docker internal network with no published ports. Setup downloads are explicit.

The input is T01's **supplied, verified source excerpts**, including a manually reviewed scan transcription. These checks do not perform PDF parsing/OCR, document ingestion, database search, or end-to-end RAG. Only the 13 development questions enter model prompts; the six holdout questions are excluded. Source documents shared by both splits may be used.

## Model candidates

| Role | Candidate | Encoding and limits |
| --- | --- | --- |
| Generation | [Google Gemma 4 E2B instruction-tuned QAT Q4_0](https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf) | Text-only GGUF; 4,096-token deployment context, at most 256 requested output tokens, one generation slot, thinking off |
| Embedding | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Publisher FP32 ONNX; 384 float32 dimensions; attention-mask mean pooling followed by L2 normalization; 256 tokens including special tokens |
| Reranking | [ms-marco-MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) | Publisher FP32 ONNX; paired question/passage input, 512 combined tokens including special tokens; raw relevance logits, higher is better |

The CPU models are compact English baselines, not a claim of best available retrieval quality. Queries and documents use the embedding model's same pinned WordPiece tokenizer with no extra prefixes. The reranker tokenizes question first, passage second. Batch size is bounded to 32 and CPU inference uses four threads. Oversized input is rejected rather than silently truncated. A chunking policy using this embedding candidate must fit **all** structural/generated context within 256 tokens, likely targeting roughly 200 tokens of evidence rather than 300-500.

`models.lock.json` pins repository revisions, file sizes, and SHA-256 for all 14 downloaded artifacts. It includes model cards and configuration files. The runtime uses the publishers' tokenizer files and ONNX exports; no remote model code is executed. Normalized dot product is the embedding similarity convention. Keep the full model/export/tokenizer/preprocessing identity when creating a future embedding space; switching it requires a new index generation.

## Setup and run

Requirements: Docker Desktop with Linux containers and working NVIDIA GPU access, the host NVIDIA driver, `nvidia-smi` on PATH, and Python 3.12 for the measurement driver. The database application's eventual host interface is not implemented. The host driver only orchestrates Docker and samples device memory; model inference stays inside containers.

From the repository root:

```sh
docker compose -f compose.models.yaml build llm model-check
docker compose -f compose.models.yaml run --rm model-download
docker compose -f compose.models.yaml run --rm --no-deps gpu-check
docker compose -f compose.models.yaml run --rm --no-deps model-check python -m unittest experiments.t02.test_contracts -v
python -m experiments.t02.run
```

Setup downloads about 3.53 GB of model/tokenizer/configuration files, plus images and runtime dependencies. Models live under the ignored `models/` directory, mounted read-only during inference. Downloads are checksum-verified and atomically replace a destination only after verification. Large artifacts use four bounded range-download workers and resume a contiguous partial file after network failures; every response must match the requested range and the completed file must match SHA-256. Invalid ranges or checksums discard the partial file. Downloads retry up to three times. Pass `--workers 1` to the download module for serial transfers. Existing valid files are reused. No model files are embedded in image layers or committed to Git.

The GPU check proves device visibility only. The full driver additionally requires positive GPU layer-offload logs, waits for runtime readiness, verifies all model hashes offline, runs the CPU and generation checks, tests context overflow rejection, and records results. It uses the dedicated Compose project `vectornext-t02`, recreates that project's generation service for a fresh process measurement, and stops it afterward. It does not stop other application projects.

To leave the experimental service running, use `python -m experiments.t02.run --keep-running`. To stop it:

```sh
docker compose --project-name vectornext-t02 -f compose.models.yaml stop llm
```

Rebuild after changing experiment code. Later runs use existing images and model files without internet access. `HF_HUB_OFFLINE=1`, local-only loading, llama.cpp's `--offline`, and the Docker internal network provide independent barriers to remote inference. ONNX Runtime telemetry is explicitly disabled after import; its initialization may still log an ephemeral device-ID warning on the read-only filesystem. External traffic is blocked during inference.

## Optional Gemma 4 26B A4B QAT comparison

The candidate is Google's [official 26B A4B instruction-tuned QAT Q4_0 GGUF](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf), pinned in [models.26b.lock.json](models.26b.lock.json). Its text weights add approximately **14.44 GB** on disk; CPU embedding/reranking artifacts are reused. The multimodal projector is not downloaded.

The override keeps the first 22 layers' MoE expert weights in system RAM (`--n-cpu-moe 22`) while offloading attention and remaining eligible tensors to CUDA. A positive/all-layer offload message does **not** mean all expert weights are on the GPU. Inspect the CPU/CUDA buffers and actual peak memory. This is a separate candidate configuration; the base Compose file still selects E2B.

```sh
docker compose -f compose.models.yaml -f compose.models.26b.yaml build llm model-check
docker compose -f compose.models.yaml -f compose.models.26b.yaml run --rm --no-deps model-download
docker compose -f compose.models.yaml -f compose.models.26b.yaml run --rm --no-deps model-check python -m unittest experiments.t02.test_contracts -v
python -m experiments.t02.run --variant 26b
```

The driver uses project `vectornext-t02-26b`, allows 10 minutes for readiness and 30 minutes for the suite, and stops its service afterward. Stop any earlier benchmark left running with `--keep-running` before starting another model on the same card. To stop this candidate manually:

```sh
docker compose --project-name vectornext-t02-26b -f compose.models.yaml -f compose.models.26b.yaml stop llm
```

The prompts, schema, dev questions, context/output limits, seed, thinking mode, and CPU models remain the same. Each new result includes a model-independent request hash. `experiments.t02.compare` rejects changed prompts, missing cases, different settings/datasets, or holdout usage before calculating comparison metrics. Historical E2B report hashes describe its original measured code; later configurable-model/download changes do not rewrite that evidence.

The [measured comparison](../../docs/reports/t02-gemma4-26b.md) records both 20- and 22-layer CPU placements and all remaining failures. To calculate a comparison for a new run, replace `RUN_ID` with its printed directory name and run from the repository root:

```sh
docker compose -f compose.models.yaml -f compose.models.26b.yaml run --rm --no-deps -v "${PWD}/docs/reports/t02-local-models.json:/baseline.json:ro" model-check python -m experiments.t02.compare --baseline /baseline.json --candidate /results/RUN_ID/models.json --output /results/RUN_ID/comparison.json
```

## Status-dependent output schema experiment

Both model benchmarks already use temperature **0**. The historical schema permits optional nullable fields for every status, so it also permits `{"status":"ambiguous","fields":{"goals":null},"source_ids":[]}` even though the prompt requests empty fields for non-answers.

The optional `status` schema uses three complete `oneOf` branches. Supported answers require every requested field with its original type/null allowance; ambiguous and insufficient-evidence answers require an empty fields object. It is a generation constraint plus independent response validation, not cleanup of model output. Nullable supported fields still require evidence and semantic validation: syntax alone cannot decide when null answers the question.

```sh
docker compose -f compose.models.yaml -f compose.models.26b.yaml build model-check
python -m experiments.t02.run --variant 26b --schema-mode status
```

The default `legacy` mode preserves the original comparisons. To compare a new status-schema run with the archived 26B result, replace `RUN_ID` below. This mode verifies that the model, question messages, sampling settings, dataset, and CPU models remain the same while the response schema changes:

```sh
docker compose -f compose.models.yaml -f compose.models.26b.yaml run --rm --no-deps -v "${PWD}/docs/reports/t02-gemma4-26b.json:/baseline.json:ro" model-check python -m experiments.t02.compare --comparison schema --baseline /baseline.json --candidate /results/RUN_ID/models.json --output /results/RUN_ID/comparison.json
```

The [status-schema result](../../docs/reports/t02-status-schema.md) improved exact status/fields from 10/13 to 13/13 dev questions in both passes at unchanged temperature 0. The larger probe passed; strict citation completeness remained 13/23. One resource-contended attempt was interrupted before any answer completed and is recorded separately.

## Pinned runtime

The official GHCR `server-cuda` image returned a registry `denied` response on this host. `docker/llama.Dockerfile` therefore packages the **official llama.cpp b11617 CUDA 12.8 release binaries**, verified against GitHub release SHA-256 digests, on the pinned Python/Debian base. It does not use a third-party runtime image or alter the engine design. The matching CUDA user-space libraries ship with that release; the NVIDIA driver remains on the host.

The source commit is `14310190cd0a0c831fe949ac8cbedd8abdc90695`. Base image digests, release archives, and all Python package versions are pinned. Each run records built image IDs. Debian package repositories are not a frozen snapshot, so a future image rebuild is not promised to be byte-identical. See the [official release](https://github.com/ggml-org/llama.cpp/releases/tag/b11617) and [server reference](https://github.com/ggml-org/llama.cpp/blob/b11617/tools/server/README.md).

## Measurements and interpretation

Each `data/t02/<UTC run id>/` directory contains:

- `host.json`: GPU device probe, before/after memory, sampled peak VRAM/utilization, process startup, layer offload, container/image identities, internal-network status, mounts, and peak generation-container memory.
- `models.json`: artifact/dataset identities, encoding conventions, dimensions/norms/repeatability, CPU timings and rankings, every structured response and correctness result, larger-context probe, and overflow response.
- `gpu.csv`, `server.log`, and `check.log`: supporting samples and logs.

Startup is **process-cold**, including container creation, loading, runtime warmup, and readiness polling. Model files are already downloaded, checksummed, and may be in the OS file cache. This is not a physical-disk cold-start measurement. The healthcheck runs every two seconds, so startup timing includes observation delay.

GPU memory is the **sampled whole-device total**, including the desktop and other workloads. The driver pauses 200 ms between `nvidia-smi` queries and reports the largest observed interval. Samples can miss shorter spikes; subtracting the baseline is only an approximate attribution. Container `memory.peak` includes file cache. CPU process peak RSS is reported separately.

Generation timings cover each local HTTP request through completion, including local waiting and JSON transport; preflight template/token counting is separate. Requests are serial, so this is not a concurrency or scheduler benchmark. Two passes use the same dev questions with prompt-cache reuse disabled. Report the first request, repeated-request timings, and long-context result separately. The 4,096-token limit is a tested deployment setting, not a claim about the model family's maximum context or answer reliability at that length. The harness bounds output; a future public API must enforce its own admission limits.

`technical_pass` means requests completed with schema-valid output and valid source IDs, not that the answers were correct. Expected status and typed fields, citation-set completeness, and schema validity are recorded separately. Source IDs can be valid while supporting the wrong fact. The initial gold support sets sometimes require both a full JSON record and a leaf reference; citation-set completeness is stricter than semantic support and needs separate interpretation. Do not treat it as an automated entailment judge.

Ranking probes compare dense scores and reranking over the same 22 supplied excerpts. They include no BM25, filters, real chunking, or context expansion; they are model smoke checks, not quality claims about VectorNext. No supplied gold answer is placed in a prompt. The `expected` values in evidence entries are source transcriptions, whereas answer labels are used only after inference for scoring.

The small Gemma candidate remains provisional. JSON fields should be read deterministically as designed, and all generated answers need evidence and ambiguity checks. See the [T02 result report](../../docs/reports/t02-local-models.md) for measured failures and the [build plan](../../docs/plan.md) for subsequent work.
