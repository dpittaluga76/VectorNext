//! Shared database owner and short-write/long-processing application boundary.
pub mod http;
pub mod remote;
use crate::{
    Database, Error, ReadSnapshot, Result,
    answers::{self, AnswerOptions, AskRequest, Scope},
    contracts::*,
    ingestion::{context::*, *},
    require,
    search::*,
};
use base64::{Engine, engine::general_purpose::STANDARD};
use remote::{Client, RemoteModels, SourceOnly};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    path::Path,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

fn structural() -> Policy {
    Policy::Structural
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Upload {
    pub job_id: String,
    pub document_id: String,
    pub expected_revision: Option<String>,
    pub media_type: MediaType,
    #[serde(default = "structural")]
    pub policy: Policy,
    #[serde(default)]
    pub record_pointer: String,
    #[serde(default)]
    pub allow_partial: bool,
    pub source_base64: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Search {
    pub text: String,
    #[serde(default = "keyword")]
    pub mode: String,
    #[serde(default)]
    pub filter: Filter,
    #[serde(default = "ten")]
    pub limit: usize,
    pub space_id: Option<String>,
}
fn keyword() -> String {
    "keyword".into()
}
fn ten() -> usize {
    10
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Question {
    pub request: AskRequest,
    pub space_id: Option<String>,
    #[serde(default)]
    pub options: AnswerOptions,
}
type IndexCache = BTreeMap<String, (u64, Arc<SearchIndex>)>;

pub struct Application {
    db: Mutex<Database>,
    pub processor: Client,
    indexes: Mutex<IndexCache>,
    background: Mutex<()>,
    interactive: Mutex<()>,
    active: Mutex<Option<String>>,
    stopping: AtomicBool,
    measured: Mutex<BTreeMap<String, (u64, f64)>>,
    structural_weight: f64,
    generated_weight: f64,
}
fn lock<T>(value: &Mutex<T>) -> Result<std::sync::MutexGuard<'_, T>> {
    value
        .lock()
        .map_err(|_| Error::Unavailable("application lock poisoned; restart required".into()))
}
fn busy<T>(value: &Mutex<T>) -> Result<std::sync::MutexGuard<'_, T>> {
    value
        .try_lock()
        .map_err(|_| Error::Unavailable("processing lane busy; retry later".into()))
}
pub fn job_summary(job: &IngestJob) -> Value {
    json!({"job_id":job.request.job_id,"document_id":job.request.document_id,"revision":job.input_sha256,
        "stage":job.stage,"successful_stages":job.successful_stages,"failure_count":job.failure_count,
        "last_failure":job.last_failure,"receipt":job.receipt})
}
impl Application {
    pub fn open(path: &Path, processor: Client) -> Result<Arc<Self>> {
        Self::open_with_weights(path, processor, 1.0, 1.0)
    }
    pub fn open_with_weights(
        path: &Path,
        processor: Client,
        structural_weight: f64,
        generated_weight: f64,
    ) -> Result<Arc<Self>> {
        require(
            structural_weight.is_finite() && (0.0..=10.0).contains(&structural_weight),
            "invalid structural keyword weight",
        )?;
        require(
            generated_weight.is_finite() && (0.0..=10.0).contains(&generated_weight),
            "invalid generated keyword weight",
        )?;
        Ok(Arc::new(Self {
            db: Mutex::new(Database::open(path)?),
            processor,
            indexes: Mutex::new(BTreeMap::new()),
            background: Mutex::new(()),
            interactive: Mutex::new(()),
            active: Mutex::new(None),
            stopping: AtomicBool::new(false),
            measured: Mutex::new(BTreeMap::new()),
            structural_weight,
            generated_weight,
        }))
    }
    fn measure(&self, name: &str, start: Instant) {
        if let Ok(mut values) = self.measured.lock() {
            let value = values.entry(name.into()).or_default();
            value.0 += 1;
            value.1 += start.elapsed().as_secs_f64() * 1000.0;
        }
    }
    pub fn metrics(&self) -> Result<Value> {
        Ok(
            json!({"scope":"process lifetime; cumulative calls and milliseconds; lost on restart",
            "stages":*lock(&self.measured)?, "processor":self.processor.health().unwrap_or(Value::Null)}),
        )
    }
    pub fn snapshot(&self) -> Result<ReadSnapshot> {
        Ok(lock(&self.db)?.snapshot())
    }
    pub fn storage_status(&self) -> Result<Value> {
        let db = lock(&self.db)?;
        Ok(
            json!({"live":true,"storage_ready":!db.poisoned,"generation":db.snapshot().generation(),
            "active_job":*lock(&self.active)?,"stopping":self.stopping.load(Ordering::Relaxed)}),
        )
    }
    pub fn ready(&self) -> Result<Value> {
        let storage = self.storage_status()?;
        let processor = self
            .processor
            .health()
            .unwrap_or_else(|e| json!({"error":e.to_string(),"capabilities":{}}));
        let capabilities = &processor["capabilities"];
        let ready = storage["storage_ready"] == true
            && ["embedding", "reranking", "pdf", "generation"]
                .iter()
                .all(|k| capabilities[*k] == true);
        Ok(
            json!({"ready":ready,"storage":storage,"processor":processor,
            "independent_operations":["document inspection","job inspection","keyword search","structured lookup without prose"]}),
        )
    }
    pub fn documents(&self) -> Result<Value> {
        let snapshot = self.snapshot()?;
        Ok(
            json!({"generation":snapshot.generation(), "spaces":snapshot.spaces().map(|(id,s)|json!({"id":id,"space":s})).collect::<Vec<_>>(),
            "documents":snapshot.documents().map(|d|json!({"document_id":d.document_id,"revision":d.revision,"media_type":d.media_type,
                "original":d.original,"chunks":d.chunks.len()})).collect::<Vec<_>>()}),
        )
    }
    pub fn document(&self, id: &str) -> Result<Value> {
        let snapshot = self.snapshot()?;
        Ok(
            json!({"generation":snapshot.generation(),"document":snapshot.document(id).ok_or_else(|| Error::Invalid("unknown document".into()))?}),
        )
    }
    pub fn jobs(&self) -> Result<Value> {
        Ok(
            json!({"jobs":lock(&self.db)?.ingestion_jobs()?.iter().map(job_summary).collect::<Vec<_>>()}),
        )
    }
    pub fn job(&self, id: &str) -> Result<Value> {
        Ok(job_summary(
            &lock(&self.db)?
                .ingestion_job(id)?
                .ok_or_else(|| Error::Invalid("unknown job".into()))?,
        ))
    }
    pub fn retry(&self, id: &str) -> Result<Value> {
        let _background = busy(&self.background)?;
        Ok(job_summary(&lock(&self.db)?.retry_ingestion(id)?))
    }
    pub fn upload(&self, upload: Upload) -> Result<Value> {
        require(
            !upload.job_id.trim().is_empty()
                && upload.job_id.len() <= 128
                && !upload.document_id.trim().is_empty()
                && upload.document_id.len() <= 128,
            "document/job IDs require 1..128 bytes",
        )?;
        require(
            upload.record_pointer.len() <= 4096,
            "record pointer too long",
        )?;
        require(
            upload.source_base64.len() <= (16usize * 1024 * 1024).div_ceil(3) * 4,
            "source exceeds 16 MiB",
        )?;
        let bytes = STANDARD
            .decode(&upload.source_base64)
            .map_err(|_| Error::Invalid("invalid source base64".into()))?;
        require(
            !bytes.is_empty() && bytes.len() <= 16 * 1024 * 1024,
            "source requires 1..16 MiB",
        )?;
        {
            let db = lock(&self.db)?;
            if let Some(job) = db.ingestion_job(&upload.job_id)? {
                let config = &job.request.config;
                require(
                    job.request.document_id == upload.document_id
                        && job.request.expected_revision == upload.expected_revision
                        && job.request.media_type == upload.media_type
                        && job.draft.document.original.sha256 == crate::sha256(&bytes)
                        && config.record_pointer == upload.record_pointer
                        && config
                            .context
                            .as_ref()
                            .is_some_and(|c| c.policy == upload.policy)
                        && config.pdf.as_ref().is_some_and(|p| p.allow_partial)
                            == upload.allow_partial,
                    "job ID already has different input/options",
                )?;
                return Ok(job_summary(&job));
            }
            require(
                db.ingestion_jobs()?
                    .iter()
                    .filter(|j| j.stage != Stage::Committed)
                    .count()
                    < 64,
                "64 unfinished jobs already queued",
            )?;
        }
        require(
            !upload.allow_partial || upload.media_type == MediaType::Pdf,
            "partial extraction applies only to PDF",
        )?;
        let _background = busy(&self.background)?;
        let upload_start = Instant::now();
        let models = RemoteModels::connect(self.processor.clone(), "background")?;
        let artifact = if upload.media_type == MediaType::Pdf {
            Some(self.processor.pdf(&bytes)?)
        } else {
            None
        };
        let mut config = if let Some(artifact) = &artifact {
            artifact.config(models.space(), upload.allow_partial)?
        } else {
            IngestConfig::new(models.space())
        };
        config.record_pointer = upload.record_pointer;
        config.context = Some(ContextConfig::new(
            upload.policy.clone(),
            (upload.policy == Policy::Generated).then(|| models.profile.generator.clone()),
        ));
        config.target_tokens = 180.min(config.chunk_limit());
        config.validate()?;
        let mut db = lock(&self.db)?;
        if let Some(artifact) = &artifact {
            require(
                artifact.source_sha256 == crate::sha256(&bytes),
                "PDF artifact source mismatch",
            )?;
            let saved = db.put_original(&serde_json::to_vec(artifact)?)?;
            require(
                saved.sha256 == artifact.id()?,
                "PDF artifact identity mismatch",
            )?;
        }
        let job = db.submit_ingestion(
            IngestRequest {
                job_id: upload.job_id,
                document_id: upload.document_id,
                expected_revision: upload.expected_revision,
                media_type: upload.media_type,
                config,
            },
            &bytes,
        )?;
        self.measure("upload_preparation_and_save", upload_start);
        Ok(job_summary(&job))
    }
    fn index(&self, id: Option<&str>) -> Result<(Arc<SearchIndex>, EmbeddingSpace)> {
        let snapshot = self.snapshot()?;
        let space = if let Some(id) = id {
            snapshot.space(id)
        } else {
            require(
                snapshot.spaces().count() <= 1,
                "multiple embedding spaces; supply space_id",
            )?;
            snapshot.spaces().next().map(|(_, s)| s)
        }
        .ok_or_else(|| {
            Error::Invalid("no matching embedding space; ingest a document first".into())
        })?
        .clone();
        let id = space.id();
        if let Some((generation, index)) = lock(&self.indexes)?.get(&id) {
            if *generation == snapshot.generation() {
                return Ok((index.clone(), space));
            }
        }
        let generation = snapshot.generation();
        let index = Arc::new(SearchIndex::build(
            snapshot,
            id.clone(),
            KeywordConfig {
                structural_weight: self.structural_weight,
                generated_weight: self.generated_weight,
                ..Default::default()
            },
        )?);
        let mut cache = lock(&self.indexes)?;
        if cache.len() >= 4 {
            cache.clear();
        }
        if cache.get(&id).is_none_or(|(g, _)| *g <= generation) {
            cache.insert(id, (generation, index.clone()));
        }
        Ok((index, space))
    }
    pub fn search(&self, request: Search) -> Result<Value> {
        require(
            !request.text.trim().is_empty()
                && request.text.len() <= 8192
                && (1..=100).contains(&request.limit),
            "invalid search text/limit",
        )?;
        require(
            matches!(request.mode.as_str(), "keyword" | "hybrid"),
            "mode must be keyword or hybrid",
        )?;
        let (index, space) = self.index(request.space_id.as_deref())?;
        let mut query = if request.mode == "hybrid" {
            let _interactive = busy(&self.interactive)?;
            let models = RemoteModels::connect(self.processor.clone(), "interactive")?;
            require(
                models.space() == space,
                "processor/index embedding spaces differ",
            )?;
            SearchRequest::hybrid(
                &request.text,
                QueryVector {
                    space_id: space.id(),
                    values: models.embed(&format!("{}{}", space.query_prefix, request.text))?,
                },
            )
        } else {
            SearchRequest::keyword(&request.text)
        };
        query.filter = request.filter;
        query.limit = request.limit;
        let trace = index.search(&query)?;
        let hits: Vec<_> = trace.results.iter().map(|hit| {
            let (_, chunk) = index.resolve(&hit.key).unwrap();
            json!({"key":hit.key,"score":hit.score,"evidence":chunk.evidence,"structural_context":chunk.structural_context,"sources":chunk.sources})
        }).collect();
        Ok(json!({"generation":index.generation(),"space_id":space.id(),"hits":hits,"trace":trace}))
    }
    pub fn ask(&self, question: Question) -> Result<Value> {
        let started = Instant::now();
        let (index, space) = self.index(question.space_id.as_deref())?;
        let index_ms = started.elapsed().as_secs_f64() * 1000.0;
        let mut report =
            if question.request.scope == Scope::StructuredLookup && !question.request.prose {
                answers::ask_with_options(
                    &index,
                    &SourceOnly(space),
                    question.request,
                    question.options,
                )?
            } else {
                let _interactive = busy(&self.interactive)?;
                let models = RemoteModels::connect(self.processor.clone(), "interactive")?;
                require(
                    models.space() == space,
                    "processor/index embedding spaces differ",
                )?;
                answers::ask_with_options(&index, &models, question.request, question.options)?
            };
        report.timings_ms.insert("snapshot_index".into(), index_ms);
        report.timings_ms.insert(
            "application_total".into(),
            started.elapsed().as_secs_f64() * 1000.0,
        );
        Ok(serde_json::to_value(report)?)
    }
    /// Process one saved stage outside the database mutex. Only one coordinator runs.
    pub fn step(&self) -> Result<bool> {
        let Ok(_background) = self.background.try_lock() else {
            return Ok(false);
        };
        let job = {
            let db = lock(&self.db)?;
            if db.poisoned {
                return Err(Error::Poisoned);
            }
            db.ingestion_jobs()?
                .into_iter()
                .find(|j| j.stage != Stage::Committed && j.last_failure.is_none())
        };
        let Some(job) = job else {
            return Ok(false);
        };
        let id = &job.request.job_id;
        let started = Instant::now();
        if job.stage == Stage::Embedded {
            let result = lock(&self.db)?.commit_ingestion(id);
            self.measure("publication", started);
            result?;
            return Ok(true);
        }
        let request = lock(&self.db)?.ingestion_stage_request(id)?;
        let input_id = request.id()?;
        *lock(&self.active)? = Some(id.clone());
        let outcome = (|| {
            let models = RemoteModels::connect(self.processor.clone(), "background")?;
            require(
                models.space() == request.config.space,
                "stored job and processor embedding spaces differ",
            )?;
            let base: Box<dyn Processor + '_> = if job.stage == Stage::Uploaded
                && request.config.pdf.is_some()
            {
                let artifact_id = &request.config.pdf.as_ref().unwrap().artifact_sha256;
                let raw = {
                    let db = lock(&self.db)?;
                    let size = std::fs::metadata(db.root.join("blobs").join(artifact_id))?.len();
                    require(size <= 16 * 1024 * 1024, "stored PDF artifact too large")?;
                    db.originals().get(&BlobRef {
                        sha256: artifact_id.clone(),
                        bytes: size,
                    })?
                };
                Box::new(pdf::PdfProcessor {
                    local: LocalProcessor { encoder: &models },
                    artifact: pdf::Artifact::from_slice(&raw)?,
                })
            } else {
                Box::new(LocalProcessor { encoder: &models })
            };
            let processor = ContextProcessor {
                base,
                generator: &models,
            };
            let result = processor.process(&request)?;
            lock(&self.db)?.accept_ingestion_stage(id, result)?;
            Ok(())
        })();
        self.measure(&format!("stage_{:?}", job.stage), started);
        *lock(&self.active)? = None;
        if let Err(error) = outcome {
            lock(&self.db)?.reject_ingestion_stage(id, &input_id, &error)?;
        }
        Ok(true)
    }
    pub fn start(self: &Arc<Self>) -> std::thread::JoinHandle<()> {
        let app = self.clone();
        std::thread::spawn(move || {
            while !app.stopping.load(Ordering::Relaxed) {
                match app.step() {
                    Ok(true) => continue,
                    Err(error) => eprintln!("ingestion coordinator: {error}"),
                    _ => (),
                }
                std::thread::sleep(Duration::from_millis(500));
            }
        })
    }
    pub fn stop(&self) {
        self.stopping.store(true, Ordering::Relaxed);
    }
}
