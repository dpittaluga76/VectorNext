use super::*;
use crate::{
    Database, Error, Receipt,
    blob::{ensure_dir, sync_dir},
    frame::{self, ReadFrame},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::Write,
};

const JOB_FRAME: u16 = frame::JOB;
const MAX_SOURCE: usize = 16 * 1024 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum JobFault {
    Write,
    Sync,
    Rename,
    DirectorySync,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Stage {
    Uploaded,
    Parsed,
    Chunked,
    Contextualized,
    Embedded,
    Committed,
}

impl Stage {
    fn next(self) -> Result<Self> {
        Ok(match self {
            Self::Uploaded => Self::Parsed,
            Self::Parsed => Self::Chunked,
            Self::Chunked => Self::Contextualized,
            Self::Contextualized => Self::Embedded,
            _ => return Err(Error::Invalid("no next processor stage".into())),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct IngestRequest {
    pub job_id: String,
    pub document_id: String,
    pub expected_revision: Option<String>,
    pub media_type: MediaType,
    pub config: IngestConfig,
}

impl IngestRequest {
    fn validate(&self) -> Result<()> {
        require(
            !self.job_id.is_empty()
                && self.job_id.len() <= 1024
                && !self.document_id.is_empty()
                && self.document_id.len() <= 1024
                && self
                    .expected_revision
                    .as_ref()
                    .is_none_or(|r| !r.is_empty() && r.len() <= 1024),
            "invalid ingestion identity",
        )?;
        require(
            (self.media_type == MediaType::Pdf) == self.config.pdf.is_some(),
            "PDF requires a PDF profile; TXT/JSON must not carry one",
        )?;
        self.config.validate()
    }
    fn digest(&self, original: &BlobRef) -> Result<String> {
        Ok(sha256(&serde_json::to_vec(&(self, original))?))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Failure {
    pub stage: Stage,
    pub message: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct IngestJob {
    pub format: u32,
    pub request: IngestRequest,
    pub input_sha256: String,
    pub stage: Stage,
    pub draft: Draft,
    pub successful_stages: u64,
    pub failure_count: u64,
    pub last_failure: Option<Failure>,
    pub last_result_sha256: Option<String>,
    pub receipt: Option<Receipt>,
}

impl IngestJob {
    /// Stable publication ID. Safe to retry even after a later replacement/deletion.
    pub fn publication_batch(&self) -> Result<Batch> {
        require(
            matches!(self.stage, Stage::Embedded | Stage::Committed),
            "draft is not fully embedded",
        )?;
        Ok(Batch {
            operation_id: format!("ingest:{}", self.input_sha256),
            spaces: vec![self.request.config.space.clone()],
            mutations: vec![Mutation::Replace {
                expected_revision: self.request.expected_revision.clone(),
                document: Box::new(self.draft.document.clone()),
            }],
        })
    }
}

fn validate_draft(job: &IngestJob) -> Result<()> {
    let d = &job.draft.document;
    let request = &job.request;
    require(
        d.document_id == request.document_id
            && d.media_type == request.media_type
            && d.revision == job.input_sha256
            && request.digest(&d.original)? == job.input_sha256,
        "job/draft identity mismatch",
    )?;
    let mut processing = d.processing.clone();
    context::validate_report(
        &job.draft,
        &request.config,
        matches!(
            job.stage,
            Stage::Contextualized | Stage::Embedded | Stage::Committed
        ),
    )?;
    processing.remove("context");
    if request.media_type == MediaType::Pdf && job.stage != Stage::Uploaded {
        pdf::validate_prepared(&job.draft, &request.config)?;
        processing.remove("pdf");
    }
    require(
        processing
            == BTreeMap::from([("ingestion".into(), serde_json::to_value(&request.config)?)]),
        "draft configuration changed",
    )?;
    require(
        d.required_spaces == BTreeSet::from([request.config.space.id()]),
        "draft spaces changed",
    )?;
    if job.stage == Stage::Uploaded {
        return require(
            d.blocks.is_empty() && d.chunks.is_empty() && job.draft.units.is_empty(),
            "uploaded job has derived data",
        );
    }
    require(
        !d.blocks.is_empty() && !job.draft.units.is_empty(),
        "parsed output has no blocks",
    )?;
    let mut units = BTreeSet::new();
    for unit in &job.draft.units {
        require(
            units.insert(&unit.block_id) && d.blocks.iter().any(|b| b.id == unit.block_id),
            "invalid parsed unit",
        )?;
        require(
            unit.pdf.is_some() == (request.media_type == MediaType::Pdf),
            "invalid unit media type",
        )?;
    }
    if job.stage == Stage::Parsed {
        require(d.chunks.is_empty(), "parsed output already has chunks")?;
    } else {
        // Validate the complete structural contract before embeddings exist, using
        // a temporary valid vector solely for validation. Never persist it.
        let mut candidate = d.clone();
        if !matches!(job.stage, Stage::Embedded | Stage::Committed) {
            let mut placeholder = vec![0.0; request.config.space.dimensions];
            placeholder[0] = 1.0;
            for chunk in &mut candidate.chunks {
                require(chunk.vectors.is_empty(), "premature embeddings")?;
                chunk
                    .vectors
                    .insert(request.config.space.id(), placeholder.clone());
            }
        }
        candidate.validate(&BTreeMap::from([(
            request.config.space.id(),
            request.config.space.clone(),
        )]))?;
    }
    Ok(())
}

impl Database {
    fn job_path(&self, id: &str) -> std::path::PathBuf {
        self.root
            .join("jobs")
            .join(format!("{}.job", sha256(id.as_bytes())))
    }

    pub fn ingestion_job(&self, id: &str) -> Result<Option<IngestJob>> {
        let path = self.job_path(id);
        if !path.exists() {
            return Ok(None);
        }
        let job = self.read_job(&path)?;
        require(job.request.job_id == id, "job filename/ID mismatch")?;
        Ok(Some(job))
    }

    fn read_job(&self, path: &std::path::Path) -> Result<IngestJob> {
        let mut file = File::open(path)?;
        let job: IngestJob = match frame::read(&mut file)? {
            ReadFrame::Complete {
                kind: JOB_FRAME,
                payload,
            } => serde_json::from_slice(&payload)?,
            _ => return Err(Error::Corrupt("incomplete/invalid job frame".into())),
        };
        require(
            matches!(frame::read(&mut file)?, ReadFrame::End),
            "trailing job data",
        )?;
        require(
            job.format == 1 && path == self.job_path(&job.request.job_id),
            "job format/filename mismatch",
        )?;
        job.request.validate()?;
        validate_draft(&job)?;
        self.originals().get(&job.draft.document.original)?;
        require(
            (job.stage == Stage::Committed) == job.receipt.is_some(),
            "job receipt/stage mismatch",
        )?;
        if matches!(job.stage, Stage::Embedded | Stage::Committed) {
            let batch = job.publication_batch()?;
            if let Some(receipt) = self.snapshot().receipt(&batch.operation_id) {
                require(
                    receipt.request_sha256 == sha256(&serde_json::to_vec(&batch)?),
                    "job publication differs from receipt",
                )?;
                if let Some(saved) = &job.receipt {
                    require(saved == receipt, "job receipt mismatch")?;
                }
            } else {
                require(
                    job.receipt.is_none(),
                    "committed job has no database receipt",
                )?;
            }
        }
        Ok(job)
    }

    /// Job state is a separate durable namespace; it never changes search generations.
    pub fn ingestion_jobs(&self) -> Result<Vec<IngestJob>> {
        let directory = self.root.join("jobs");
        if !directory.exists() {
            return Ok(vec![]);
        }
        let mut jobs = vec![];
        for entry in fs::read_dir(directory)? {
            let path = entry?.path();
            if path.extension().is_some_and(|e| e == "job") {
                jobs.push(self.read_job(&path)?);
            }
        }
        jobs.sort_by(|a, b| a.request.job_id.cmp(&b.request.job_id));
        Ok(jobs)
    }

    pub(crate) fn validate_jobs(&self) -> Result<()> {
        self.ingestion_jobs().map(|_| ())
    }

    fn save_job(&mut self, job: &IngestJob) -> Result<()> {
        self.writable()?;
        validate_draft(job)?;
        let bytes = frame::encode(JOB_FRAME, &serde_json::to_vec(job)?)?;
        let result = (|| -> Result<()> {
            let directory = self.root.join("jobs");
            ensure_dir(&directory)?;
            let pending = directory.join("stage.pending");
            let mut file = OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .open(&pending)?;
            file.write_all(&bytes)?;
            self.job_fault(JobFault::Write)?;
            file.sync_all()?;
            self.job_fault(JobFault::Sync)?;
            drop(file);
            fs::rename(pending, self.job_path(&job.request.job_id))?;
            self.job_fault(JobFault::Rename)?;
            sync_dir(&directory)?;
            self.job_fault(JobFault::DirectorySync)
        })();
        if result.is_err() {
            self.poisoned = true;
        }
        result
    }

    fn job_fault(&self, point: JobFault) -> Result<()> {
        #[cfg(test)]
        if self.job_fail_at == Some(point) {
            return Err(std::io::Error::other(format!("injected job {point:?}")).into());
        }
        let _ = point;
        Ok(())
    }

    pub fn submit_ingestion(&mut self, request: IngestRequest, bytes: &[u8]) -> Result<IngestJob> {
        self.writable()?;
        request.validate()?;
        require(
            !bytes.is_empty() && bytes.len() <= MAX_SOURCE,
            "source must contain 1..16 MiB of bytes",
        )?;
        let original = BlobRef {
            sha256: sha256(bytes),
            bytes: bytes.len() as u64,
        };
        let input_sha256 = request.digest(&original)?;
        if let Some(job) = self.ingestion_job(&request.job_id)? {
            return if job.input_sha256 == input_sha256 {
                Ok(job)
            } else {
                Err(Error::RetryConflict)
            };
        }
        if self
            .snapshot()
            .document(&request.document_id)
            .map(|d| &d.revision)
            != request.expected_revision.as_ref()
        {
            return Err(Error::Conflict(request.document_id.clone()));
        }
        self.put_original(bytes)?;
        let draft = Draft {
            document: DocumentRevision {
                document_id: request.document_id.clone(),
                revision: input_sha256.clone(),
                original,
                media_type: request.media_type.clone(),
                processing: BTreeMap::from([(
                    "ingestion".into(),
                    serde_json::to_value(&request.config)?,
                )]),
                required_spaces: BTreeSet::from([request.config.space.id()]),
                blocks: vec![],
                chunks: vec![],
            },
            units: vec![],
        };
        let job = IngestJob {
            format: 1,
            request,
            input_sha256,
            stage: Stage::Uploaded,
            draft,
            successful_stages: 0,
            failure_count: 0,
            last_failure: None,
            last_result_sha256: None,
            receipt: None,
        };
        self.save_job(&job)?;
        Ok(job)
    }

    fn required_job(&self, id: &str) -> Result<IngestJob> {
        self.ingestion_job(id)?
            .ok_or_else(|| Error::Invalid("unknown ingestion job".into()))
    }

    pub fn ingestion_stage_request(&self, id: &str) -> Result<StageRequest> {
        let job = self.required_job(id)?;
        require(
            !matches!(job.stage, Stage::Embedded | Stage::Committed),
            "stage has no processor work",
        )?;
        Ok(StageRequest {
            job_id: id.into(),
            stage: job.stage,
            config: job.request.config,
            original: if job.stage == Stage::Uploaded {
                Some(self.originals().get(&job.draft.document.original)?)
            } else {
                None
            },
            draft: job.draft,
        })
    }

    pub fn accept_ingestion_stage(&mut self, id: &str, result: StageResult) -> Result<IngestJob> {
        self.writable()?;
        let mut job = self.required_job(id)?;
        let digest = sha256(&serde_json::to_vec(&result)?);
        if job.last_result_sha256.as_ref() == Some(&digest) {
            return Ok(job);
        }
        require(
            self.ingestion_stage_request(id)?.id()? == result.input_sha256,
            "stale or mismatched stage result",
        )?;
        let previous = &job.draft;
        match job.stage {
            Stage::Uploaded => {}
            Stage::Parsed => {
                require(
                    result.draft.units == previous.units
                        && result.draft.document.processing == previous.document.processing
                        && result
                            .draft
                            .document
                            .blocks
                            .starts_with(&previous.document.blocks),
                    "chunking changed parsed blocks/units",
                )?;
            }
            Stage::Chunked => {
                let mut stripped = result.draft.clone();
                stripped.document.processing.remove("context");
                for chunk in &mut stripped.document.chunks {
                    chunk.generated_context = None;
                }
                require(
                    stripped == *previous,
                    "contextualization changed evidence/structure",
                )?;
            }
            Stage::Contextualized => {
                let mut stripped = result.draft.clone();
                for chunk in &mut stripped.document.chunks {
                    chunk.vectors.clear();
                }
                require(
                    stripped == *previous,
                    "embedding changed evidence/structure",
                )?;
            }
            _ => return Err(Error::Invalid("no processor result expected".into())),
        }
        job.stage = job.stage.next()?;
        job.draft = result.draft;
        job.successful_stages += 1;
        job.last_failure = None;
        job.last_result_sha256 = Some(digest);
        self.save_job(&job)?;
        Ok(job)
    }

    fn save_failure(&mut self, mut job: IngestJob, error: &Error) -> Result<()> {
        job.failure_count += 1;
        job.last_failure = Some(Failure {
            stage: job.stage,
            message: error.to_string().chars().take(4096).collect(),
        });
        self.save_job(&job)
    }

    /// Record an externally executed stage failure only if its input is still current.
    pub fn reject_ingestion_stage(
        &mut self,
        id: &str,
        input_sha256: &str,
        error: &Error,
    ) -> Result<()> {
        require(
            self.ingestion_stage_request(id)?.id()? == input_sha256,
            "stale stage failure",
        )?;
        self.save_failure(self.required_job(id)?, error)
    }

    pub fn retry_ingestion(&mut self, id: &str) -> Result<IngestJob> {
        let mut job = self.required_job(id)?;
        job.last_failure = None;
        self.save_job(&job)?;
        Ok(job)
    }

    /// Publish a fully embedded revision without contacting a processor.
    pub fn commit_ingestion(&mut self, id: &str) -> Result<IngestJob> {
        self.writable()?;
        let mut job = self.required_job(id)?;
        if job.stage == Stage::Committed {
            return Ok(job);
        }
        require(job.stage == Stage::Embedded, "job is not ready to publish")?;
        match self.commit(job.publication_batch()?) {
            Ok(receipt) => {
                job.receipt = Some(receipt);
                job.stage = Stage::Committed;
                job.last_failure = None;
                self.save_job(&job)?;
                Ok(job)
            }
            Err(error) => {
                if !self.poisoned {
                    self.save_failure(job, &error)?;
                }
                Err(error)
            }
        }
    }

    /// Run at most one stage. Processor work completes before durable writes begin.
    pub fn advance_ingestion(&mut self, id: &str, processor: &impl Processor) -> Result<IngestJob> {
        self.writable()?;
        let job = self.required_job(id)?;
        if job.stage == Stage::Committed {
            return Ok(job);
        }
        if job.stage == Stage::Embedded {
            return self.commit_ingestion(id);
        }
        let request = self.ingestion_stage_request(id)?;
        let outcome = processor
            .process(&request)
            .and_then(|result| self.accept_ingestion_stage(id, result));
        if let Err(error) = &outcome {
            if !self.poisoned {
                self.save_failure(job, error)?;
            }
        }
        outcome
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;

    #[test]
    fn job_io_boundaries_recover_old_or_new_stage_and_publish_once() {
        for point in [
            JobFault::Write,
            JobFault::Sync,
            JobFault::Rename,
            JobFault::DirectorySync,
        ] {
            for publish in [false, true] {
                let dir = tempfile::tempdir().unwrap();
                let mut db = Database::open(dir.path()).unwrap();
                let p = LocalProcessor {
                    encoder: TestEncoder::default(),
                };
                db.submit_ingestion(
                    IngestRequest {
                        job_id: "fault".into(),
                        document_id: "doc".into(),
                        expected_revision: None,
                        media_type: MediaType::Txt,
                        config: IngestConfig::new(p.encoder.space()),
                    },
                    b"complete evidence",
                )
                .unwrap();
                if publish {
                    for _ in 0..4 {
                        db.advance_ingestion("fault", &p).unwrap();
                    }
                }
                db.job_fail_at = Some(point);
                assert!(db.advance_ingestion("fault", &p).is_err());
                assert!(matches!(
                    db.advance_ingestion("fault", &p),
                    Err(Error::Poisoned)
                ));
                assert_eq!(db.snapshot().generation(), u64::from(publish));
                drop(db);
                let mut db = Database::open(dir.path()).unwrap();
                let saved = db.ingestion_job("fault").unwrap().unwrap();
                let renamed = matches!(point, JobFault::Rename | JobFault::DirectorySync);
                assert_eq!(
                    saved.stage,
                    match (publish, renamed) {
                        (false, false) => Stage::Uploaded,
                        (false, true) => Stage::Parsed,
                        (true, false) => Stage::Embedded,
                        (true, true) => Stage::Committed,
                    }
                );
                while db.advance_ingestion("fault", &p).unwrap().stage != Stage::Committed {}
                assert_eq!(db.snapshot().generation(), 1);
                assert_eq!(db.snapshot().documents().count(), 1);
            }
        }
    }
}
