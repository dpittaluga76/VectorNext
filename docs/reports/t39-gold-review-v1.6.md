# T39 — Activate case 107's Level A definition

2026-10-17. The user explicitly waived the two-reviewer requirement for case 107.
The [v1.6 gold](t39-gold-review-v1.6/gold.json) now uses the authors' Level A
definition. All **101 provisional primary cases have resolved gold**; the roster
remains 101 primary, three derived and sixteen stress. This is user adjudication
after internal source review, without an independent-review attestation.

| Item | Applied rule |
| --- | --- |
| Question | What is the definition of offensive language? |
| Canonical value | any form of non-acceptable language (profanity) or a targeted offense, which can be veiled or direct |
| Scope | The paper's own Level A offensive/non-offensive distinction; Levels B and C are narrower classifications |
| Alternatives | Five finite source-derived alternatives, including the complete definition; unchanged normalization floor |
| Required proof | Original QASPER text for paper 1902.09666, UTF-8 bytes [6415,6672) |
| Rejected alternatives | The old prior-work catalogue, profanity alone, targeted offense alone, hate speech alone, or changing `or` to `and` |
| Original labels | Preserved unchanged in every case and in all prior versions |

The [adjudication](t39-gold-review-v1.6/adjudication.json) records the exact user
instruction, old/new case and three exact source quotes with offsets. The
[policy](../../evals/measurement/gold-review-v1.6.md) fixes aliases and field names
before inference. Value correctness remains primary; grounding remains a separate
diagnostic. A correct definition cited to the old introduction is recorded as
correct answer/wrong evidence. Unlisted paraphrases receive no primary credit.

Verification: **126 measurement tests passed**, including nine new activation
tests. The builder verified 116 development members and 104 prior frozen artifact
entries. It reproduced all nine generated files byte-for-byte in a second output
directory. Only case 107 changed from v1.5; all 120 source hashes, questions,
original labels and tiers remain unchanged. Its source collision scan found no
additional matching location. No answer inference or sealed access was used.

Reproduce against the already acquired, unchanged development proposal:

```powershell
python -m evals.measurement.activate_level_a --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output NEW_DIRECTORY
python -m unittest discover -s evals/measurement -t . -q
```

The [manifest](t39-gold-review-v1.6/manifest.json) freezes this review amendment,
not benchmark execution. The [new custody packet](t39-gold-review-v1.6/custodian-input.json)
and [blank receipt](t39-gold-review-v1.6/custodian-receipt-template.json) are rebound
to v1.6. The blank receipt deliberately fails validation; older receipts cannot be
reused. Daniel Pittaluga / Architect remains the designated custodian.

T39 remains active. Four primary family identities and actual sealed screening,
collision and quota reconciliation remain unresolved. Evaluation-only format,
scorer, coordinate-capture and closed-book runtime integration and the final
committed execution freeze also remain pending. The case-107 waiver does not
waive those requirements. Ranked-five and NuExtract defaults remain unchanged.
