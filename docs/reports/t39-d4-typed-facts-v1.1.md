# T39 D4 — Typed facts, format and collision review

Date: **2026-10-16**. Daniel Pittaluga approved the direction with amendments. Implemented as a source-only review candidate: **no inference, sealed reads or production changes**. This is not independent adaptation approval or an execution freeze.

## Recorded decisions

| Concern | Implemented rule |
| --- | --- |
| Question units versus cell units | Primary requires the cell string. Enumerated exact conversions are derived-only and require scale evidence; approximations get no exact credit. |
| Format convention | A dated, hash-bound instruction requires final string fields, source spelling and one final answer. JSON retains pointer selection and Rust materialization. Apply identically at planning, assessment and extraction. |
| Normalization | NFC and ASCII/NBSP whitespace only globally. Currency, punctuation, TeX, case, unit and field-name equivalences are per case. Signs, parentheses and placeholders remain meaningful. |
| Unlisted answers | Wrong in primary; retained for separate blind human sensitivity review. Unreviewed sensitivity is null. No list changes from outputs. |
| Two-code answer | Explicit member aliases/separators, either order, all-or-nothing primary. Member hits diagnostic only. Partial/extra/duplicate candidates and swapped citations fail. |
| Collisions | Correct source hash and location required. Equal text in another cell is insufficient; repeated text outside annotated support is a review lead. |
| Failure attribution | Type, mapping, proof, scale conversion, imprecision, format-like and other nonmatches remain separate. Diagnostic cleanup never awards correctness. |
| Oracle | Names/types/locations without gold values. Same format/scorer/lists. A field-only arm must reuse automatic evidence bytes; a gold-evidence gap is not planning cost. |

[Contract](../../evals/measurement/typed-facts-v1.1.md) · [Format instruction](../../evals/measurement/answer-format-v1.1.txt) · [Fact-role schema](../../evals/measurement/typed-facts.schema.json) · [Scorer](../../evals/measurement/typed_facts.py).

## Findings and coverage

The [integrated gold candidate](t39-d4-gold-candidate-v1.1.json) applies recorded D1/D2 decisions and D3 tiers without modifying their originals. It retains **102 primary, three derived/inference, 15 stress** cases. Six primary gold decisions remain unresolved: **010, 034, 047, 053, 071, 107**. The 60 sealed cases remain unopened. Original labels/alternatives remain separate; no benchmark scores exist yet.

The builder verified **116 development members**, 120 question-to-document bindings, **217 proof references**, **37 table-value bindings** and **96 unit/period context bindings**. Across all tiers there are 87 positive roles and **330 per-role accepted strings**, including the finite two-code grammar. Pending/stress aliases are tested mechanically, not approved for primary accuracy.

| Cases | Source finding |
| --- | --- |
| 002 | Opening fiscal-2019 `$1,264` cannot cite the equal prior closing balance. Thousands is stated in the reconciliation paragraph. |
| 025 / 087 / 108 / 119 | Percentage columns/rows do not inherit neighboring million/thousand units. |
| 028 / 029 | Per-share NT dollars and reserve amounts in thousand NT dollars have different units. 029's upstream scale annotation is blank despite the source heading. |
| 048 / 049 | EPS uses cents per share, not a neighboring shares-in-millions heading. |
| 080 / 092 | Diluted EPS cannot prove basic EPS; net emissions cannot prove gross emissions. 092 remains stress because geography is ambiguous. |
| 089 / 090 / 116 | Supplied unit context is unspecified. 089/090's upstream `thousand` annotation is insufficient proof; no conversion aliases are enabled. |
| 074 / 081 | Require classifier-feature evidence and the exact dataset-total statement. Preprocessing, rounded introductions and split sizes cannot substitute. |

The [collision audit](t39-d4-collision-audit-v1.1.json) checks **1,432 cells across 37 question cases** (some share one of 32 table documents). It records **three wrong-cell collisions** (002/080/092) and **147 text occurrence leads across eight cases**. Repeated `car` occurrences in unresolved 053 are leads, not proven annotation errors. All 83 non-table cases are inventoried; 50 have positive roles and 33 have no positive aliases to compare. No occurrence automatically adds a proof. The scan cannot establish the absence of every semantic paraphrase or wrong fact within a long annotated paragraph.

Fifteen individually configured amount cases have exact conversion lists. Direct and converted correctness use separate views of the same roster; outputs never determine tier membership. D3's derived questions remain 004/082/088; 33 of the 37 tables remain primary. Keep small failure categories as counts and avoid ranking systems on sub-10-point pilot differences.

## Verification

- **47 measurement tests passed:** 17 D4 checks plus the existing 30. These enumerate all 330 accepted strings and cover layouts, exact long numbers as text, numeric types, source-specific TeX, placeholders, units, qualifiers, wrong locations/hashes, scale proofs, two-code extras/duplicates and swapped citations.
- JSON Schema Draft 2020-12 validates the candidate. The standard-library scorer also checks critical invariants without adding a production dependency.
- Regeneration into a new directory is checked for identical candidate/audit bytes. Original D1/D2/D3 hash records and 116 proposal members are rechecked. Unit tests do not regenerate fixtures or labels.
- No Rust, Docker or GPU checks were needed for these isolated Python/documentation changes. No service, model setting, production validator or historical scorer changed.

```powershell
python -m unittest discover -s evals/measurement -t . -p "test_*.py"
python -m evals.measurement.build_typed_candidate --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-d4-new-audit
```

The second command needs the retained local source-review package and a **new** output directory. It refuses existing outputs/sealed member paths, does not acquire sources and does not run models. Private proposal/acquisition folders remain out of Git. [Verification and artifact hashes](t39-d4-review-manifest-v1.1.json).

## Remaining freeze

Code, instruction, schema and lists are hash-bound as a **review candidate**. D5–D7, six gold decisions, final field/proof mappings and independent adaptation/custody remain pending. The separate case-107 review requirement is still unattested.

The pure format/oracle helpers are tested but **not installed in the worker or wired into the current runner**. Before inference, integrate them in the isolated evaluation path, resolve captured JSON/PDF proofs into the declared coordinates and verify actual per-stage prompt audits. Do not combine the current runner with the stricter scorer while omitting its format instruction.

Then make the requested **single final Git/execution freeze** of corrected inputs, prompt, lists, scorer and runtime identities. Preserve this candidate and original v1 for audit. Unlisted-output reviews produce separate sensitivity results, never revised primary scores. T39 remains active; synthetic scorer tests establish no model-quality or promotion result.
