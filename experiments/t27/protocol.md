# T27: current-runtime 12B versus offloaded 26B

Adopted before inference, 2026-10-15. Depends on T26. This reuses observed regression data; it is not independent quality validation. Historical T11/T14 execution freezes, scores, sources, annotations and original holdout are unchanged.

## Preflight and profiles

The candidate is Google's Gemma 4 12B QAT Q4_0 at revision `29d097773436b69ff9feafd636ab4cf873786537`, SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`. Use pinned llama.cpp b11617, full GPU placement, 4,096 tokens, one slot, batch 512/ubatch 128, temperature zero, seed 42, reasoning off. No quantization/context/runtime fallback. The control keeps 26B with 22 CPU expert layers; embeddings, reranker, prompts, retrieval and proof validation stay unchanged. The optional all-GPU 26B profile is not measured on this 8 GB GPU.

Download explicitly and verify size/hash. Start the candidate alone on the GPU; inspect allocation and full-context constrained output, repeat requests and restart. Retain all startup failures and device/process samples. Insufficient memory/runtime incompatibility ends measured evaluation before any benchmark request, retaining 26B as default. No model accuracy/latency score can be inferred from a failed preflight. Normal document browsing remains available while only its generator is stopped; restore that generator after the test in a finally block. Leave unrelated workloads alone.

## Paired comparison, conditional on passing preflight

Freeze current execution files, model/runtime hashes, resolved Compose and image IDs before measured requests. Fresh T27 storage/capture/cache paths only; never overwrite attempts. Ingest each corpus once with structural context and preserve exact committed documents/revisions for both arms. Frozen source failures remain in denominators. Only public requests reach the model; labels/scorers remain host-side.

T14 preserves five-cold, two-cold, coverage-cold, coverage-warm, two-warm, five-warm (16 questions each). T11 preserves five-cold, two-cold, two-warm, five-warm (28 questions each). Pair each block by model, 26B first on even block indices and 12B first on odd indices. That totals 192 T14 plus 224 T11 calls, 416 overall. Run T14 then T11. Process fixed public question order; do not tune, retry failed measured requests, or drop errors. Resume only unattempted requests with identical frozen identities; record uncertain interrupted requests as failed.

Recreate API/processor each block; isolate persisted caches by corpus/model/strategy. Empty caches define cold, reused caches define warm; OS caches are uncontrolled. Run one generator at a time, with a separate synthetic warmup after every load. Exclude loading/warmup from query latency, report them separately. Capture original response bytes, exact values, score, model audit, tokens, stage timing, end-to-end time and sampled GPU/container RAM. Preserve raw rejected reports. Source-review exceptions stay separate from frozen scores.

## Predeclared gates

Require no lost correct control case or associated validated source support across every strategy/pass. Preserve correct negative cases and introduce no newly falsely supported negative. Ranked-five floors in both passes: T14 >=8/16, T11 >=16/28. Require >=20% lower median end-to-end time for ranked five in each suite/pass, both all planned requests and the common HTTP-success subset; an empty subset fails the gate. Report p95 and all variants without selecting favorable groups. Evaluate the suggested 65–75% speedup only as a hypothesis. Repeated calls are not independent questions; deterministic settings do not guarantee bitwise GPU determinism.

Separately require T26 final 12 planner, eight source-backed and five observed-regression cases plus live browser follow-up/exact-value/export checks. Relevant Python/Rust/HTTP/offline-browser checks cover profile identities, cache separation, aliases, corrupt artifacts, outages and rollback. Any failed gate keeps 26B default and marks 12B experimental. Completion means an auditable gate decision, not a required improvement. No deployment promotion follows a failed preflight.

## Artifacts and publication

Retain ignored raw captures/data under `data/t27/` and dedicated project volumes; committed reports contain only public/synthetic evidence and reproducible commands. The pre-T27 source is `backups/t26-source-before-t27.zip`, SHA-256 `37ba46b6b378df1a39e485edcbf3e8f3a59fbb1487a34c44a2dbbf7771a84888`, from commit `85831167307b5b6d7f9fad0a6f6364c97858bdf6`. Preserve prior runtime images and models. Update architecture/plan/README/handoff with actual executed checks, limitations and next steps; never mark unexecuted work passed.
