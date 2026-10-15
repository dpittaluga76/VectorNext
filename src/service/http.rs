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
    require(
        !request.headers().iter().any(|h| h.field.equiv("Origin")),
        "browser origins are unsupported; use the local client",
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
    let result = (|| {
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
            let (status, value) = error_response(&error);
            respond(request, status, value);
        }
    }
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
