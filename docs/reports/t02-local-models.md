# T02 local model feasibility results

Measured on 2026-10-14. Final run: `20261014T135900Z`. T02 is complete: local GPU generation, CPU embeddings/reranking, persistence, and offline operation were demonstrated. **The tested prompt/model configuration is not yet reliable enough for unattended answers.** Database implementation and retrieval-quality work remain separate tasks.

The [machine-readable record](t02-local-models.json) contains runtime identities, source-code hashes, model conventions, every response, rankings, and earlier run outcomes. Raw logs and GPU samples remain under the ignored `data/t02/20261014T135900Z/` directory. Reproduction instructions are in the [experiment guide](../../experiments/t02/README.md).

## Environment and configuration

- Windows / Docker Desktop Linux containers; Docker engine 29.6.2; NVIDIA driver 616.92.
- RTX 4060: 8,188 MiB reported by host `nvidia-smi`; AMD Ryzen 5 7600 (6 cores / 12 logical processors); approximately 64 GB host RAM.
- Official llama.cpp b11617 CUDA 12.8 binaries, commit `14310190cd0a0c831fe949ac8cbedd8abdc90695`. Packaged locally because the official GHCR image returned `denied`.
- Google Gemma 4 E2B instruction-tuned QAT Q4_0 GGUF, revision `675cff42a74c774d6cb76f76d8eacb49b48c9b93`. No multimodal projector was downloaded; this is text inference.
- Generation: 4,096-token context, 256 requested output tokens, one slot, thinking off, temperature 0, seed 42, prompt-cache reuse disabled, flash attention on, four CPU threads.
- CPU: publisher FP32 ONNX exports of `sentence-transformers/all-MiniLM-L6-v2` and `cross-encoder/ms-marco-MiniLM-L6-v2`, four threads, maximum batch 32. Exact revisions and file hashes are in [models.lock.json](../../experiments/t02/models.lock.json).
- ONNX Runtime 1.31.0, tokenizers 0.23.3, NumPy 2.5.4. All Python dependencies and the base image are pinned; Debian repositories are not frozen. Built image IDs are retained in the JSON record.

## Measured resource use and latency

| Measurement | Final run |
| --- | --- |
| Container creation to healthy | 19.62 s |
| GPU layers offloaded | 36 / 36 transformer/output layers |
| CUDA model buffer reported by runtime | 1,341.78 MiB |
| CPU-mapped model buffers reported by runtime | 1,837.50 + 315.00 MiB |
| CUDA KV buffers | 24 + 9 MiB |
| Device memory before / sampled peak / after | 1,302 / 2,857 / 1,298 MiB |
| GPU samples / largest sampling interval | 165 / 0.334 s |
| Generation-container peak memory, including file cache | 4,128,186,368 bytes, approximately 3.84 GiB |
| CPU check process peak RSS | 449,748 KiB, approximately 439 MiB |
| First short generation request | 1.147 s |
| Median across 13 first-pass short requests | 0.789 s |
| Median across 13 repeated short requests | 0.764 s |
| Embedding / reranker load, including artifact checksums | 0.999 / 0.895 s |
| Embedding 22 excerpts: first batch | 147 ms |
| Embedding 22 excerpts: three warm batches | 139 / 136 / 105 ms |
| Single-query embedding across four probes | 2.3-3.3 ms |
| Reranking 22 pairs across four probes | 163-200 ms |

The approximate device-memory increase was 1,555 MiB, but the peak is **whole-device**, including desktop activity; it is not an isolated process VRAM measurement. The model also consumes system RAM. These measurements support this specific 4K, single-request configuration fitting the PC, not arbitrary model sizes, context lengths, or concurrency.

Startup was process-cold with already-downloaded model files and an unflushed OS file cache. It includes runtime warmup and readiness-polling delay. Request timings cover local HTTP through completion; preflight token counting is separate. There were no concurrent user requests, so these numbers do not establish queueing behavior or production tail latency.

## Correctness results and failures

The model received supplied excerpts, not results from a VectorNext index. The test used 13 unique **dev** questions twice, plus one larger-context probe. Holdout questions were not used.

| Check | Result |
| --- | --- |
| Completed, schema-valid responses | 27 / 27 |
| Valid supplied source IDs | 27 / 27; empty citations are allowed for non-answers |
| Correct outcome status on short questions | 10 / 13 in each pass |
| Correct status and exact typed fields on short questions | 8 / 13 in each pass |
| Correct status and fields including repeats and larger-context probe | 16 / 27 |
| Gold citation-set completeness where defined | 14 / 23 |
| Repeated embedding maximum absolute difference | 0.0 on the measured repeat |
| Embedding dimension / L2 norms | 384 / 0.99999994-1.0 |

Observed failures:

- **Ambiguity:** when the year was omitted for Pelé versus Argentina, the model chose the 1954 match and answered 3 rather than requesting clarification.
- **Zero versus unknown:** the explicit zero goals for Iris Vega in 2021 was incorrectly treated as insufficient evidence.
- **Raw null:** a request for the stored JSON null value returned the value but classified it as insufficient evidence rather than supported.
- **Output contract:** for two genuinely unknown-count questions, the model correctly reported insufficient evidence but returned null-valued fields instead of the requested empty object. These count as strict contract failures, not fabricated numeric answers. The constrained JSON schema alone does not enforce that semantic rule.
- **Longer context:** a 3,723-input-token request with the same explicit Pelé evidence and unrelated filler completed in 1.334 s but incorrectly reported insufficient evidence. It used 59 output tokens, 3,782 total, and no cached prompt tokens. Fitting a context window does not establish reliable use of its contents.

The runtime independently rejected a 5,009-token prompt with HTTP 400 at the 4,096-token limit. The embedding and reranking wrappers also rejected oversized inputs without truncation. One earlier experiment stopped when the client guard caught 3,863 input tokens plus 256 reserved output tokens exceeding the budget; the final larger-context probe was reduced accordingly. Earlier results are summarized in the JSON record rather than discarded.

The source-ID checks establish referential validity, not factual entailment. Gold citation sets can require both a complete JSON record and a separate leaf citation, even when one source semantically contains the other. Their completeness score is therefore a strict diagnostic, not an automated factual-support judgment.

## Retrieval-role observations

The CPU models executed over the same 22 prepared excerpts. The largest embedding input was 101 tokens; reranker pair inputs reached 119 tokens. The configured limits remain 256 and 512 tokens respectively, including special tokens.

On the Iris Vega zero-goals question, dense similarity ranked a Pelé passage first; the cross-encoder moved the correct JSON record to first. For the pump table, both ranked the heading first, which alone lacks the requested row value. For the cross-page question, the two rankers favored different halves of the needed passage. These probes support keeping exact attributes, keyword search, reranking, and context assembly in the architecture. They do not measure the future combined system's recall.

## Consequences for implementation

1. Keep this runtime/model configuration as a reproducible hardware baseline. Treat generation quality as provisional; compare better prompts/models/context policies later without using the holdout set for tuning.
2. Extract explicit JSON values deterministically, as designed. Preserve zero/null/missing distinctions in storage, filters, and formatting rather than delegating them to the LLM.
3. Preserve original constraints and ambiguity checks. A schema-valid, well-cited-looking answer cannot automatically become a trusted answer.
4. Give T03 an explicit 384-dimensional normalized embedding-space identity, including the pinned export/tokenizer and preprocessing version. Keep the database compatible with other spaces rather than hard-coding this candidate.
5. Proceed to T03 persistence/contracts, then T04 retrieval. GPU feasibility is established; trustworthy end-to-end answers remain T05-T10 work.

Verification: all five T02 contract tests passed, all 14 model files verified offline, runtime logs confirmed CUDA layer offload, the final smoke driver exited 0, T01 fixture validation passed, and Compose configuration validated. Models survived fresh container creation/restarts and remained read-only during inference. The experimental generation service was stopped after testing.
