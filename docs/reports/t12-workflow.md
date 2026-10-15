# T12: human-readable workflow debugging

Completed 2026-10-14. Start with **[the Voyager workflow report](t12-voyager-workflow.md)**. It was generated from a fresh local Docker run that ingested the attributed NASA source, searched it and answered with Gemma 4 26B. [Failure examples](t12-failure-workflows.md) show saved T11 ambiguity, insufficient-evidence, rejected-pointer and PDF-admission outcomes.

## Delivered

`deployment/workflow.py` renders recorded operations into concise Markdown: document preparation, chunking/context, embeddings/storage, search and reranking, selected evidence, answerability, extraction, validation and presentation. Source excerpts stay bounded; source locations, numeric precision and value types remain visible. No extra LLM call narrates the workflow.

`deployment/client.py` adds `--explain`, `--report`, `--capture` and the offline `explain` command. Existing JSON stdout remains byte-for-byte server output unless `--explain` is requested. Reports/captures refuse existing output paths. A completed ingestion report optionally reads the matching committed document to obtain counts, model identity and quality details; it rejects a newer revision as evidence for the earlier job. HTTP/transport and job failures retain failure exit status.

Read [the usage guide](../workflow-debugging.md) for Docker and host commands. These changes follow the workflow-report scope in [the architecture](../architecture.md#human-readable-workflow-reports--t12-implemented). Storage, search, model configuration, prompts, answer validation and the 30/20/5 defaults are unchanged.

## Verification

| Check | Observed result |
| --- | --- |
| Offline software checks | 83 passed after the invocation extension: 25 workflow/client checks, four existing transport checks, 54 existing evaluation checks; initial implementation passed 78 |
| Fresh ingestion | NASA Voyager TXT committed; 86 blocks, 25 chunks, structural context and real MiniLM embeddings |
| Fresh standalone search | Three requested results, with original source locations and excerpts |
| Fresh local-model answer | `Voyager 1 \| Launch: 1977 \| Jupiter: 1979 \| Saturn: 1980` |
| Client elapsed times | Ingestion 1.537 s; search 0.018 s; answer 33.499 s. Model/service startup was separate: 123.010 s |
| Offline combined report | Generated in the Docker client with networking disabled and all application services stopped |
| Retained non-answer/failure responses | Ambiguous Voyager, missing numeric station distance, missing JSON pointer and rejected partial Apollo PDF rendered without invented success |

The single live answer request performs the existing assessment and extraction calls. It is a reporting drill, not another quality benchmark. Raw JSON stdout matched the saved capture response; neither the capture format nor the renderer round-trips exact answer numbers through floats. The final Markdown was regenerated from the same captures after small presentation fixes, without repeating inference.

The follow-up requested commands or high-level function calls. New captures now retain the client argument list, and reports show an equivalent Python invocation, API handler and stage implementation references. The three published Voyager envelopes were enriched with operation arguments from the original saved run record, explicitly labeled as recovered and omitting report/capture switches. Their exact response strings and the original ignored drill files remain unchanged; older failure captures explicitly say their invocation was not recorded. Both published reports were regenerated in Docker with networking disabled and no new inference. Code references are a current implementation guide, not measured call-stack events. Disabled reranking is now correctly labeled skipped. Five additional regressions plus the expanded CLI round-trip check cover these behaviors.

An initial retained-case check assumed the null-distance case reached field extraction; its audit actually shows abstention during assessment. The review was corrected to assert the recorded insufficient-evidence outcome. A subsequent literal-message assertion was corrected to the actual API wording. No source, answer or scoring rule was changed.

All three dedicated `vectornext-t12` services are stopped. Its database/cache volumes and ignored raw captures under `data/t12/20261014-workflow/` remain available; earlier projects were untouched. The seven [published captures](t12-captures/) contain public NASA/USGS evidence, covered by the [source attribution and reuse notes](../../evals/independent/README.md#source-attribution-and-reuse). [Machine-readable verification](t12-workflow.json) records images, hashes, commands and source provenance.

## Limits and handoff

Ingestion steps are reconstructed from the durable job state, not a fine-grained event timeline. Stage durations, embedding/reranking cache hits and missing HTTP-error traces are explicitly unrecorded. The last saved job stage does not diagnose a crashed coordinator. PDF illustrations, retry/recovery and rejected-draft diagnostics remain T13. Reporting adds no facts to a model answer and does not automatically establish semantic correctness.

T11 sources, questions, labels, captures and scorer remain unchanged. T12 intentionally extends `deployment/client.py`, one of T11's frozen execution files. The original execution freeze is preserved and correctly rejects the newer code. Reproduce the historical comparison from commit `aed598c336477b184a25c86e17cf63136ff88fdd` in a separate checkout rather than rewriting the freeze. New quality work remains T14, after T13.
