//! Offline diagnostic comparison. No service route or runtime validator switch.
use super::*;

/// Source-ordered evidence using the production bundler, for offline diagnostics.
pub fn document_evidence(document: &DocumentRevision) -> Vec<Evidence> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for chunk in &document.chunks {
        let key = ChunkKey {
            document_id: document.document_id.clone(),
            revision: document.revision.clone(),
            chunk_id: chunk.id.clone(),
        };
        let evidence = bundle(document, chunk, &key, format!("E{}", result.len() + 1));
        if seen.insert(identity(&evidence)) {
            result.push(evidence);
        }
    }
    result
}

/// Observe the same captured candidate before/after mechanical validation.
/// Values read from JSON are materialized by the production resolver; unresolved
/// placeholders are never treated as answer values, even in the disabled arm.
pub fn compare_candidate(input: &AnswerInput, candidate: &Answer) -> Value {
    let mut materialized = candidate.clone();
    let resolved = match resolve_json_values(input, &mut materialized) {
        Ok(fields) => fields,
        Err(error) => {
            return json!({"diagnostic_only":true,"materialization":"rejected",
            "error":error.to_string(),"candidate":candidate,"validator_on":null,"validator_off":null});
        }
    };
    let mut enabled = materialized.clone();
    let mut stage = "validate_answer";
    let mut source_null = false;
    let validation = (|| {
        if enabled.status == Status::Supported
            && enabled.fields.iter().any(|(name, proof)| {
                proof.value.is_null() && input.fields.get(name).is_some_and(|f| !f.nullable)
            })
        {
            stage = "validate_source_null";
            let mut fields = input.fields.clone();
            for field in fields.values_mut() {
                field.nullable = true;
            }
            validate_answer(&fields, &input.evidence, &enabled)?;
            enabled = Answer::empty(Status::InsufficientEvidence);
            source_null = true;
        }
        stage = "validate_answer";
        validate_answer(&input.fields, &input.evidence, &enabled)
    })();
    let on = match validation {
        Ok(()) => json!({"state":"accepted","answer":enabled}),
        Err(error) => json!({"state":"rejected","stage":stage,"error":error.to_string()}),
    };
    json!({"diagnostic_only":true,"materialization":"completed","resolved_fields":resolved,
        "candidate":candidate,"validator_off":{"state":"untrusted","answer":materialized},
        "validator_on":on,"source_null_abstention":source_null,
        "semantic_correctness":"requires_independent_labels_and_proof_review"})
}

#[cfg(test)]
mod tests {
    use super::*;

    fn input(text: &str, record: Value, nullable: bool) -> AnswerInput {
        serde_json::from_value(json!({"question":"What is the count?","history":[],
            "fields":{"count":{"kind":"integer","nullable":nullable,"description":"count","pointer":null}},
            "evidence":[{"id":"E1","key":{"document_id":"d","revision":"r","chunk_id":"c"},
                "text":text,"record":record,"sources":[{"revision":"r","locator":{
                    "Json":{"pointer":"","record_id":null}}}],
                "spans":[],"labels":[]}],"constrain_pointers":true})).unwrap()
    }
    fn candidate(value: Value, quote: &str, pointer: Option<&str>) -> Answer {
        serde_json::from_value(json!({"status":"supported","fields":{"count":{
            "value":value,"evidence_id":"E1","quote":quote,"pointer":pointer}}}))
        .unwrap()
    }
    #[test]
    fn exact_materialization_is_shared_and_missing_is_not_null() {
        let record: Value = serde_json::from_str("{\"count\":9007199254740993123}").unwrap();
        let input = input(&record.to_string(), record.clone(), false);
        let result = compare_candidate(&input, &candidate(Value::Null, "", Some("/count")));
        assert_eq!(
            result["validator_off"]["answer"]["fields"]["count"]["value"],
            record["count"]
        );
        assert_eq!(
            result["validator_on"]["answer"]["fields"]["count"]["value"],
            record["count"]
        );
        let missing = compare_candidate(&input, &candidate(Value::Null, "", Some("/missing")));
        assert_eq!(missing["materialization"], "rejected");
        assert!(missing["validator_off"].is_null());
    }
    #[test]
    fn source_null_and_zero_keep_production_decisions() {
        for value in [Value::Null, json!(0)] {
            let record = json!({"count":value});
            for nullable in [false, true] {
                let input = input(&record.to_string(), record.clone(), nullable);
                let result = compare_candidate(&input, &candidate(Value::Null, "", Some("/count")));
                assert_eq!(
                    result["source_null_abstention"],
                    value.is_null() && !nullable
                );
                assert_eq!(
                    result["validator_on"]["answer"]["status"],
                    if value.is_null() && !nullable {
                        "insufficient_evidence"
                    } else {
                        "supported"
                    }
                );
            }
        }
    }
    #[test]
    fn rejected_numeric_fragment_remains_diagnostic_not_a_fact() {
        let input = input("The count is 3,000.", Value::Null, false);
        let result = compare_candidate(&input, &candidate(json!(3), "3", None));
        assert_eq!(
            result["validator_off"]["answer"]["fields"]["count"]["value"],
            3
        );
        assert_eq!(result["validator_on"]["state"], "rejected");
        assert_eq!(result["diagnostic_only"], true);
    }
}
