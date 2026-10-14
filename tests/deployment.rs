#![cfg(target_os = "linux")]
use base64::{Engine, engine::general_purpose::STANDARD};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs,
    sync::{
        Arc, Condvar, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use tempfile::TempDir;
use vectornext::{
    Database, Error, backup,
    contracts::*,
    ingestion::{context::*, *},
    service::{Application, Question, Search, Upload, remote::Client},
};

fn seed(db: &mut Database, job: &str, source: &[u8], media: MediaType, finish: bool) -> IngestJob {
    let encoder = TestEncoder::default();
    let mut config = IngestConfig::new(encoder.space());
    config.context = Some(ContextConfig::new(Policy::Structural, None));
    db.submit_ingestion(
        IngestRequest {
            job_id: job.into(),
            document_id: job.into(),
            expected_revision: None,
            media_type: media,
            config,
        },
        source,
    )
    .unwrap();
    if finish {
        let processor = LocalProcessor { encoder };
        while db.advance_ingestion(job, &processor).unwrap().stage != Stage::Committed {}
    }
    db.ingestion_job(job).unwrap().unwrap()
}

#[test]
fn export_restore_preserves_exact_records_jobs_receipts_and_resumes_once() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path().join("db")).unwrap();
    let done = seed(
        &mut db,
        "done",
        br#"[{"id":"a","large":9007199254740993.00000000000001,"zero":0,"unknown":null}]"#,
        MediaType::Json,
        true,
    );
    seed(
        &mut db,
        "pending",
        b"New evidence waiting to be embedded.",
        MediaType::Txt,
        false,
    );
    let before = serde_json::to_value(db.snapshot().documents().collect::<Vec<_>>()).unwrap();
    let export = root.path().join("export");
    let manifest = db.export(&export).unwrap();
    assert_eq!(manifest.generation, 1);
    assert_eq!(manifest.jobs, 2);
    assert!(matches!(
        Database::open(root.path().join("db")),
        Err(Error::Locked)
    ));
    let restored = root.path().join("restored");
    backup::restore(&export, &restored).unwrap();
    let mut copy = Database::open(&restored).unwrap();
    assert_eq!(
        serde_json::to_value(copy.snapshot().documents().collect::<Vec<_>>()).unwrap(),
        before
    );
    assert_eq!(copy.commit_ingestion("done").unwrap().receipt, done.receipt);
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    while copy.advance_ingestion("pending", &processor).unwrap().stage != Stage::Committed {}
    assert_eq!(copy.snapshot().generation(), 2);
    copy.commit_ingestion("pending").unwrap();
    assert_eq!(copy.snapshot().generation(), 2);
    assert!(backup::restore(&export, &restored).is_err());
    assert!(db.export(&root.path().join("db/nested-export")).is_err());
}

#[test]
fn backup_rejects_corruption_missing_extra_traversal_and_symlinks() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path().join("db")).unwrap();
    seed(&mut db, "a", b"Stored original text.", MediaType::Txt, true);
    for kind in ["corrupt", "missing", "extra", "traversal", "symlink"] {
        let source = root.path().join(kind);
        let manifest = db.export(&source).unwrap();
        let blob = manifest
            .files
            .keys()
            .find(|s| s.starts_with("blobs/"))
            .unwrap();
        match kind {
            "corrupt" => fs::write(source.join(blob), b"corrupted").unwrap(),
            "missing" => fs::remove_file(source.join(blob)).unwrap(),
            "extra" => {
                fs::write(source.join("unexpected"), b"extra").unwrap();
            }
            "traversal" => {
                let mut value = serde_json::to_value(&manifest).unwrap();
                value["files"]["../escape"] = json!({"bytes":1,"sha256":"a".repeat(64)});
                fs::write(
                    source.join("backup.json"),
                    serde_json::to_vec(&value).unwrap(),
                )
                .unwrap();
            }
            _ => {
                fs::remove_file(source.join(blob)).unwrap();
                std::os::unix::fs::symlink(root.path().join("db").join(blob), source.join(blob))
                    .unwrap();
            }
        }
        let destination = root.path().join(format!("restore-{kind}"));
        assert!(backup::restore(&source, &destination).is_err(), "{kind}");
        assert!(!destination.exists());
    }
}

#[test]
fn pending_pdf_artifact_survives_backup_and_restart() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path().join("db")).unwrap();
    let artifact =
        pdf::Artifact::from_slice(&fs::read("tests/fixtures/pdf/scanned_note.json").unwrap())
            .unwrap();
    let encoder = TestEncoder::default();
    let config = artifact.config(encoder.space(), false).unwrap();
    let bytes = serde_json::to_vec(&artifact).unwrap();
    let blob = db.put_original(&bytes).unwrap();
    assert_eq!(blob.sha256, config.pdf.as_ref().unwrap().artifact_sha256);
    db.submit_ingestion(
        IngestRequest {
            job_id: "pdf".into(),
            document_id: "pdf".into(),
            expected_revision: None,
            media_type: MediaType::Pdf,
            config,
        },
        &fs::read("evals/fixtures/scanned_note.pdf").unwrap(),
    )
    .unwrap();
    db.export(&root.path().join("backup")).unwrap();
    backup::restore(&root.path().join("backup"), &root.path().join("restored")).unwrap();
    let mut copy = Database::open(root.path().join("restored")).unwrap();
    let artifact = pdf::Artifact::from_slice(&copy.originals().get(&blob).unwrap()).unwrap();
    let processor = pdf::PdfProcessor {
        local: LocalProcessor { encoder },
        artifact,
    };
    while copy.advance_ingestion("pdf", &processor).unwrap().stage != Stage::Committed {}
    assert_eq!(copy.snapshot().generation(), 1);
}

#[test]
fn external_stage_failures_are_current_durable_and_explicitly_retried() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path()).unwrap();
    seed(&mut db, "a", b"Source text.", MediaType::Txt, false);
    let request = db.ingestion_stage_request("a").unwrap();
    db.reject_ingestion_stage(
        "a",
        &request.id().unwrap(),
        &Error::Unavailable("processor stopped".into()),
    )
    .unwrap();
    drop(db);
    let mut db = Database::open(root.path()).unwrap();
    assert_eq!(db.ingestion_job("a").unwrap().unwrap().failure_count, 1);
    db.retry_ingestion("a").unwrap();
    assert!(
        db.ingestion_job("a")
            .unwrap()
            .unwrap()
            .last_failure
            .is_none()
    );
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    db.advance_ingestion("a", &processor).unwrap();
    assert!(
        db.reject_ingestion_stage(
            "a",
            &request.id().unwrap(),
            &Error::Unavailable("stale".into())
        )
        .is_err()
    );
    assert_eq!(db.ingestion_job("a").unwrap().unwrap().stage, Stage::Parsed);
}

fn search(text: &str, mode: &str) -> Search {
    serde_json::from_value(json!({"text":text,"mode":mode})).unwrap()
}
#[test]
fn source_reads_keyword_and_exact_lookup_survive_processor_outage() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path()).unwrap();
    seed(
        &mut db,
        "record",
        br#"[{"id":"a","goals":0,"assists":null}]"#,
        MediaType::Json,
        true,
    );
    drop(db);
    let app = Application::open(root.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    assert_eq!(app.documents().unwrap()["generation"], 1);
    assert!(
        !app.search(search("goals", "keyword")).unwrap()["hits"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let question:Question=serde_json::from_value(json!({"request":{"question":"Read goals and assists of a.","scope":"structured_lookup",
        "filter":{"DocumentIds":["record"]},"fields":{"goals":{"kind":"integer","pointer":"/goals"},"assists":{"kind":"integer","nullable":true,"pointer":"/assists"}}}})).unwrap();
    let answer = app.ask(question).unwrap();
    assert_eq!(answer["answer"]["fields"]["goals"]["value"], 0);
    assert_eq!(answer["answer"]["fields"]["assists"]["value"], Value::Null);
    assert!(matches!(
        app.search(search("goals", "hybrid")),
        Err(Error::Unavailable(_))
    ));
    assert_eq!(app.snapshot().unwrap().generation(), 1);
    drop(app);
    let app = Application::open_with_weights(
        root.path(),
        Client::new("http://127.0.0.1:1".into()),
        0.0,
        0.0,
    )
    .unwrap();
    let trace = app.search(search("goals", "keyword")).unwrap();
    assert_eq!(trace["trace"]["keyword_config"]["structural_weight"], 0.0);
    assert_eq!(trace["trace"]["keyword_config"]["generated_weight"], 0.0);
    assert!(!trace["hits"].as_array().unwrap().is_empty());
    assert!(matches!(
        Application::open_with_weights(
            root.path(),
            Client::new("http://127.0.0.1:1".into()),
            f64::NAN,
            1.0,
        ),
        Err(Error::Invalid(_))
    ));
}

struct FakeProcessor {
    url: String,
    stopped: Arc<AtomicBool>,
    hold: Arc<(Mutex<(bool, bool)>, Condvar)>,
    thread: Option<thread::JoinHandle<()>>,
}
impl FakeProcessor {
    fn new() -> Self {
        let server = tiny_http::Server::http("127.0.0.1:0").unwrap();
        let url = format!("http://{}", server.server_addr());
        let stopped = Arc::new(AtomicBool::new(false));
        let stop = stopped.clone();
        let hold = Arc::new((Mutex::new((false, false)), Condvar::new()));
        let gate = hold.clone();
        let thread = thread::spawn(move || {
            let encoder = TestEncoder::default();
            let prompt = "synthetic generator test";
            let generator = GenerationConfig {
                model: "synthetic".into(),
                revision: "v1".into(),
                artifact_sha256: "a".repeat(64),
                runtime: "test".into(),
                prompt: prompt.into(),
                prompt_version: format!("{:x}", Sha256::digest(prompt)),
                temperature: 0,
                seed: 42,
                context_window: 4096,
                output_tokens: 256,
                annotation_tokens: 60,
            };
            while !stop.load(Ordering::Relaxed) {
                let Some(mut request) = server.recv_timeout(Duration::from_millis(50)).unwrap()
                else {
                    continue;
                };
                let value: Value = serde_json::from_reader(request.as_reader()).unwrap();
                if value["op"] == "count" {
                    let (lock, signal) = &*gate;
                    let mut state = lock.lock().unwrap();
                    state.0 = true;
                    signal.notify_all();
                    while !state.1 {
                        state = signal.wait(state).unwrap();
                    }
                }
                let result = match value["op"].as_str().unwrap() {
                    "profile" => json!({"space":encoder.space(),"generator":generator}),
                    "count" => json!(
                        encoder
                            .count_tokens(value["input"].as_str().unwrap())
                            .unwrap()
                    ),
                    "embed" => json!(encoder.embed(value["input"].as_str().unwrap()).unwrap()),
                    _ => panic!("unexpected operation"),
                };
                request
                    .respond(tiny_http::Response::from_string(
                        json!({"result":result}).to_string(),
                    ))
                    .unwrap();
            }
        });
        Self {
            url,
            stopped,
            hold,
            thread: Some(thread),
        }
    }
    fn release(&self) {
        let (lock, signal) = &*self.hold;
        lock.lock().unwrap().1 = true;
        signal.notify_all();
    }
}
impl Drop for FakeProcessor {
    fn drop(&mut self) {
        self.release();
        self.stopped.store(true, Ordering::Relaxed);
        self.thread.take().unwrap().join().unwrap();
    }
}

#[test]
fn ingestion_does_not_hold_database_lock_during_slow_models_and_refreshes_index() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path()).unwrap();
    seed(
        &mut db,
        "old",
        b"Old archived information.",
        MediaType::Txt,
        true,
    );
    drop(db);
    let fake = FakeProcessor::new();
    let app = Application::open(root.path(), Client::new(fake.url.clone())).unwrap();
    let old_snapshot = app.snapshot().unwrap();
    let upload = Upload {
        job_id: "new".into(),
        document_id: "new".into(),
        expected_revision: None,
        media_type: MediaType::Txt,
        policy: Policy::Structural,
        record_pointer: String::new(),
        allow_partial: false,
        source_base64: STANDARD.encode(b"New orchid evidence."),
    };
    app.upload(upload.clone()).unwrap();
    let worker = app.start();
    {
        let (lock, signal) = &*fake.hold;
        let state = lock.lock().unwrap();
        let (state, timeout) = signal
            .wait_timeout_while(state, Duration::from_secs(5), |s| !s.0)
            .unwrap();
        assert!(!timeout.timed_out() && state.0);
    }
    let started = Instant::now();
    assert_eq!(app.documents().unwrap()["generation"], 1);
    assert_eq!(
        app.search(search("archived", "keyword")).unwrap()["generation"],
        1
    );
    assert!(started.elapsed() < Duration::from_secs(1));
    fake.release();
    let deadline = Instant::now() + Duration::from_secs(5);
    while app.job("new").unwrap()["stage"] != "Committed" && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(10));
    }
    app.stop();
    worker.join().unwrap();
    assert_eq!(
        app.search(search("orchid", "keyword")).unwrap()["generation"],
        2
    );
    assert_eq!(old_snapshot.generation(), 1);
    assert!(old_snapshot.document("new").is_none());
    assert_eq!(
        app.upload(upload.clone()).unwrap()["receipt"]["generation"],
        2
    );
    let mut changed = upload;
    changed.source_base64 = STANDARD.encode(b"changed");
    assert!(app.upload(changed).is_err());
}
