//! Post-T14 deterministic diagnostic; no models, dataset labels or database access.
use serde_json::json;
use std::collections::BTreeMap;
use vectornext::answers::{Answer, Evidence, FieldSpec, validate_answer};

fn main() {
    let fields: BTreeMap<String, FieldSpec> =
        serde_json::from_value(json!({"count":{"kind":"integer"}})).unwrap();
    let cases = [
        ("grouped", "Count: 3,000.", "3,000", 3000),
        ("fragment", "Count: 3,000.", "3", 3),
        ("date", "Date: Feb. 25,1969", "Feb. 25,1969", 1969),
    ];
    let rows: Vec<_> = cases.into_iter().map(|(id, source, quote, value)| {
        let evidence: Evidence = serde_json::from_value(json!({
            "id":"E1","key":{"document_id":"synthetic-probe","revision":"r1","chunk_id":"c1"},
            "text":source,"sources":[{"revision":"r1","locator":{"Text":{
                "bytes":{"start":0,"end":source.len()},"line_start":1,"line_end":1,"encoding":"UTF-8",
                "mappings":[{"normalized":{"start":0,"end":source.len()},"original":{"start":0,"end":source.len()}}]
            }}}],
            "spans":[],"labels":[],"record":null
        })).unwrap();
        let answer: Answer = serde_json::from_value(json!({"status":"supported","fields":{
            "count":{"value":value,"evidence_id":"E1","quote":quote,"pointer":null}
        }})).unwrap();
        let result = validate_answer(&fields, &[evidence], &answer);
        json!({"case":id,"source":source,"quote":quote,"value":value,
            "accepted":result.is_ok(),"error":result.err().map(|e|e.to_string())})
    }).collect();
    println!("{}", serde_json::to_string_pretty(&json!({"purpose":"post-T14 mechanical support diagnostic; not a quality benchmark", "cases":rows})).unwrap());
}
