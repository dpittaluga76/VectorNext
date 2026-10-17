# Answerability policy v1.1 — development adjudications

Adopted 2026-10-16 from Daniel Pittaluga's case-by-case D1 response. This supplements protocol 1 for a future successor freeze; it does not edit the original proposal, approve the entire benchmark or change application validation.

**Answerable means that the complete scoped source entails the requested fact without outside knowledge, resolving only unambiguous source-grounded aliases; nonliteral entailments and attributed claims must be tagged, and competing entity or premise readings are ambiguous.**

## Labels and reporting views

Use `answerable`, `unanswerable` and `ambiguous` for semantic gold labels. These map to expected answer outcomes `supported`, `insufficient_evidence` and `ambiguous`; model/system errors are still errors, not gold labels.

- **Original public v1:** unchanged human labels, original denominator and source-support rules. Keep this view even where a later review disagrees.
- **Reviewed v1.1:** apply only explicit case amendments, with source hashes and evidence offsets. Preserve unrelated unresolved cases as unresolved; no implicit approval of the remaining dataset.
- **Strict extractive:** report literal-extraction cases separately from cases requiring logical inference or a qualified attributed paraphrase. Do not use 004 or 088 to claim literal-extraction accuracy.
- **Inference/attribution allowed:** include separately tagged and approved entailments such as 004 and the limited attribution reading of 088. Report those strata individually as well as any combined score.
- **Ambiguity:** report 067 separately and exclude it from the reviewed binary answerable/unanswerable denominator. The unchanged original/strict public-label view retains its original unanswerable label; a separately labelled lenient diagnostic may record 60, but that is not its reviewed primary gold.

Publish numerator and denominator for every view. Compare label versions on identical captured responses and common case sets to isolate relabeling effects; report exclusions separately. Never describe a gain caused by label changes as a model improvement. No scores exist for these new benchmark cases yet.

## Scope, aliases and evidence

The document binding defines the closed source scope. For a single-paper question, the paper is the referent unless the wording establishes another one. This does not permit importing world knowledge or silently correcting a malformed entity name. In particular, mapping “Miasta City Council” to Warsaw is not an automatic accepted alias.

Literal answers must preserve the requested fact, source type, units, negation and qualifiers. Name aliases are explicitly enumerated per case, not general fuzzy or substring matching. For 088, accept Richard Lindzen or Lindzen only with source-backed attribution of the uncertainty-understatement criticism. Do not claim a verbatim quote saying that models are uncertain, infer a statement by Houghton, or evaluate the scientific truth of the criticism.

For 074 the requested feature representation is TF-IDF. Joined bigrams are part of input token preparation, while LDA serves the separately described visualization task. A correct feature answer need not list the classifier algorithms as features. If an answer adds factual claims, those claims require their own source proof; they cannot be ignored merely because TF-IDF also occurs. Wider field/type matching decisions in D4 remain pending.

Evidence records use half-open `[start, end)` UTF-8 byte offsets into the hashed original scoped document; Unicode code-point offsets may also be supplied and must be labelled. Answer spans and supporting spans can differ: 004 extracts “MSP” but infers the non-exclusive citizenship requirement from the eligibility sentence. Source references and chunks in a later model request must be mapped to these bytes without assuming offsets survive parsing or prompt formatting.

Corpus gold and retrieved-context sufficiency are separate axes. After inference, retain the actual evidence/prompt input or its exact source mappings and hashes. Assess whether that specific context contained sufficient proof; if it did not, attribute the failure to retrieval/selection as appropriate without flipping the corpus gold to unanswerable. A missing capture is unknown context, not proof of insufficient evidence.

## Review provenance and limits

Audit both original answerable and unanswerable cases. The existing development screening covered all 120 cases before benchmark inference: 83 originally supported and 37 originally unanswerable. It flagged incorrect/incomplete positive answers as well as suspected false negatives. It was not an exhaustive independent adjudication of every case, and it did not use model disagreements to select the five D1 items.

Retain the implementation agent's original recommendation, Daniel's later decision, and the subsequent source-condition checks as separate records. They are not two independent blinded reviews: Daniel saw the agent's analysis, and the agent built the adapters. A true second blinded review is not fabricated or inferred from these records.

Record the original annotation's reason as unknown unless the source supplies it. A plausible-answer distractor, if present, is evidence about the annotation structure, not proof of the annotator's rationale. Interpretations such as “probably an adversarial entity substitution” remain hypotheses.

The [D1 amendment and changelog](../../docs/reports/t39-d1-adjudication-v1.1.md) binds the five case decisions. Its overlay is not accepted by the execution runner as an independent-review acceptance file. Keep sealed custody, remaining D2–D7 decisions, final proof/field definitions, source-family checks and the complete execution freeze separate.
