# Table context and coordinate grounding, v1.2

Adopted 2026-10-16, before any benchmark inference. This is a development-only
review candidate under T39/D5, not an execution approval or production change.
The original proposal, D1–D4 artifacts and sealed material remain unchanged.

## Annotation is interpretation

Every one of the 32 development tables receives a source-only, versioned annotation
in `table-annotations-v1.2.json`. Captions, column headers, unit rows, body headings,
data and blank rows are explicitly classified. Numeric years can be headers; text
rows can be data. Neither the adapter nor its tests infer these classes from content,
indentation, blanks, gold answers or model outputs.

Each rule declares source references, target rows and columns, and its relation.
Group scopes are finite lists, never implicit ranges ending at the next blank.
Cross-column propagation is tagged `from_span`. Flat TAT-QA cells do not preserve
publisher merge geometry: this tag records an interpreted span, not verified PDF
geometry. The interpretation may be wrong and remains auditable. Row labels that
are blank remain blank; the adapter does not invent “Total”.

Unit excerpts attach only to their annotated cells, rows or columns. Amount scales
do not propagate to percentages, EPS, share counts, dates or note numbers. A literal
currency symbol establishes only that symbol, not an unstated multiplier. An
unestablished scope is `unspecified`. All quantitative values and paragraph text
remain original strings. D4's per-case scale-conversion policy still applies.

This annotation was performed by the implementation assistant, with questions
already visible, but without model outputs. It is not independent or blind review.
The user waived the broad D3 two-reviewer pass; that does not attest case 107 or
sealed custody. Source tables and provenance are under `table-sources-v1.2/`.

## Generic adapter and representation

`table_adapter.py` consumes source bytes and annotations, with no question/gold
argument or case-number branches. Reject changed source hashes, missing row
classifications, invalid references and overlapping unit scopes. Preserve every
source cell, row order and narrative paragraph. Original source files remain v1.

The structured sidecar retains arrays of exact strings, references, relation tags
and annotation-rule IDs. Only rendering joins nonempty strings, in registry order,
using the fixed separator ` | `. Such joined strings are derived context, never
original cells or acceptable value pointers. Data records contain rendered
`structural_context`; they no longer repeat the first source row as `headers`.
Non-data rows retain their original cells without that repeated field. Source
record indexes are stable. Full sidecars remain outside indexed records.

The corrected representation is predeclared as the primary candidate; v1 is an
ablation. This choice cannot be changed after seeing scores. Context is serialized
into JSON records, so it changes embedding, keyword search and reranking input as
well as generation. It is not a generator-only intervention. Measure value-cell
recall and complete-proof recall at each candidate/selection k, separately from
answer correctness. Preserve ingestion/token-limit failures in denominators; do
not truncate rows or change MiniLM limits to make the candidate pass.

Freeze annotations, renderer, generated-document hashes, lineage, proof registry,
D4 answer instruction and D5 scorer together before execution. All compared
systems receive the same representation. Planning continues to use the original
question/history and the same frozen format instruction; it does not gain source
headers or gold values. An oracle-location arm is separately labelled.

## Proof identity and scoring change

Header repair (012) and proof identity (002/080/092) are separate fixes. Each proof
alternative specifies a value `{table_id, source_sha256, row, col}` and all required
disambiguating original coordinates: row label, period, group, unit and applicable
qualifier. Paragraph alternatives use the original record index and half-open UTF-8
offsets. Repeated values never automatically create alternative proofs. Alternatives
must be justified from source and question before inference, including narrative or
summary alternatives where they establish the same fact. Comparison case 082 needs
the compared values, not just the winning currency label.

Captured coordinates must be derived from revision/hash-checked source records and
actual source pointers, not model claims. `visible_coordinates` checks an entire
captured record against its frozen representation. It grants only the context
actually rendered; it cannot count unseen sidecar fields as retrieved evidence.
Partial/truncated chunks need a future range-aware capture adapter and must not be
represented as whole records. A wrong selected value cell fails grounding even when
the correct cell is visible elsewhere in the same evidence bundle. A complete proof
may span multiple captured passages. Location alternatives do not loosen D4 values.

D5 explicitly supersedes D4's joint primary metric. Primary correctness is the
validated final answer's exact typed value, allowed field layout and frozen
per-case alternatives. Report grounding and joint correctness separately, including
“correct answer, wrong evidence”. Never turn rejected drafts into primary answers;
errors and failed abstentions remain failures. Keep the prior D4 joint result as a
separate view. Production validators are unchanged. Exact derived conversions retain
their separate D4 diagnostic; unlisted values remain wrong pending separate review.

For the eventual E0.5 adapter, `correct` maps to this typed-value primary and
`harmful` to a supported wrong value/category, including a supported answer to a
negative case. Wrong grounding alone is a separate diagnostic, not a hidden primary
penalty or a second definition of harmful. Keep joint support and grounding-error
counts visible. The prior numerical thresholds and inadequate sample-size finding
are unchanged; current runner/gate integration must explicitly bind this definition
before any new execution. No default promotion follows from these offline checks.

## D3 interaction and exclusions

Before inference, a source-content exclusion can be reconsidered only if the required
content is present in the raw source and the generic annotation/adapter restores it
without choosing an ambiguous interpretation. Record the source proof and version
the roster before execution. Scope ambiguity cannot be resolved by adding headers.
Missing raw content cannot be invented by annotation. No roster changes are made here:
002/080 remain primary; 082 derived; 062/064/092 remain stress; 017/099 still lack the
referenced table-image content. For 064 and 092, coordinate-grounded conditional
readings are diagnostics only. Recognizing ambiguity or stating assumptions still
requires separately recorded review, not a guessed score from a value match.

Scan all tables for multiple header rows and interior headings, and all 37 table
questions for duplicate gold values and narrative alternatives. Publish all-table
v1/v2 diffs and counts. The review roster remains 102 primary, 3 derived and 15
stress; six primary gold decisions and D6/D7 remain unresolved. No final execution
freeze or evaluation is authorized by this candidate artifact alone.
