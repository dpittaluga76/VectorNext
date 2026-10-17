# Internal pilot runtime integration — 2026-10-17

The isolated runner now connects the reviewed successor package to structural
ingestion, immutable document snapshots, ordinary NuExtract questions, exact
durable-job captures, frozen typed/coordinate scorers, question-only controls and
both supported models' oracle interventions. The original independently gated
runners remain unchanged. See the [execution amendment](../../evals/measurement/internal-execution-v1.8.md)
and [run guide](../../evals/measurement/internal-runtime-guide.md).

New source and policy are committed before measured requests. A separate execution
receipt will bind the completed ingestion, private oracle inputs, actual image
IDs and source hashes. No candidate-model inference has occurred at this checkpoint.
The source review's exposed-candidate, incomplete-lineage and sample-size limits
remain in force. Defaults remain NuExtract and ranked 30/20/5.

Verification at this checkpoint:

- 180 offline Linux measurement tests pass, including lost-submission
  reconciliation, direct-call uncertainty without replay, source-coordinate
  coverage, strict original-label matching and oracle budget failure.
- The Rust main suite and new measurement helpers passed; formatting and Clippy
  passed. The all-target run encountered the HTTP admission timing test's
  three-second startup bound during concurrent build/ingestion work. Its focused
  rerun passed unchanged (0.09 seconds). Both logs are retained; the initial run
  is not reported as an entirely green all-target invocation.
- The production API image was rebuilt; the current app continues using its
  existing container and library. Two supported weights/runtime profiles remain
  unchanged; no downloads or historical quality reruns were performed.
- Synthetic preflight exposed two runner wiring defects: multiline processor
  frames and a background/interactive lease mismatch. Both were fixed before
  benchmark inference; failed preflight captures remain. A question-only control
  and a supported two-call synthetic answer then completed successfully.
- CPU prefix-count wire capture was reduced to aggregate counts/time before
  freezing. Full reranking/generation captures remain. The isolated processor
  restarted at a completed-document boundary; no normal service was changed.
- Historical review hashes remain valid. Private candidate IDs do not occur in
  the new public files. Runtime packages, sources, captures and databases remain
  ignored by Git.

Local logs: `tmp/t39-runtime-core.log`, `tmp/t39-runtime-core-followup.log`,
`tmp/t39-runtime-python-freeze.log`, `tmp/t39-runtime-ingestion.log` and
`tmp/t39-execution-20261017/preflight/`. Ingestion admission failures remain in the
frozen denominator; later results must enumerate them, not retry them into success.
