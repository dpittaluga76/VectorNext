# Accepted six-case gold review — v1.5

User acceptance on 2026-10-17: `recommendationa accepted`, referring to the six
source-backed recommendations presented immediately before it. This is user
adjudication after an internal source review, not independent blinded approval.
No model outputs informed the recommendations or alternatives.

| Case | Accepted action | Successor treatment |
| --- | --- | --- |
| 010 | Require the complete destination set | Bukhara, Besh Baliq, Almaliq and Samarqand; order-independent; subsets/duplicates/extra candidates fail primary |
| 034 | Retain the always-YES baseline | Preserve the batches 2/3 qualification; entailment is not an interchangeable gold alternative |
| 047 | Keep the specialization/confidence answer | Remove the method-only sparse-attention alternative; bind grounding to the specialization statement |
| 053 | Identify car model, without year | Replace bare car/the car; accept the model identity, not manufacturer, individual vehicle or model-plus-year |
| 071 | Move to stress for premise ambiguity | Preserve original supported label/answers for original-label scoring; no primary accuracy contribution |
| 107 | Accept the Level A replacement direction | Keep proposed definition/rubric separate; activation still awaits two independent source reviews |

## Exact scoring rules

Use the existing D4 normalization floor and D5 value-primary/separate-grounding
scorer. No new global normalizations or application behavior are introduced.
Original labels, source bytes, requests, fixtures and D1–D7 artifacts stay immutable.

010 is a single unordered set-valued fact, represented as a string. Its four
members have their literal source spellings. The finite list accepts all orders
with comma, slash, semicolon or `and` separators; explicitly enumerate mixed final
`and` and Oxford-comma forms. Do not accept partial subsets, duplicate members,
additional candidates or unreviewed spelling aliases. Per-member completeness is
diagnostic only. Required source proof covers both the administrators and
artisans/farmers statements. This is an explicit completeness tightening from v1.

034 retains its original source phrase and adds only source-derived formulations
that preserve always-YES and batches 2/3. The canonical display wording is
`Always answer YES—the baseline used in batches 2 and 3.` The same question and
paper scope are retained; no new question is silently substituted.

047's original specialization/higher-confidence answer remains the canonical
string. No new mechanism paraphrase is added. Only the explicit specialization
statement is accepted as its proof; the removed method-only sentence cannot prove
that answer merely because it was formerly an alternative.

053's canonical string is `car model, ignoring the model year`. Source-only
alternatives are `car model`, `model of the car`, `model`, and `the model`; the last
two are literal short extractions whose proof must include the car-review and
year-exclusion statements. These are not model-output-derived alternatives. Bare
`car`, `the car`, manufacturer, individual vehicle and a model-year label do not
pass. The question asks the label category, so one example such as `Acura ILX`
alone is insufficient. Keep value and grounding diagnostics separate.

071's primary defect is `premise_or_entity_ambiguous`: the question describes an
offered plea agreement as a type of punishment. Its question and old labels stay
unchanged. Report stress behaviors under D3, not ordinary accuracy or an automatic
insufficient-evidence relabel. No replacement or twin is selected.

107's proposed answer uses the authors' own Level A definition. Preserve the
disjunction: profanity/non-acceptable language **or** a targeted offense, which
may be veiled or direct. Insults/threats/profanity are examples, not a requirement
that all occur together. Do not narrow the definition to group-directed hate
speech or replace it with a related-work catalogue. Source-derived accepted
formulations and any rubric must be frozen after the separate reviews; unforeseen
paraphrases belong to sensitivity review. This acceptance does not waive the
two-reviewer condition, attest either review or activate the replacement.

## Updated roster and downstream bindings

The development roster becomes **101 primary, 3 derived, 16 stress**. Primary is
75 positive / 26 negative and 51 TXT / 17 clean-render PDF / 33 JSON-table items.
All 120 exposed cases still participate in family/collision checks, including 071.
All six content recommendations are accepted; only 107's activation review remains
pending among these six. Gold/custody/runtime gates still prevent an execution freeze.

Recompute D6 family summaries and a newly hash-bound custodian packet; keep the
strict D6 receipt schema and all fields unset until the actual custodian returns
them. Add this policy, the successor gold and D7 control contract to the packet's
policy bindings. Old receipts must not reconcile against the new packet.

Recompute D7's candidate control roster from primary membership: 101 calls per
model, still provisional. D7's exact claim limits, question-only instruction,
response schema, negative handling and unknown-control policy remain unchanged.
TXT/PDF pairing remains absent; NASA/USGS historical views remain separate. Do not
edit the historical 102-case D6/D7 reports to conceal their former membership.

This amendment and its reproducible artifacts are a review candidate only. Final
runner/format/native-template/proof integration, actual table-budget checks,
family/custodian reconciliation and the final committed freeze remain outstanding.
