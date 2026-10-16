//! Durable operational answer queue, deliberately outside the database backup format.
use super::*;
use std::{
    fs::{self, File},
    io::Write,
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};

const RESERVATION: usize = 16 * 1024 * 1024;
const QUOTA: usize = 256 * 1024 * 1024;
const MAX_UNFINISHED: usize = 16;
const WAIT_MS: u64 = 15 * 60 * 1000;

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Mode {
    #[default]
    Hybrid,
    Gemma,
    Nuextract,
}
impl Mode {
    fn first(self) -> Model {
        if self == Self::Gemma {
            Model::Gemma
        } else {
            Model::Nuextract
        }
    }
}
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Model {
    Gemma,
    Nuextract,
}
impl Model {
    fn other(self) -> Self {
        if self == Self::Gemma {
            Self::Nuextract
        } else {
            Self::Gemma
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Submission {
    pub request_id: String,
    #[serde(default)]
    pub mode: Mode,
    pub kind: Kind,
    pub payload: Value,
}
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Ui,
    Structured,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Attempt {
    pub model: Model,
    pub state: String,
    pub started_ms: u64,
    pub finished_ms: Option<u64>,
    pub queue_ms: u64,
    pub activation_ms: f64,
    pub work_ms: f64,
    pub identity: Value,
    pub status_code: u16,
    /// Opaque exact JSON, never a JavaScript number projection.
    pub response_text: Option<String>,
    pub operations: Value,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Job {
    pub submission: Submission,
    pub fingerprint: String,
    pub bindings: BTreeMap<String, String>,
    pub generation: u64,
    pub created_ms: u64,
    pub waiting_since_ms: u64,
    pub updated_ms: u64,
    pub state: String,
    pub next_model: Model,
    pub cancelled: bool,
    pub fallback_reason: Option<String>,
    pub attempts: Vec<Attempt>,
    pub terminal_error: Option<String>,
}
impl Job {
    pub fn terminal(&self) -> bool {
        matches!(
            self.state.as_str(),
            "completed" | "cancelled" | "stale" | "queue_timeout" | "interrupted" | "failed"
        )
    }
    fn waiting(&self) -> bool {
        matches!(self.state.as_str(), "queued" | "waiting_for_gemma")
    }
    pub fn view(&self, full: bool) -> Result<Value> {
        let mut value = json!({"request_id":self.submission.request_id,"mode":self.submission.mode,
            "kind":self.submission.kind,"state":self.state,"terminal":self.terminal(),"next_model":self.next_model,
            "created_ms":self.created_ms,"updated_ms":self.updated_ms,"waiting_since_ms":self.waiting_since_ms,
            "fallback_reason":self.fallback_reason,"error":self.terminal_error,"cancel_requested":self.cancelled,
            "attempt_count":self.attempts.len(),"total_ms":self.updated_ms.saturating_sub(self.created_ms)});
        if full {
            value["attempts"] = serde_json::to_value(&self.attempts)?;
            value["diagnostics_text"] = json!(serde_json::to_string(self)?);
            if self.state == "completed" {
                if let Some(attempt) = self.attempts.last() {
                    value["status_code"] = json!(attempt.status_code);
                    let mut result: Value =
                        serde_json::from_str(attempt.response_text.as_deref().unwrap_or("null"))?;
                    let diagnostics = json!({"request_id":self.submission.request_id,"mode":self.submission.mode,
                        "fallback_reason":self.fallback_reason,"attempts":self.attempts,
                        "total_ms":self.updated_ms.saturating_sub(self.created_ms)});
                    if self.submission.kind == Kind::Ui && result["raw_report"].is_string() {
                        let mut raw: Value =
                            serde_json::from_str(result["raw_report"].as_str().unwrap())?;
                        raw["answer_job"] = diagnostics;
                        result["raw_report"] = json!(raw.to_string());
                    } else if result.is_object() {
                        result["answer_job"] = diagnostics;
                    }
                    // Structured callers use response_text to retain exact numeric values.
                    value["response_text"] = json!(result.to_string());
                    if self.submission.kind == Kind::Ui {
                        value["result"] = result;
                    }
                }
            }
        }
        Ok(value)
    }
}

pub(super) struct Store {
    root: PathBuf,
    pub jobs: BTreeMap<String, Job>,
    pub failed: Option<String>,
    current: Model,
    batch: usize,
}
pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
pub fn identity() -> String {
    static SERIAL: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    crate::sha256(
        format!(
            "{}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos(),
            SERIAL.fetch_add(1, Ordering::Relaxed)
        )
        .as_bytes(),
    )
}
impl Store {
    pub fn open(db: &Path) -> Result<Self> {
        let name = db
            .file_name()
            .ok_or_else(|| Error::Invalid("database path needs a directory name".into()))?
            .to_string_lossy();
        let root = db.with_file_name(format!("{name}.answer-jobs"));
        fs::create_dir_all(&root)?;
        let mut store = Self {
            root,
            jobs: BTreeMap::new(),
            failed: None,
            current: Model::Nuextract,
            batch: 0,
        };
        for entry in fs::read_dir(&store.root)? {
            let entry = entry?;
            if entry.path().extension().is_some_and(|v| v == "tmp") {
                fs::remove_file(entry.path())?;
                continue;
            }
            require(
                entry.path().extension().is_some_and(|v| v == "json"),
                "unknown answer queue file",
            )?;
            require(
                entry.metadata()?.len() <= RESERVATION as u64,
                "oversized answer queue record",
            )?;
            let raw: Value = serde_json::from_slice(&fs::read(entry.path())?)?;
            let text = raw["record"]
                .as_str()
                .ok_or_else(|| Error::Corrupt("answer record missing".into()))?;
            require(
                raw["version"] == 1 && raw["sha256"] == crate::sha256(text.as_bytes()),
                "answer record integrity failure",
            )?;
            let mut job: Job = serde_json::from_str(text)?;
            require(
                entry.path() == store.path(&job.submission.request_id),
                "answer record identity mismatch",
            )?;
            if matches!(
                job.state.as_str(),
                "running_nuextract" | "running_gemma" | "loading_nuextract" | "loading_gemma"
            ) {
                if let Some(a) = job.attempts.last_mut() {
                    a.state = "interrupted_uncertain".into();
                    a.finished_ms = Some(now());
                }
                if job.cancelled {
                    job.state = "cancelled".into();
                } else if job.submission.mode == Mode::Hybrid
                    && job.attempts.len() == 1
                    && job.next_model == Model::Nuextract
                {
                    job.state = "waiting_for_gemma".into();
                    job.next_model = Model::Gemma;
                    job.fallback_reason = Some(
                        "NuExtract attempt interrupted; no replay; backend reconciliation required"
                            .into(),
                    );
                    job.waiting_since_ms = now();
                } else {
                    job.state = "interrupted".into();
                    job.terminal_error = Some(
                        "attempt outcome uncertain; explicitly submit a new request ID".into(),
                    );
                }
                store.save(job.clone())?;
            }
            store.jobs.insert(job.submission.request_id.clone(), job);
        }
        require(
            store.usage()? <= QUOTA,
            "answer job retention quota exceeded",
        )?;
        Ok(store)
    }
    fn path(&self, id: &str) -> PathBuf {
        self.root
            .join(format!("{}.json", crate::sha256(id.as_bytes())))
    }
    fn encoded(job: &Job) -> Result<Vec<u8>> {
        let text = serde_json::to_string(job)?;
        Ok(serde_json::to_vec(
            &json!({"version":1,"sha256":crate::sha256(text.as_bytes()),"record":text}),
        )?)
    }
    fn usage(&self) -> Result<usize> {
        self.jobs.values().try_fold(0usize, |total, j| {
            Ok(total
                + if j.terminal() {
                    Self::encoded(j)?.len()
                } else {
                    RESERVATION
                })
        })
    }
    fn healthy(&self) -> Result<()> {
        if let Some(reason) = &self.failed {
            return Err(Error::Unavailable(format!(
                "answer queue stopped: {reason}; restart required"
            )));
        }
        Ok(())
    }
    pub fn save(&mut self, job: Job) -> Result<()> {
        self.healthy()?;
        let raw = Self::encoded(&job)?;
        require(
            raw.len() <= RESERVATION,
            "answer diagnostic reservation exceeded",
        )?;
        let path = self.path(&job.submission.request_id);
        let result = (|| -> Result<()> {
            let mut file = File::create(path.with_extension("tmp"))?;
            file.write_all(&raw)?;
            file.sync_all()?;
            fs::rename(path.with_extension("tmp"), &path)?;
            File::open(&self.root)?.sync_all()?;
            Ok(())
        })();
        if let Err(error) = result {
            self.failed = Some(error.to_string());
            return Err(error);
        }
        self.jobs.insert(job.submission.request_id.clone(), job);
        Ok(())
    }
    pub fn get(&self, id: &str) -> Result<&Job> {
        self.jobs
            .get(id)
            .ok_or_else(|| Error::Invalid("answer job not found".into()))
    }
    pub fn existing(&self, input: &Submission) -> Result<Option<Job>> {
        self.healthy()?;
        if let Some(job) = self.jobs.get(&input.request_id) {
            if job.fingerprint != crate::sha256(&serde_json::to_vec(input)?) {
                return Err(Error::RetryConflict);
            }
            return Ok(Some(job.clone()));
        }
        Ok(None)
    }
    pub fn admit(
        &mut self,
        input: Submission,
        bindings: BTreeMap<String, String>,
        generation: u64,
    ) -> Result<Job> {
        if let Some(job) = self.existing(&input)? {
            return Ok(job);
        }
        require(
            (16..=128).contains(&input.request_id.len())
                && input
                    .request_id
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'-'),
            "invalid answer request identity",
        )?;
        if self.jobs.values().filter(|j| !j.terminal()).count() >= MAX_UNFINISHED
            || self.usage()? + RESERVATION > QUOTA
        {
            return Err(Error::Busy(
                "answer queue capacity or retained diagnostic quota reached; clear terminal jobs"
                    .into(),
            ));
        }
        let timestamp = now();
        let job = Job {
            fingerprint: crate::sha256(&serde_json::to_vec(&input)?),
            next_model: input.mode.first(),
            submission: input,
            bindings,
            generation,
            created_ms: timestamp,
            waiting_since_ms: timestamp,
            updated_ms: timestamp,
            state: "queued".into(),
            cancelled: false,
            fallback_reason: None,
            attempts: vec![],
            terminal_error: None,
        };
        self.save(job.clone())?;
        Ok(job)
    }
    pub fn cancel(&mut self, id: &str) -> Result<Job> {
        let mut job = self.get(id)?.clone();
        if !job.terminal() {
            job.cancelled = true;
            if job.waiting() {
                job.state = "cancelled".into();
            }
            job.updated_ms = now();
            self.save(job.clone())?;
        }
        Ok(job)
    }
    pub fn clear(&mut self, id: &str) -> Result<()> {
        self.healthy()?;
        if !self.get(id)?.terminal() {
            return Err(Error::Conflict(
                "cancel and finish the job before clearing".into(),
            ));
        }
        let result =
            fs::remove_file(self.path(id)).and_then(|_| File::open(&self.root)?.sync_all());
        if let Err(error) = result {
            self.failed = Some(error.to_string());
            return Err(error.into());
        }
        self.jobs.remove(id);
        Ok(())
    }
    pub fn next(&mut self, timestamp: u64) -> Result<Option<Job>> {
        self.healthy()?;
        let expired: Vec<_> = self
            .jobs
            .values()
            .filter(|j| j.waiting() && timestamp.saturating_sub(j.waiting_since_ms) >= WAIT_MS)
            .cloned()
            .collect();
        for mut job in expired {
            job.state = "queue_timeout".into();
            job.updated_ms = timestamp;
            job.terminal_error =
                Some("waited 15 minutes without beginning the next attempt".into());
            self.save(job)?;
        }
        let oldest = |model| {
            self.jobs
                .values()
                .filter(|j| j.waiting() && j.next_model == model)
                .min_by_key(|j| (j.waiting_since_ms, j.created_ms, &j.submission.request_id))
                .cloned()
        };
        let same = oldest(self.current);
        let other = oldest(self.current.other());
        if other.as_ref().is_some_and(|j| {
            same.is_none()
                || self.batch >= 4
                || timestamp.saturating_sub(j.waiting_since_ms) >= 30_000
        }) {
            self.current = self.current.other();
            self.batch = 0;
        }
        let selected = if self.current == Model::Gemma {
            self.jobs
                .values()
                .filter(|j| j.waiting() && j.next_model == Model::Gemma)
                .min_by_key(|j| (j.waiting_since_ms, j.created_ms, &j.submission.request_id))
        } else {
            self.jobs
                .values()
                .filter(|j| j.waiting() && j.next_model == Model::Nuextract)
                .min_by_key(|j| (j.waiting_since_ms, j.created_ms, &j.submission.request_id))
        }
        .cloned();
        if selected.is_some() {
            self.batch += 1;
        }
        Ok(selected)
    }
}

impl Application {
    pub fn submit_answer(&self, input: Submission) -> Result<Value> {
        // Reconciliation precedes current-library validation: a completed ID stays stable.
        if let Some(job) = lock(&self.answer_store)?.existing(&input)? {
            return job.view(true);
        }
        require(
            serde_json::to_vec(&input)?.len() <= 65536,
            "answer submission exceeds 64 KiB",
        )?;
        let selected = match input.kind {
            Kind::Ui => {
                let question: ui::UiQuestion = serde_json::from_value(input.payload.clone())?;
                Self::prepare_ui(&question)?;
                Some(question.document_ids)
            }
            Kind::Structured => {
                let question: Question = serde_json::from_value(input.payload.clone())?;
                answers::validate_request_options(&question.request, &question.options)?;
                // Bind all current documents for arbitrary boolean/attribute filters.
                if let Filter::DocumentIds(ids) = question.request.filter {
                    Some(ids)
                } else {
                    None
                }
            }
        };
        let snapshot = self.snapshot()?;
        if let Some(ids) = &selected {
            require(
                ids.iter().all(|id| snapshot.document(id).is_some()),
                "selected document is no longer available; refresh scope",
            )?;
        }
        let bindings = snapshot
            .documents()
            .filter(|d| {
                selected
                    .as_ref()
                    .is_none_or(|ids| ids.contains(&d.document_id))
            })
            .map(|d| (d.document_id.clone(), d.revision.clone()))
            .collect();
        // Validate the embedding-space choice before durable admission, without inference.
        let space_id = if input.kind == Kind::Structured {
            input.payload["space_id"].as_str()
        } else {
            None
        };
        self.index_snapshot(snapshot.clone(), space_id)?;
        let job = lock(&self.answer_store)?.admit(input, bindings, snapshot.generation())?;
        self.start_answers();
        job.view(true)
    }
    pub fn answer_job(&self, id: &str) -> Result<Value> {
        lock(&self.answer_store)?.get(id)?.view(true)
    }
    pub fn answer_jobs(&self) -> Result<Value> {
        let store = lock(&self.answer_store)?;
        let jobs = store
            .jobs
            .values()
            .rev()
            .map(|j| j.view(false))
            .collect::<Result<Vec<_>>>()?;
        Ok(
            json!({"jobs":jobs,"unfinished":store.jobs.values().filter(|j|!j.terminal()).count(),
            "capacity":MAX_UNFINISHED,"retained_and_reserved_bytes":store.usage()?,"quota_bytes":QUOTA,
            "ready":store.failed.is_none(),"error":store.failed}),
        )
    }
    pub fn cancel_answer(&self, id: &str) -> Result<Value> {
        let job = lock(&self.answer_store)?.cancel(id)?;
        if !job.terminal() {
            if let Some(token) = job
                .attempts
                .last()
                .and_then(|a| a.identity["token"].as_str())
            {
                self.processor
                    .generation("cancel", json!({"token":token}))?;
            }
        }
        job.view(true)
    }
    pub fn clear_answer(&self, id: &str) -> Result<Value> {
        lock(&self.answer_store)?.clear(id)?;
        Ok(json!({"cleared":true}))
    }
    pub fn answer_sync(&self, kind: Kind, payload: Value, mode: Mode) -> Result<Value> {
        let (_, value) = self.answer_sync_response(kind, payload, mode)?;
        if let Some(error) = value.get("error") {
            let message = error["message"]
                .as_str()
                .unwrap_or("answer failed")
                .to_owned();
            return Err(match error["code"].as_str() {
                Some("busy") => Error::Busy(message),
                Some("invalid_request") => Error::Invalid(message),
                Some("conflict") => Error::Conflict(message),
                Some("answer_rejected") => Error::AnswerRejected {
                    message,
                    diagnostics: Box::new(error["diagnostics"].clone()),
                },
                _ => Error::Unavailable(message),
            });
        }
        Ok(value)
    }
    pub fn answer_sync_response(
        &self,
        kind: Kind,
        payload: Value,
        mode: Mode,
    ) -> Result<(u16, Value)> {
        let id = identity();
        self.submit_answer(Submission {
            request_id: id.clone(),
            mode,
            kind,
            payload,
        })?;
        loop {
            let view = self.answer_job(&id)?;
            if view["terminal"] == true {
                if let Some(raw) = view["response_text"].as_str() {
                    return Ok((
                        view["status_code"].as_u64().unwrap_or(500) as u16,
                        serde_json::from_str(raw)?,
                    ));
                }
                return Err(Error::Unavailable(format!(
                    "answer job {}: {}",
                    view["state"], view["error"]
                )));
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }
    pub(super) fn start_answers(&self) {
        if self.answer_started.swap(true, Ordering::SeqCst) {
            return;
        }
        let weak = self
            .weak_self
            .get()
            .expect("initialized application")
            .clone();
        std::thread::spawn(move || {
            loop {
                let Some(app) = weak.upgrade() else {
                    return;
                };
                if app.stopping.load(Ordering::Relaxed) {
                    return;
                }
                let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    // Only reconcile when work exists; document browsing stays independent.
                    let pending = lock(&app.answer_store)?.jobs.values().any(|j| j.waiting());
                    if !pending {
                        return Ok(false);
                    }
                    app.answer_step()
                }));
                match outcome {
                    Ok(Ok(true)) => {}
                    Ok(Ok(false)) => {
                        drop(app);
                        std::thread::sleep(Duration::from_millis(200));
                    }
                    other => {
                        let reason = match other {
                            Ok(Err(e)) => e.to_string(),
                            _ => "answer coordinator panicked".into(),
                        };
                        if let Ok(mut store) = app.answer_store.lock() {
                            store.failed = Some(reason);
                        }
                        return;
                    }
                }
            }
        });
    }
    fn answer_step(&self) -> Result<bool> {
        let mut store = lock(&self.answer_store)?;
        let Some(mut job) = store.next(now())? else {
            return Ok(false);
        };
        let snapshot = self.snapshot()?;
        if job
            .bindings
            .iter()
            .any(|(id, rev)| snapshot.document(id).is_none_or(|d| &d.revision != rev))
        {
            job.state = "stale".into();
            job.updated_ms = now();
            job.terminal_error =
                Some("bound document revision changed or cannot be reconstructed".into());
            store.save(job)?;
            return Ok(true);
        }
        let model = job.next_model;
        job.state = if model == Model::Gemma {
            "loading_gemma"
        } else {
            "loading_nuextract"
        }
        .into();
        let timestamp = now();
        job.updated_ms = timestamp;
        job.attempts.push(Attempt {
            model,
            state: "activating".into(),
            started_ms: timestamp,
            finished_ms: None,
            queue_ms: timestamp.saturating_sub(job.waiting_since_ms),
            activation_ms: 0.0,
            work_ms: 0.0,
            identity: Value::Null,
            status_code: 0,
            response_text: None,
            operations: Value::Null,
        });
        store.save(job.clone())?;
        drop(store);
        let token = identity();
        let lease =
            json!({"model":model,"token":token,"owner":self.answer_owner,"priority":"interactive"});
        let mut model_identity = Value::Null;
        let mut operations = Value::Null;
        let mut work_ms = 0.0;
        let mut acquisition_attempted = false;
        let result = (|| -> Result<Value> {
            let _interactive = busy(&self.interactive)?;
            let only_source = job.submission.kind == Kind::Structured
                && job.submission.payload["request"]["scope"] == "structured_lookup"
                && job.submission.payload["request"]["prose"] != true;
            let space_id = if job.submission.kind == Kind::Structured {
                job.submission.payload["space_id"].as_str()
            } else {
                None
            };
            let (index, space) = self.index_snapshot(snapshot, space_id)?;
            if only_source {
                let mut question: Question =
                    serde_json::from_value(job.submission.payload.clone())?;
                question.request.filter = Filter::All(vec![
                    question.request.filter,
                    Filter::DocumentIds(job.bindings.keys().cloned().collect()),
                ]);
                let mut report = answers::ask_with_options(
                    &index,
                    &SourceOnly(space),
                    question.request,
                    question.options,
                )?;
                report.request = serde_json::from_value(job.submission.payload["request"].clone())?;
                return Ok(serde_json::to_value(report)?);
            }
            self.check_answer_cancel(&job.submission.request_id)?;
            self.processor
                .generation("reconcile", json!({"owner":self.answer_owner}))?;
            acquisition_attempted = true;
            model_identity = self.processor.generation("acquire", lease.clone())?;
            require(
                model_identity["model"] == lease["model"] && model_identity["token"] == token,
                "generation lease identity mismatch",
            )?;
            let mut store = lock(&self.answer_store)?;
            let mut current = store.get(&job.submission.request_id)?.clone();
            current.state = if model == Model::Gemma {
                "running_gemma"
            } else {
                "running_nuextract"
            }
            .into();
            current.updated_ms = now();
            let attempt = current.attempts.last_mut().unwrap();
            attempt.state = "running".into();
            attempt.identity = model_identity.clone();
            attempt.activation_ms =
                model_identity["activation_seconds"].as_f64().unwrap_or(0.0) * 1000.0;
            store.save(current)?;
            drop(store);
            self.check_answer_cancel(&job.submission.request_id)?;
            let start = Instant::now();
            let mut models = RemoteModels::connect(self.processor.clone(), "interactive")?;
            models.lease = Some(lease.clone());
            let weak = self.weak_self.get().unwrap().clone();
            let id = job.submission.request_id.clone();
            models.check = Some(Arc::new(move || {
                weak.upgrade()
                    .ok_or_else(|| Error::Unavailable("application stopped".into()))?
                    .check_answer_cancel(&id)
            }));
            let result = match job.submission.kind {
                Kind::Ui => self.ui_ask_attempt(
                    serde_json::from_value(job.submission.payload.clone())?,
                    index,
                    space,
                    &models,
                ),
                Kind::Structured => {
                    let mut question: Question =
                        serde_json::from_value(job.submission.payload.clone())?;
                    let original_filter = serde_json::to_value(&question.request.filter)?;
                    question.request.filter = Filter::All(vec![
                        question.request.filter,
                        Filter::DocumentIds(job.bindings.keys().cloned().collect()),
                    ]);
                    self.ask_attempt(question, index, space, &models)
                        .map(|mut report| {
                            report["request"]["filter"] = original_filter;
                            report
                        })
                }
            };
            work_ms = start.elapsed().as_secs_f64() * 1000.0;
            operations = serde_json::to_value(&*lock(&models.operations)?)?;
            result
        })();
        let admission = matches!(&result, Err(Error::Busy(_)));
        let invalid_request = matches!(
            &result,
            Err(Error::Invalid(_) | Error::Conflict(_) | Error::RetryConflict)
        );
        let (status, response) = match result {
            Ok(value) => (200, value),
            Err(error) => http::error_response(&error),
        };
        let supported = status == 200
            && (response["outcome"] == "supported" || response["answer"]["status"] == "supported");
        let mut store = lock(&self.answer_store)?;
        let mut current = store.get(&job.submission.request_id)?.clone();
        let attempt = current.attempts.last_mut().unwrap();
        attempt.state = "finished".into();
        attempt.finished_ms = Some(now());
        attempt.status_code = status;
        attempt.response_text = Some(response.to_string());
        attempt.identity = model_identity.clone();
        attempt.activation_ms =
            model_identity["activation_seconds"].as_f64().unwrap_or(0.0) * 1000.0;
        attempt.work_ms = work_ms;
        attempt.operations = operations;
        current.updated_ms = now();
        // Persist the exact outcome before releasing GPU ownership. If release is
        // uncertain, restart recovery retains this record and never repeats the model.
        store.save(current.clone())?;
        drop(store);
        if acquisition_attempted && !admission {
            self.processor
                .generation("release", json!({"token":token}))?;
        }
        // A cancellation can arrive during release; never overwrite it with a stale copy.
        let mut store = lock(&self.answer_store)?;
        current = store.get(&job.submission.request_id)?.clone();
        if current.cancelled {
            current.state = "cancelled".into();
        } else if !supported
            && !admission
            && !invalid_request
            && current.submission.mode == Mode::Hybrid
            && model == Model::Nuextract
            && current.attempts.len() == 1
        {
            current.state = "waiting_for_gemma".into();
            current.next_model = Model::Gemma;
            current.waiting_since_ms = now();
            current.fallback_reason = Some(
                response["outcome"]
                    .as_str()
                    .or(response["answer"]["status"].as_str())
                    .or(response["error"]["message"].as_str())
                    .unwrap_or("NuExtract did not produce a validated supported answer")
                    .to_owned(),
            );
        } else {
            current.state = "completed".into();
        }
        store.save(current)?;
        Ok(true)
    }
    fn check_answer_cancel(&self, id: &str) -> Result<()> {
        if lock(&self.answer_store)?.get(id)?.cancelled {
            return Err(Error::Invalid(
                "answer cancelled; no further stages will run".into(),
            ));
        }
        Ok(())
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn submission(id: usize, mode: Mode) -> Submission {
        Submission {
            request_id: format!("synthetic-job-{id:04}"),
            mode,
            kind: Kind::Ui,
            payload: json!({"question":"What is the stored amount?","document_ids":["doc"]}),
        }
    }
    fn store() -> (TempDir, Store) {
        let root = TempDir::new().unwrap();
        let store = Store::open(&root.path().join("db")).unwrap();
        (root, store)
    }
    #[test]
    fn admission_reconciles_identity_and_reserves_quota_before_writes() {
        let (_root, mut store) = store();
        for id in 0..16 {
            store
                .admit(submission(id, Mode::Hybrid), BTreeMap::new(), 0)
                .unwrap();
        }
        let input = submission(0, Mode::Hybrid);
        assert_eq!(
            store
                .admit(input.clone(), BTreeMap::new(), 1)
                .unwrap()
                .generation,
            0
        );
        assert!(matches!(
            store.admit(submission(16, Mode::Hybrid), BTreeMap::new(), 0),
            Err(Error::Busy(_))
        ));
        let mut changed = input;
        changed.mode = Mode::Gemma;
        assert!(matches!(
            store.admit(changed, BTreeMap::new(), 0),
            Err(Error::RetryConflict)
        ));
        store.cancel("synthetic-job-0000").unwrap();
        // A retained record still consumes its actual bytes; no diagnostic eviction.
        assert!(
            store
                .admit(submission(16, Mode::Hybrid), BTreeMap::new(), 0)
                .is_err()
        );
        store.clear("synthetic-job-0000").unwrap();
        store
            .admit(submission(16, Mode::Hybrid), BTreeMap::new(), 0)
            .unwrap();
    }
    #[test]
    fn queue_fairness_hands_off_after_four_and_after_thirty_seconds() {
        let (_root, mut store) = store();
        for id in 0..6 {
            store
                .admit(submission(id, Mode::Nuextract), BTreeMap::new(), 0)
                .unwrap();
        }
        let gemma = store
            .admit(submission(8, Mode::Gemma), BTreeMap::new(), 0)
            .unwrap();
        let time = now();
        for _ in 0..4 {
            let job = store.next(time).unwrap().unwrap();
            assert_eq!(job.next_model, Model::Nuextract);
            store.cancel(&job.submission.request_id).unwrap();
        }
        assert_eq!(store.next(time).unwrap().unwrap().next_model, Model::Gemma);
        store.current = Model::Nuextract;
        store.batch = 0;
        assert_eq!(
            store
                .next(gemma.waiting_since_ms + 30_000)
                .unwrap()
                .unwrap()
                .next_model,
            Model::Gemma
        );
    }
    #[test]
    fn waiting_expiry_and_clearing_are_explicit() {
        let (_root, mut store) = store();
        let job = store
            .admit(submission(0, Mode::Hybrid), BTreeMap::new(), 0)
            .unwrap();
        assert!(store.clear(&job.submission.request_id).is_err());
        assert!(
            store
                .next(job.waiting_since_ms + WAIT_MS)
                .unwrap()
                .is_none()
        );
        assert_eq!(
            store.get(&job.submission.request_id).unwrap().state,
            "queue_timeout"
        );
        store.clear(&job.submission.request_id).unwrap();
        assert!(store.jobs.is_empty());
    }
    #[test]
    fn uncertain_restart_never_replays_an_attempt_and_keeps_exact_diagnostics() {
        for (mode, model, expected) in [
            (Mode::Hybrid, Model::Nuextract, "waiting_for_gemma"),
            (Mode::Hybrid, Model::Gemma, "interrupted"),
            (Mode::Nuextract, Model::Nuextract, "interrupted"),
            (Mode::Gemma, Model::Gemma, "interrupted"),
        ] {
            let (root, mut store) = store();
            let mut job = store
                .admit(submission(0, mode), BTreeMap::new(), 0)
                .unwrap();
            job.next_model = model;
            job.state = "running_nuextract".into();
            job.attempts.push(Attempt {
                model,
                state: "running".into(),
                started_ms: now(),
                finished_ms: None,
                queue_ms: 0,
                activation_ms: 0.,
                work_ms: 0.,
                identity: Value::Null,
                status_code: 0,
                response_text: Some("{\"amount\":9007199254740993.00000000000001}".into()),
                operations: Value::Null,
            });
            store.save(job).unwrap();
            drop(store);
            let reopened = Store::open(&root.path().join("db")).unwrap();
            let job = reopened.get("synthetic-job-0000").unwrap();
            assert_eq!(job.state, expected);
            assert_eq!(job.attempts.len(), 1);
            assert!(
                job.attempts[0]
                    .response_text
                    .as_ref()
                    .unwrap()
                    .contains("9007199254740993.00000000000001")
            );
            assert_eq!(job.attempts[0].state, "interrupted_uncertain");
        }
    }
    #[test]
    fn corrupt_records_fail_closed_and_answer_history_is_outside_database() {
        let (root, mut store) = store();
        let job = store
            .admit(submission(0, Mode::Hybrid), BTreeMap::new(), 0)
            .unwrap();
        assert!(!store.root.starts_with(root.path().join("db")));
        fs::write(store.path(&job.submission.request_id), b"{}").unwrap();
        assert!(Store::open(&root.path().join("db")).is_err());
    }

    struct Fixture {
        root: TempDir,
        app: Arc<Application>,
        calls: Arc<Mutex<Vec<Value>>>,
        server: Arc<tiny_http::Server>,
        thread: Option<std::thread::JoinHandle<()>>,
    }
    impl Fixture {
        fn new(behavior: &str) -> Self {
            use crate::ingestion::context::{ContextConfig, GenerationConfig};
            let root = TempDir::new().unwrap();
            let mut db = Database::open(root.path().join("db")).unwrap();
            let encoder = TestEncoder::default();
            let mut config = IngestConfig::new(encoder.space());
            config.context = Some(ContextConfig::new(Policy::Structural, None));
            db.submit_ingestion(
                IngestRequest {
                    job_id: "seed".into(),
                    document_id: "doc".into(),
                    expected_revision: None,
                    media_type: MediaType::Json,
                    config,
                },
                br#"{"amount":9007199254740993.00000000000001,"zero":0,"unknown":null}"#,
            )
            .unwrap();
            let processor = LocalProcessor {
                encoder: TestEncoder::default(),
            };
            while db.advance_ingestion("seed", &processor).unwrap().stage != Stage::Committed {}
            drop(db);
            let server = Arc::new(tiny_http::Server::http("127.0.0.1:0").unwrap());
            let url = format!("http://{}", server.server_addr());
            let calls = Arc::new(Mutex::new(vec![]));
            let recording = calls.clone();
            let running = server.clone();
            let behavior = behavior.to_owned();
            let thread = std::thread::spawn(move || {
                while let Ok(mut request) = running.recv() {
                    let mut raw = String::new();
                    request.as_reader().read_to_string(&mut raw).unwrap();
                    let value: Value = serde_json::from_str(&raw).unwrap();
                    recording.lock().unwrap().push(value.clone());
                    let result = if request.url().starts_with("/generation/") {
                        json!({"model":value["model"],"token":value["token"],"activation_seconds":0,"reconciled":true})
                    } else {
                        let data = &value["input"];
                        let nu = value["lease"]["model"] == "nuextract";
                        let result: Result<Value> = (|| match value["op"].as_str().unwrap() {
                            "profile" => {
                                let prompt = "synthetic answer test";
                                let generator = GenerationConfig {
                                    model: "fixture".into(),
                                    revision: "v1".into(),
                                    artifact_sha256: "a".repeat(64),
                                    runtime: "fixture".into(),
                                    prompt: prompt.into(),
                                    prompt_version: crate::sha256(prompt.as_bytes()),
                                    temperature: 0,
                                    seed: 42,
                                    context_window: 4096,
                                    output_tokens: 256,
                                    annotation_tokens: 60,
                                };
                                Ok(json!({"space":encoder.space(),"generator":generator}))
                            }
                            "count" => Ok(json!(encoder.count_tokens(data.as_str().unwrap())?)),
                            "embed" => Ok(json!(encoder.embed(data.as_str().unwrap())?)),
                            "rerank" => Ok(
                                json!({"scores":vec![1.;data["passages"].as_array().unwrap().len()],"pair_tokens":vec![20;data["passages"].as_array().unwrap().len()],"identity":{}}),
                            ),
                            "answer_tokens" => Ok(json!(100)),
                            "plan_fields" => {
                                if nu && behavior == "clarification" {
                                    return Ok(
                                        json!({"plan":{"status":"needs_clarification","fields":[]}}),
                                    );
                                }
                                if nu && behavior == "malformed_plan" {
                                    return Ok(json!({"plan":{"status":"ready","fields":[]}}));
                                }
                                Ok(
                                    json!({"plan":{"status":"ready","fields":[{"name":"amount","kind":"number","nullable":false,"description":"Stored amount"}]}}),
                                )
                            }
                            "answer" => {
                                if behavior == "slow" {
                                    std::thread::sleep(Duration::from_millis(300));
                                }
                                if nu && behavior == "outage" {
                                    return Err(Error::Unavailable("injected outage".into()));
                                }
                                let status = if nu
                                    && matches!(
                                        behavior.as_str(),
                                        "ambiguous" | "insufficient_evidence"
                                    ) {
                                    behavior.as_str()
                                } else {
                                    "supported"
                                };
                                let mut fields = serde_json::Map::new();
                                if status == "supported" {
                                    for (name, _) in data["fields"].as_object().unwrap() {
                                        fields.insert(name.clone(),json!({"value":null,"evidence_id":data["evidence"][0]["id"],"quote":"","pointer":if nu && behavior=="rejected" {"/missing".to_owned()} else {format!("/{name}")}}));
                                    }
                                }
                                Ok(
                                    json!({"answer":{"status":status,"fields":fields},"audit":{"model":value["lease"]["model"]}}),
                                )
                            }
                            "rewrite" => Err(Error::Unavailable("optional draft failed".into())),
                            _ => panic!("unexpected operation {value}"),
                        })();
                        match result {
                            Ok(result) => json!({"result":result}),
                            Err(error) => json!({"error":error.to_string()}),
                        }
                    };
                    request
                        .respond(tiny_http::Response::from_string(result.to_string()))
                        .unwrap();
                }
            });
            let app = Application::open(&root.path().join("db"), Client::new(url)).unwrap();
            app.answer_started.store(true, Ordering::Relaxed); // Drive one durable transition at a time.
            Self {
                root,
                app,
                calls,
                server,
                thread: Some(thread),
            }
        }
        fn run(&self, mode: Mode) -> Value {
            self.app.submit_answer(submission(0, mode)).unwrap();
            self.app.answer_step().unwrap();
            self.app.answer_step().unwrap();
            self.app.answer_job("synthetic-job-0000").unwrap()
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            self.app.stop();
            self.server.unblock();
            self.thread.take().unwrap().join().unwrap();
        }
    }
    #[test]
    fn validated_nuextract_skips_gemma_and_preserves_exact_export() {
        let fixture = Fixture::new("supported");
        let job = fixture.run(Mode::Hybrid);
        assert_eq!(job["attempt_count"], 1);
        assert_eq!(job["result"]["outcome"], "supported");
        assert_eq!(
            job["result"]["fields"][0]["value_text"],
            "9007199254740993.00000000000001"
        );
        assert!(
            job["diagnostics_text"]
                .as_str()
                .unwrap()
                .contains("9007199254740993.00000000000001")
        );
        assert!(
            fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .all(|c| c["lease"]["model"] != "gemma")
        );
    }
    #[test]
    fn eligible_failures_get_one_independent_gemma_attempt_and_no_rejected_context() {
        for behavior in [
            "clarification",
            "malformed_plan",
            "ambiguous",
            "insufficient_evidence",
            "rejected",
            "outage",
        ] {
            let fixture = Fixture::new(behavior);
            let job = fixture.run(Mode::Hybrid);
            assert_eq!(job["attempt_count"], 2, "{behavior}: {job}");
            assert_eq!(job["result"]["outcome"], "supported", "{behavior}: {job}");
            let calls = fixture.calls.lock().unwrap();
            let plans: Vec<_> = calls.iter().filter(|c| c["op"] == "plan_fields").collect();
            assert_eq!(plans.len(), 2);
            assert_eq!(plans[0]["input"], plans[1]["input"]);
            assert_eq!(plans[0]["lease"]["model"], "nuextract");
            assert_eq!(plans[1]["lease"]["model"], "gemma");
            assert!(!fixture.app.answer_step().unwrap());
        }
    }
    #[test]
    fn forced_modes_do_not_cross_models_even_on_failure() {
        for mode in [Mode::Gemma, Mode::Nuextract] {
            let fixture = Fixture::new("outage");
            let job = fixture.run(mode);
            assert_eq!(job["attempt_count"], 1);
            assert_eq!(
                job["attempts"][0]["model"],
                serde_json::to_value(mode.first()).unwrap()
            );
        }
    }
    #[test]
    fn invalid_requests_cancelled_and_changed_sources_never_fall_back() {
        let fixture = Fixture::new("supported");
        let mut bad = submission(0, Mode::Hybrid);
        bad.payload["question"] = json!("What is the sum of all amounts?");
        assert!(fixture.app.submit_answer(bad).is_err());
        assert!(fixture.calls.lock().unwrap().is_empty());
        fixture
            .app
            .submit_answer(submission(1, Mode::Hybrid))
            .unwrap();
        fixture.app.cancel_answer("synthetic-job-0001").unwrap();
        assert!(!fixture.app.answer_step().unwrap());
        fixture
            .app
            .submit_answer(submission(2, Mode::Hybrid))
            .unwrap();
        let rev = fixture
            .app
            .snapshot()
            .unwrap()
            .document("doc")
            .unwrap()
            .revision
            .clone();
        fixture.app.ui_remove("doc", &rev).unwrap();
        fixture.app.answer_step().unwrap();
        assert_eq!(
            fixture.app.answer_job("synthetic-job-0002").unwrap()["state"],
            "stale"
        );
        assert!(fixture.calls.lock().unwrap().is_empty());
        assert!(fixture.root.path().join("db.answer-jobs").is_dir());
    }
    #[test]
    fn optional_prose_failure_does_not_trigger_fallback() {
        let fixture = Fixture::new("supported");
        let mut input = submission(0, Mode::Hybrid);
        input.payload["prose"] = json!(true);
        fixture.app.submit_answer(input).unwrap();
        fixture.app.answer_step().unwrap();
        let job = fixture.app.answer_job("synthetic-job-0000").unwrap();
        assert_eq!(job["attempt_count"], 1);
        assert_eq!(job["result"]["outcome"], "supported");
        assert!(
            job["result"]["raw_report"]
                .as_str()
                .unwrap()
                .contains("presentation_error")
        );
    }

    #[test]
    fn cancellation_during_an_active_rpc_is_not_lost_and_stops_later_stages() {
        let fixture = Fixture::new("slow");
        let mut input = submission(0, Mode::Hybrid);
        input.payload["prose"] = json!(true);
        fixture.app.submit_answer(input).unwrap();
        let app = fixture.app.clone();
        let active = std::thread::spawn(move || app.answer_step().unwrap());
        for _ in 0..200 {
            if fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .any(|v| v["op"] == "answer")
            {
                break;
            }
            std::thread::sleep(Duration::from_millis(5));
        }
        assert!(
            fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .any(|v| v["op"] == "answer")
        );
        fixture.app.cancel_answer("synthetic-job-0000").unwrap();
        assert!(active.join().unwrap());
        let job = fixture.app.answer_job("synthetic-job-0000").unwrap();
        assert_eq!(job["state"], "cancelled");
        assert_eq!(job["attempt_count"], 1);
        assert!(
            !fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .any(|v| v["op"] == "rewrite")
        );
    }

    #[test]
    fn removed_ingestion_generator_refuses_upgrade_without_rewriting_saved_policy() {
        let fixture = Fixture::new("supported");
        let profile = RemoteModels::connect(fixture.app.processor.clone(), "interactive")
            .unwrap()
            .profile;
        let mut config = IngestConfig::new(profile.space);
        config.context = Some(ContextConfig::new(
            Policy::Generated,
            Some(profile.generator.clone()),
        ));
        config.target_tokens = config.chunk_limit();
        let request = IngestRequest {
            job_id: "unfinished-generator".into(),
            document_id: "pending".into(),
            expected_revision: None,
            media_type: MediaType::Txt,
            config,
        };
        lock(&fixture.app.db)
            .unwrap()
            .submit_ingestion(request.clone(), b"A pending source.")
            .unwrap();
        fixture
            .app
            .check_ingestion_generator(&profile.generator)
            .unwrap();
        let mut removed = profile.generator;
        removed.runtime = "different-removed-runtime".into();
        assert!(
            fixture
                .app
                .check_ingestion_generator(&removed)
                .unwrap_err()
                .to_string()
                .contains("unavailable generator")
        );
        assert_eq!(
            lock(&fixture.app.db)
                .unwrap()
                .ingestion_job("unfinished-generator")
                .unwrap()
                .unwrap()
                .request,
            request
        );
    }
}
