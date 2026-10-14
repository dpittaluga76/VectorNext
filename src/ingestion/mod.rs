//! Versioned, source-preserving ingestion. See docs/ingestion.md.
pub mod context;
mod jobs;
pub mod pdf;
mod prepare;
pub mod worker;

use crate::{Result, contracts::*, require, sha256};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[cfg(test)]
pub(crate) use jobs::JobFault;
pub use jobs::{Failure, IngestJob, IngestRequest, Stage};

pub const PARSER_VERSION: &str = "txt-json-v1";
pub const CHUNKER_VERSION: &str = "sections-subtrees-v1";
pub const INPUT_VERSION: &str = "prefix-context-evidence-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct IngestConfig {
    pub parser_version: String,
    pub chunker_version: String,
    pub input_version: String,
    pub target_tokens: usize,
    /// RFC 6901 pointer selecting records. Empty means the root.
    pub record_pointer: String,
    /// Relative to each record. Missing/null IDs are allowed; other types fail.
    pub record_id_pointer: String,
    pub space: EmbeddingSpace,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pdf: Option<pdf::PdfConfig>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub context: Option<context::ContextConfig>,
}

impl IngestConfig {
    pub fn new(space: EmbeddingSpace) -> Self {
        Self {
            parser_version: PARSER_VERSION.into(),
            chunker_version: CHUNKER_VERSION.into(),
            input_version: INPUT_VERSION.into(),
            target_tokens: 200.min(space.max_tokens),
            record_pointer: String::new(),
            record_id_pointer: "/id".into(),
            space,
            pdf: None,
            context: None,
        }
    }
    pub fn validate(&self) -> Result<()> {
        require(
            serde_json::to_vec(self)?.len() <= 32 * 1024,
            "ingestion configuration exceeds 32 KiB",
        )?;
        self.space.validate()?;
        require(
            ((self.pdf.is_none()
                && self.parser_version == PARSER_VERSION
                && self.chunker_version == CHUNKER_VERSION)
                || (self.pdf.is_some()
                    && self.parser_version == pdf::PARSER_VERSION
                    && self.chunker_version == pdf::CHUNKER_VERSION))
                && self.input_version == INPUT_VERSION,
            "unsupported ingestion version",
        )?;
        require(
            self.target_tokens > 0 && self.target_tokens <= self.space.max_tokens,
            "invalid chunk target",
        )?;
        pointer_parts(&self.record_pointer)?;
        pointer_parts(&self.record_id_pointer)?;
        if let Some(pdf) = &self.pdf {
            pdf.validate()?;
        }
        if let Some(context) = &self.context {
            context.validate(&self.space)?;
            require(
                self.target_tokens <= self.chunk_limit(),
                "target exceeds context-reserved limit",
            )?;
        }
        Ok(())
    }
    pub fn chunk_limit(&self) -> usize {
        self.space
            .max_tokens
            .saturating_sub(self.context.as_ref().map_or(0, |c| c.reserve_tokens()))
    }
}

pub(crate) fn pointer_parts(pointer: &str) -> Result<Vec<String>> {
    if pointer.is_empty() {
        return Ok(vec![]);
    }
    require(pointer.starts_with('/'), "invalid JSON pointer")?;
    pointer[1..]
        .split('/')
        .map(|part| {
            let mut chars = part.chars();
            let mut decoded = String::new();
            while let Some(c) = chars.next() {
                decoded.push(if c == '~' {
                    match chars.next() {
                        Some('0') => '~',
                        Some('1') => '/',
                        _ => {
                            return Err(crate::Error::Invalid(
                                "invalid JSON pointer escape".into(),
                            ));
                        }
                    }
                } else {
                    c
                });
            }
            Ok(decoded)
        })
        .collect()
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Record {
    pub pointer: String,
    pub id: Option<Value>,
    pub value: Value,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ParsedUnit {
    pub block_id: String,
    pub context: String,
    pub section: Option<String>,
    pub record: Option<Record>,
    pub pointer: Option<String>,
    pub value: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pdf: Option<pdf::PdfUnit>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Draft {
    pub document: DocumentRevision,
    pub units: Vec<ParsedUnit>,
}

/// Internal transport contract, deliberately independent of database handles.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct StageRequest {
    pub job_id: String,
    pub stage: Stage,
    pub config: IngestConfig,
    pub draft: Draft,
    /// Only the parse stage needs original bytes. These are not normalized text.
    pub original: Option<Vec<u8>>,
}

impl StageRequest {
    pub fn id(&self) -> Result<String> {
        Ok(sha256(&serde_json::to_vec(self)?))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct StageResult {
    pub input_sha256: String,
    pub draft: Draft,
}

pub trait Processor {
    fn process(&self, request: &StageRequest) -> Result<StageResult>;
}

/// Count exactly what embed receives, including its special tokens. Never truncate.
pub trait Encoder {
    fn space(&self) -> EmbeddingSpace;
    fn count_tokens(&self, input: &str) -> Result<usize>;
    fn embed(&self, input: &str) -> Result<Vec<f32>>;
}

impl<E: Encoder + ?Sized> Encoder for &E {
    fn space(&self) -> EmbeddingSpace {
        (**self).space()
    }
    fn count_tokens(&self, input: &str) -> Result<usize> {
        (**self).count_tokens(input)
    }
    fn embed(&self, input: &str) -> Result<Vec<f32>> {
        (**self).embed(input)
    }
}

impl<P: Processor + ?Sized> Processor for Box<P> {
    fn process(&self, request: &StageRequest) -> Result<StageResult> {
        (**self).process(request)
    }
}

pub struct LocalProcessor<E> {
    pub encoder: E,
}

/// One versioned input serializer, shared by chunk budgeting and embedding.
pub fn embedding_input(space: &EmbeddingSpace, chunk: &Chunk) -> String {
    let context = &chunk.structural_context;
    if context.is_empty() {
        format!("{}{}", space.document_prefix, chunk.evidence)
    } else {
        format!("{}{context}\n\n{}", space.document_prefix, chunk.evidence)
    }
}

pub fn configured_input(config: &IngestConfig, chunk: &Chunk) -> String {
    use context::Policy;
    match config.context.as_ref().map(|c| &c.policy) {
        Some(Policy::Plain) => format!("{}{}", config.space.document_prefix, chunk.evidence),
        Some(Policy::Generated) => {
            let mut parts = vec![];
            if !chunk.structural_context.is_empty() {
                parts.push(chunk.structural_context.as_str());
            }
            if let Some(generated) = &chunk.generated_context {
                parts.push(generated.text.as_str());
            }
            parts.push(&chunk.evidence);
            format!("{}{}", config.space.document_prefix, parts.join("\n\n"))
        }
        _ => embedding_input(&config.space, chunk),
    }
}

impl<E: Encoder> Processor for LocalProcessor<E> {
    fn process(&self, request: &StageRequest) -> Result<StageResult> {
        request.config.validate()?;
        require(
            self.encoder.space() == request.config.space,
            "processor embedding-space mismatch",
        )?;
        let mut draft = request.draft.clone();
        match request.stage {
            Stage::Uploaded => prepare::parse(
                &mut draft,
                request
                    .original
                    .as_deref()
                    .ok_or_else(|| crate::Error::Invalid("missing source bytes".into()))?,
                &request.config,
            )?,
            Stage::Parsed if draft.document.media_type == MediaType::Pdf => {
                pdf::chunk(&mut draft, &request.config, &self.encoder)?
            }
            Stage::Parsed => prepare::chunk(&mut draft, &request.config, &self.encoder)?,
            Stage::Chunked => require(
                request
                    .config
                    .context
                    .as_ref()
                    .is_none_or(|c| c.policy != context::Policy::Generated),
                "generated policy requires a context processor",
            )?,
            Stage::Contextualized => {
                let mut budget = remaining_budget(&draft)?;
                for chunk in &mut draft.document.chunks {
                    let input = configured_input(&request.config, chunk);
                    require(
                        self.encoder.count_tokens(&input)? <= request.config.space.max_tokens,
                        "encoder input exceeds token limit",
                    )?;
                    let vector = self.encoder.embed(&input)?;
                    request.config.space.validate_vector(&vector)?;
                    reserve(&vector, &mut budget)?;
                    budget = budget.checked_sub(80).ok_or_else(|| {
                        crate::Error::Invalid("embedding output exceeds job size limit".into())
                    })?;
                    chunk.vectors.insert(request.config.space.id(), vector);
                }
            }
            _ => return Err(crate::Error::Invalid("stage has no processor work".into())),
        }
        Ok(StageResult {
            input_sha256: request.id()?,
            draft,
        })
    }
}

fn remaining_budget(draft: &Draft) -> Result<usize> {
    (crate::frame::MAX_PAYLOAD as usize)
        .checked_sub(serde_json::to_vec(draft)?.len() + 128 * 1024)
        .ok_or_else(|| crate::Error::Invalid("draft exceeds job size limit".into()))
}

fn reserve<T: Serialize>(value: &T, budget: &mut usize) -> Result<()> {
    *budget = budget
        .checked_sub(serde_json::to_vec(value)?.len() + 1)
        .ok_or_else(|| crate::Error::Invalid("derived output exceeds job size limit".into()))?;
    Ok(())
}

/// Explicitly synthetic plumbing fixture. Never use this as a semantic model.
#[derive(Clone, Debug)]
pub struct TestEncoder {
    pub max_tokens: usize,
    pub document_prefix: String,
}

impl Default for TestEncoder {
    fn default() -> Self {
        Self {
            max_tokens: 256,
            document_prefix: String::new(),
        }
    }
}

impl Encoder for TestEncoder {
    fn space(&self) -> EmbeddingSpace {
        EmbeddingSpace {
            model: "vectornext/synthetic-hash-NOT-semantic".into(),
            revision: "v1".into(),
            artifact_sha256: sha256(b"synthetic-sha256-16-positive-l2-v1"),
            tokenizer: "unicode-scalars-plus-two-specials-v1".into(),
            preprocessing: INPUT_VERSION.into(),
            dimensions: 16,
            max_tokens: self.max_tokens,
            query_prefix: String::new(),
            document_prefix: self.document_prefix.clone(),
            normalization: Normalization::L2,
        }
    }
    fn count_tokens(&self, input: &str) -> Result<usize> {
        Ok(input.chars().count() + 2)
    }
    fn embed(&self, input: &str) -> Result<Vec<f32>> {
        require(
            self.count_tokens(input)? <= self.max_tokens,
            "test encoder input too long",
        )?;
        use sha2::{Digest, Sha256};
        let hash = Sha256::digest(input.as_bytes());
        let mut vector: Vec<f32> = hash[..16].iter().map(|&b| f32::from(b) + 1.0).collect();
        let norm = vector.iter().map(|x| x * x).sum::<f32>().sqrt();
        for v in &mut vector {
            *v /= norm;
        }
        Ok(vector)
    }
}
