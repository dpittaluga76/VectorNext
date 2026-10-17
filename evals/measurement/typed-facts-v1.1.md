# Typed facts, format and source proofs — D4 v1.1

Adopted **2026-10-16**, from Daniel Pittaluga's D4 amendments. This is a source-only review contract; no benchmark inference or model outputs were used. D1/D2 adjudications and D3 tiers precede the candidate. Their original artifacts remain unchanged. The candidate is **not an execution freeze**: D5–D7, six individual gold decisions, final mappings, runtime integration and adaptation/custody gates remain open.

## What is correct

The primary direct-extraction metric requires the requested fact's **string**, an explicitly allowed field layout, and the correct source location. The question's conversational wording (“amount”, “how much”) does not authorize conversion in this track. The format instruction tells every system to return the source cell spelling. Numeric JSON values, an identical value from the wrong cell, unlisted aliases and extra candidate fields fail. A pending gold is unscorable, never silently treated as correct or removed from the roster.

Each fact role records `value_string`, `source_type`, `scale` (unit, source context and upstream annotation separately), `period`, `qualifier`, `question_target`, `allowed_alternatives`, `proof_sets`, and per-case `allowed_field_mappings` at the case level. It also has separate `derived_alternatives`, `derived_proof_sets`, `imprecise_alternatives` and diagnostic rules. The [JSON schema](typed-facts.schema.json) defines this review interchange, not a new public API.

Table values remain source JSON strings. The model still emits a pointer with `value:null` as its protocol placeholder; Rust materializes the exact source value. A benchmark string rule must **not** change that into model transcription. The scored capture projection carries `type`, `value_text` and verified, source-resolved proofs; it must not trust locations invented in a raw model reply. PDF text offsets refer to the verified extracted/source-text coordinate system, not PDF binary byte offsets. The capture adapter must establish that mapping before scoring.

### Scale and units

Primary: `$1,264` or the per-case listed `$1,264 thousand`. Derived-only: the explicitly listed exact equivalents such as `$1,264,000` and `$1.264 million`, with the same source value **and evidence for the scale**. `about $1.26 million` is a declared imprecise diagnostic for 002; it is neither exact-derived nor primary credit. Do not globally accept rounding, infer unspecified multipliers, convert percents into ratios, or use binary floating point. Candidate construction uses `Decimal` to enumerate exact conversions for individually configured source-backed amount cases; inference-time scoring only compares the frozen strings.

The original cell and all source context remain recorded even when a dataset annotation disagrees. A thousand/million header cannot leak into per-share or percentage columns. Case 015's bare `0.3` remains bare. Case 064's `0.6` and `0.8` retain distinct column locations; D3 stress status remains. Cases 089/090 lack applicable scale text in the supplied source and receive **no conversion alternatives**, despite the upstream `thousand` labels. Case 116 likewise has unspecified supplied units. No outside report text is silently imported.

Scale-conversion results are a separate derived diagnostic over the *same fixed case roster*. They do not move an item between tiers according to a model's output. D3's derived/inference cases are still 004/082/088. Source-backed imprecise D2 answers for 081/097 also remain outside full credit.

## Frozen format and normalization

The [answer-format instruction](answer-format-v1.1.txt) is hashed together with the scorer, schema and gold lists. Apply its identical bytes to planning, assessment and extraction for every system and oracle arm. Preserve original question/history bytes, retrieval settings and model budgets. A type-noncompliant plan fails; do not coerce it after the fact. [Pure adapter helpers](format_contract.py) are tested, but the production worker and current benchmark runner are **not switched** to this contract by this review. Final runtime integration must prove stage audits and exact rendered prompt identities before measured requests.

The complete global floor is:

1. Unicode **NFC**, not NFKC or case folding.
2. Trim and collapse runs of ASCII space, tab, CR, LF and NBSP to one ASCII space.

No other characters are changed globally. Curly quotes, dashes, Unicode minus, currency signs, commas, scale words and case changes require enumerated per-case alternatives. Parentheses negatives `(12)`, signs, placeholders `-` / `—`, and an empty string are distinct source values; none becomes zero, null or missing. Empty strings can be accepted only as an explicit gold string with proof.

Case 054's source uses TeX-wrapped counts; its count aliases are explicitly listed. A TeX `$12$` count and a currency `$12` are **not interchangeable**. There is no table TeX-stripping rule. Cases 061/103 have explicit range-dash spellings; that does not authorize arbitrary date/identifier rewriting. No substring, fuzzy number or generic entity matching awards credit.

## Case 043: two codes

Two distinct members are required: Taihō Code and Yōrō Code. Their exact source-name/year/article variants are listed in the role. Allowed combined-string separators are `,`, `, `, `/`, ` / ` and ` and `; either order is accepted. Original full source phrases remain explicitly listed. Separate layouts `first_code`/`second_code` or `code_1`/`code_2` also accept either order. Both members require source proof.

Primary credit is **all-or-nothing**. Partial pairs, repeated members, a third candidate, unrelated extra fields, numeric types and arrays fail. Exact per-member hits are diagnostic counts only. Never use containment to reward a hedged list. No gold name such as `taiho_code` is injected into an oracle field definition.

## Unlisted variants, collisions and failure counts

Build alternatives from question/source only. An unlisted value or field mapping is wrong in primary and is retained verbatim with source/capture identity in a review queue. Before any outputs are seen, the separate sensitivity protocol is: hide system/strategy and original score from the human reviewer; show question, scoped source, candidate and frozen role; record a source-based decision and rationale; retain unresolved/non-blind reviews as such. No automatic reviewer is substituted for a blind human. Report the additional accepted count and sensitivity numerator separately on the same denominator. Until reviewed, that number is **null**, not zero. Never update primary lists from this queue.

Scan every allowed direct alternative, and each set member, against every cell in the same table and every literal whole-token occurrence in the passage/document. Inspect all 37 table cases, including non-primary ones. Equal text at a different location is a collision/review lead, not new proof. In particular 002's prior closing balance cannot prove its opening balance, 080's diluted EPS cannot prove basic EPS, and 092's net row cannot prove gross emissions. Locations are checked against the source document hash. Text matching cannot prove that all paraphrased semantic collisions have been found; a long annotated paragraph can contain multiple facts. Record that limitation and preserve the source contexts for final mapping review.

Freeze diagnostic classification separately from scoring. Ordered classes are type failure; exact value with wrong proof; exact scale conversion; listed imprecise variant; format-like nonmatch; factual-or-unlisted nonmatch. “Format-like” uses only that role's listed literal removals (e.g. `$`, commas, scale words); it may expose lossy collisions and **never grants credit**. Do not label every unlisted paraphrase factually wrong as a semantic conclusion. Field-layout failures, missing captures, model errors and unresolved gold are separate axes. Report failure subcategories as **counts**, not tiny-subgroup percentages.

## Oracle and reporting

The field-only oracle receives field names/types and source locations, never gold strings, aliases, scale-converted answers or expected outcomes. It uses the automatic arm's **identical captured evidence**, original question, model identity, retrieval settings, format instruction, scorer and gold hashes. The paired audit helper rejects a mismatch or missing stage-format audit. The resulting paired gap is a field-planning ablation, with selection-conditioned coverage reported; it is not an additive causal decomposition of all latency/errors.

A separate gold-evidence oracle changes retrieval/selection as well. Do **not** call its gap planning cost. Both preserve JSON source materialization and the production validator. Turning validation off is a diagnostic comparison of the same captured candidate, never a production answer.

Publish from the same reviewed scorer: primary direct extraction, D3 derived/inference, stress behaviors (human observations, no single-answer accuracy), and a distinct exact scale-conversion diagnostic. Keep original public v1 scoring and D1/D2 effects separate on identical captures. The new scorer does not replace historical scorers or invent v1 scores. Include roster n, unresolved n, missing captures, errors, successes and provenance support. Wilson intervals and paired/grouped comparisons belong to the full outcome report, not a ranking of a few failure categories. The original 37 tables become 33 primary, one derived and three stress under D3; even n=37 has about ±15–16 percentage points at 50%. Do not rank models from sub-10-point differences in this pilot.

## Reproducibility and remaining freeze

Run the source-only builder against the retained development audit and proposal; it verifies 116 development members, refuses sealed paths and writes into a new output directory. Original bytes/labels are not edited. Synthetic tests enumerate all accepted alternatives and set grammar outputs, assert wrong-location and formatting near-misses, and preserve pending/stress decisions. The D4 review manifest records code, prompt, schema, gold and audit hashes. A **single final Git/execution freeze** follows the remaining D5–D7/case decisions and runtime integration; a source-review hash record is not permission to run an unapproved benchmark.
