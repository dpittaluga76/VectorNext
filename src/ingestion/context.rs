//! Versioned context selection and strict stage validation, independent of inference.
use super::*;
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Policy {
    Plain,
    Structural,
    Generated,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct GenerationConfig {
    pub model: String,
    pub revision: String,
    pub artifact_sha256: String,
    pub runtime: String,
    pub prompt: String,
    pub prompt_version: String,
    pub temperature: u32,
    pub seed: u64,
    pub context_window: usize,
    pub output_tokens: usize,
    pub annotation_tokens: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct ContextConfig {
    pub policy: Policy,
    pub version: String,
    pub generator: Option<GenerationConfig>,
}
impl ContextConfig {
    pub fn new(policy: Policy, generator: Option<GenerationConfig>) -> Self {
        Self {
            policy,
            version: "prose-scope8000-reserve64-v1".into(),
            generator,
        }
    }
    pub fn reserve_tokens(&self) -> usize {
        if self.policy == Policy::Generated {
            64
        } else {
            0
        }
    }
    pub fn validate(&self, space: &EmbeddingSpace) -> Result<()> {
        require(
            self.version == "prose-scope8000-reserve64-v1",
            "unknown context policy version",
        )?;
        require(
            (self.policy == Policy::Generated) == self.generator.is_some(),
            "generator/policy mismatch",
        )?;
        if let Some(g) = &self.generator {
            require(
                !g.model.is_empty()
                    && !g.revision.is_empty()
                    && hash_valid(&g.artifact_sha256)
                    && !g.runtime.is_empty()
                    && !g.prompt.is_empty()
                    && g.prompt_version == sha256(g.prompt.as_bytes())
                    && g.temperature == 0
                    && g.context_window == 4096
                    && g.output_tokens == 256
                    && g.annotation_tokens == 60
                    && space.max_tokens > self.reserve_tokens(),
                "invalid generation configuration",
            )?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct ScopePart {
    pub span: BlockSpan,
    pub text: String,
    pub sources: Vec<SourceRef>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct ContextInput {
    pub config: ContextConfig,
    pub space: EmbeddingSpace,
    pub evidence: String,
    pub structural_context: String,
    pub scope: Vec<ScopePart>,
}
impl ContextInput {
    pub fn id(&self) -> Result<String> {
        Ok(sha256(&serde_json::to_vec(self)?))
    }
    pub fn sources(&self) -> Vec<SourceRef> {
        let mut sources = vec![];
        for source in self.scope.iter().flat_map(|p| &p.sources) {
            if !sources.contains(source) {
                sources.push(source.clone());
            }
        }
        sources
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct ContextRecord {
    pub input_sha256: String,
    pub scope: Vec<ScopePart>,
    pub outcome: String,
}

/// Complete parsed document when bounded; otherwise exact evidence plus nearest
/// complete blocks. No source text is clipped to manufacture a fitting prompt.
pub fn input_for(
    draft: &Draft,
    config: &IngestConfig,
    chunk: &Chunk,
) -> Result<Option<ContextInput>> {
    let Some(context) = &config.context else {
        return Ok(None);
    };
    if context.policy != Policy::Generated || draft.document.media_type == MediaType::Json {
        return Ok(None);
    }
    let blocks = &draft.document.blocks;
    let evidence_blocks: Vec<_> = chunk
        .spans
        .iter()
        .map(|span| {
            blocks
                .iter()
                .position(|b| b.id == span.block_id)
                .ok_or_else(|| crate::Error::Invalid("unknown context block".into()))
        })
        .collect::<Result<_>>()?;
    if evidence_blocks
        .iter()
        .any(|&i| !matches!(blocks[i].kind, BlockKind::Paragraph | BlockKind::List))
    {
        return Ok(None);
    }
    let whole = |b: &Block| ScopePart {
        span: BlockSpan {
            block_id: b.id.clone(),
            bytes: ByteRange {
                start: 0,
                end: b.text.len() as u64,
            },
        },
        text: b.text.clone(),
        sources: b.sources.clone(),
    };
    let scope = if blocks.iter().map(|b| b.text.len()).sum::<usize>() <= 8000 {
        blocks.iter().map(whole).collect()
    } else {
        let mut selected = vec![];
        let mut size = 0;
        for span in &chunk.spans {
            let b = blocks.iter().find(|b| b.id == span.block_id).unwrap();
            let text = b
                .text
                .get(span.bytes.start as usize..span.bytes.end as usize)
                .ok_or_else(|| crate::Error::Invalid("invalid context span".into()))?
                .to_string();
            size += text.len();
            selected.push(ScopePart {
                span: span.clone(),
                text,
                sources: b.sources.clone(),
            });
        }
        // Structural text is also supplied to the model. Its ancestors and PDF
        // context sources are mandatory, even when distant from the excerpt.
        let mut required = std::collections::BTreeSet::new();
        for &i in &evidence_blocks {
            let mut parent = blocks[i].parent.as_ref();
            let mut visited = std::collections::BTreeSet::new();
            while let Some(id) = parent {
                require(visited.insert(id), "cyclic context ancestry")?;
                let index = blocks
                    .iter()
                    .position(|b| &b.id == id)
                    .ok_or_else(|| crate::Error::Invalid("unknown context ancestor".into()))?;
                required.insert(index);
                parent = blocks[index].parent.as_ref();
            }
        }
        if let Some(attribute) = chunk.attributes.get("pdf_context") {
            for source in &attribute.sources {
                let index = blocks
                    .iter()
                    .position(|b| b.sources.contains(source))
                    .ok_or_else(|| {
                        crate::Error::Invalid("PDF context source has no scope block".into())
                    })?;
                required.insert(index);
            }
        }
        for i in required {
            if !evidence_blocks.contains(&i) {
                size += blocks[i].text.len();
                selected.push(whole(&blocks[i]));
            }
        }
        require(
            size <= 8000,
            "required evidence/structure exceeds context scope budget",
        )?;
        let mut neighbors: Vec<_> = (0..blocks.len())
            .filter(|i| !selected.iter().any(|p| p.span.block_id == blocks[*i].id))
            .collect();
        neighbors.sort_by_key(|i| (evidence_blocks.iter().map(|j| i.abs_diff(*j)).min(), *i));
        for i in neighbors {
            if size + blocks[i].text.len() <= 8000 {
                size += blocks[i].text.len();
                selected.push(whole(&blocks[i]));
            }
        }
        selected.sort_by_key(|p| blocks.iter().position(|b| b.id == p.span.block_id));
        selected
    };
    Ok(Some(ContextInput {
        config: context.clone(),
        space: config.space.clone(),
        evidence: chunk.evidence.clone(),
        structural_context: chunk.structural_context.clone(),
        scope,
    }))
}

pub trait Generator {
    fn generate(&self, input: &ContextInput) -> Result<Option<String>>;
}
impl<G: Generator + ?Sized> Generator for &G {
    fn generate(&self, input: &ContextInput) -> Result<Option<String>> {
        (**self).generate(input)
    }
}

pub struct ContextProcessor<P, G> {
    pub base: P,
    pub generator: G,
}
impl<P: Processor, G: Generator> Processor for ContextProcessor<P, G> {
    fn process(&self, request: &StageRequest) -> Result<StageResult> {
        if request.stage != Stage::Chunked
            || request
                .config
                .context
                .as_ref()
                .is_none_or(|c| c.policy != Policy::Generated)
        {
            return self.base.process(request);
        }
        request.config.validate()?;
        let mut draft = request.draft.clone();
        let mut report = BTreeMap::new();
        let mut budget = remaining_budget(&draft)?;
        for (i, chunk) in request.draft.document.chunks.iter().enumerate() {
            if let Some(input) = input_for(&request.draft, &request.config, chunk)? {
                let text = self.generator.generate(&input)?;
                if let Some(text) = &text {
                    require(
                        !text.trim().is_empty() && text.len() <= 4096,
                        "invalid generated context text",
                    )?;
                    let g = input.config.generator.as_ref().unwrap();
                    let annotation = GeneratedContext {
                        text: text.clone(),
                        model: g.artifact_sha256.clone(),
                        prompt_version: g.prompt_version.clone(),
                        source_scope: input.sources(),
                    };
                    reserve(&annotation, &mut budget)?;
                    draft.document.chunks[i].generated_context = Some(annotation);
                }
                let record = ContextRecord {
                    input_sha256: input.id()?,
                    scope: input.scope,
                    outcome: if text.is_some() {
                        "generated"
                    } else {
                        "no_context"
                    }
                    .into(),
                };
                reserve(&record, &mut budget)?;
                report.insert(chunk.id.clone(), record);
            }
        }
        draft
            .document
            .processing
            .insert("context".into(), serde_json::to_value(report)?);
        validate_report(&draft, &request.config, true)?;
        Ok(StageResult {
            input_sha256: request.id()?,
            draft,
        })
    }
}

pub(super) fn validate_report(
    draft: &Draft,
    config: &IngestConfig,
    contextualized: bool,
) -> Result<()> {
    if !contextualized
        || config
            .context
            .as_ref()
            .is_none_or(|c| c.policy != Policy::Generated)
    {
        return require(
            !draft.document.processing.contains_key("context")
                && draft
                    .document
                    .chunks
                    .iter()
                    .all(|c| c.generated_context.is_none()),
            "unexpected generated context/report",
        );
    }
    let report: BTreeMap<String, ContextRecord> = serde_json::from_value(
        draft
            .document
            .processing
            .get("context")
            .ok_or_else(|| crate::Error::Invalid("missing context report".into()))?
            .clone(),
    )?;
    let mut expected = 0;
    for chunk in &draft.document.chunks {
        if let Some(input) = input_for(draft, config, chunk)? {
            expected += 1;
            let record = report
                .get(&chunk.id)
                .ok_or_else(|| crate::Error::Invalid("missing chunk context result".into()))?;
            require(
                record.input_sha256 == input.id()? && record.scope == input.scope,
                "context input/scope changed",
            )?;
            if let Some(generated) = &chunk.generated_context {
                let g = input.config.generator.as_ref().unwrap();
                require(
                    record.outcome == "generated"
                        && !generated.text.trim().is_empty()
                        && generated.text.len() <= 4096
                        && generated.model == g.artifact_sha256
                        && generated.prompt_version == g.prompt_version
                        && generated.source_scope == input.sources(),
                    "generated context metadata mismatch",
                )?;
            } else {
                require(record.outcome == "no_context", "context outcome mismatch")?;
            }
        } else {
            require(
                chunk.generated_context.is_none(),
                "generation on ineligible chunk",
            )?;
        }
    }
    require(
        report.len() == expected,
        "unexpected context report entries",
    )
}
