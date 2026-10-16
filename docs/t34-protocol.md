# T34 — bounded Ministral / Phi / Liquid comparison

Authorized candidates: Ministral 3 8B Instruct 2512, Phi-4-mini-instruct (3.8B), and LFM2.5-1.2B-Instruct, each Q4_K_M. Fresh Gemma 4 12B QAT Q4_0 is the control. This is a small application compatibility pilot, not a broad model ranking or promotion gate.

## Frozen requests and scoring

Exactly **24 scheduled scored requests**, six per model, one pass. Select four unchanged public requests from `experiments/t32/requests.json`: `pressure_revision`, `long_exact_record`, `unknown_count`, and `pdf_correction`. They exercise TXT revision selection, an exact integer above JavaScript's safe range, unknown versus zero, and PDF evidence. Reuse both unchanged T33 browser requests/labels: `planned_piers` and `planned_followup`. The fixed preceding exchange is source-verified, identical for every model, and contains no follow-up answer. All are observed regression cases; labels are never model inputs. Freeze sources, request bytes, labels, selection and scorers before inference.

Ingest all ten unchanged T32 synthetic sources once with structural context and MiniLM/MiniLM into a fresh isolated volume, retaining every ingestion failure. All arms share the complete committed documents, chunks, vectors and revisions. Use ranked 30/20/5 and two-call assessment/extraction. Fixed arm order: Gemma, Ministral, Phi, Liquid; fixed case order. Recreate API/processor between arms and use separate CPU cache namespaces. The retained API image `:t28-12b` deliberately excludes the unactivated numeric-range repair. Build one processor and one generator image for all four arms.

Use the unchanged T32 literal-source scorer, exact Decimal values and source checks. Browser answers require one field of the expected type/value, a ready plan, exact text projection and source support. Keep frozen scores distinct from the existing T32 alternate PDF-citation exception. HTTP, transport, planning and validation failures count as failures. A failed preflight leaves all six cases blocked in the denominator, with no invented latency. Never retry a measured failure, adjust prompts after observing results, or expand the quality batch. Report paired gains/losses and medians for both all dispatched requests and common reviewed successes. Six observations give descriptive timings only; this is neither a cache-pass comparison nor a statistical claim.

## Runtime and safety

Pin revisions, sizes and SHA-256 in new generator-only locks. Ministral and Liquid artifacts are publisher-provided; Phi uses an Unsloth conversion of Microsoft's model. See the reproduction guide for provenance and licenses. The `lfm25-12b-q4km` profile denotes **1.2B**, not 12B. Text-only use requires no projector. No embedding/reranker artifacts or identities change.

Use existing llama.cpp b11617, 4,096 context, one slot, full GPU placement, f16 KV, batch 512 / ubatch 128, threads 4, temperature 0, seed 42, cache_prompt=false, disabled reasoning and existing deadlines/output budgets. Instruct variants use their embedded templates without new template options. Validate the actual launched command. Any runtime, memory or constrained-output incompatibility fails preflight; no runtime/quantization/context substitution is allowed. Liquid runs through the full GPU answer pipeline, not a new CPU-only planner route.

Before measured requests, verify artifacts, offline startup, a synthetic almost-full 3,300-token input with 768 output-token reservation and schema-constrained result, and restart. A separate synthetic application warmup after restart is excluded from latency. Capture failures, raw response bytes, model audits/tokens/stage timings, actual backend commands, startup/restart and sampled GPU/container memory. Device totals include desktop use; sampling cannot prove absence of WDDM page-outs. Windows model bind mounts and OS cache influence startup times.

## Preservation and completion

Freeze inputs, source archive/hashes, model profiles, image IDs and commands before measured calls. Fresh run names only; preserve interrupted attempts and never retry failures into success. Require normal jobs committed, then stop only `vectornext-llm-1`; keep the normal API/processor, document browsing and unrelated workloads available. Run one model at a time on internal Docker networking. Restore the original normal generator container/configuration in a finally block and verify readiness and unchanged library/jobs. Remove only experiment containers/networks, retaining all data/caches/captures.

Complete once all 24 scheduled outcomes, focused offline checks, retained errors and normal restoration are reported. Do not promote any candidate or change normal Compose/launcher defaults. Preserve historical freezes, labels, scores and the unused original holdout.
