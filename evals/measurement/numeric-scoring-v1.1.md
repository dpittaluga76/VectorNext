# Numeric precision and D2 review policy v1.1

Adopted from Daniel Pittaluga's D2 instructions, 2026-10-16. This supplements the unchanged [answerability policy](answerability-v1.1.md) and applies to **every numeric development item**, including dates, ranges and incidental numbers in longer answers. It defines the successor benchmark's scoring contract; it does not change production numeric validation, historical scorers, public labels or the execution freeze. Pending scope/type/proof decisions still require adjudication.

## Three tiers

| Tier | Requirement | Primary correctness |
| --- | --- | --- |
| Faithful | Preserves the requested quantity, entity, time, unit, scale and source precision. An exact source requires the exact value; a qualified source requires its bound/direction/approximation. | Eligible for full correctness only when the other factual, type and source-proof checks pass. |
| Supported but imprecise | A separately approved, source-backed weaker statement about that same quantity, without asserting a false exact value. | Flag and report separately; **no full credit and no fractional credit in the primary metric**. |
| Wrong | Wrong value/scope/unit, unsupported rounding, dropped bound presented as exact, changed quantity or unsupported additional claim. | Incorrect. |

Unresolved gold scope is **unscorable/pending**, not a fourth quality tier and not a reason to silently remove a difficult measured request. Finalize it or predeclare its separate track before freezing. An unanswered request keeps the outcome-matrix abstention/error category; these tiers classify proposed numeric answers, not system states.

### Exact count: 081

The two passages concern the same U.S. Blogger industry dataset. The introduction summarizes it as over 20,000 users; the Dataset section specifies 22,880 users. No separate collection dates or snapshots are supplied for these two descriptions. The later train/development/test split is 17,880 / 2,500 / 2,500, consistent with the same total. This is a source-based same-dataset judgment, not independent confirmation of collection dates.

- **Faithful:** `22,880`, `22880`, `22,880 users`, `22880 users` for the total user count, with appropriate proof.
- **Supported but imprecise:** `over 20,000 users` or `more than 20,000 users`, with the qualified introduction passage. Do not accept the lower bound as an exact count.
- **Wrong:** bare `20,000`, `20,000 users`, or a rounded count asserted as exact. A training-only or test-only count answers a different quantity.

### Directed approximation: 097

The source describes alpine areas that **rise to almost 2,000 m**. This is their regional upper extent, not an average elevation. Mount Bogong's 1,986 m is a separately stated peak measurement; it does not replace the requested regional wording.

- **Faithful:** `almost 2,000 m`, `nearly 2,000 m`, `just under 2,000 m`, with comma-free and `metres`/`meters` spelling variants explicitly enumerated in the amendment.
- **Supported but imprecise:** `about 2,000 m` is a weaker approximation that loses the below-bound direction. It is **not** full credit. This explicit case alias must not become a general permission to erase bounds elsewhere.
- **Wrong:** bare `2,000 m`, `exactly 2,000 m`, `over 2,000 m`, or an average-height claim. Do not turn “almost” into a fabricated numeric interval or tolerance.

## Apply consistently

1. Bind each number to its semantic role before comparing it. Dates, years in code names, batch identifiers, dataset sizes and financial amounts are different facts. Extra context numbers need source support even when they are not required answer fields.
2. Preserve source types. TAT-QA cells are JSON **strings**, including numeric-looking strings. A diagnostic numeric interpretation does not authorize converting those cells to numbers, stripping currency symbols or multiplying by a separately stated scale. D4/D5 still govern approved field mappings and table proofs.
3. Use exact decimal/integer comparison where an approved mapping permits numeric normalization; never binary floating point, substring matching, generic rounding tolerance or inferred percentages. Do not equate `0.3` with `30%` without an explicit approved source mapping.
4. Require both range endpoints, their relationship and the correct quantity. A date or range cannot be shortened to a convenient matching component. A year may be acceptable for a “when” question only under its frozen granularity rule; the scan does not silently withdraw existing year aliases.
5. Enumerate permissible paraphrases and imprecise alternatives per item. A spelling change is not a new numeric value. Preserve negation, attribution and allegation separately from numeric precision.
6. Retain individual labels, original alternatives, accepted/rejected examples, source offsets and unresolved decisions. The [systematic audit](../../docs/reports/t39-d2-alternative-audit-v1.1.md) binds this policy to all detected numeric cases and records manual coverage of numeric words. It is an audit, not a semantic model-output scorer.

## Freeze and reporting

Keep the original public v1 view, D1-only view, D2-only view and combined reviewed v1.1 view on identical captures and common case sets. D1 changes answerability; D2 tightens alternatives or changes a rubric. Report their effects separately, including the per-case transition, denominators, exclusions and imprecise-answer counts. Historical 16/28-question captures belong to other datasets and must not be relabelled with these amendments. No new benchmark scores exist yet.

Record whether each issue came from source inspection or model disagreement. These D2 candidates were found in internal development source review before benchmark inference. Freeze their five IDs, decisions and input hashes before the next run. New scan findings are separate pending candidates, not automatically added corrections.

Case **107 is a gold replacement**. Its candidate Level A definition requires **two independent source reviews**, recorded separately before activation. The implementation agent's check and Daniel's conditional approval from a table do not satisfy that requirement. Use a human rubric over required semantic elements, not exact-match alone or an LLM judge. Keep the original gold intact and the successor unresolved until the reviews are complete.
