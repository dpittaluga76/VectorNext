//! Persisted public records. IDs are scoped to their document revision unless stated otherwise.
use crate::{Result, require, sha256};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct BlobRef {
    pub sha256: String,
    pub bytes: u64,
}

pub(crate) fn hash_valid(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Normalization {
    None,
    L2,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct EmbeddingSpace {
    pub model: String,
    pub revision: String,
    pub artifact_sha256: String,
    /// Hash/version of tokenizer artifacts and configuration, not just its model name.
    pub tokenizer: String,
    pub preprocessing: String,
    pub dimensions: usize,
    pub max_tokens: usize,
    pub query_prefix: String,
    pub document_prefix: String,
    pub normalization: Normalization,
}

impl EmbeddingSpace {
    pub fn id(&self) -> String {
        sha256(
            &serde_json::to_vec(self).expect("embedding identity contains only JSON-safe fields"),
        )
    }
    pub fn validate(&self) -> Result<()> {
        require(
            !self.model.is_empty()
                && !self.revision.is_empty()
                && !self.tokenizer.is_empty()
                && !self.preprocessing.is_empty(),
            "embedding identity must be fully versioned",
        )?;
        require(
            hash_valid(&self.artifact_sha256),
            "invalid model artifact hash",
        )?;
        require(
            self.dimensions > 0 && self.dimensions <= 65_536 && self.max_tokens > 0,
            "invalid embedding dimensions/token limit",
        )
    }
    pub fn validate_vector(&self, vector: &[f32]) -> Result<()> {
        require(
            vector.len() == self.dimensions,
            "embedding dimension mismatch",
        )?;
        require(vector.iter().all(|x| x.is_finite()), "nonfinite vector")?;
        let norm = vector
            .iter()
            .map(|&x| f64::from(x).powi(2))
            .sum::<f64>()
            .sqrt();
        require(norm > 0.0, "zero vector")?;
        require(
            self.normalization != Normalization::L2 || (norm - 1.0).abs() <= 0.001,
            "expected an L2-normalized vector",
        )
    }
}

/// Half-open byte interval. Chunk/block intervals always refer to UTF-8 strings.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ByteRange {
    pub start: u64,
    pub end: u64,
}

impl ByteRange {
    fn within(&self, limit: u64) -> bool {
        self.start < self.end && self.end <= limit
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextMapping {
    pub normalized: ByteRange,
    pub original: ByteRange,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Locator {
    Text {
        encoding: String,
        bytes: ByteRange,
        line_start: u64,
        line_end: u64,
        /// Coordinates in the normalized document text, with original-byte spans.
        mappings: Vec<TextMapping>,
    },
    Pdf {
        /// One-based page and top-left-origin page-point rectangle [x0,y0,x1,y1].
        page: u32,
        bbox: [f64; 4],
        extraction: PdfExtraction,
        diagnostics: BTreeMap<String, Value>,
    },
    Json {
        pointer: String,
        record_id: Option<Value>,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum PdfExtraction {
    Native,
    Ocr,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SourceRef {
    pub revision: String,
    pub locator: Locator,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum MediaType {
    Txt,
    Pdf,
    Json,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum BlockKind {
    Paragraph,
    Heading,
    List,
    Table,
    JsonSubtree,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Block {
    pub id: String,
    pub kind: BlockKind,
    pub parent: Option<String>,
    pub text: String,
    pub sources: Vec<SourceRef>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct BlockSpan {
    pub block_id: String,
    pub bytes: ByteRange,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Derivation {
    Source,
    Deterministic {
        version: String,
    },
    Generated {
        model: String,
        prompt_version: String,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Attribute {
    /// Exact JSON value: null is stored; missing is absence of the attribute key.
    pub value: Value,
    pub sources: Vec<SourceRef>,
    pub derivation: Derivation,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GeneratedContext {
    pub text: String,
    pub model: String,
    pub prompt_version: String,
    pub source_scope: Vec<SourceRef>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Representation {
    NormalizedText,
    PdfText,
    OcrText,
    JsonSerialization,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Chunk {
    pub id: String,
    pub spans: Vec<BlockSpan>,
    pub evidence: String,
    pub representation: Representation,
    pub sources: Vec<SourceRef>,
    pub structural_context: String,
    pub generated_context: Option<GeneratedContext>,
    pub attributes: BTreeMap<String, Attribute>,
    pub parent: Option<String>,
    pub previous: Option<String>,
    pub next: Option<String>,
    /// Space ID -> supplied float32 vector. No inference occurs in the core.
    pub vectors: BTreeMap<String, Vec<f32>>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DocumentRevision {
    pub document_id: String,
    pub revision: String,
    pub original: BlobRef,
    pub media_type: MediaType,
    pub processing: BTreeMap<String, Value>,
    pub required_spaces: BTreeSet<String>,
    pub blocks: Vec<Block>,
    pub chunks: Vec<Chunk>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Mutation {
    Replace {
        expected_revision: Option<String>,
        document: Box<DocumentRevision>,
    },
    Delete {
        document_id: String,
        expected_revision: String,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Batch {
    pub operation_id: String,
    pub spaces: Vec<EmbeddingSpace>,
    pub mutations: Vec<Mutation>,
}

fn pointer_valid(pointer: &str) -> bool {
    if !pointer.is_empty() && !pointer.starts_with('/') {
        return false;
    }
    let mut chars = pointer.chars();
    while let Some(c) = chars.next() {
        if c == '~' && !matches!(chars.next(), Some('0' | '1')) {
            return false;
        }
    }
    true
}

impl DocumentRevision {
    fn sources_valid(&self, sources: &[SourceRef]) -> Result<()> {
        require(!sources.is_empty(), "evidence requires source provenance")?;
        for source in sources {
            require(
                source.revision == self.revision,
                "source points to a different revision",
            )?;
            match &source.locator {
                Locator::Text {
                    encoding,
                    bytes,
                    line_start,
                    line_end,
                    mappings,
                } => {
                    require(
                        self.media_type == MediaType::Txt
                            && !encoding.is_empty()
                            && bytes.within(self.original.bytes)
                            && *line_start > 0
                            && line_end >= line_start,
                        "invalid TXT locator",
                    )?;
                    require(
                        !mappings.is_empty(),
                        "TXT locator needs normalization mappings",
                    )?;
                    let mut last = 0;
                    for mapping in mappings {
                        require(
                            mapping.normalized.start >= last
                                && mapping.normalized.start < mapping.normalized.end
                                && mapping.original.within(self.original.bytes)
                                && mapping.original.start >= bytes.start
                                && mapping.original.end <= bytes.end,
                            "invalid TXT mapping",
                        )?;
                        last = mapping.normalized.end;
                    }
                }
                Locator::Pdf { page, bbox, .. } => require(
                    self.media_type == MediaType::Pdf
                        && *page > 0
                        && bbox.iter().all(|v| v.is_finite() && *v >= 0.0)
                        && bbox[0] < bbox[2]
                        && bbox[1] < bbox[3],
                    "invalid PDF locator",
                )?,
                Locator::Json { pointer, record_id } => require(
                    self.media_type == MediaType::Json
                        && pointer_valid(pointer)
                        && record_id
                            .as_ref()
                            .is_none_or(|v| v.is_string() || v.is_number()),
                    "invalid JSON locator/record identity",
                )?,
            }
        }
        Ok(())
    }

    pub fn validate(&self, spaces: &BTreeMap<String, EmbeddingSpace>) -> Result<()> {
        require(
            !self.document_id.is_empty() && !self.revision.is_empty(),
            "empty document/revision ID",
        )?;
        require(hash_valid(&self.original.sha256), "invalid original hash")?;
        require(
            !self.processing.is_empty(),
            "missing processing configuration",
        )?;
        require(
            !self.blocks.is_empty() && !self.chunks.is_empty() && !self.required_spaces.is_empty(),
            "published revision requires blocks, chunks, and spaces",
        )?;
        require(
            self.required_spaces
                .iter()
                .all(|id| spaces.contains_key(id)),
            "unknown embedding space",
        )?;
        let blocks: BTreeMap<_, _> = self.blocks.iter().map(|b| (b.id.as_str(), b)).collect();
        let chunks: BTreeMap<_, _> = self.chunks.iter().map(|c| (c.id.as_str(), c)).collect();
        require(
            blocks.len() == self.blocks.len() && chunks.len() == self.chunks.len(),
            "duplicate block/chunk ID",
        )?;
        for block in &self.blocks {
            require(
                !block.id.is_empty() && !block.text.is_empty(),
                "empty block",
            )?;
            self.sources_valid(&block.sources)?;
            let mut seen = BTreeSet::from([block.id.as_str()]);
            let mut parent = block.parent.as_deref();
            while let Some(id) = parent {
                require(seen.insert(id), "cyclic block hierarchy")?;
                let ancestor = blocks
                    .get(id)
                    .ok_or_else(|| crate::Error::Invalid("unknown parent block".into()))?;
                parent = ancestor.parent.as_deref();
            }
        }
        for chunk in &self.chunks {
            require(
                !chunk.id.is_empty() && !chunk.evidence.is_empty() && !chunk.spans.is_empty(),
                "empty chunk",
            )?;
            self.sources_valid(&chunk.sources)?;
            for span in &chunk.spans {
                let block = blocks
                    .get(span.block_id.as_str())
                    .ok_or_else(|| crate::Error::Invalid("unknown span block".into()))?;
                require(
                    span.bytes.within(block.text.len() as u64)
                        && block.text.is_char_boundary(span.bytes.start as usize)
                        && block.text.is_char_boundary(span.bytes.end as usize),
                    "invalid block span",
                )?;
            }
            for id in [&chunk.parent, &chunk.previous, &chunk.next]
                .into_iter()
                .flatten()
            {
                require(
                    id != &chunk.id && chunks.contains_key(id.as_str()),
                    "invalid chunk link",
                )?;
            }
            let mut seen = BTreeSet::from([chunk.id.as_str()]);
            let mut parent = chunk.parent.as_deref();
            while let Some(id) = parent {
                require(seen.insert(id), "cyclic chunk hierarchy")?;
                parent = chunks
                    .get(id)
                    .ok_or_else(|| crate::Error::Invalid("unknown parent chunk".into()))?
                    .parent
                    .as_deref();
            }
            if let Some(context) = &chunk.generated_context {
                require(
                    !context.model.is_empty() && !context.prompt_version.is_empty(),
                    "unversioned generated context",
                )?;
                self.sources_valid(&context.source_scope)?;
            }
            for attribute in chunk.attributes.values() {
                self.sources_valid(&attribute.sources)?;
                match &attribute.derivation {
                    Derivation::Source => (),
                    Derivation::Deterministic { version } => {
                        require(!version.is_empty(), "unversioned derivation")?
                    }
                    Derivation::Generated {
                        model,
                        prompt_version,
                    } => require(
                        !model.is_empty() && !prompt_version.is_empty(),
                        "unversioned derivation",
                    )?,
                }
            }
            require(
                chunk.vectors.keys().cloned().collect::<BTreeSet<_>>() == self.required_spaces,
                "incomplete or unexpected vector spaces",
            )?;
            for (id, vector) in &chunk.vectors {
                spaces[id].validate_vector(vector)?;
            }
        }
        Ok(())
    }
}
