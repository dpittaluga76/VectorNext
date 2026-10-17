# Source families and sealed reconciliation v1.3

Declared 2026-10-17 before T39 benchmark inference, incorporating Daniel's D6
amendments. This is a development review policy, not an execution approval. It
supersedes the report-level family and reserve proposals without rewriting the
frozen [D3](tiers-v1.1.md), [D4](typed-facts-v1.1.md) or
[D5](table-context-v1.2.md) artifacts.

## Identity and confidence

Trace every provisional primary case, regardless of format, and retain all 120
inspected development cases in the exposure ledger. Derived/stress exclusion does
not erase exposure. Every row binds the original document and supplied-text hashes,
format, tier, label, family, tracing method and evidence. Questions, answers and
source text are omitted from the custodian handoff.

- Financial families are **companies/filers across reports and fiscal years**.
  Keep the report's named filer, reporting year and company-plus-year key separately.
  A comparative column's year is not the report year. An unresolved reporting year
  does not invalidate an otherwise established company identity.
- Use stable regulator identifiers where available, otherwise a reviewed named
  entity key. Renames retain the same key. Do not infer aliases from spelling or
  a fuzzy string match. Record aliases and their public evidence explicitly.
- Consolidated parents and controlled subsidiaries belong to one conservative
  family. Use documented control at either source period; a merger or renamed
  successor joins predecessors when that relationship is established. Transitive
  relationships may merge multiple provisional keys. Minority investments, shared
  directors, and an asset purchase alone do not establish corporate identity;
  copied business disclosures still require an overlap check. Record unresolved
  ownership/lineage as a limitation, not a negative match. The custodian must check
  lineage on both sides, including relationships not discovered in development.
- For SQuAD, the original Wikipedia article is the family, across paragraphs and
  TXT/PDF renderings. For QASPER, use the source paper identifier, ignoring arXiv
  version suffixes. Translations, revisions and known republications stay together.
  Same topic, author or institution alone does not prove identity. Article/paper
  keys establish dataset source identity, not universal absence of reused text.

| Tier | Established claim | Use |
| --- | --- | --- |
| A | Issuer/regulator-authored report identifies the filer and matches the supplied table/context. | Established company trace; lineage still checked by custodian. |
| B | Pinned upstream article/paper identity, or explicit filer attribution in supplied material, with source reference. | Established identity at that stated scope; external report lineage may remain incomplete. |
| C | Public report search/matching clues suggest a filer but direct attribution is not sufficiently verified. | Candidate only; no separation certification. |
| U | No defensible family attribution. | Unknown; never manufacture an independent family from a table UUID. |

The registry records what was checked, including failed access or uncertain report
years. A/B are not numerical probabilities. Public report URLs are evidence links,
not immutable copies; pinned development hashes establish which text was traced.
Internal review has seen development questions; it is not a blind independent
review. No T39 outputs or sealed material are used for this trace.

## Custodian contract

Daniel Pittaluga / Architect remains the designated custodian. Generate a
development-only handoff from the complete exposure ledger. It contains family
keys, key types, known development aliases, confidence, formats and counts, plus
hashes of the exact policies/ledger. Unknown exposure counts remain visible.

Privately, the custodian must:

1. Trace every sealed candidate by the same identity/confidence rules, logging
   source references, method, report period and alias/control decisions in a
   private audit. Compare against **all exposed development families**, not just
   the eventual primary subset. Missing matches are not evidence of independence.
2. Screen every sealed candidate against D3's ordered defect taxonomy and D4's
   typed fact-role, alias, unit/scale, format and collision requirements. Apply D5's
   header/unit scopes and coordinate-proof checks to every table. Source/question
   review precedes inference; no model-dependent amendments. Pending decisions
   remain pending. Do not assume all 60 candidates are primary.
3. Keep the complete private audit and sealed identities/content under custody.
   Return only the strict aggregate receipt described by `families.py`: handoff
   and policy hashes, custodian name, counts, colliding **development** keys,
   evidence-tier totals, screening/exclusion totals and achieved primary quotas.
   No sealed identifiers, titles, questions, content, answers, aliases, per-item
   hashes, free-text findings or public private-audit paths are accepted.

The public receipt is an attestation, not an independent verification of the
custodian's private work. Its validator checks structure and arithmetic; it cannot
prove that screening happened. Refuse incomplete or mismatched receipts. Private
audit reproducibility is required, but private audit contents are never inputs to
the development tool. Do not open the sealed directory to prepare this handoff.

## Collision and uncertainty resolution

Move **every development case** in a colliding family to a separately reported
family-collision diagnostic view; preserve its prior primary/derived/stress tier
and original v1 label. This is an overlay, never an edit to the source/gold files.
Never move a sealed item into development. An unresolved development family cannot
enter the family-certified primary set. Log losses by format and label.

Report traced identity coverage separately from verified split separation.
Before a custodian receipt, cross-split verification is **pending, not zero
collisions**. With unknown sealed provenance, report noncollision only against the
established portion; do not certify whole-split independence. State both unknown
sealed and unknown development exposure counts. Remaining unresolved lineage or
alias questions prevent certification of the affected family. A receipt must
explicitly attest those checks before any full separation claim.

## Counts and clustered uncertainty

Recompute original and retained primary counts, answerable/negative counts,
format-by-label counts, family counts, largest clusters and the full cluster-size
distribution. A family spanning TXT/PDF is counted once globally and once in each
format where present; per-format family counts are not additive. Candidate/unknown
family counts are shown separately and never treated as independent observations.

For scored outcomes, use a **case-weighted percentile cluster bootstrap**: resample
the K established families with replacement K times, retaining every case of each
selected family, for 10,000 resamples with seed 3906; take empirical 2.5/97.5
percentiles. Paired strategy comparisons retain the existing paired family gate.
Failures stay in the planned denominator. Do not combine repeated model/cache
passes as independent cases. No score interval exists before outcomes exist; one
family is insufficient for an interval. Family count is not an estimate of an
independent effective sample size, and a bootstrap does not repair annotation bias.

Targets remain 150–300 primary overall, 25–30% negatives, at least 30% sealed,
and the protocol's format/family floors. Report targets and achieved counts, even
if unmet. The provisional development roster is 102 = 76 positive + 26 negative,
with 52 TXT, 17 PDF and 33 JSON/table; it is not the final denominator. Show the
loss of table coverage when family exclusions disproportionately remove tables.

## Development reserve, predeclared before inspection

**No reserve is currently selected or acquired.** A smaller reported primary set
is the default when no eligible reserve exists. This v1.3 rule adds size matching
to D3 and uses a new seed; the original proposed procedure remains historical.

Before examining reserve questions, freeze a development-only inventory with
public source IDs, hashes, established noncolliding families, original label,
format, source dataset, structure, question type and supplied-evidence byte length.
An external preparer/custodian must trace and screen reserve material by the same
source-only rules without model outputs. No sealed or original-holdout families,
unknown provenance, unchecked lineage or previously inspected items are eligible.

Match `[source, original_answerability, format, structure, question_type, size_band]`
exactly. Size is the original supplied evidence's UTF-8 bytes (not a rendered PDF's
file size): `small` <= 4,096, `medium` <= 16,384, otherwise `large`. Freeze these
strata and seed **`t39-d6-reserve-20261017-v1`** before any candidate draw. Process
excluded development IDs lexicographically; within the matching stratum sort by
SHA-256 of `seed + "\n" + compact_JSON_stratum + "\n" + case_id`, breaking ties by
case ID. Log every selected/rejected candidate and checklist reason; proceed only
in that order. Do not relax strata or choose on apparent ease. Exhaustion means a
reported shortfall. Establish noncollision before drawing; recheck the final
family inventory after replacements. No draw is authorized by the existence of
this policy alone.

## One execution freeze

Apply D1–D3 decisions → D5 source annotations → all-format family trace → private
custodian screening/check → development collision resolution and any predeclared
reserve → counts/quotas/clusters → hash and commit gold, lists, scorer, prompt,
adapter, annotations, family ledger and final split → inference. Review manifests
are intermediate provenance snapshots, not execution freezes. D7 and the six
pending primary gold decisions still require resolution. No model run or final
benchmark approval is implied by D6.
