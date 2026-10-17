# T39 internal successor and grounding preflight

Date: 2026-10-17. This continues the [delegated source review](t39-internal-review-v1.7.md).
It is offline integration work, **not a model evaluation or an execution freeze**.

The new builder assembles a private successor from the preserved original proposal,
v1.6 development gold and v1.7 review/exclusion records. It checks all proposal
member hashes, prior review freezes, unchanged questions, source bytes, reviewed
text, annotations and complete case rosters before writing to a new directory.
It preserves the original representations and labels alongside corrected tables.

| Package | Questions retained | Primary | Derived | Stress | Documents |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 111 | 92 | 3 | 16 | 105 |
| Exposed candidates | 60 | 55 | 2 | 3 | 56 |

Nine colliding development questions remain in the separate exclusion record.
No candidate question moved into development. Question-only controls contain only
the original question and a case identifier; automatic-question requests contain
no gold fields, answers, aliases or proof locations. Reviewed UTF-8 source text is
bound separately from original PDF bytes, so later citation alignment can use the
correct coordinate system. Candidate content and individual hashes remain private.

The grounding mapper verifies complete JSON records against the frozen v1/v2
representation, then maps visible context and cited original cells to coordinates.
It does not credit a sidecar that the model could not see. Text/PDF alignment uses
captured block spans and whitespace-only alignment to the reviewed text; repeated
or unmatched passages remain explicit gaps. This does not change answer-value
normalization or relax the production validator.

The durable-job projection checks model mode, completion, original question,
document revision, source hashes and exact browser value text. Rejected drafts
remain outside final facts. It preserves large integers/decimals while parsing
diagnostics, and sends only exact string values/types to the frozen scorer. A
regression test demonstrates **correct answer, wrong table cell**: value-primary
credit remains true while grounding and joint correctness fail.

Verification:

- **172 Linux measurement tests passed**, including 22 successor/grounding tests,
  in one temporary offline Docker container, removed after completion.
- All **591 package member files**, plus the manifest, reproduced byte-for-byte in
  a second new private directory. Original sources and review freezes are unchanged.
- Retained unscored pipeline captures supplied **75 evidence occurrences across
  10 distinct table records**; every record/coordinate mapping verified. These are
  operational checks, not model-quality scores.
- No new generation calls, service changes, production-data changes or access to
  the older original holdout.

[Exact verification and code/package hashes](t39-internal-successor-preflight.json).
Earlier preparation working copies and the source-audit split-name validation
failure were retained; the failed validation wrote no package and ran no model.

Private preparation command, using retained review inputs and a **new** output path:

```powershell
python -m evals.measurement.internal_successor --proposal ORIGINAL_T39_PROPOSAL --private-audit PRIVATE_REVIEW_AUDIT --private-annotations PRIVATE_ANNOTATIONS --development-sources DEVELOPMENT_SOURCE_AUDIT --candidate-sources CANDIDATE_SOURCE_AUDIT --output NEW_PRIVATE_PACKAGE
python -m unittest evals.measurement.test_internal_successor evals.measurement.test_capture_grounding evals.measurement.test_capture_projection -v
```

T39 still needs live ingestion-bound snapshots, runner/control/oracle integration,
a committed execution freeze and measured captures. The current corpus is an
internal exposed pilot with 147 primary cases and uncertified broader lineage;
independence, blind-split and minimum-size acceptance have not passed. No strategy
promotion or generalization claim is available. NuExtract and ranked-five remain
the application defaults.
