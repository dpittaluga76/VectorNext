# T36 — Requested-field planning repair and fresh comparison

Authorized 2026-10-16; architecture and active task updated before implementation. Production remains Gemma 4 12B at temperature zero. This is a bounded engineering pilot, not a promotion gate or a broad model ranking.

## Change and controls

The new `nuextract3-requested-facts-v1` profile adds a versioned planner instruction: emit properties the user requests as outputs; keep supplied subject/date/location constraints in descriptions. Explicitly requested names, years and other multiple properties remain fields. Follow-ups ask only for their new requested properties. The original question/history, JSON Schema, output validation and native NuExtract template remain unchanged. No field pruning, forced single-field schema, retry or extra inference call is introduced. Bind the variant into planning audits and generation/runtime/cache identity; preserve all existing profiles and saved-job identities.

Run exactly eight new browser requests per arm (24 total), fixed order:

1. Production `12b`, temperature 0.
2. Unchanged `nuextract3-q4km`, temperature 0.2.
3. Fixed `nuextract3-requested-facts-v1`, temperature 0.2.

Both NuExtract arms use the same official Q4_K_M artifact, native adapter, sampler/runtime settings and assessment/extraction prompts. Gemma is the current production reference. No weights are downloaded, no runtime upgrade or extraction/assessment change is included. Preserve one GPU model, 4,096 context, one slot, full GPU placement, f16 KV, seed 42, cache_prompt=false, reasoning off, current budgets/deadlines, structural context and MiniLM/MiniLM ranked 30/20/5.

## Development and fresh cases

Before fresh inference, run two separate planner-only development probes: the exact observed T35 extra-field failure and an explicit three-property contrast on that same subject. Retain both raw plans and failures. The original regression must pass with only the requested count; the contrast must retain all three fields. These probes do not enter the 24-request denominator. If development needs another version, preserve the failed attempt and document it before freezing execution; never use fresh measured cases for tuning.

New synthetic fixtures comprise two TXT files, two exact JSON records and a one-page native-text PDF. The PDF is visually and textually reviewed. They describe fictional records, not real engineering instructions. Freeze sources, public requests and gold before any model sees them. Cases, in order:

| Case | Expected contract |
| --- | --- |
| constrained_count | One integer berth count; subject/month/year are identifying constraints |
| pdf_pressure | One numeric pressure; valve/cycle/plant are identifying constraints; cite final PDF pressure |
| explicit_identifiers | Three requested fields: depot name, inspection year, loading-bay count |
| followup_draft | One numeric draft using fixed source-verified prior exchange; no repeated count |
| exact_sequence | One exact integer above JavaScript's safe range; no batch/archive fields |
| missing_manual_count | Ready nonnullable integer plan; final insufficient evidence, not raw null or zero |
| unclear_subject | Explicit needs-clarification decline for an unresolved subject/property |
| aggregate_sum | Explicit unsupported decline for a cross-record computation |

Every arm receives identical scope/history and the same committed corpus, chunks, vectors and revisions, ingested once. History is supplied from the frozen request, never another model's answer. Model-generated field names are matched by predeclared kind/nullability and semantic regex in name/description, bijectively. Extra/omitted fields fail planning even if the correct requested value is also present. Match request field specifications to the returned plan. Positive answers require exact types/values, passed mechanical validation, correct outcomes, per-field citations matching committed revision/chunk/source text and the frozen fact fragments, and exact browser value-text projections. JSON uses Decimal and integer parsing, never floating conversion. The insufficient-evidence case requires empty fields. HTTP 400 is correct only for its predeclared decline reason; other errors do not count as abstention. Existing API decline envelopes do not expose the planner audit; report that limitation rather than inventing it.

## Execution, reporting and preservation

Use retained API `vectornext-app:t28-12b` and common candidate processor/generator `:t36` images. Freeze implementation/scorer files, image IDs, profiles, hashes and actual launch commands before measured requests. Separate caches per arm, recreate processes, synthetic near-full-input constrained preflight, generator restart and synthetic application warmup before each arm. Loading/preflight/warmup are outside measured latency. Fixed arm/question order and one seeded sample are limitations; no stochastic-reliability or statistical-significance claim.

Record every attempted response exactly, including failures, model audits, tokens, stage times, sampled GPU/container memory, startup/restart and source snapshots. Retain ingestion failures and preflight-blocked cases in all denominators; never retry or replace failed scored requests. Report all-request median/p95 and paired common-correct and common-supported latency separately. Report fixed versus unfixed NuExtract and fresh production Gemma; all eight outcomes must be included. nvidia-smi measures whole-device allocation, not WDDM residency.

Pause only the normal generator after confirming no unfinished ingestion; retain browsing and unrelated services. Restore the same normal generator container/configuration and verify library/jobs/readiness on success and failure. Remove only isolated experiment containers/networks; retain volumes, caches, captures, source ZIPs and all interrupted attempts. Preserve historical freezes/scores and the original unused holdout. Run focused offline planner/profile/scheduler/worker/answer/scorer tests. No Rust/API code changes require a new Rust build. Completion requires the known repair to pass, 24 fresh outcomes reported honestly, frozen identities verified and normal restoration. Any new failure is reported without tuning it away or promoting the candidate.
