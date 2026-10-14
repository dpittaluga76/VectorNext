# T02 follow-up: enforce fields by answer status

Measured on 2026-10-14. Temperature was already **0** in the E2B and 26B tests. The three remaining 26B formatting failures were allowed by the old schema. With an explicit status-dependent schema, **all 13 dev questions matched the expected status and fields in both passes**, and the larger-context probe also passed. This improves output-contract compliance; citation completeness remains unresolved.

Selected run: `20261014T145846Z`. [Complete evidence](t02-status-schema.json), [previous 26B comparison](t02-gemma4-26b.md), and [run instructions](../../experiments/t02/README.md).

## Change and controlled comparison

The new `status` schema has three complete `oneOf` branches:

- `supported`: every requested field is required, with its specified type and original null allowance.
- `ambiguous`: `fields` must be an empty object.
- `insufficient_evidence`: `fields` must be an empty object.

All branches still require status, fields, and source IDs and prohibit extra object properties. A supported raw JSON null remains allowed; a zero remains an integer. The schema cannot determine whether a nullable value answers the question or whether evidence supports it. Those remain semantic checks.

This is enforced during generation and checked independently with JSON Schema afterward. No answer cleanup, value substitution, or gold-label-driven schema was used. The schema is built from requested field names/types and the same three statuses for every question, never from its expected answer. The prompt already described these status rules and was unchanged.

The pinned llama.cpp runtime supports a subset of JSON Schema. Its [grammar documentation](https://raw.githubusercontent.com/ggml-org/llama.cpp/b11617/grammars/README.md) lists `if`/`then`/`else` as unsupported and warns against combining `properties` with `oneOf` in the same schema object. Complete separate branches avoid those limitations. All 27 runtime responses passed independent validation against the new schema.

The comparison verified all 27 request pairs, permitting **only the response schema** to change. Model artifacts, alias, CPU model identities, packages, dataset, question messages, requested fields, source excerpts, temperature 0, seed 42, thinking off, cache settings, and token limits were unchanged. The generation image and complete server command also matched the previous selected 26B run, including 22 CPU expert layers. The six holdout questions were not used.

## Results

| Measurement | Previous 26B schema | Status-dependent schema |
| --- | --- | --- |
| Correct outcome status, each pass | 13/13 | 13/13 |
| Exact status and typed fields, each pass | 10/13 | **13/13** |
| Exact outputs including repeats and larger probe | 21/27 | **27/27** |
| Schema-valid responses / valid source IDs | 27/27 | 27/27 |
| Larger-context answer | Correct | Correct |
| Strict gold citation-set completeness | 13/23 | **13/23, unchanged** |
| Median repeated short request | 4.136 s | 4.389 s |
| Larger-context request | 18.079 s | 18.507 s |

The ambiguous-match, missing-match, and unknown-assist questions now produce `{}` for fields. The explicit zero-goals question still produces `{"goals": 0}` with supported status; the raw-null request still produces `{"assists": null}` with supported status. This is observed improvement on the existing development set, not evidence of general answer reliability.

The table response still cites a row without all the header/unit context, and the cross-page response still omits a needed earlier passage. Some JSON gold sets also require redundant record/leaf references. As before, source-ID validity alone does not establish complete evidential support. T08 must address assembly and citation validation separately.

Startup was 66.87 seconds. Sampled whole-device GPU memory was 530 MiB before, 6,170 MiB peak, and 575 MiB after shutdown. Generation-container peak memory was 17,517,916,160 bytes, including file cache. Desktop GPU use was lower than in the previous comparison, so the lower total device peak must not be attributed to the schema. Timings are individual measurements under different background load, not a controlled estimate of schema overhead.

The larger probe used the same 3,727 input tokens and returned the correct year, goals, and opponent. The server still rejected a 5,013-token input with HTTP 400 at the 4,096-token limit. The final driver exited 0 and stopped the generation service.

## Interrupted first attempt

Run `20261014T145123Z` started while another workload was occupying roughly 5.3 GiB of GPU memory at about 97% utilization before this model loaded. The first response remained pending under contention. We stopped only this experiment's generation service, producing a recorded `RemoteDisconnected` error and **zero completed answers**. This was not scored as a quality result or silently discarded.

After the user requested a retry, device usage had dropped and the selected run completed. The interrupted run's metadata/error and the successful retry are both preserved in the JSON report. Other workloads were not stopped by this experiment.

## Verification and handoff

All **11 contract tests** passed, including rejection of null-valued fields on non-answers, required supported fields, correct types, valid zero/raw-null values, and a check that schema selection does not alter the question payload or leak answer labels. Comparison checks rejected an undeclared schema change and changes to temperature, model identity, or prompt. The historical E2B-to-26B comparison still verifies all 27 archived payloads.

Use `python -m experiments.t02.run --variant 26b --schema-mode status` for this experiment. The `legacy` default preserves earlier comparisons. This is an implemented experimental constraint and a tested contract for future T08 integration; the production answer pipeline is not implemented. T03 remains next and requires no running LLM. No further GPU testing is needed for unrelated storage work.
