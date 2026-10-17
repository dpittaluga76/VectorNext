#![cfg(target_os = "linux")]
use axum::{
    Router,
    body::{Body, to_bytes},
    http::Request,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use tempfile::TempDir;
use tower::ServiceExt;
use vectornext::{
    Database,
    contracts::*,
    ingestion::{context::*, *},
    service::{Application, http, remote::Client},
};

const EXACT: &str = "9007199254740993.00000000000001";

fn seed(db: &mut Database, id: &str, bytes: &[u8], media_type: MediaType) {
    let encoder = TestEncoder::default();
    let mut config = IngestConfig::new(encoder.space());
    config.context = Some(ContextConfig::new(Policy::Structural, None));
    db.submit_ingestion(
        IngestRequest {
            job_id: id.into(),
            document_id: id.into(),
            expected_revision: None,
            media_type,
            config,
        },
        bytes,
    )
    .unwrap();
    let processor = LocalProcessor { encoder };
    while db.advance_ingestion(id, &processor).unwrap().stage != Stage::Committed {}
}

async fn request(
    router: &Router,
    method: &str,
    path: &str,
    content_type: &str,
    body: Vec<u8>,
) -> (u16, String) {
    let response = router
        .clone()
        .oneshot(
            Request::builder()
                .method(method)
                .uri(path)
                .header("Host", "localhost:8099")
                .header("Content-Type", content_type)
                .header("X-VectorNext-Client", "1")
                .header("Content-Length", body.len())
                .body(Body::from(body))
                .unwrap(),
        )
        .await
        .unwrap();
    (
        response.status().as_u16(),
        String::from_utf8(
            to_bytes(response.into_body(), 32 * 1024 * 1024)
                .await
                .unwrap()
                .to_vec(),
        )
        .unwrap(),
    )
}
async fn post(router: &Router, path: &str, value: Value) -> (u16, Value) {
    let (status, raw) = request(
        router,
        "POST",
        path,
        "application/json",
        serde_json::to_vec(&value).unwrap(),
    )
    .await;
    (status, serde_json::from_str(&raw).unwrap())
}
async fn get(router: &Router, path: &str) -> (u16, String) {
    request(router, "GET", path, "application/json", vec![]).await
}
fn multipart(id: &str, text: &str) -> Vec<u8> {
    format!("--x\r\nContent-Disposition: form-data; name=\"metadata\"\r\n\r\n{{\"upload_id\":\"{id}\",\"filename\":\"fixture.txt\"}}\r\n--x\r\nContent-Disposition: form-data; name=\"file\"; filename=\"fixture.txt\"\r\n\r\n{text}\r\n--x--\r\n").into_bytes()
}

/// Deterministic processor protocol substitute, never a semantic quality claim.
struct Processor {
    url: String,
    stop: Arc<AtomicBool>,
    release: Arc<AtomicBool>,
    entered: Arc<AtomicUsize>,
    thread: Option<thread::JoinHandle<()>>,
}
impl Processor {
    fn new(hold: bool) -> Self {
        let server = tiny_http::Server::http("127.0.0.1:0").unwrap();
        let url = format!("http://{}", server.server_addr());
        let stop = Arc::new(AtomicBool::new(false));
        let release = Arc::new(AtomicBool::new(!hold));
        let entered = Arc::new(AtomicUsize::new(0));
        let (s, r, e) = (stop.clone(), release.clone(), entered.clone());
        let thread = thread::spawn(move || {
            let mut workers = vec![];
            while !s.load(Ordering::SeqCst) {
                let Some(mut req) = server.recv_timeout(Duration::from_millis(10)).unwrap() else {
                    continue;
                };
                let (r, e) = (r.clone(), e.clone());
                workers.push(thread::spawn(move || {
                    e.fetch_add(1, Ordering::SeqCst);
                    while !r.load(Ordering::SeqCst) { thread::sleep(Duration::from_millis(2)); }
                    let output = if req.method().as_str() == "GET" {
                        json!({"capabilities":{"embedding":true,"generation":true,"pdf":true,"reranking":true}})
                    } else {
                        let value: Value = serde_json::from_reader(req.as_reader()).unwrap();
                        if req.url().starts_with("/generation/") {
                            let output=json!({"model":value["model"],"token":value["token"],"activation_seconds":0,"reconciled":true});
                            let _=req.respond(tiny_http::Response::from_string(output.to_string()));
                            return;
                        }
                        let input = &value["input"];
                        let encoder = TestEncoder::default();
                        let result = match value["op"].as_str().unwrap() {
                            "profile" => {
                                let prompt = "synthetic HTTP compatibility fixture";
                                json!({"space":encoder.space(),"generator":GenerationConfig{
                                    model:"synthetic".into(), revision:"v1".into(),artifact_sha256:"a".repeat(64),runtime:"test".into(),
                                    prompt:prompt.into(),prompt_version:format!("{:x}",Sha256::digest(prompt)),temperature:0.into(),seed:42,
                                    context_window:4096,output_tokens:256,annotation_tokens:60}})
                            }
                            "count" => json!(encoder.count_tokens(input.as_str().unwrap()).unwrap()),
                            "embed" => json!(encoder.embed(input.as_str().unwrap()).unwrap()),
                            "answer_tokens" => json!(100),
                            "plan_fields" => json!({"plan":{"status":"ready","fields":[{"name":"amount","kind":"number","nullable":false,"description":"Stored amount"}]}}),
                            "answer" => {
                                let question = input["question"].as_str().unwrap();
                                let status = if question.contains("ambiguous") { "ambiguous" } else if question.contains("missing") { "insufficient_evidence" } else { "supported" };
                                let mut fields = json!({});
                                if status == "supported" {
                                    for (name, _) in input["fields"].as_object().unwrap() {
                                        fields[name] = json!({"value":null,"evidence_id":input["evidence"][0]["id"],"quote":"",
                                            "pointer":if question.contains("reject") {"/nonexistent".to_owned()} else {format!("/{name}")}});
                                    }
                                }
                                json!({"answer":{"status":status,"fields":fields},"audit":{"fixture":true}})
                            }
                            other => panic!("unexpected processor operation {other}"),
                        };
                        json!({"result":result})
                    };
                    let _ = req.respond(tiny_http::Response::from_string(output.to_string()));
                }));
            }
            for worker in workers {
                worker.join().unwrap();
            }
        });
        Self {
            url,
            stop,
            release,
            entered,
            thread: Some(thread),
        }
    }
    async fn wait_for(&self, count: usize) {
        let deadline = Instant::now() + Duration::from_secs(2);
        while self.entered.load(Ordering::SeqCst) < count {
            assert!(
                Instant::now() < deadline,
                "processor never received {count} operations"
            );
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    }
}
impl Drop for Processor {
    fn drop(&mut self) {
        self.release.store(true, Ordering::SeqCst);
        self.stop.store(true, Ordering::SeqCst);
        self.thread.take().unwrap().join().unwrap();
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn disconnected_requests_retain_all_sixteen_permits_until_work_finishes() {
    let tmp = TempDir::new().unwrap();
    let processor = Processor::new(true);
    let app = Application::open(tmp.path(), Client::new(processor.url.clone())).unwrap();
    let router = http::router(app);
    let tasks: Vec<_> = (0..16)
        .map(|_| {
            let r = router.clone();
            tokio::spawn(async move { get(&r, "/v1/metrics").await })
        })
        .collect();
    processor.wait_for(16).await;
    for task in tasks {
        task.abort();
        let _ = task.await;
    }
    let (status, body) = get(&router, "/healthz").await;
    assert_eq!(status, 503);
    assert_eq!(
        serde_json::from_str::<Value>(&body).unwrap()["error"]["message"],
        "HTTP capacity reached; retry later"
    );
    processor.release.store(true, Ordering::SeqCst);
    let deadline = Instant::now() + Duration::from_secs(2);
    while get(&router, "/healthz").await.0 != 200 {
        assert!(Instant::now() < deadline);
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn interrupted_upload_reconciles_preparation_and_one_durable_job() {
    let tmp = TempDir::new().unwrap();
    let processor = Processor::new(true);
    let app = Application::open(tmp.path(), Client::new(processor.url.clone())).unwrap();
    let router = http::router(app.clone());
    let id = "t19-upload-reconciliation";
    let r = router.clone();
    let task = tokio::spawn(async move {
        request(
            &r,
            "POST",
            "/v1/ui/upload",
            "multipart/form-data; boundary=x",
            multipart(id, "Stored evidence."),
        )
        .await
    });
    processor.wait_for(1).await;
    task.abort();
    let _ = task.await;
    assert_eq!(
        post(&router, "/v1/ui/upload-status", json!({"upload_id":id}))
            .await
            .1["state"],
        "preparing"
    );
    assert_eq!(
        request(
            &router,
            "POST",
            "/v1/ui/upload",
            "multipart/form-data; boundary=x",
            multipart(id, "Stored evidence.")
        )
        .await
        .0,
        503
    );
    assert_eq!(get(&router, "/v1/ui/library").await.0, 200);
    processor.release.store(true, Ordering::SeqCst);
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        let (_, v) = post(&router, "/v1/ui/upload-status", json!({"upload_id":id})).await;
        if v["state"] == "acknowledged" {
            break;
        }
        assert!(Instant::now() < deadline);
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
    assert_eq!(
        request(
            &router,
            "POST",
            "/v1/ui/upload",
            "multipart/form-data; boundary=x",
            multipart(id, "Stored evidence.")
        )
        .await
        .0,
        202
    );
    assert_eq!(app.jobs().unwrap()["jobs"].as_array().unwrap().len(), 1);
    drop(router);
    drop(app);
    let reopened = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    assert_eq!(
        reopened.ui_upload_status(id).unwrap()["state"],
        "acknowledged"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn answer_outcomes_and_exact_values_cross_the_http_boundary() {
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    seed(
        &mut db,
        "numbers",
        format!(r#"[{{"amount":{EXACT},"zero":0,"unknown":null}}]"#).as_bytes(),
        MediaType::Json,
    );
    drop(db);
    let processor = Processor::new(false);
    let app = Application::open(tmp.path(), Client::new(processor.url.clone())).unwrap();
    let router = http::router(app);
    let fields = json!({"amount":{"kind":"number","pointer":"/amount"},"zero":{"kind":"integer","pointer":"/zero"},"unknown":{"kind":"integer","nullable":true,"pointer":"/unknown"}});
    let (status,legacy)=post(&router,"/v1/ask",json!({"request":{"question":"Read the numbers","fields":fields,"scope":"structured_lookup","filter":{"DocumentIds":["numbers"]}}})).await;
    assert_eq!(status, 200, "{legacy}");
    assert_eq!(
        legacy["answer"]["fields"]["amount"]["value"].to_string(),
        EXACT
    );
    for outcome in ["supported", "ambiguous", "missing", "reject"] {
        let (status,answer)=post(&router,"/v1/ui/ask",json!({"question":format!("{outcome} amount"),"document_ids":["numbers"],"fields":fields,"options":{"rerank":false}})).await;
        assert_eq!(status, 200, "{answer}");
        assert_eq!(
            answer["outcome"],
            match outcome {
                "missing" => "insufficient_evidence",
                "reject" => "rejected",
                other => other,
            }
        );
        if outcome == "supported" {
            let values: Vec<_> = answer["fields"]
                .as_array()
                .unwrap()
                .iter()
                .map(|f| f["value_text"].as_str().unwrap())
                .collect();
            assert_eq!(values, vec![EXACT, "null", "0"]);
            assert!(answer["raw_report"].as_str().unwrap().contains(EXACT));
            assert!(
                answer["evidence"][0]["record_text"]
                    .as_str()
                    .unwrap()
                    .contains(EXACT)
            );
        } else {
            assert_eq!(answer["fields"], json!([]));
        }
    }
    let (status, answer) = post(
        &router,
        "/v1/ui/ask",
        json!({"question":"amount","document_ids":["numbers"],"options":{"rerank":false}}),
    )
    .await;
    assert_eq!(status, 200, "{answer}");
    assert_eq!(answer["fields"][0]["value_text"], EXACT);
    let (status, rejected) = post(
        &router,
        "/v1/ask",
        json!({"request":{"question":"reject amount","fields":fields},"options":{"rerank":false}}),
    )
    .await;
    assert_eq!(status, 400);
    assert_eq!(rejected["error"]["code"], "answer_rejected");
    assert!(rejected["error"].get("diagnostics").is_some());
}

#[tokio::test]
async fn pdf_and_passage_access_reject_removed_revisions_and_keep_jobs() {
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    let artifact =
        pdf::Artifact::from_slice(&std::fs::read("tests/fixtures/pdf/scanned_note.json").unwrap())
            .unwrap();
    let encoder = TestEncoder::default();
    let config = artifact.config(encoder.space(), false).unwrap();
    db.put_original(&serde_json::to_vec(&artifact).unwrap())
        .unwrap();
    let original = std::fs::read("evals/fixtures/scanned_note.pdf").unwrap();
    db.submit_ingestion(
        IngestRequest {
            job_id: "pdf".into(),
            document_id: "pdf".into(),
            expected_revision: None,
            media_type: MediaType::Pdf,
            config,
        },
        &original,
    )
    .unwrap();
    let processor = pdf::PdfProcessor {
        local: LocalProcessor { encoder },
        artifact,
    };
    while db.advance_ingestion("pdf", &processor).unwrap().stage != Stage::Committed {}
    let revision = db.snapshot().document("pdf").unwrap().revision.clone();
    drop(db);
    let app = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    let router = http::router(app);
    let path = format!("/v1/ui/original?document_id=pdf&revision={revision}");
    let response = router
        .clone()
        .oneshot(
            Request::builder()
                .uri(&path)
                .header("Host", "localhost:8099")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 200);
    assert_eq!(response.headers()["Content-Type"], "application/pdf");
    assert_eq!(
        to_bytes(response.into_body(), 16 * 1024 * 1024)
            .await
            .unwrap()
            .as_ref(),
        original
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/remove",
            json!({"document_id":"pdf","revision":"stale"})
        )
        .await
        .0,
        409
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"pdf","revision":revision})
        )
        .await
        .0,
        200
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/remove",
            json!({"document_id":"pdf","revision":revision})
        )
        .await
        .0,
        200
    );
    assert_eq!(get(&router, &path).await.0, 409);
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"pdf","revision":revision})
        )
        .await
        .0,
        409
    );
    assert_eq!(
        post(&router, "/v1/job", json!({"job_id":"pdf"})).await.0,
        200
    );
}

#[tokio::test]
async fn documentation_routes_and_explicit_method_rejections() {
    let tmp = TempDir::new().unwrap();
    let app = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    let router = http::router(app);
    let (status, raw) = get(&router, "/openapi.json").await;
    assert_eq!(status, 200);
    let spec: Value = serde_json::from_str(&raw).unwrap();
    assert_eq!(spec["paths"].as_object().unwrap().len(), 22);
    assert_eq!(
        spec["components"]["schemas"]["AnswerOptions"]["properties"]["primary_limit"]["default"],
        5
    );
    for (path, methods) in spec["paths"].as_object().unwrap() {
        for (_, operation) in methods.as_object().unwrap() {
            assert!(operation["operationId"].is_string(), "{path}");
            assert!(operation["responses"]["503"].is_object(), "{path}");
        }
    }
    for path in [
        "/docs",
        "/docs/",
        "/docs/init.js",
        "/docs/swagger-ui-bundle.js",
        "/docs/swagger-ui.css",
    ] {
        assert_eq!(get(&router, path).await.0, 200, "{path}");
    }
    for method in ["HEAD", "OPTIONS", "DELETE"] {
        assert_eq!(
            request(&router, method, "/v1/documents", "application/json", vec![])
                .await
                .0,
            404
        );
    }
    let (_, js) = get(&router, "/docs/init.js").await;
    assert!(js.contains("validatorUrl: null"));
    assert!(js.contains("textContent = rawResponse"));
    let response = router
        .oneshot(
            Request::builder()
                .uri("/docs")
                .header("Host", "localhost:8099")
                .header("Origin", "http://evil.test")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), 403);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn replacement_guards_old_evidence_until_atomic_publication() {
    let tmp = TempDir::new().unwrap();
    let mut db = Database::open(tmp.path()).unwrap();
    seed(&mut db, "replace", b"Previous source text.", MediaType::Txt);
    let old = db.snapshot().document("replace").unwrap().revision.clone();
    drop(db);
    let processor = Processor::new(false);
    let app = Application::open(tmp.path(), Client::new(processor.url.clone())).unwrap();
    let router = http::router(app.clone());
    let replacement = |id: &str| {
        let metadata = json!({"upload_id":id,"filename":"replacement.txt","document_id":"replace","expected_revision":old});
        format!("--x\r\nContent-Disposition: form-data; name=\"metadata\"\r\n\r\n{metadata}\r\n--x\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\nReplacement source text.\r\n--x--\r\n").into_bytes()
    };
    let id = "t19-replacement-identity";
    let first = request(
        &router,
        "POST",
        "/v1/ui/upload",
        "multipart/form-data; boundary=x",
        replacement(id),
    )
    .await;
    assert_eq!(first.0, 202, "{}", first.1);
    assert_eq!(
        post(
            &router,
            "/v1/ui/remove",
            json!({"document_id":"replace","revision":old})
        )
        .await
        .0,
        409
    );
    assert_eq!(
        request(
            &router,
            "POST",
            "/v1/ui/upload",
            "multipart/form-data; boundary=x",
            replacement("t19-another-replacement")
        )
        .await
        .0,
        409
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"replace","revision":old})
        )
        .await
        .0,
        200
    );
    let worker = app.start();
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        let (_, job) = post(&router, "/v1/job", json!({"job_id":format!("ui-{id}")})).await;
        if job["stage"] == "Committed" {
            break;
        }
        assert!(Instant::now() < deadline, "{job}");
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
    app.stop();
    worker.join().unwrap();
    let current = app
        .snapshot()
        .unwrap()
        .document("replace")
        .unwrap()
        .revision
        .clone();
    assert_ne!(current, old);
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"replace","revision":old})
        )
        .await
        .0,
        409
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"replace","revision":current})
        )
        .await
        .0,
        200
    );
    drop(router);
    drop(app);
    let reopened = Application::open(tmp.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
    let router = http::router(reopened);
    assert_eq!(
        request(
            &router,
            "POST",
            "/v1/ui/upload",
            "multipart/form-data; boundary=x",
            replacement(id)
        )
        .await
        .0,
        202
    );
    assert_eq!(
        post(
            &router,
            "/v1/ui/source",
            json!({"document_id":"replace","revision":current})
        )
        .await
        .0,
        200
    );
}
