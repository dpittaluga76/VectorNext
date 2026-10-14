//! Validated PDF artifact adapter; never invokes Python or opens database files.
use super::*;
use crate::{Error, contracts::hash_valid};
use std::collections::{BTreeMap, BTreeSet};

pub const PARSER_VERSION: &str = "docling-pdf-v1";
pub const CHUNKER_VERSION: &str = "pdf-sections-rows-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct PdfConfig {
    pub profile_sha256: String,
    pub artifact_sha256: String,
    pub allow_partial: bool,
}
impl PdfConfig {
    pub fn validate(&self) -> Result<()> {
        require(
            hash_valid(&self.profile_sha256) && hash_valid(&self.artifact_sha256),
            "invalid PDF profile/artifact hash",
        )
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Page {
    pub page: u32,
    pub width: f64,
    pub height: f64,
    pub native_cells: usize,
    pub ocr_cells: usize,
    pub ocr_mean_confidence: Option<f64>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Warning {
    pub code: String,
    pub page: Option<u32>,
    pub message: String,
    pub bbox: Option<[f64; 4]>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct PdfSpan {
    pub bytes: ByteRange,
    pub page: u32,
    pub bbox: [f64; 4],
    pub extraction: PdfExtraction,
    pub confidence: Option<f64>,
}
impl PdfSpan {
    fn source(&self, revision: &str) -> SourceRef {
        SourceRef {
            revision: revision.into(),
            locator: Locator::Pdf {
                page: self.page,
                bbox: self.bbox,
                extraction: self.extraction.clone(),
                diagnostics: self
                    .confidence
                    .map(|c| BTreeMap::from([("ocr_confidence".into(), Value::from(c))]))
                    .unwrap_or_default(),
            },
        }
    }
    fn validate(&self, pages: &[Page], text: Option<&str>) -> Result<()> {
        let page = pages
            .iter()
            .find(|p| p.page == self.page)
            .ok_or_else(|| Error::Invalid("PDF source page does not exist".into()))?;
        let [x0, y0, x1, y1] = self.bbox;
        require(
            self.bbox.iter().all(|v| v.is_finite())
                && x0 >= 0.
                && y0 >= 0.
                && x1 > x0
                && y1 > y0
                && x1 <= page.width
                && y1 <= page.height,
            "PDF source outside page bounds",
        )?;
        require(
            self.confidence
                .is_none_or(|c| c.is_finite() && (0. ..=1.).contains(&c)),
            "invalid OCR confidence",
        )?;
        if let Some(text) = text {
            require(
                self.bytes.start < self.bytes.end
                    && self.bytes.end <= text.len() as u64
                    && text.is_char_boundary(self.bytes.start as usize)
                    && text.is_char_boundary(self.bytes.end as usize),
                "PDF source has invalid UTF-8 span",
            )?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Body,
    Furniture,
    TableContainer,
    TableRow,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Item {
    pub id: String,
    pub kind: BlockKind,
    pub role: Role,
    pub parent: Option<String>,
    pub text: String,
    pub sources: Vec<PdfSpan>,
    pub context: String,
    pub context_sources: Vec<PdfSpan>,
    pub section: Option<String>,
    pub table: Option<Value>,
    pub indexed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub schema: String,
    pub source_sha256: String,
    pub profile_sha256: String,
    pub status: String,
    pub pages: Vec<Page>,
    pub items: Vec<Item>,
    pub warnings: Vec<Warning>,
    pub tables: Vec<Value>,
}

impl Artifact {
    /// Parse a bounded transport artifact. Identity uses canonical Rust serialization.
    pub fn from_slice(bytes: &[u8]) -> Result<Self> {
        require(
            bytes.len() <= 16 * 1024 * 1024,
            "PDF artifact exceeds 16 MiB",
        )?;
        Ok(serde_json::from_slice(bytes)?)
    }
    pub fn id(&self) -> Result<String> {
        Ok(sha256(&serde_json::to_vec(self)?))
    }
    pub fn config(&self, space: EmbeddingSpace, allow_partial: bool) -> Result<IngestConfig> {
        let mut config = IngestConfig::new(space);
        config.parser_version = PARSER_VERSION.into();
        config.chunker_version = CHUNKER_VERSION.into();
        config.pdf = Some(PdfConfig {
            profile_sha256: self.profile_sha256.clone(),
            artifact_sha256: self.id()?,
            allow_partial,
        });
        Ok(config)
    }
    fn report(&self) -> Result<Report> {
        Ok(Report {
            schema: self.schema.clone(),
            source_sha256: self.source_sha256.clone(),
            profile_sha256: self.profile_sha256.clone(),
            artifact_sha256: self.id()?,
            status: self.status.clone(),
            pages: self.pages.clone(),
            warnings: self.warnings.clone(),
            tables: self.tables.clone(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Report {
    schema: String,
    source_sha256: String,
    profile_sha256: String,
    artifact_sha256: String,
    status: String,
    pages: Vec<Page>,
    warnings: Vec<Warning>,
    tables: Vec<Value>,
}
impl Report {
    fn validate(&self, config: &PdfConfig, original: &BlobRef) -> Result<()> {
        require(
            self.schema == "pdf-v1"
                && self.source_sha256 == original.sha256
                && self.profile_sha256 == config.profile_sha256
                && self.artifact_sha256 == config.artifact_sha256,
            "PDF source/profile/artifact identity mismatch",
        )?;
        require(
            self.status
                == if self.warnings.is_empty() {
                    "complete"
                } else {
                    "partial"
                },
            "inconsistent PDF quality status",
        )?;
        require(
            config.allow_partial || self.status == "complete",
            "partial PDF extraction rejected; inspect diagnostics or explicitly allow partial",
        )?;
        require(
            !self.pages.is_empty() && self.pages.len() <= 32,
            "invalid PDF page count",
        )?;
        let mut pages = BTreeSet::new();
        for p in &self.pages {
            require(
                p.page > 0
                    && p.page <= 32
                    && pages.insert(p.page)
                    && [p.width, p.height]
                        .iter()
                        .all(|v| v.is_finite() && *v > 0. && *v <= 1440.),
                "invalid PDF page geometry",
            )?;
            require(
                p.ocr_mean_confidence
                    .is_none_or(|c| c.is_finite() && (0. ..=1.).contains(&c)),
                "invalid PDF page confidence",
            )?;
            if self.status == "complete" {
                require(
                    p.native_cells > 0 || p.ocr_cells > 0,
                    "complete PDF contains empty page",
                )?;
            }
        }
        if self.status == "complete" {
            require(
                pages.iter().copied().eq(1..=self.pages.len() as u32),
                "complete PDF has missing pages",
            )?;
        }
        require(self.warnings.len() <= 10_000, "too many PDF diagnostics")?;
        for warning in &self.warnings {
            require(
                !warning.code.is_empty() && warning.page.is_none_or(|p| pages.contains(&p)),
                "invalid PDF diagnostic",
            )?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct PdfUnit {
    pub role: Role,
    pub indexed: bool,
    pub mappings: Vec<PdfSpan>,
    pub context_sources: Vec<PdfSpan>,
    pub table: Option<Value>,
}

/// Artifact-backed adapter. The caller can receive the artifact over any transport.
pub struct PdfProcessor<E> {
    pub local: LocalProcessor<E>,
    pub artifact: Artifact,
}
impl<E: Encoder> Processor for PdfProcessor<E> {
    fn process(&self, request: &StageRequest) -> Result<StageResult> {
        if request.stage != Stage::Uploaded {
            return self.local.process(request);
        }
        request.config.validate()?;
        require(
            request.config.space == self.local.encoder.space(),
            "processor embedding-space mismatch",
        )?;
        require(
            request.draft.document.media_type == MediaType::Pdf,
            "PDF processor requires PDF request",
        )?;
        let config = request
            .config
            .pdf
            .as_ref()
            .ok_or_else(|| Error::Invalid("missing PDF profile".into()))?;
        let original = request
            .original
            .as_ref()
            .ok_or_else(|| Error::Invalid("missing original".into()))?;
        require(
            sha256(original) == self.artifact.source_sha256
                && original.len() as u64 == request.draft.document.original.bytes,
            "PDF original bytes mismatch",
        )?;
        let report = self.artifact.report()?;
        report.validate(config, &request.draft.document.original)?;
        require(
            serde_json::to_vec(&self.artifact)?.len() <= 16 * 1024 * 1024,
            "PDF artifact exceeds 16 MiB",
        )?;
        require(
            !self.artifact.items.is_empty() && self.artifact.items.len() <= 10_000,
            "invalid PDF item count",
        )?;
        let mut draft = request.draft.clone();
        require(
            draft.units.is_empty()
                && draft.document.blocks.is_empty()
                && draft.document.chunks.is_empty(),
            "PDF parse draft is not empty",
        )?;
        for item in &self.artifact.items {
            draft.document.blocks.push(Block {
                id: item.id.clone(),
                kind: item.kind.clone(),
                parent: item.parent.clone(),
                text: item.text.clone(),
                sources: item
                    .sources
                    .iter()
                    .map(|s| s.source(&draft.document.revision))
                    .collect(),
            });
            draft.units.push(ParsedUnit {
                block_id: item.id.clone(),
                context: item.context.clone(),
                section: item.section.clone(),
                record: None,
                pointer: None,
                value: None,
                pdf: Some(PdfUnit {
                    role: item.role.clone(),
                    indexed: item.indexed,
                    mappings: item.sources.clone(),
                    context_sources: item.context_sources.clone(),
                    table: item.table.clone(),
                }),
            });
        }
        draft
            .document
            .processing
            .insert("pdf".into(), serde_json::to_value(report)?);
        validate_prepared(&draft, &request.config)?;
        remaining_budget(&draft)?;
        Ok(StageResult {
            input_sha256: request.id()?,
            draft,
        })
    }
}

pub(super) fn validate_prepared(draft: &Draft, config: &IngestConfig) -> Result<()> {
    let config = config
        .pdf
        .as_ref()
        .ok_or_else(|| Error::Invalid("missing PDF config".into()))?;
    let report: Report = serde_json::from_value(
        draft
            .document
            .processing
            .get("pdf")
            .ok_or_else(|| Error::Invalid("missing PDF report".into()))?
            .clone(),
    )?;
    report.validate(config, &draft.document.original)?;
    require(
        draft.units.len() == draft.document.blocks.len() && draft.units.len() <= 10_000,
        "invalid PDF unit/block count",
    )?;
    let blocks: BTreeMap<_, _> = draft.document.blocks.iter().map(|b| (&b.id, b)).collect();
    require(
        blocks.len() == draft.document.blocks.len(),
        "duplicate PDF block",
    )?;
    let mut seen = BTreeSet::new();
    let mut indexed = false;
    for unit in &draft.units {
        let b = blocks
            .get(&unit.block_id)
            .ok_or_else(|| Error::Invalid("missing PDF block".into()))?;
        let pdf = unit
            .pdf
            .as_ref()
            .ok_or_else(|| Error::Invalid("missing PDF unit".into()))?;
        require(
            !b.id.is_empty()
                && b.id.len() <= 1024
                && !b.text.trim().is_empty()
                && unit.record.is_none()
                && unit.pointer.is_none()
                && unit.value.is_none(),
            "invalid PDF block/unit",
        )?;
        require(
            b.parent.as_ref().is_none_or(|p| seen.contains(p))
                && unit.section.as_ref().is_none_or(|p| {
                    seen.contains(p) && blocks.get(p).is_some_and(|p| p.kind == BlockKind::Heading)
                }),
            "invalid PDF hierarchy/order",
        )?;
        require(seen.insert(b.id.clone()), "duplicate PDF unit")?;
        require(
            !pdf.mappings.is_empty(),
            "PDF block without source mappings",
        )?;
        for span in &pdf.mappings {
            span.validate(&report.pages, Some(&b.text))?;
        }
        for span in &pdf.context_sources {
            span.validate(&report.pages, None)?;
        }
        require(
            b.sources
                == pdf
                    .mappings
                    .iter()
                    .map(|s| s.source(&draft.document.revision))
                    .collect::<Vec<_>>(),
            "PDF mappings differ from block sources",
        )?;
        // Check the union in O(text + spans log spans), not text × spans.
        let mut intervals: Vec<_> = pdf.mappings.iter().map(|s| &s.bytes).collect();
        intervals.sort_by_key(|s| s.start);
        let gap_ok = |text: &str| {
            text.chars()
                .all(|c| c.is_whitespace() || (c == '|' && b.kind == BlockKind::Table))
        };
        let mut end = 0;
        for span in intervals {
            if span.start > end {
                require(
                    gap_ok(&b.text[end as usize..span.start as usize]),
                    "unmapped PDF evidence text",
                )?;
            }
            end = end.max(span.end);
        }
        require(
            gap_ok(&b.text[end as usize..]),
            "unmapped PDF evidence text",
        )?;
        require(
            unit.context.is_empty() || !pdf.context_sources.is_empty(),
            "PDF context has no source support",
        )?;
        require(
            !matches!(pdf.role, Role::Furniture | Role::TableContainer) || !pdf.indexed,
            "PDF furniture/container cannot be indexed",
        )?;
        require(
            b.kind != BlockKind::JsonSubtree,
            "PDF cannot contain JSON blocks",
        )?;
        indexed |= pdf.indexed;
    }
    require(indexed, "PDF has no indexable evidence")?;
    // Bind the accepted/replayed parsed draft to the exact artifact in the job's
    // identity, including geometry, context support, table cells and diagnostics.
    let artifact = Artifact {
        schema: report.schema,
        source_sha256: report.source_sha256,
        profile_sha256: report.profile_sha256,
        status: report.status,
        pages: report.pages,
        warnings: report.warnings,
        tables: report.tables,
        items: draft
            .units
            .iter()
            .map(|u| {
                let b = blocks[&u.block_id];
                let p = u.pdf.as_ref().unwrap();
                Item {
                    id: b.id.clone(),
                    kind: b.kind.clone(),
                    role: p.role.clone(),
                    parent: b.parent.clone(),
                    text: b.text.clone(),
                    sources: p.mappings.clone(),
                    context: u.context.clone(),
                    context_sources: p.context_sources.clone(),
                    section: u.section.clone(),
                    table: p.table.clone(),
                    indexed: p.indexed,
                }
            })
            .collect(),
    };
    require(
        artifact.id()? == config.artifact_sha256,
        "PDF parsed data differs from bound artifact",
    )
}

pub(super) fn chunk<E: Encoder>(
    draft: &mut Draft,
    config: &IngestConfig,
    encoder: &E,
) -> Result<()> {
    validate_prepared(draft, config)?;
    let mut budget = remaining_budget(draft)?;
    let mut groups: Vec<Option<String>> = vec![];
    for unit in &draft.units {
        let pdf = unit.pdf.as_ref().unwrap();
        if !pdf.indexed {
            continue;
        }
        let block = draft
            .document
            .blocks
            .iter()
            .find(|b| b.id == unit.block_id)
            .unwrap();
        let representation = if pdf
            .mappings
            .iter()
            .any(|s| s.extraction == PdfExtraction::Ocr)
        {
            Representation::OcrText
        } else {
            Representation::PdfText
        };
        let mut base = prepare::blank_chunk(block, &unit.context, representation);
        if !unit.context.is_empty() {
            base.attributes.insert(
                "pdf_context".into(),
                Attribute {
                    value: Value::String(unit.context.clone()),
                    sources: pdf
                        .context_sources
                        .iter()
                        .map(|s| s.source(&draft.document.revision))
                        .collect(),
                    derivation: Derivation::Deterministic {
                        version: CHUNKER_VERSION.into(),
                    },
                },
            );
        }
        if let Some(table) = &pdf.table {
            base.attributes.insert(
                "pdf_table_row".into(),
                Attribute {
                    value: table.clone(),
                    sources: block.sources.clone(),
                    derivation: Derivation::Deterministic {
                        version: PARSER_VERSION.into(),
                    },
                },
            );
        }
        let mut pieces = prepare::split(base, block, config, encoder, &mut budget)?;
        for piece in &mut pieces {
            let range = &piece.spans[0].bytes;
            piece.sources = pdf
                .mappings
                .iter()
                .filter(|s| s.bytes.start < range.end && range.start < s.bytes.end)
                .map(|s| s.source(&draft.document.revision))
                .collect();
            require(!piece.sources.is_empty(), "PDF split has no source")?;
        }
        let group = if block.kind == BlockKind::Table {
            block.parent.clone()
        } else {
            unit.section.clone()
        };
        if pieces.len() == 1
            && matches!(block.kind, BlockKind::Paragraph | BlockKind::List)
            && groups.last() == Some(&group)
        {
            if let Some(last) = draft.document.chunks.last_mut() {
                let previous = draft
                    .document
                    .blocks
                    .iter()
                    .find(|b| b.id == last.spans[0].block_id)
                    .unwrap();
                if matches!(previous.kind, BlockKind::Paragraph | BlockKind::List)
                    && last.structural_context == pieces[0].structural_context
                    && last.representation == pieces[0].representation
                {
                    let mut combined = last.clone();
                    combined.evidence.push_str("\n\n");
                    combined.evidence.push_str(&pieces[0].evidence);
                    if encoder.count_tokens(&configured_input(config, &combined))?
                        <= config.target_tokens
                    {
                        combined.spans.extend(pieces[0].spans.clone());
                        combined.sources.extend(pieces[0].sources.clone());
                        *last = combined;
                        continue;
                    }
                }
            }
        }
        groups.extend(std::iter::repeat_n(group, pieces.len()));
        draft.document.chunks.extend(pieces);
    }
    let headings: BTreeMap<_, _> = draft
        .document
        .chunks
        .iter()
        .enumerate()
        .filter_map(|(i, c)| {
            draft
                .document
                .blocks
                .iter()
                .find(|b| b.id == c.spans[0].block_id && b.kind == BlockKind::Heading)
                .map(|b| (b.id.clone(), format!("c{i}")))
        })
        .collect();
    let length = draft.document.chunks.len();
    for (i, c) in draft.document.chunks.iter_mut().enumerate() {
        c.id = format!("c{i}");
        c.parent = groups[i].as_ref().and_then(|s| headings.get(s).cloned());
        c.previous = (i > 0 && groups[i] == groups[i - 1]).then(|| format!("c{}", i - 1));
        c.next = (i + 1 < length && groups[i] == groups[i + 1]).then(|| format!("c{}", i + 1));
    }
    require(length > 0, "PDF produced no chunks")
}
