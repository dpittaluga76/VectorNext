# D7 — Pilot scope and closed-book controls, v1.4

Decision recorded 2026-10-17, before benchmark inference. This supplements D1–D6;
it does not edit their frozen artifacts or approve execution.

## Purpose and mandatory headline/changelog limitations

**Purpose: validate the benchmark harness (scorers, adapters and splits) and
provide bounded source-grounded strategy diagnostics; results are provisional
for decisions about real documents.**

Every successor headline and changelog must repeat these statements verbatim:

- Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.
- Not evidence of table-extraction performance, only of reading from supplied structured cells.
- Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.
- Not a measurement of the NASA/USGS track if that stays separate, and not comparable with it unless you state how.

No model outputs informed this amendment. Historical freezes keep their original
terminology; the names below govern current documents and successor reporting.

## Track names, pairing and denominators

| Track | Provisional primary n | What the input actually tests |
| --- | ---: | --- |
| TXT prose QA | 52 | Supplied Wikipedia paragraphs and paper text |
| PDF text ingestion (clean render) | 17 | Clean, one-column typeset Wikipedia paragraphs |
| structured-table QA (JSON) | 33 | Supplied cells with the corrected D5 context adapter |

These sum to 102: 76 positive, 26 negative, including six unresolved gold decisions.
69/102 (67.6%) are clean prose. The 37 development table questions cover 32 table
files; 33 enter primary. They bypass recovery of a grid from rendered pages.
Reading corrected structured cells is an optimistic input condition, not a
measured or guaranteed numerical upper bound on end-to-end PDF accuracy.

Audit all 120 development cases, then primary alone, using exact source-text hashes,
NFC/whitespace-normalized text equality and exact question equality. Equal family
keys alone do not constitute a pair. A valid ingestion pair needs the same question,
source paragraph, gold/aliases, scope and evidence representation except for the
container; runtime, strategy, parser settings, chunking policy and caches must be
controlled and captured. Report extraction/chunk differences and per-system paired
correctness changes, not only two aggregate accuracies. No twins are added here.

There are **zero exact or normalized paragraph pairs**, and zero question pairs,
between development TXT and PDF. The 17-versus-52 comparison is descriptive only:
**paired ingestion gap: not estimable (n=0)**, for every system. Similar marginal
scores would not establish ingestion equivalence. A small loss on clean renders
would be expected in a genuinely paired design and would not solve real PDF handling.

Of 19 development PDFs, 065 and 079 are stress cases, not derived items. Their
scope/premise defects, not parser losses, caused exclusion. The PDF share changes
from 19/120 (15.8%) to 17/102 (16.7%). Recompute counts after D6 collision resolution;
do not silently preserve these provisional counts as final quotas.

## Closed-book diagnostic, frozen before any inference

Run **every finally admitted primary item once per evaluated model**, before its
retrieval-strategy measurements. The current primary pilot uses NuExtract; a Gemma
oracle comparison also needs its own control mask. No small subset is selected
after looking at answers. At the provisional roster this is 102 extra calls per
model, not 102 independent new questions. Controls are separate from strategy and
oracle denominators, timings and two-call production answering.

Use the fixed [question-only instruction](closed-book-v1.4.txt) and
[schema](closed-book-v1.4.schema.json). The actual model receives only this generic
instruction and the unchanged question. No passage, history, title, file name,
family, format, field name, gold type/value, aliases, source pointers, annotation
status, retrieval or tools are supplied. Case IDs are capture metadata only. An
empty-document application request is not a control: the app may reject it or
instruct abstention without measuring question-only answer availability.

One constrained generation call; string-valued single answer or explicit abstain.
Use each supported profile's pinned model/runtime, temperature (NuExtract 0.2,
Gemma 0), seed 42, disabled reasoning, cache_prompt false, 4,096-token context and
768 output-token cap. Use the normal model lease and input-limit check; reject an
oversize prompt rather than truncating it. Freeze the native NuExtract template
adapter and actual serialized request, not merely this generic schema. Capture
profile/model/runtime hashes, prompt/schema/payload hashes, raw response bytes,
status/errors, usage and timings. Model loading and synthetic warmup are separate.
Persist attempt-start records; reconcile interruption without silently repeating
failed/uncertain controls. No prompt tuning, answer review or gold changes between
controls and retrieval runs. Bind final case roster, D4/D5 scoring, D6 split, model
identity and controls into the same final execution freeze.

`pilot_controls.py` is offline audit/scoring support, **not an inference runner**.
Its candidate roster and review hashes are not a runnable freeze. Runtime capture,
native-template checks, restart handling and final runner integration remain required.

### Matching, negative cases and missing controls

For a reviewed positive with one fact role (all 76 provisional positives), score
`closed_book_gold_match` only when the response is schema-valid and its answer
matches D4's finite per-case value/alias list after its existing normalization floor.
Two-code roles remain all-or-nothing. No numeric coercion, containment, source-proof
requirement, scale conversion or global formatting forgiveness is introduced.
Do not send role names or alternatives to the model. Future multi-role cases need a
new predeclared generic response/scoring contract; they cannot pass by partial match.

This is a conservative **gold-string match**, not proof of training contamination
or semantic correctness. The answer may be known, inferred or guessed from the
question. Unlisted but correct variants may miss, especially hidden table spelling,
scale and qualifiers. Nonmatching therefore does not prove clean/unseen data.
Queue unforeseen variants for separate blind sensitivity review without changing
the primary lists, match mask or source labels.

Source-relative negatives have no annotated world-answer gold. An answer without
the supplied source is **not automatically true or false**, and abstention is
**not a closed-book solved item**. Report negative answered/abstained/error counts
and cross-tabulate with retrieval outcomes; retain all negatives in both views.
This prevents abstention from deleting the negative test set or flipping its gold.

Report, for each system/strategy:

1. Original primary accuracy over the entire final roster, with failures retained.
2. Accuracy after excluding positive closed-book gold matches, with exact n,
   positive/negative counts, source/track composition and family clusters.
3. Positive matched/nonmatched/abstained and negative answered/abstained counts;
   missing, failed, malformed and unresolved controls remain unknown, never nonmatches.

Suppress the adjusted headline when any control is unknown or gold unresolved;
report known-subset diagnostics explicitly if useful. The full primary score does
not depend on control success. Use one frozen per-model mask across all retrieval
strategies. For cross-model comparisons additionally report a **common mask** that
excludes positives matched by either model, so denominators agree; model-specific
views alone cannot rank models. Recompute D6 family-resampled intervals and cluster
counts for each view (single-question Wilson intervals remain descriptive). Do not
relabel these views as an uncontaminated benchmark or independent evidence.

### Custodian supplement

After development choices and the final split are frozen, the custodian applies
the identical controls privately to all sealed primary items under each evaluated
model, before sealed retrieval runs. Keep questions, outputs, match masks and all
per-item hashes private. Return only aggregate control completeness, positive
match/nonmatch/abstain counts, negative answer/abstain counts, unknown counts,
all/adjusted accuracy with n, by-track/source summaries, family cluster statistics
and intervals, plus the public policy/model/freeze identities. Return common-mask
aggregates for a multi-model comparison. Suppress small cells if they would disclose
sealed content. Keep the full binding/audit privately for reproducibility. This is
a separate D7 aggregate supplement; do not add fields to D6's strict receipt schema.
No sealed control has run and no custody acceptance is claimed here.

## NASA/USGS and the conditional real-layout probe

Historical NASA/USGS results remain **scored historical views**, using their own
unchanged frozen gold/scorers: [independent suite](../../docs/reports/t11-independent.md)
has n=28 distinct questions (112 repeated requests), and
[coverage suite](../../docs/reports/t14-evidence-coverage.md) has n=16 (96 repeated
requests). They are not pooled with this pilot, relabelled under D1–D4, or rerun.
There is no fresh NASA/USGS extension in the current run plan. Retained raw scores
and later reviewed exceptions remain separate. Cross-version/runtime/selection
differences preclude treating a pilot score delta as a model improvement.

Any future fresh extension has its own frozen gold and n, source-family tracing
across all exposed primary/derived/stress and sealed families, D1–D6 screening and
custodian reconciliation. Source overlap is currently **unverified**, not absent.
Reusing old questions gives a regression view, not fresh independent evidence;
auditing their labels requires a versioned score view alongside the original.

**Trigger:** if a decision depends on performance on real documents, run a
separately scoped **original-layout PDF probe of at most 20 items** next, before
making that claim. Prefer original QASPER paper PDFs, preserving existing questions
and gold evidence while aligning spans to extracted text. It is not needed to
validate this harness and is not acquired or added now. Verify availability,
license/reuse/redistribution rights and source identity before selecting files;
do not assume dataset access grants PDF redistribution. TAT-QA original reports are
only candidates if recoverable and rights/provenance are verified.

Keep each original-layout derivative in the same D6 family and split as its text
counterpart. Freeze eligibility, selection seed/strata, alignment, D1–D5 screening,
scorer and custodian handling before outcomes. Report failures to acquire/align as
such, not model negatives. Matched text/PDF versions are dependent observations,
not extra independent questions. The probe is separate from primary; report counts
and reading-order/header/hyphenation/scan/table-loss failure categories. With at
most 20 items, intervals are broad and the probe cannot rank systems reliably.
