//! OpenAPI route registration and local documentation. Schema-only definitions
//! describe existing wire shapes without changing application serialization.
use super::*;
use utoipa_axum::{router::OpenApiRouter, routes};

/// Inspect process and storage liveness.
#[utoipa::path(get, path = "/healthz", tag = "Health", responses((status = 200, description = "Inspect process and storage liveness")))]
async fn health(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Inspect individual capability readiness.
#[utoipa::path(get, path = "/readyz", tag = "Health", responses((status = 200, description = "Inspect individual capability readiness")))]
async fn ready(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Read process-lifetime counters.
#[utoipa::path(get, path = "/v1/metrics", tag = "Health", responses((status = 200, description = "Read process-lifetime counters")))]
async fn metrics(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// List committed documents.
#[utoipa::path(get, path = "/v1/documents", tag = "Documents", responses((status = 200, description = "List committed documents")))]
async fn documents(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Inspect a complete document revision.
#[utoipa::path(post, path = "/v1/document", tag = "Documents", responses((status = 200, description = "Inspect a complete document revision")))]
async fn document(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// List durable ingestion jobs.
#[utoipa::path(get, path = "/v1/jobs", tag = "Jobs", responses((status = 200, description = "List durable ingestion jobs")))]
async fn jobs(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Inspect a durable ingestion job.
#[utoipa::path(post, path = "/v1/job", tag = "Jobs", responses((status = 200, description = "Inspect a durable ingestion job")))]
async fn job(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Explicitly retry a saved job failure.
#[utoipa::path(post, path = "/v1/retry", tag = "Jobs", responses((status = 202, description = "Explicitly retry a saved job failure")))]
async fn retry(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Submit a base64 document with durable identity.
#[utoipa::path(post, path = "/v1/ingest", tag = "Documents", responses((status = 202, description = "Submit a base64 document with durable identity")))]
async fn ingest(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Search source passages.
#[utoipa::path(post, path = "/v1/search", tag = "Retrieval", responses((status = 200, description = "Search source passages")))]
async fn search(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Answer with explicit typed fields.
#[utoipa::path(post, path = "/v1/ask", tag = "Retrieval", responses((status = 200, description = "Answer with explicit typed fields")))]
async fn ask(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Browse compact document and unfinished-job metadata.
#[utoipa::path(get, path = "/v1/ui/library", tag = "Browser", responses((status = 200, description = "Browse compact document and unfinished-job metadata")))]
async fn library(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Prepare a file and acknowledge a durable ingestion job.
#[utoipa::path(post, path = "/v1/ui/upload", tag = "Browser", responses((status = 202, description = "Prepare a file and acknowledge a durable ingestion job")))]
async fn upload(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Reconcile a retained upload identity before retrying.
#[utoipa::path(post, path = "/v1/ui/upload-status", tag = "Browser", responses((status = 200, description = "Reconcile a retained upload identity before retrying")))]
async fn upload_status(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Remove a current document revision.
#[utoipa::path(post, path = "/v1/ui/remove", tag = "Browser", responses((status = 200, description = "Remove a current document revision")))]
async fn remove(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Inspect revision-bound source passages.
#[utoipa::path(post, path = "/v1/ui/source", tag = "Browser", responses((status = 200, description = "Inspect revision-bound source passages")))]
async fn source(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Open a current original PDF.
#[utoipa::path(get, path = "/v1/ui/original", tag = "Browser", responses((status = 200, description = "Open a current original PDF")))]
async fn original_pdf(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

/// Ask an ordinary question with selected documents.
#[utoipa::path(post, path = "/v1/ui/ask", tag = "Browser", responses((status = 200, description = "Ask an ordinary question with selected documents")))]
async fn ui_ask(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

fn compatible(
    mut route: utoipa_axum::router::UtoipaMethodRouter<Arc<HttpState>>,
) -> utoipa_axum::router::UtoipaMethodRouter<Arc<HttpState>> {
    route.2 = route.2.head(handle).fallback(handle);
    route
}

#[utoipa::path(post, path = "/v1/answer-jobs", tag = "Answer jobs", responses((status = 202, description = "Admit or reconcile a durable answer job")))]
async fn answer_submit(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}
#[utoipa::path(get, path = "/v1/answer-jobs", tag = "Answer jobs", responses((status = 200, description = "List retained jobs and queue capacity")))]
async fn answer_list(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}
#[utoipa::path(get, path = "/v1/answer-jobs/{request_id}", tag = "Answer jobs", responses((status = 200, description = "Inspect state, exact attempts and final result")))]
async fn answer_status(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}
#[utoipa::path(post, path = "/v1/answer-jobs/{request_id}/cancel", tag = "Answer jobs", responses((status = 200, description = "Cancel queued work or stop after the active call")))]
async fn answer_cancel(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}
#[utoipa::path(post, path = "/v1/answer-jobs/{request_id}/clear", tag = "Answer jobs", responses((status = 200, description = "Explicitly clear a terminal record")))]
async fn answer_clear(state: State<Arc<HttpState>>, request: Request) -> Response {
    handle(state, request).await
}

pub(super) fn routes() -> (Router<Arc<HttpState>>, Value) {
    let routes = OpenApiRouter::<Arc<HttpState>>::new()
        .routes(compatible(routes!(answer_submit, answer_list)))
        .routes(compatible(routes!(answer_status)))
        .routes(compatible(routes!(answer_cancel)))
        .routes(compatible(routes!(answer_clear)))
        .routes(compatible(routes!(health)))
        .routes(compatible(routes!(ready)))
        .routes(compatible(routes!(metrics)))
        .routes(compatible(routes!(documents)))
        .routes(compatible(routes!(document)))
        .routes(compatible(routes!(jobs)))
        .routes(compatible(routes!(job)))
        .routes(compatible(routes!(retry)))
        .routes(compatible(routes!(ingest)))
        .routes(compatible(routes!(search)))
        .routes(compatible(routes!(ask)))
        .routes(compatible(routes!(library)))
        .routes(compatible(routes!(upload)))
        .routes(compatible(routes!(upload_status)))
        .routes(compatible(routes!(remove)))
        .routes(compatible(routes!(source)))
        .routes(compatible(routes!(original_pdf)))
        .routes(compatible(routes!(ui_ask)));
    let (router, api) = routes.split_for_parts();
    let mut spec = serde_json::to_value(api).unwrap();
    spec["info"] = json!({"title":"VectorNext local API", "version":env!("CARGO_PKG_VERSION"),
        "description":"Local single-user document retrieval. Existing endpoints retain their original contracts. All POST requests require X-VectorNext-Client: 1, a positive Content-Length and the documented content type. Origin must match the loopback Host; CLI requests can omit Origin. JSON is limited to 64 KiB except /v1/ingest (23 MiB). Multipart allows 16 MiB + 16 KiB, with one file <=16 MiB and metadata <=8 KiB. Busy/unavailable operations return 503; do not blindly retry unknown outcomes. Preserve arbitrary-precision numbers as raw JSON text. Browser /v1/ui responses expose exact factual values as text. Retrieval defaults remain ranked 30/20/5."});
    spec["servers"] = json!([{"url":"/", "description":"This local VectorNext instance"}]);
    spec["components"]["schemas"] = serde_json::from_str(include_str!("schemas.json")).unwrap();
    for (path, method, request, response, status) in [
        (
            "/v1/answer-jobs",
            "post",
            "AnswerSubmission",
            "AnswerJob",
            "202",
        ),
        ("/v1/answer-jobs", "get", "", "AnswerJobs", "200"),
        (
            "/v1/answer-jobs/{request_id}",
            "get",
            "",
            "AnswerJob",
            "200",
        ),
        (
            "/v1/answer-jobs/{request_id}/cancel",
            "post",
            "EmptyObject",
            "AnswerJob",
            "200",
        ),
        (
            "/v1/answer-jobs/{request_id}/clear",
            "post",
            "EmptyObject",
            "AnswerCleared",
            "200",
        ),
        ("/healthz", "get", "", "Health", "200"),
        ("/readyz", "get", "", "Readiness", "200"),
        ("/v1/metrics", "get", "", "Metrics", "200"),
        ("/v1/documents", "get", "", "Documents", "200"),
        ("/v1/document", "post", "DocumentId", "Document", "200"),
        ("/v1/jobs", "get", "", "Jobs", "200"),
        ("/v1/job", "post", "JobId", "Job", "200"),
        ("/v1/retry", "post", "JobId", "Job", "202"),
        ("/v1/ingest", "post", "Upload", "Job", "202"),
        ("/v1/search", "post", "Search", "SearchResult", "200"),
        ("/v1/ask", "post", "Question", "AnswerReport", "200"),
        ("/v1/ui/library", "get", "", "Library", "200"),
        ("/v1/ui/upload", "post", "MultipartUpload", "Job", "202"),
        (
            "/v1/ui/upload-status",
            "post",
            "UploadId",
            "UploadStatus",
            "200",
        ),
        ("/v1/ui/remove", "post", "Revision", "Removal", "200"),
        ("/v1/ui/source", "post", "Revision", "Source", "200"),
        ("/v1/ui/original", "get", "", "", "200"),
        ("/v1/ui/ask", "post", "UiQuestion", "UiAnswer", "200"),
    ] {
        let operation = &mut spec["paths"][path][method];
        for (status, description) in [
            ("400", "Invalid request or rejected answer"),
            ("403", "Unrelated browser origin"),
            ("409", "Revision or processing conflict"),
            ("503", "Busy or unavailable capability"),
            ("500", "Storage or internal failure"),
        ] {
            operation["responses"][status] = json!({"description":description,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/Error"}}}});
        }
        if !response.is_empty() {
            operation["responses"][status]["content"] = json!({"application/json":{"schema":{"$ref":format!("#/components/schemas/{response}")}}});
        } else {
            operation["responses"][status]["content"] =
                json!({"application/pdf":{"schema":{"type":"string","format":"binary"}}});
            operation["parameters"] = json!([{"name":"document_id","in":"query","required":true,"schema":{"type":"string"}}, {"name":"revision","in":"query","required":true,"schema":{"type":"string"}}]);
        }
        if !request.is_empty() {
            let content_type = if path == "/v1/ui/upload" {
                "multipart/form-data"
            } else {
                "application/json"
            };
            operation["requestBody"] = json!({"required":true,"content":{content_type:{"schema":{"$ref":format!("#/components/schemas/{request}")}}}});
            operation["parameters"] = json!([{"name":"X-VectorNext-Client","in":"header","required":true,"schema":{"type":"string","enum":["1"],"default":"1"}}]);
        }
        if path.contains("{request_id}") {
            if !operation["parameters"].is_array() {
                operation["parameters"] = json!([]);
            }
            operation["parameters"].as_array_mut().unwrap().push(json!({"name":"request_id","in":"path","required":true,"schema":{"type":"string","minLength":16,"maxLength":128}}));
            operation["responses"]["404"] = json!({"description":"Unknown answer request ID","content":{"application/json":{"schema":{"$ref":"#/components/schemas/Error"}}}});
        }
    }
    // Readiness 503 is a capability report, while admission can still return Error.
    spec["paths"]["/readyz"]["get"]["responses"]["503"]["content"]["application/json"]["schema"] = json!({"oneOf":[{"$ref":"#/components/schemas/Readiness"},{"$ref":"#/components/schemas/Error"}]});
    (router, spec)
}

pub(super) fn documentation(url: &str) -> Response {
    let path = url.split('?').next().unwrap_or(url);
    let (bytes, kind) = match path {
        "/docs" | "/docs/" => (
            include_bytes!("docs.html").to_vec(),
            "text/html; charset=utf-8".to_owned(),
        ),
        "/docs/init.js" => (
            include_bytes!("docs.js").to_vec(),
            "text/javascript".to_owned(),
        ),
        "/docs/swagger-ui-bundle.js" | "/docs/swagger-ui.css" => {
            let asset = path.strip_prefix("/docs/").unwrap();
            match utoipa_swagger_ui::serve(asset, Arc::new(utoipa_swagger_ui::Config::default())) {
                Ok(Some(file)) => (file.bytes.into_owned(), file.content_type),
                _ => {
                    return respond(
                        500,
                        json!({"error":{"code":"documentation_unavailable","message":"bundled documentation asset missing"}}),
                    );
                }
            }
        }
        _ => {
            return respond(
                404,
                json!({"error":{"code":"not_found","message":"unknown endpoint"}}),
            );
        }
    };
    respond_bytes(200, bytes, &kind)
}
