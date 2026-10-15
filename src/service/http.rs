use super::*;
use std::{io::Read, sync::atomic::AtomicUsize};
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};
const MAX_BODY: usize = 23 * 1024 * 1024;

fn respond(request: Request, status: u16, value: Value) {
    let bytes = serde_json::to_vec(&value)
        .unwrap_or_else(|_| b"{\"error\":\"serialization failure\"}".to_vec());
    let response = Response::from_data(bytes)
        .with_status_code(StatusCode(status))
        .with_header(Header::from_bytes("Content-Type", "application/json").unwrap())
        .with_header(Header::from_bytes("Cache-Control", "no-store").unwrap());
    let _ = request.respond(response);
}
fn body(request: &mut Request) -> Result<Value> {
    let content_type = request
        .headers()
        .iter()
        .find(|h| h.field.equiv("Content-Type"))
        .map(|h| h.value.as_str());
    require(
        content_type == Some("application/json"),
        "application/json content type required",
    )?;
    require(
        request
            .headers()
            .iter()
            .any(|h| h.field.equiv("X-VectorNext-Client") && h.value.as_str() == "1"),
        "X-VectorNext-Client: 1 is required",
    )?;
    let limit = if request.url() == "/v1/ingest" {
        MAX_BODY
    } else {
        64 * 1024
    };
    require(
        request.body_length().is_some_and(|n| n > 0 && n <= limit),
        "invalid/missing content length",
    )?;
    let mut bytes = vec![];
    request
        .as_reader()
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)?;
    require(bytes.len() <= limit, "request too large")?;
    Ok(serde_json::from_slice(&bytes)?)
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
fn handle(app: &Application, mut request: Request) {
    if let Err(error) = check_origin(&request) {
        respond(
            request,
            403,
            json!({"error":{"code":"origin_rejected","message":error.to_string()}}),
        );
        return;
    }
    if request.method() == &Method::Get
        && !request.url().starts_with("/v1/")
        && !matches!(request.url(), "/healthz" | "/readyz")
    {
        static_file(request);
        return;
    }
    if request.method() == &Method::Get && request.url().starts_with("/v1/ui/original?") {
        let result = (|| {
            let query = request.url().split_once('?').unwrap().1;
            let parts: BTreeMap<_, _> =
                query.split('&').filter_map(|p| p.split_once('=')).collect();
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
        })();
        match result {
            Ok(bytes) => respond_bytes(request, 200, bytes, "application/pdf"),
            Err(e) => {
                let (s, v) = error_response(&e);
                respond(request, s, v);
            }
        }
        return;
    }
    let ui = request.url().starts_with("/v1/ui/");
    let result = (|| {
        if request.method() == &Method::Post && request.url() == "/v1/ui/upload" {
            let (metadata, bytes) = multipart_body(&mut request)?;
            return Ok((202, app.ui_upload(metadata, bytes)?));
        }
        let input = if request.method() == &Method::Post {
            body(&mut request)?
        } else {
            Value::Null
        };
        dispatch(app, request.method().as_str(), request.url(), input)
    })();
    match result {
        Ok((status, value)) => respond(request, status, value),
        Err(error) => {
            let (status, mut value) = error_response(&error);
            if ui {
                if let Some(diagnostic) = value["error"]
                    .as_object_mut()
                    .and_then(|v| v.remove("diagnostics"))
                {
                    value["error"]["raw_report"] = json!(diagnostic.to_string());
                }
            }
            respond(request, status, value);
        }
    }
}
pub fn origin_allowed(host: &str, origin: &str) -> bool {
    let authority = host.split(':').next().unwrap_or("");
    matches!(authority, "localhost" | "127.0.0.1") && origin == format!("http://{host}")
}
fn check_origin(request: &Request) -> Result<()> {
    let origins: Vec<_> = request
        .headers()
        .iter()
        .filter(|h| h.field.equiv("Origin"))
        .collect();
    let hosts: Vec<_> = request
        .headers()
        .iter()
        .filter(|h| h.field.equiv("Host"))
        .collect();
    require(
        origins.len() <= 1 && hosts.len() == 1,
        "ambiguous browser origin",
    )?;
    if request
        .headers()
        .iter()
        .any(|h| h.field.equiv("Sec-Fetch-Site"))
    {
        require(
            matches!(
                hosts[0].value.as_str().split(':').next(),
                Some("localhost" | "127.0.0.1")
            ),
            "browser access requires a loopback host",
        )?;
    }
    require(
        !request
            .headers()
            .iter()
            .any(|h| h.field.equiv("Sec-Fetch-Site") && h.value.as_str() == "cross-site"),
        "unrelated browser origin rejected",
    )?;
    require(
        origins
            .first()
            .is_none_or(|h| origin_allowed(hosts[0].value.as_str(), h.value.as_str())),
        "unrelated browser origin rejected",
    )
}
fn multipart_body(request: &mut Request) -> Result<(ui::UploadMetadata, Vec<u8>)> {
    require(
        request
            .headers()
            .iter()
            .any(|h| h.field.equiv("X-VectorNext-Client") && h.value.as_str() == "1"),
        "X-VectorNext-Client: 1 is required",
    )?;
    let kind = request
        .headers()
        .iter()
        .find(|h| h.field.equiv("Content-Type"))
        .map(|h| h.value.as_str())
        .unwrap_or("");
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
    let limit = 16 * 1024 * 1024 + 16384;
    require(
        request.body_length().is_some_and(|n| n > 0 && n <= limit),
        "upload exceeds 16 MiB plus metadata",
    )?;
    parse_multipart(request.as_reader().take(limit as u64 + 1), boundary)
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
fn respond_bytes(request: Request, status: u16, bytes: Vec<u8>, kind: &str) {
    let response=Response::from_data(bytes).with_status_code(StatusCode(status))
        .with_header(Header::from_bytes("Content-Type",kind).unwrap())
        .with_header(Header::from_bytes("X-Content-Type-Options","nosniff").unwrap())
        .with_header(Header::from_bytes("Cache-Control","no-store").unwrap())
        .with_header(Header::from_bytes("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'").unwrap());
    let _ = request.respond(response);
}
fn static_file(request: Request) {
    let path = request.url().split('?').next().unwrap_or("");
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
            respond_bytes(request, 200, bytes, kind);
            return;
        }
    }
    respond(
        request,
        404,
        json!({"error":{"message":"file not found; build the browser assets"}}),
    );
}
struct Permit(Arc<AtomicUsize>);
impl Drop for Permit {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::Relaxed);
    }
}
pub fn serve(app: Arc<Application>, address: &str) -> Result<()> {
    let server = Server::http(address).map_err(|e| Error::Unavailable(e.to_string()))?;
    let active = Arc::new(AtomicUsize::new(0));
    for request in server.incoming_requests() {
        if active
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |n| {
                (n < 16).then_some(n + 1)
            })
            .is_err()
        {
            respond(
                request,
                503,
                json!({"error":{"code":"busy","message":"HTTP capacity reached; retry later"}}),
            );
            continue;
        }
        let permit = Permit(active.clone());
        let app = app.clone();
        std::thread::spawn(move || {
            let _permit = permit;
            handle(&app, request);
        });
    }
    Ok(())
}
