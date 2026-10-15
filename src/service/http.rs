//! HTTP compatibility adapter. Application work stays synchronous and bounded.
use super::*;
use axum::{
    Router,
    body::{Body, to_bytes},
    extract::{Request, State},
    http::HeaderMap,
    middleware::{self, Next},
    response::Response,
};
use std::io::Read;
use tokio::sync::{OwnedSemaphorePermit, Semaphore};

mod openapi;
const MAX_BODY: usize = 23 * 1024 * 1024;
const UPLOAD_BODY: usize = 16 * 1024 * 1024 + 16384;
const CSP: &str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'";

pub(super) struct HttpState {
    app: Arc<Application>,
    permits: Arc<Semaphore>,
    specification: Value,
}

fn respond(status: u16, value: Value) -> Response {
    let bytes = serde_json::to_vec(&value)
        .unwrap_or_else(|_| b"{\"error\":\"serialization failure\"}".to_vec());
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .header("Cache-Control", "no-store")
        .body(Body::from(bytes))
        .unwrap()
}
fn respond_bytes(status: u16, bytes: Vec<u8>, kind: &str) -> Response {
    Response::builder()
        .status(status)
        .header("Content-Type", kind)
        .header("X-Content-Type-Options", "nosniff")
        .header("Cache-Control", "no-store")
        .header("Content-Security-Policy", CSP)
        .body(Body::from(bytes))
        .unwrap()
}
fn failure(error: &Error, ui: bool) -> Response {
    let (status, mut value) = error_response(error);
    if ui {
        if let Some(diagnostic) = value["error"]
            .as_object_mut()
            .and_then(|v| v.remove("diagnostics"))
        {
            value["error"]["raw_report"] = json!(diagnostic.to_string());
        }
    }
    respond(status, value)
}

fn field<'a>(body: &'a Value, name: &str) -> Result<&'a str> {
    body.get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| Error::Invalid(format!("missing {name}")))
}
pub fn dispatch(app: &Application, method: &str, path: &str, input: Value) -> Result<(u16, Value)> {
    match (method, path) {
        ("GET", "/v1/ui/library") => Ok((200, app.ui_library()?)),
        ("POST", "/v1/ui/upload-status") => {
            Ok((200, app.ui_upload_status(field(&input, "upload_id")?)?))
        }
        ("POST", "/v1/ui/remove") => Ok((
            200,
            app.ui_remove(field(&input, "document_id")?, field(&input, "revision")?)?,
        )),
        ("POST", "/v1/ui/source") => Ok((
            200,
            app.ui_source(field(&input, "document_id")?, field(&input, "revision")?)?,
        )),
        ("POST", "/v1/ui/ask") => Ok((200, app.ui_ask(serde_json::from_value(input)?)?)),
        ("GET", "/healthz") => Ok((200, app.storage_status()?)),
        ("GET", "/readyz") => {
            let value = app.ready()?;
            Ok((if value["ready"] == true { 200 } else { 503 }, value))
        }
        ("GET", "/v1/documents") => Ok((200, app.documents()?)),
        ("GET", "/v1/jobs") => Ok((200, app.jobs()?)),
        ("GET", "/v1/metrics") => Ok((200, app.metrics()?)),
        ("POST", "/v1/ingest") => Ok((202, app.upload(serde_json::from_value(input)?)?)),
        ("POST", "/v1/document") => Ok((200, app.document(field(&input, "document_id")?)?)),
        ("POST", "/v1/job") => Ok((200, app.job(field(&input, "job_id")?)?)),
        ("POST", "/v1/retry") => Ok((202, app.retry(field(&input, "job_id")?)?)),
        ("POST", "/v1/search") => Ok((200, app.search(serde_json::from_value(input)?)?)),
        ("POST", "/v1/ask") => Ok((200, app.ask(serde_json::from_value(input)?)?)),
        _ => Ok((
            404,
            json!({"error":{"code":"not_found","message":"unknown endpoint"}}),
        )),
    }
}
pub fn error_response(error: &Error) -> (u16, Value) {
    let (status, code) = match error {
        Error::Busy(_) => (503, "busy"),
        Error::AnswerRejected { .. } => (400, "answer_rejected"),
        Error::Unavailable(_) | Error::Poisoned => (503, "capability_unavailable"),
        Error::Conflict(_) | Error::RetryConflict | Error::Locked => (409, "conflict"),
        Error::Invalid(_) | Error::Json(_) => (400, "invalid_request"),
        _ => (500, "storage_or_internal_error"),
    };
    let mut value = json!({"error":{"code":code,"message":error.to_string()}});
    if let Error::AnswerRejected { diagnostics, .. } = error {
        value["error"]["diagnostics"] = diagnostics.as_ref().clone();
    }
    (status, value)
}
pub fn origin_allowed(host: &str, origin: &str) -> bool {
    let authority = host.split(':').next().unwrap_or("");
    matches!(authority, "localhost" | "127.0.0.1") && origin == format!("http://{host}")
}

fn header<'a>(headers: &'a HeaderMap, name: &str) -> Option<&'a str> {
    headers.get(name).and_then(|v| v.to_str().ok())
}
fn check_origin(headers: &HeaderMap) -> Result<()> {
    let origins: Vec<_> = headers.get_all("origin").iter().collect();
    let hosts: Vec<_> = headers.get_all("host").iter().collect();
    require(
        origins.len() <= 1 && hosts.len() == 1,
        "ambiguous browser origin",
    )?;
    let host = hosts[0].to_str().unwrap_or("");
    if headers.contains_key("sec-fetch-site") {
        require(
            matches!(host.split(':').next(), Some("localhost" | "127.0.0.1")),
            "browser access requires a loopback host",
        )?;
    }
    require(
        !headers
            .get_all("sec-fetch-site")
            .iter()
            .any(|h| h == "cross-site"),
        "unrelated browser origin rejected",
    )?;
    require(
        origins
            .first()
            .is_none_or(|h| origin_allowed(host, h.to_str().unwrap_or(""))),
        "unrelated browser origin rejected",
    )
}
fn has_client_header(headers: &HeaderMap) -> bool {
    headers
        .get_all("x-vectornext-client")
        .iter()
        .any(|v| v == "1")
}
/// Validate headers before reading the body, including the legacy validation order.
fn body_limit(method: &str, url: &str, headers: &HeaderMap) -> Result<usize> {
    if method != "POST" {
        return Ok(0);
    }
    let length = header(headers, "content-length").and_then(|n| n.parse::<usize>().ok());
    if url == "/v1/ui/upload" {
        require(
            has_client_header(headers),
            "X-VectorNext-Client: 1 is required",
        )?;
        multipart_boundary(headers)?;
        require(
            length.is_some_and(|n| n > 0 && n <= UPLOAD_BODY),
            "upload exceeds 16 MiB plus metadata",
        )?;
        return Ok(UPLOAD_BODY);
    }
    require(
        header(headers, "content-type") == Some("application/json"),
        "application/json content type required",
    )?;
    require(
        has_client_header(headers),
        "X-VectorNext-Client: 1 is required",
    )?;
    let limit = if url == "/v1/ingest" {
        MAX_BODY
    } else {
        64 * 1024
    };
    require(
        length.is_some_and(|n| n > 0 && n <= limit),
        "invalid/missing content length",
    )?;
    Ok(limit)
}
fn multipart_boundary(headers: &HeaderMap) -> Result<String> {
    let kind = header(headers, "content-type").unwrap_or("");
    require(
        kind.starts_with("multipart/form-data;"),
        "multipart/form-data required",
    )?;
    let boundary = kind
        .split(';')
        .map(str::trim)
        .find_map(|s| s.strip_prefix("boundary="))
        .unwrap_or("")
        .trim_matches('"')
        .to_owned();
    require(
        !boundary.is_empty() && boundary.len() <= 70,
        "invalid multipart boundary",
    )?;
    Ok(boundary)
}

pub fn parse_multipart(
    reader: impl Read,
    boundary: String,
) -> Result<(ui::UploadMetadata, Vec<u8>)> {
    let mut multipart = multipart::server::Multipart::with_body(reader, boundary);
    let mut metadata = None;
    let mut file = None;
    while let Some(mut entry) = multipart.read_entry()? {
        let name = entry.headers.name.to_string();
        let limit = if name == "metadata" {
            8192
        } else {
            16 * 1024 * 1024
        };
        let mut bytes = vec![];
        entry
            .data
            .by_ref()
            .take(limit + 1)
            .read_to_end(&mut bytes)?;
        require(bytes.len() as u64 <= limit, "multipart field exceeds limit")?;
        match name.as_str() {
            "metadata" if metadata.is_none() => metadata = Some(serde_json::from_slice(&bytes)?),
            "file" if file.is_none() => file = Some(bytes),
            _ => {
                return Err(Error::Invalid(
                    "expected exactly one metadata field and one file".into(),
                ));
            }
        }
    }
    Ok((
        metadata.ok_or_else(|| Error::Invalid("missing upload metadata".into()))?,
        file.filter(|b| !b.is_empty())
            .ok_or_else(|| Error::Invalid("empty or missing file".into()))?,
    ))
}

fn static_file(url: &str) -> Response {
    let path = url.split('?').next().unwrap_or("");
    let relative = if path == "/" {
        "index.html"
    } else {
        path.trim_start_matches('/')
    };
    let safe = relative.split('/').all(|p| {
        !p.is_empty()
            && p != "."
            && p != ".."
            && p.bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"-_.".contains(&b))
    });
    let root = std::env::var("VECTORNEXT_UI_DIR").unwrap_or_else(|_| "/app/ui".into());
    if safe {
        if let Ok(bytes) = std::fs::read(Path::new(&root).join(relative)) {
            let kind = match relative.rsplit('.').next().unwrap_or("") {
                "html" => "text/html; charset=utf-8",
                "js" => "text/javascript",
                "css" => "text/css",
                "svg" => "image/svg+xml",
                _ => "application/octet-stream",
            };
            return respond_bytes(200, bytes, kind);
        }
    }
    respond(
        404,
        json!({"error":{"message":"file not found; build the browser assets"}}),
    )
}
fn original(app: &Application, url: &str) -> Result<Vec<u8>> {
    let query = url.split_once('?').unwrap().1;
    let parts: BTreeMap<_, _> = query.split('&').filter_map(|p| p.split_once('=')).collect();
    let id = parts
        .get("document_id")
        .ok_or_else(|| Error::Invalid("missing document_id".into()))?;
    let revision = parts
        .get("revision")
        .ok_or_else(|| Error::Invalid("missing revision".into()))?;
    let id = percent_encoding::percent_decode_str(id)
        .decode_utf8()
        .map_err(|_| Error::Invalid("invalid document ID encoding".into()))?;
    app.ui_original(&id, revision)
}
fn execute(
    state: &HttpState,
    method: &str,
    url: &str,
    headers: &HeaderMap,
    bytes: &[u8],
) -> Response {
    if method == "GET" {
        if url == "/openapi.json" {
            return respond(200, state.specification.clone());
        }
        if url == "/docs" || url.starts_with("/docs/") {
            return openapi::documentation(url);
        }
        if !url.starts_with("/v1/") && !matches!(url, "/healthz" | "/readyz") {
            return static_file(url);
        }
        if url.starts_with("/v1/ui/original?") {
            return match original(&state.app, url) {
                Ok(bytes) => respond_bytes(200, bytes, "application/pdf"),
                Err(e) => failure(&e, false),
            };
        }
    }
    let result = (|| {
        if method == "POST" && url == "/v1/ui/upload" {
            let (metadata, bytes) = parse_multipart(bytes, multipart_boundary(headers)?)?;
            return Ok((202, state.app.ui_upload(metadata, bytes)?));
        }
        let input = if method == "POST" {
            serde_json::from_slice(bytes)?
        } else {
            Value::Null
        };
        dispatch(&state.app, method, url, input)
    })();
    match result {
        Ok((status, value)) => respond(status, value),
        Err(e) => failure(&e, url.starts_with("/v1/ui/")),
    }
}
async fn admit(State(state): State<Arc<HttpState>>, mut request: Request, next: Next) -> Response {
    let permit = match state.permits.clone().try_acquire_owned() {
        Ok(permit) => Arc::new(permit),
        Err(_) => {
            return respond(
                503,
                json!({"error":{"code":"busy","message":"HTTP capacity reached; retry later"}}),
            );
        }
    };
    request.extensions_mut().insert(permit);
    next.run(request).await
}
pub(super) async fn handle(State(state): State<Arc<HttpState>>, request: Request) -> Response {
    let (mut parts, body) = request.into_parts();
    let permit = parts
        .extensions
        .remove::<Arc<OwnedSemaphorePermit>>()
        .expect("HTTP admission middleware");
    if let Err(error) = check_origin(&parts.headers) {
        return respond(
            403,
            json!({"error":{"code":"origin_rejected","message":error.to_string()}}),
        );
    }
    let method = parts.method.as_str().to_owned();
    let url = parts
        .uri
        .path_and_query()
        .map(|v| v.as_str())
        .unwrap_or("/")
        .to_owned();
    let ui = url.starts_with("/v1/ui/");
    let limit = match body_limit(&method, &url, &parts.headers) {
        Ok(limit) => limit,
        Err(e) => return failure(&e, ui),
    };
    let bytes = if limit == 0 {
        Vec::new()
    } else {
        match to_bytes(body, limit).await {
            Ok(bytes) => bytes.to_vec(),
            Err(_) => {
                return failure(
                    &Error::Invalid("request too large or incomplete".into()),
                    ui,
                );
            }
        }
    };
    // The closure, not the HTTP future, owns admission during synchronous work.
    // Dropping a response future must never free capacity for a duplicate operation.
    match tokio::task::spawn_blocking(move || {
        let _permit = permit;
        execute(&state, &method, &url, &parts.headers, &bytes)
    })
    .await
    {
        Ok(response) => response,
        Err(_) => failure(
            &Error::Unavailable("HTTP worker failed; inspect readiness".into()),
            ui,
        ),
    }
}

pub fn router(app: Arc<Application>) -> Router {
    let (routes, api) = openapi::routes();
    let state = Arc::new(HttpState {
        app,
        permits: Arc::new(Semaphore::new(16)),
        specification: serde_json::to_value(api).expect("OpenAPI serialization"),
    });
    routes
        .fallback(handle)
        .layer(middleware::from_fn_with_state(state.clone(), admit))
        .with_state(state)
}
pub fn serve(app: Arc<Application>, address: &str) -> Result<()> {
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()?;
    runtime.block_on(async {
        let listener = tokio::net::TcpListener::bind(address).await?;
        axum::serve(listener, router(app))
            .await
            .map_err(Error::from)
    })
}
