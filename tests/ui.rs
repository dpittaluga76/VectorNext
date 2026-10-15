#![cfg(target_os = "linux")]
use serde_json::{Value, json};
use tempfile::TempDir;
use vectornext::{
    Database,
    contracts::*,
    ingestion::*,
    service::{Application, http, remote::Client, ui},
};

#[test]
fn unfinished_replacement_blocks_removal_and_other_uploads() {
    use base64::{Engine, engine::general_purpose::STANDARD};
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    let config = IngestConfig::new(processor.encoder.space());
    db.submit_ingestion(
        IngestRequest {
            job_id: "first".into(),
            document_id: "doc".into(),
            expected_revision: None,
            media_type: MediaType::Txt,
            config: config.clone(),
        },
        b"First source.",
    )
    .unwrap();
    while db.advance_ingestion("first", &processor).unwrap().stage != Stage::Committed {}
    let revision = db.snapshot().document("doc").unwrap().revision.clone();
    db.submit_ingestion(
        IngestRequest {
            job_id: "pending".into(),
            document_id: "doc".into(),
            expected_revision: Some(revision.clone()),
            media_type: MediaType::Txt,
            config,
        },
        b"Replacement.",
    )
    .unwrap();
    drop(db);
    let app = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    assert!(matches!(
        app.ui_remove("doc", &revision),
        Err(vectornext::Error::Conflict(_))
    ));
    assert_eq!(
        app.ui_library().unwrap()["documents"][0]["processing"],
        true
    );
    let result = app.upload(vectornext::service::Upload {
        job_id: "another".into(),
        document_id: "doc".into(),
        expected_revision: Some(revision),
        media_type: MediaType::Txt,
        policy: vectornext::ingestion::context::Policy::Structural,
        record_pointer: String::new(),
        allow_partial: false,
        source_base64: STANDARD.encode(b"Another replacement."),
    });
    assert!(matches!(result, Err(vectornext::Error::Conflict(_))));
}

#[test]
fn browser_retry_is_identity_bound_even_after_removal_and_offline() {
    use vectornext::ingestion::context::{ContextConfig, Policy};
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    let mut config = IngestConfig::new(processor.encoder.space());
    config.source_name = Some("sample.txt".into());
    config.context = Some(ContextConfig::new(Policy::Structural, None));
    let id = "1234567890123456";
    let source = b"First source.";
    db.submit_ingestion(
        IngestRequest {
            job_id: format!("ui-{id}"),
            document_id: format!("doc-{id}"),
            expected_revision: None,
            media_type: MediaType::Txt,
            config,
        },
        source,
    )
    .unwrap();
    while db
        .advance_ingestion(&format!("ui-{id}"), &processor)
        .unwrap()
        .stage
        != Stage::Committed
    {}
    let revision = db
        .snapshot()
        .document(&format!("doc-{id}"))
        .unwrap()
        .revision
        .clone();
    drop(db);
    let app = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    let metadata =
        |name: &str| serde_json::from_value(json!({"upload_id":id,"filename":name})).unwrap();
    assert!(
        app.ui_upload(metadata("sample.txt"), source.to_vec())
            .is_ok()
    );
    assert!(
        app.ui_upload(metadata("different.txt"), source.to_vec())
            .is_err()
    );
    assert!(
        app.ui_upload(metadata("sample.txt"), b"changed".to_vec())
            .is_err()
    );
    app.ui_remove(&format!("doc-{id}"), &revision).unwrap();
    assert_eq!(app.ui_upload_status(id).unwrap()["state"], "acknowledged");
    assert!(
        app.ui_upload(metadata("sample.txt"), source.to_vec())
            .is_ok()
    );
    assert_eq!(app.ui_library().unwrap()["documents"], json!([]));
}

#[test]
fn same_origin_is_local_and_exact() {
    assert!(http::origin_allowed(
        "localhost:8088",
        "http://localhost:8088"
    ));
    for (host, origin) in [
        ("localhost:8088", "null"),
        ("localhost:8088", "http://localhost:9999"),
        ("evil.test", "http://evil.test"),
        ("localhost:8088", "http://localhost:8088.evil.test"),
    ] {
        assert!(!http::origin_allowed(host, origin));
    }
}
#[test]
fn metadata_absence_preserves_old_serialization() {
    let config = IngestConfig::new(TestEncoder::default().space());
    let old = serde_json::to_value(&config).unwrap();
    assert!(old.get("source_name").is_none());
    let restored: IngestConfig = serde_json::from_value(old.clone()).unwrap();
    assert_eq!(serde_json::to_value(restored).unwrap(), old);
}
#[test]
fn planner_rejects_invented_values_and_pointers() {
    let plan = json!({"plan":{"status":"ready","fields":[{"name":"year","kind":"integer","nullable":false,"description":"Launch year"}]}});
    assert!(ui::parse_plan(&plan).unwrap()["year"].pointer.is_none());
    for key in ["value", "pointer", "filter", "question"] {
        let mut bad = plan.clone();
        bad["plan"]["fields"][0][key] = json!("bad");
        assert!(ui::parse_plan(&bad).is_err());
    }
    let mut duplicate = plan.clone();
    duplicate["plan"]["fields"]
        .as_array_mut()
        .unwrap()
        .push(plan["plan"]["fields"][0].clone());
    assert!(ui::parse_plan(&duplicate).is_err());
    assert!(ui::parse_plan(&json!({"plan":{"status":"unsupported","fields":[]}})).is_err());
}
#[test]
fn planner_errors_distinguish_clarification_aggregation_and_invalid_plans() {
    let parse = |status: &str| {
        ui::parse_plan(&json!({"plan":{"status":status,"fields":[]}}))
            .unwrap_err()
            .to_string()
    };
    assert!(parse("needs_clarification").contains("name the subject and requested fact"));
    assert!(parse("unsupported").contains("calculations across records"));
    assert!(parse("unrecognized").contains("invalid planning status"));
    assert!(parse("ready").contains("invalid planned field count"));
    let bad = json!({"plan":{"status":"needs_clarification","fields":[{"name":"x","kind":"string","nullable":false,"description":"x"}]}});
    assert!(
        ui::parse_plan(&bad)
            .unwrap_err()
            .to_string()
            .contains("fields must be empty")
    );
}

#[test]
fn exact_numbers_only_cross_browser_boundary_as_text() {
    let raw:Value=serde_json::from_str(r#"{"answer":{"status":"supported","fields":{"amount":{"value":9007199254740993.00000000000001,"evidence_id":"E1","quote":"","pointer":"/amount"},"zero":{"value":0},"unknown":{"value":null}}},"request":{"fields":{"amount":{"kind":"number"},"zero":{"kind":"integer"}}},"evidence":[{"id":"E1","record":{"amount":9007199254740993.00000000000001}}],"generation":9007199254740993}"#).unwrap();
    let view = ui::answer_view(&raw).unwrap();
    assert_eq!(
        view["fields"][0]["value_text"],
        "9007199254740993.00000000000001"
    );
    assert_eq!(view["fields"][1]["kind"], "null");
    assert_eq!(view["fields"][2]["value_text"], "0");
    assert_eq!(
        serde_json::from_str::<Value>(view["raw_report"].as_str().unwrap()).unwrap(),
        raw
    );
    assert!(
        view["evidence"][0]["record_text"]
            .as_str()
            .unwrap()
            .contains("9007199254740993.00000000000001")
    );
}
#[test]
fn multipart_requires_one_file_and_metadata() {
    let body=b"--boundary\r\nContent-Disposition: form-data; name=\"metadata\"\r\n\r\n{\"upload_id\":\"1234567890123456\",\"filename\":\"sample.txt\"}\r\n--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sample.txt\"\r\n\r\nHello\r\n--boundary--\r\n";
    let (metadata, bytes) = http::parse_multipart(body.as_slice(), "boundary".into()).unwrap();
    assert_eq!(metadata.filename, "sample.txt");
    assert_eq!(bytes, b"Hello");
    assert!(http::parse_multipart(b"--boundary--\r\n".as_slice(), "boundary".into()).is_err());
}
#[test]
fn removal_is_revision_bound_and_keeps_jobs_and_originals() {
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    let config = IngestConfig::new(processor.encoder.space());
    db.submit_ingestion(
        IngestRequest {
            job_id: "seed".into(),
            document_id: "doc".into(),
            expected_revision: None,
            media_type: MediaType::Txt,
            config: config.clone(),
        },
        b"Voyager 1 launched in 1977.",
    )
    .unwrap();
    while db.advance_ingestion("seed", &processor).unwrap().stage != Stage::Committed {}
    let revision = db.snapshot().document("doc").unwrap().revision.clone();
    drop(db);
    let app = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    assert!(app.ui_remove("doc", "stale").is_err());
    assert!(app.ui_source("doc", &revision).is_ok());
    app.ui_remove("doc", &revision).unwrap();
    assert!(app.ui_source("doc", &revision).is_err());
    assert!(app.job("seed").is_ok());
    assert_eq!(app.ui_library().unwrap()["documents"], json!([]));
    drop(app);
    let db = Database::open(tmp.path()).unwrap();
    let job = db.ingestion_job("seed").unwrap().unwrap();
    assert!(db.originals().get(&job.draft.document.original).is_ok());
}
