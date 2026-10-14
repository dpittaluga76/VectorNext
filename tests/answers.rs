#![cfg(target_os = "linux")]
mod support;
use serde_json::{Value, json};
use std::{cell::RefCell, collections::BTreeMap};
use support::*;
use vectornext::{
    Database, Error, Result,
    answers::*,
    contracts::*,
    ingestion::{Encoder, IngestConfig, IngestRequest, LocalProcessor, Stage, TestEncoder},
    search::*,
};

struct Models {
    space: EmbeddingSpace,
    input: RefCell<Option<AnswerInput>>,
    response: Option<Answer>,
    budget: bool,
}
impl Models {
    fn new(space: EmbeddingSpace) -> Self {
        Self {
            space,
            input: RefCell::new(None),
            response: None,
            budget: false,
        }
    }
}
impl Encoder for Models {
    fn space(&self) -> EmbeddingSpace {
        self.space.clone()
    }
    fn count_tokens(&self, s: &str) -> Result<usize> {
        Ok(s.split_whitespace().count())
    }
    fn embed(&self, _: &str) -> Result<Vec<f32>> {
        let value = if self.space.normalization == Normalization::L2 {
            1. / (self.space.dimensions as f32).sqrt()
        } else {
            1.
        };
        Ok(vec![value; self.space.dimensions])
    }
}
impl AnswerModels for Models {
    fn rerank(&self, _: &str, passages: &[String]) -> Result<Rerank> {
        assert!(passages.iter().all(|p| !p.contains("GENERATED LIE")));
        Ok(Rerank {
            scores: passages
                .iter()
                .map(|p| {
                    if p.contains("H2 | 12 | 20") {
                        100.
                    } else if p.contains("1954") {
                        10.
                    } else {
                        0.
                    }
                })
                .collect(),
            pair_tokens: vec![30; passages.len()],
            identity: json!("test"),
        })
    }
    fn answer_tokens(&self, input: &AnswerInput) -> Result<usize> {
        Ok(if self.budget && input.evidence.len() > 1 {
            4000
        } else {
            100
        })
    }
    fn extract(&self, input: &AnswerInput) -> Result<Extraction> {
        *self.input.borrow_mut() = Some(input.clone());
        Ok(Extraction {
            answer: self.response.clone().unwrap_or(Answer {
                status: Status::InsufficientEvidence,
                fields: BTreeMap::new(),
            }),
            audit: json!({"fake":true}),
        })
    }
    fn rewrite(&self, _: &str, _: &Answer) -> Result<Value> {
        Err(Error::Invalid("unused".into()))
    }
}
fn request() -> AskRequest {
    serde_json::from_value(json!({"question":"How many goals did Pele score against Argentina in 1954?", "fields":{"goals":{"kind":"integer"}}})).unwrap()
}
fn source_evidence(text: &str) -> Evidence {
    Evidence {
        id: "E1".into(),
        key: ChunkKey {
            document_id: "d".into(),
            revision: "r1".into(),
            chunk_id: "c1".into(),
        },
        text: text.into(),
        sources: vec![SourceRef {
            revision: "r1".into(),
            locator: Locator::Json {
                pointer: "/0".into(),
                record_id: None,
            },
        }],
        spans: vec![],
        labels: vec![],
        record: None,
    }
}
fn supported(v: Value, quote: &str, pointer: Option<&str>) -> Answer {
    Answer {
        status: Status::Supported,
        fields: BTreeMap::from([(
            "goals".into(),
            FieldAnswer {
                value: v,
                evidence_id: "E1".into(),
                quote: quote.into(),
                pointer: pointer.map(str::to_owned),
            },
        )]),
    }
}
#[test]
fn rejects_schema_invalid_forged_quotes_wrong_ids_and_digit_substrings() {
    let r = request();
    let e = vec![source_evidence("He scored 3 in 1954.")];
    assert!(validate_answer(&r.fields, &e, &supported(json!(3), "He scored 3", None)).is_ok());
    for a in [
        supported(json!(9), "He scored 9", None),
        supported(json!(54), "1954", None),
        supported(json!(null), "He scored 3", None),
        Answer {
            status: Status::Supported,
            fields: BTreeMap::new(),
        },
        Answer {
            status: Status::Ambiguous,
            ..supported(json!(3), "3", None)
        },
    ] {
        assert!(validate_answer(&r.fields, &e, &a).is_err());
    }
    let mut a = supported(json!(3), "3", None);
    a.fields.get_mut("goals").unwrap().evidence_id = "fake".into();
    assert!(validate_answer(&r.fields, &e, &a).is_err());
    for text in ["3.5", "5.3", "-3", "3,000"] {
        assert!(
            validate_answer(
                &r.fields,
                &[source_evidence(text)],
                &supported(json!(3), text, None)
            )
            .is_err()
        );
    }
}
#[test]
fn exact_json_zero_null_missing_and_large_numbers() {
    let mut r = request();
    r.fields.get_mut("goals").unwrap().nullable = true;
    let mut e = source_evidence("");
    e.record = Some(serde_json::from_str(r#"{"zero":0,"null":null,"big":9007199254740993123456789,"decimal":1.000000000000000000001}"#).unwrap());
    for (p, v) in [
        ("/zero", json!(0)),
        ("/null", Value::Null),
        ("/big", e.record.as_ref().unwrap()["big"].clone()),
    ] {
        assert!(validate_answer(&r.fields, &[e.clone()], &supported(v, "", Some(p))).is_ok());
    }
    assert!(
        validate_answer(
            &r.fields,
            &[e.clone()],
            &supported(Value::Null, "", Some("/missing"))
        )
        .is_err()
    );
    assert!(
        validate_answer(
            &r.fields,
            &[e.clone()],
            &supported(json!(1), "", Some("/decimal"))
        )
        .is_err()
    );
    r.fields.get_mut("goals").unwrap().pointer = Some("/zero".into());
    assert!(validate_answer(&r.fields, &[e], &supported(Value::Null, "", Some("/null"))).is_err());
}
#[test]
fn templates_render_values_once_without_interpreting_value_braces() {
    let mut a = supported(json!(0), "", None);
    assert_eq!(render(&a, Some("Goals: {goals}")).unwrap(), "Goals: 0");
    a.fields.get_mut("goals").unwrap().value = json!("{other}");
    assert_eq!(
        render(&a, Some("Value: {goals}")).unwrap(),
        "Value: {other}"
    );
    assert!(render(&a, Some("{missing}")).is_err());
    assert!(render(&a, Some("{goals")).is_err());
}
#[test]
fn pipeline_preserves_constraints_filters_budget_and_generated_separation() {
    let (_dir, mut db) = database();
    let space = space(3);
    let mut doc = document(
        &mut db,
        "d",
        "r1",
        &[TARGET, NEAR, UNIT],
        vec![vec![1.; 3]; 3],
        &space,
    );
    doc.chunks[0].generated_context = Some(GeneratedContext {
        text: "GENERATED LIE".into(),
        model: "fake".into(),
        prompt_version: "v1".into(),
        source_scope: doc.chunks[0].sources.clone(),
    });
    publish(&mut db, doc, &space, None);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let mut models = Models::new(space);
    models.budget = true;
    let mut r = request();
    r.history = vec![Turn {
        role: Role::User,
        text: "We are discussing Pele, not Mira.".into(),
    }];
    r.filter = Filter::DocumentIds(["d".into()].into());
    let report = ask(&index, &models, r.clone()).unwrap();
    assert_eq!(report.request.question, r.question);
    assert!(report.search_text.contains("not Mira"));
    assert_eq!(report.evidence.len(), 1);
    assert!(report.evidence[0].text.contains("1954"));
    assert!(report.skipped.iter().any(|s| s.reason.contains("budget")));
    assert_eq!(report.retrieval.unwrap().request.filter, r.filter);
    assert_eq!(report.answer.status, Status::InsufficientEvidence);
}
fn ingest_json(bytes: &[u8]) -> (tempfile::TempDir, Database, EmbeddingSpace) {
    let (dir, mut db) = database();
    let encoder = TestEncoder::default();
    let space = encoder.space();
    db.submit_ingestion(
        IngestRequest {
            job_id: "j".into(),
            document_id: "d".into(),
            expected_revision: None,
            media_type: MediaType::Json,
            config: IngestConfig::new(space.clone()),
        },
        bytes,
    )
    .unwrap();
    let processor = LocalProcessor { encoder };
    while db.advance_ingestion("j", &processor).unwrap().stage != Stage::Committed {}
    (dir, db, space)
}
#[test]
fn bounded_options_keep_filter_and_expose_stage_timings() {
    let (_dir, db, space) = ingest_json(br#"[{"id":"a","goals":0},{"id":"b","goals":2}]"#);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let models = Models::new(space);
    let options = AnswerOptions {
        candidates: 1,
        rerank_limit: 1,
        primary_limit: 1,
        rerank: false,
    };
    let report = ask_with_options(&index, &models, request(), options.clone()).unwrap();
    assert_eq!(report.ranked.len(), 1);
    assert_eq!(report.reranker.unwrap()["reranking"], "disabled");
    assert_eq!(report.retrieval.unwrap().request.dense_k, 1);
    for stage in [
        "answer_total",
        "search_dense",
        "search_keyword",
        "search_fusion_dedup",
        "assembly_and_model_tokenization",
    ] {
        assert!(report.timings_ms[stage].is_finite() && report.timings_ms[stage] >= 0.0);
    }
    let invalid = AnswerOptions {
        candidates: 0,
        ..options
    };
    assert!(ask_with_options(&index, &models, request(), invalid).is_err());
}
#[test]
fn structured_lookup_scans_all_records_and_dedupes_copies() {
    let (_dir, db, space) =
        ingest_json(br#"[{"id":"a","goals":0,"assists":null},{"id":"b","goals":2}]"#);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let models = Models::new(space);
    let mut r = request();
    r.scope = Scope::StructuredLookup;
    r.fields.get_mut("goals").unwrap().pointer = Some("/goals".into());
    r.filter = Filter::Attribute {
        key: "record".into(),
        pointer: "/id".into(),
        predicate: Predicate::Eq(json!("a")),
        trust: AttributeTrust::SourceOrDeterministic,
    };
    let report = ask(&index, &models, r.clone()).unwrap();
    assert_eq!(report.answer.fields["goals"].value, json!(0));
    assert_eq!(report.audit["eligible_records"], 1);
    r.fields.get_mut("goals").unwrap().pointer = Some("/assists".into());
    r.fields.get_mut("goals").unwrap().nullable = true;
    assert!(
        ask(&index, &models, r.clone()).unwrap().answer.fields["goals"]
            .value
            .is_null()
    );
    r.fields.get_mut("goals").unwrap().pointer = Some("/missing".into());
    assert_eq!(
        ask(&index, &models, r.clone()).unwrap().answer.status,
        Status::InsufficientEvidence
    );
    r.filter = Filter::DocumentIds(["d".into()].into());
    assert_eq!(
        ask(&index, &models, r).unwrap().answer.status,
        Status::Ambiguous
    );
    assert!(models.input.borrow().is_none());
}
#[test]
fn source_headings_and_duplicate_spans_are_preserved_once() {
    let (_dir, mut db) = database();
    let space = space(3);
    let mut doc = document(
        &mut db,
        "d",
        "r1",
        &["# Cup 1954", "He scored 3 goals."],
        vec![vec![1.; 3]; 2],
        &space,
    );
    doc.blocks[0].kind = BlockKind::Heading;
    doc.blocks[1].parent = Some("b0".into());
    doc.chunks[1].parent = Some("c0".into());
    let mut copy = doc.chunks[1].clone();
    copy.id = "copy".into();
    doc.chunks.push(copy);
    publish(&mut db, doc, &space, None);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let models = Models::new(space);
    let report = ask(&index, &models, request()).unwrap();
    assert!(
        report
            .evidence
            .iter()
            .any(|e| e.text.contains("# Cup 1954") && e.text.contains("He scored 3"))
    );
    assert!(report.evidence.iter().any(|e| e.sources.len() == 2));
    assert_eq!(
        report
            .evidence
            .iter()
            .map(|e| e.text.matches("# Cup 1954").count())
            .sum::<usize>(),
        1
    );
}
#[test]
fn aggregate_and_overlong_questions_fail_explicitly() {
    let (_dir, db, space) = ingest_json(br#"[{"goals":0}]"#);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let models = Models::new(space);
    let mut r = request();
    r.scope = Scope::CorpusAggregate;
    assert!(ask(&index, &models, r.clone()).is_err());
    r.scope = Scope::Passage;
    r.question = "What is the sum of goals across all records?".into();
    assert!(ask(&index, &models, r.clone()).is_err());
    r.question = "question ".repeat(300);
    assert!(ask(&index, &models, r).is_err());
}

#[test]
fn verified_source_null_abstains_for_counts_but_remains_supported_when_requested_raw() {
    let (_dir, db, space) = ingest_json(br#"[{"id":"a","goals":null}]"#);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let mut models = Models::new(space);
    models.response = Some(supported(Value::Null, "", Some("/goals")));
    let mut r = request();
    let report = ask(&index, &models, r.clone()).unwrap();
    assert_eq!(report.answer.status, Status::InsufficientEvidence);
    assert!(report.answer.fields.is_empty());
    assert_eq!(
        report.audit["source_null_abstention"]["verified_source_fields"]["goals"]["value"],
        Value::Null
    );
    r.fields.get_mut("goals").unwrap().nullable = true;
    assert_eq!(
        ask(&index, &models, r).unwrap().answer.status,
        Status::Supported
    );
    models.response = Some(supported(Value::Null, "", Some("/missing")));
    assert!(ask(&index, &models, request()).is_err());
    models.response = Some(supported(json!(0), "", Some("/goals")));
    assert!(ask(&index, &models, request()).is_err());
}

#[test]
fn json_selection_materializes_exact_values_without_model_transcription() {
    let (_dir, db, space) = ingest_json(br#"[{"goals":9007199254740993.00000000000001}]"#);
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let mut models = Models::new(space);
    models.response = Some(supported(Value::Null, "", Some("/goals")));
    let mut r = request();
    r.fields.get_mut("goals").unwrap().kind = FieldKind::Number;
    let report = ask(&index, &models, r.clone()).unwrap();
    assert_eq!(
        report.answer.fields["goals"].value.to_string(),
        "9007199254740993.00000000000001"
    );
    assert_eq!(
        report.audit["json_values_resolved_from_source"],
        json!(["goals"])
    );
    r.fields.get_mut("goals").unwrap().pointer = Some("/other".into());
    assert!(ask(&index, &models, r).is_err());
}

#[test]
fn pdf_table_expansion_keeps_units_without_repeating_parent_table_rows() {
    use vectornext::ingestion::pdf::{Artifact, PdfProcessor};
    let (_dir, mut db) = database();
    let artifact =
        Artifact::from_slice(&std::fs::read("tests/fixtures/pdf/equipment_guide.json").unwrap())
            .unwrap();
    let processor = PdfProcessor {
        local: LocalProcessor {
            encoder: TestEncoder::default(),
        },
        artifact,
    };
    let space = processor.local.encoder.space();
    let config = processor.artifact.config(space.clone(), false).unwrap();
    db.submit_ingestion(
        IngestRequest {
            job_id: "pdf".into(),
            document_id: "pdf".into(),
            expected_revision: None,
            media_type: MediaType::Pdf,
            config,
        },
        &std::fs::read("evals/fixtures/equipment_guide.pdf").unwrap(),
    )
    .unwrap();
    while db.advance_ingestion("pdf", &processor).unwrap().stage != Stage::Committed {}
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let report = ask(&index, &Models::new(space), request()).unwrap();
    let text = report
        .evidence
        .iter()
        .map(|e| e.text.as_str())
        .collect::<Vec<_>>()
        .join("\n");
    assert_eq!(text.matches("H2 | 12 | 20").count(), 1);
    assert_eq!(text.matches("Model | Flow (L/min) | Water (C)").count(), 1);
    assert!(text.contains("Nominal flow at water temperature 20 C"));
}
