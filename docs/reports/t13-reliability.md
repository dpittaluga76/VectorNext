# T13: ingestion recovery and failure diagnostics

Completed 2026-10-14 using [the architecture](../architecture.md). Read the **[operational workflow report](t13-operational-workflow.md)** to see strict PDF rejection, bounded busy admission, explicit partial-text ingestion, a processor outage and recovery. [Recovery instructions](../reliability.md) document the commands and error contracts.

## Delivered

- Supervised ingestion coordinator with explicit state in readiness/job inspection. Unexpected panic or fatal coordinator error stops admission and directs the user to restart the API. The client no longer silently waits on a failed coordinator. Durable failed jobs retain explicit retry semantics.
- Hash-bound PDF extraction diagnostics visible before publication, including page warnings and the existing partial-text policy. Strict rejection remains the default; a new job ID is required to change that policy.
- Explicit `busy` admission errors and bounded CLI retries for ingestion/retry, retaining the same payload/job ID. Every rejected attempt appears in stderr and opted-in captures/reports; uncertain transport failures are not retried.
- Bounded rejected-answer diagnostics for JSON pointer and quote/value validation errors, inside an HTTP 400 error envelope. Drafts remain unvalidated, with no supported answer or formatted response. Source precision, model prompts and validation rules are unchanged.

## Verification

| Check | Result |
| --- | --- |
| Rust | 97 passed, including six new coordinator/PDF/admission/rejected-answer regressions; two subprocess helpers are invoked by their parent tests |
| Python | 90 passed: 25 workflow/client, seven new reliability, four transport and 54 evaluation/protocol/scorer checks |
| Static/deployment | Rust formatting, Clippy with warnings denied, Compose validation and both final application/processor images built |
| Fresh CPU admission | Five observed busy rejections; sixth attempt accepted the same upload, and identical reupload returned the same receipt |
| Apollo illustrated PDF | Two pages; strict rejection; explicit partial-text publication with all 48 extraction warnings retained |
| Perseverance illustrated PDF | Two pages; strict rejection; explicit partial-text publication with all four warnings retained |
| Interrupted ingestion | API killed during active ingestion; reopened at the saved Parsed stage; unavailable processor recorded as one durable failure; explicit retry completed 500 blocks/chunks |
| Integrity | Original committed Voyager revision unchanged; recovery publication and repeated upload idempotent; final generation five |
| GPU | No generation service started and no model-quality requests repeated |

The fresh drill used only the dedicated `vectornext-t13` project on port 8093. Both services are stopped; volumes, CPU caches and ignored raw captures under `data/t13/20261014-reliability/` are retained. Seven [published captures](t13-captures/) contain public-source PDF diagnostics or synthetic operational metadata; the NASA sources retain their [original attribution](../../evals/independent/README.md#source-attribution-and-reuse). The final readable report was rendered offline in Docker. [Verification metadata](t13-reliability.json) records image identities, hashes and observed outcomes.

Coordinator panic recovery is a deterministic injected Rust test: committed evidence survives, readiness/job inspection show failure, in-place restart is refused and reopening publishes pending work once. The operational drill separately tests actual process termination and CPU-service outage; it does not claim a real production panic occurred. Missing-pointer and forged-quote drafts are deterministic answer/API-envelope regressions, not fresh Gemma outputs. An initial missing Rust import and a lint finding in a test assertion were repaired before the passing checks.

## Limits and handoff

Coordinator status is process-local; restart clears it. There is no watchdog for every possible deadlock or operating-system failure, no automatic in-place recovery of poisoned locks, and no durable server-side ledger of requests rejected before job admission. Retain CLI captures for those attempts. Page diagnostics require a saved PDF artifact. Conversion failures before that boundary still have limited diagnostics. Partial-text acceptance preserves warnings; it does not improve OCR, recover illustration meaning or establish answer quality.

T11 sources, labels, requests, captures, scores and execution freezes remain unchanged. T13 intentionally extends seven files in its historical execution manifest; reproduce the old comparison using its recorded pre-T12 commit rather than rewriting its freeze. No retrieval default, model identity, prompt, PDF adapter or dataset was retuned. The next proposed task is T14 evidence coverage using new frozen validation data; the original six holdout questions remain unused.
