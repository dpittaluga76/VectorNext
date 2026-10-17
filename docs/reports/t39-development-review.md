# T39 internal development review

Date: 2026-10-16. Reviewer: Codex implementation agent. **Internal screening complete; independent approval and execution freeze remain pending.** The requested answer sheet is [T39 review decisions](../reviews/t39-review-decisions.md).

Subsequent D1 adjudication is recorded separately in the [v1.1 amendment](t39-d1-adjudication-v1.1.md): four qualified answerable changes and one ambiguous case. The initial recommendations and five-flip arithmetic below are preserved as historical screening, not the current decision. No original source or label was overwritten.

## Scope and result

Reviewed the 120 development questions, their public human annotations and available scoped source text in `tmp/t39-v2-review-proposal-v2/development/`. The original manifest remains `3e3a1c37fd3a9d3e216eaaebcf0d41dc9adad718f24a9d2fa6c6a77cb33452b1`.

| Screening result | SQuAD | QASPER | TAT-QA | Total |
| --- | ---: | ---: | ---: | ---: |
| No case-specific concern identified | 50 | 12 | 33 | 95 |
| Needs a decision | 12 | 9 | 4 | 25 |
| Reviewed | 62 | 21 | 37 | 120 |

The 25 findings comprise five suspected false-negative labels, five answer-semantics corrections, fourteen scope/completeness/unit concerns and one unsupported comparison. These are judgments about the supplied evidence and application contract, not measurements of either model. No proposed correction has been applied to labels or source files.

“No case-specific concern” is not complete gold-label certification: typed fact mappings, sufficient proof sets, shared adapter decisions and independent review are still required. QASPER positive annotations and relevant surrounding passages were checked; negative review used relevant-section/keyword inspection. That cannot prove absence under every possible interpretation. All SQuAD scoped paragraphs and all development TAT-QA tables were inspected. Publisher PDFs and QASPER table images were not acquired.

## Findings that affect the benchmark

1. **Public authorship does not guarantee a correct adapted label.** For example, the pathology question marked unanswerable is answered by TF-IDF features in the title, abstract and method. Other labels discard qualifiers or confuse cause and effect. Preserve original public scoring separately from the proposed reviewed labels.
2. **Some questions need a defined interpretation.** Temporal scope, fiscal versus calendar years, geographic scope and truncated questions can turn an apparent model error into a label error. Keep uncertain cases visible and unresolved until adjudicated.
3. **Table adaptation is incomplete.** Repeating the first row does not reliably carry years, units and section headings into a value record. This is a proposed benchmark-adapter correction, not a production chunker change. It requires a successor corpus and new hashes before inference.
4. **Equal values are not interchangeable proofs.** Cases 002, 080 and 092 match multiple cells. Opening/closing balances, basic/diluted EPS and gross/net emissions must remain distinct. The machine-readable review records proposed value pointers, not final semantic approval.
5. **All table values are strings.** Their exact stored types and formatting must survive scoring. Numeric normalization, units and semantic field mappings need explicit frozen rules; no permissive fuzzy matching or model judge is proposed.
6. **Table IDs are not verified source families.** The 32 development table files cannot be certified as 32 independent reports. No repeated paragraph of at least 80 characters was found across those development files, but absence of exact duplicates does not establish family independence. Sealed family checks remain custodian work.
7. **Coverage is limited.** The one-column PDFs exercise PDF ingestion, not complex layout/OCR/table fidelity. This candidate excludes fresh NASA/USGS questions. D7 requests a concrete scope decision rather than silently claiming broader coverage.

The existing 180-question proposal is therefore **not ready to freeze as an approved benchmark**. Applying the recommended five negative-to-supported changes and moving the fifteen D3 cases out of the primary set would provisionally yield 165 primary questions, 39 negative (23.6%). This arithmetic uses only development changes and previously recorded sealed counts, not inspected sealed labels. Replacement/family corrections must restore the agreed quotas before execution; do not relabel ambiguous questions merely to meet a target percentage.

## Verification and preserved artifacts

- All **116 development manifest members** match their original SHA-256 values, including 112 document files.
- All **four pinned public source artifacts** match recorded sizes and SHA-256 values. Only matching development records were displayed for source comparison; no sealed proposal requests, labels, documents or rendered pages were opened.
- All **120 questions, outcomes, original alternatives, annotation support and provisional family IDs** match the corresponding public source records. All non-PDF document transformations match the builder output exactly.
- All **19 development PDF files/pages** reproduce their source paragraphs under whitespace-normalized extraction. The five existing development contact sheets were visually inspected; no clipping, overlap or missing glyphs was observed. No source PDF was regenerated.
- Original proposal files, public sources, historical captures and labels remain unchanged. No model inference, service restart, benchmark run or default change occurred during this review.
- The 120-case inventory/count reconciliation, 82 local Markdown link targets and tracked diff whitespace check passed. Proposal hashes were checked again after writing the review. No production tests or GPU rerun were needed for this documentation-only review.

The local audit is in `tmp/t39-internal-review/source-audit.json` and `mechanical-checks.json`; source bytes and full development labels remain outside Git. The local read-only comparison script is `tmp/t39-internal-review-tools.py`. The report's JSON records their hashes, all 120 case IDs/dispositions and case-specific recommendations. It explicitly sets `independent_of_implementation` and `approved_for_execution` to `false`.

[Decision sheet](../reviews/t39-review-decisions.md) · [Detailed flagged cases and local source links](t39-development-review-cases.md) · [Machine-readable record](t39-development-review.json)

The detailed source links require the ignored local proposal package; GitHub readers should use the pinned acquisition information in [public-sources.json](../../evals/measurement/public-sources.json). They are not links to files committed with the report.
