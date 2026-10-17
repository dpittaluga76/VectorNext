# T39 D1 adjudication v1.1

Date: 2026-10-16. Authority: Daniel Pittaluga / Architect's case-by-case response, followed by source-condition verification by the implementation agent. This is a **partial development-label amendment**, not approval of the full benchmark.

## Decisions and changelog

| Case | Original public label | Reviewed decision | Gold and qualification |
| --- | --- | --- | --- |
| 109 | Unanswerable | Answerable; literal extraction | Circuit switching is charged by connection time. |
| 074 | Unanswerable | Answerable; literal extraction | TF-IDF features for classification. Feature-set check below. |
| 088 | Unanswerable | Answerable; attributed paraphrase | Richard Lindzen, as the passage attributes an uncertainty-understatement criticism to him. |
| 004 | Unanswerable | Answerable; inference-required | MSP. Non-UK alternatives make UK citizenship non-exclusive. |
| 067 | Unanswerable | Ambiguous; separate from reviewed binary scoring | Do not silently map the malformed name to Warsaw. The unchanged public/strict view retains unanswerable. |

There are **four negative-to-answerable changes**, with two requiring qualified strata. Case 067 is not a fifth flip to answerable. The original proposal, original review recommendations and source bytes are preserved. The [v1.1 JSON amendment](t39-d1-adjudication-v1.1.json) records the five decisions, prior recommendations, accepted aliases, exact source hashes and half-open UTF-8/code-point evidence offsets. It explicitly remains ineligible as an execution or independent-review approval file.

The [answerability policy](../../evals/measurement/answerability-v1.1.md) defines closed source scope, conservative alias resolution and separate literal, inference, attribution and ambiguity reporting. This is an evaluation policy; application prompts and validation are unchanged.

## Source-condition checks

### 074 — Feature completeness

The supplied paper says:

> We performed experiments by extracting the TF-IDF features from the reports and classifying them using three different methods---SVM, XGBoost, and Logistic Regression.

It also describes joining common bigrams into single tokens before vectorization. This is part of TF-IDF input preparation, not a separate embedding or metadata feature channel. The experimental section distinguishes classification using TF-IDF from a second task using TF-IDF and LDA to highlight keywords. LDA groups those keywords for visualization; it is not described as an additional classification input.

Approve the representation-level answer **TF-IDF features**, including explicit aliases such as **TF-IDF feature vectors** and **Term Frequency-Inverse Document Frequency**. Do not require classifier names as features. Additional answer claims still need their own proof; the presence of “TF-IDF” cannot make an otherwise incorrect answer pass. The unchanged question is scoped to this single paper, rather than interpreted as an unspecified paper elsewhere.

### 088 — Attribution, not a stronger quotation

The exact claim is:

> For example, Lindzen states that the SPM understates the uncertainty associated with climate models.

This is narrower than a verbatim statement that “models are uncertain.” The approved interpretation extracts the speaker of that qualified uncertainty criticism; it does not establish the scientific truth of the criticism. Accept **Richard Lindzen** and **Lindzen** as the same explicitly identified speaker.

The paragraph also names **John Houghton**, but attributes a different statement to him: the summary is agreed upon by government delegates and changes must be supported by scientific evidence. He is not an additional gold speaker for this question. Tag this case `attributed_paraphrase`; keep it out of claims about purely literal extraction.

### 004 — Inference and distractors

Gold **MSP** is an exact source span, but the citizenship conclusion requires interpreting the eligibility list. The supporting sentence permits UK, Irish, Commonwealth, British overseas territory and qualifying EU citizenship alternatives. The source never literally says “UK citizenship is not required.”

Record `inference_required` and report it separately from literal extraction. Police, armed-forces, civil-service and foreign-legislature roles are disqualifications for sitting as an MSP, not answers about citizenship eligibility. Do not use external knowledge to add MPs or any other job to the gold set.

### 067 — Entity/premise ambiguity

The source says:

> Legislative power in Warsaw is vested in a unicameral Warsaw City Council (Rada Miasta), which comprises 60 members.

The question instead says “Miasta City Council.” Preserve the ambiguity between a lenient reference to the only council and a strict malformed-entity reading. The reviewed primary label is **ambiguous**, with no answerable gold. A lenient diagnostic may identify integer `60` or the surface form `60 members`, but those variants do not silently enter the strict gold set. No outside translation is needed to establish the exact name mismatch.

### 109 — Explicit contrast

The paragraph directly describes circuit switching as charged by a **fee per unit of connection time**, even with no data transferred; it contrasts packet switching charged by information transmitted. Accept the connection-time span and explicit shorter aliases only as the charging basis of **circuit switching**, not merely any quoted phrase from the paragraph.

## Review provenance and scoring cautions

- **Both directions were screened.** All 120 development cases were reviewed: 83 originally supported and 37 originally unanswerable. The earlier report flags positive-label errors too, including causal reversal, lost quantity qualifiers and a mismatched definition. That screening is not exhaustive independent adjudication.
- **These cases were not surfaced by model disagreement.** No benchmark inference has run on them. Selection for D1 came from the complete development review.
- **The original rationale is unknown.** The source records provide no annotator explanation. All four SQuAD D1 cases contain a `plausible_answers` distractor matching the candidate answer discussed here. That warns against treating a matching span as proof of answerability; it does not tell us the annotator's actual reason. The v1.1 labels express the explicitly chosen semantic policy.
- **Two independent blinded reviewers have not been obtained.** The records contain an internal implementation review, Daniel's later adjudication after seeing that review, and subsequent mechanical/source checks. None is relabelled as a second blinded review.
- **Corpus and context are separate.** All five source documents were checked byte-for-byte against the preserved proposal and their SHA-256 values. There is no runtime evidence context yet, so no claim is made that a model saw these passages. After evaluation, inspect actual selected evidence separately; missing retrieved proof must not rewrite corpus gold.
- **Label effects must be visible.** On a fixed 120-case development denominator, four binary label changes can shift accuracy by up to 3.33 percentage points without changing a model. Excluding 067 changes the reviewed binary denominator separately. The full proposal has 180 candidates, not approximately 110. Publish unchanged-label and reviewed-label views over the same captures, with exact denominators and paired changes. No new accuracy or confidence interval is claimed here.

## Verification and remaining work

All ten supporting spans and twelve source-answer alias spans match their recorded UTF-8 byte and Unicode code-point offsets. Their source hashes match the proposal; the amendment also binds the original request/label files, internal review and policy hashes. All 116 original development manifest members remain unchanged. The 68 local link targets and documentation whitespace checks passed. The existing review verifier correctly rejected this partial amendment as an execution approval. These checks required no inference or service changes. Alias definitions are recorded; complete scorer integration remains pending and is not claimed as implemented by this review.

D1 is recorded. D2–D7 remain pending, as do final benchmark-wide field/proof mappings, report-family checks, source-coverage decisions, independent approval and sealed custody. The amendment does not silently apply the earlier proposed fifteen exclusions or change quotas. Create and verify a complete successor only after those decisions; keep the sealed candidate files unopened by the implementation agent.

[Decision sheet](../reviews/t39-review-decisions.md) · [Original internal screening](t39-development-review.md) · [Detailed original case findings](t39-development-review-cases.md)
