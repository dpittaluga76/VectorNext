//! Snapshot-scoped retrieval and mechanically checked extraction. See docs/answers.md.
use crate::{
    Error, Result,
    contracts::*,
    ingestion::{Encoder, worker::ModelWorker},
    require,
    search::*,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;
mod coverage;
mod facets;
mod final_selection;
mod numeric;

pub const INPUT_TOKENS: usize = 3328;
pub const OUTPUT_TOKENS: usize = 768;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FieldKind {
    String,
    Integer,
    Number,
    Boolean,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FieldSpec {
    pub kind: FieldKind,
    #[serde(default)]
    pub nullable: bool,
    #[serde(default)]
    pub description: String,
    /// Relative to the complete JSON record, not the document root.
    pub pointer: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    User,
    Assistant,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Turn {
    pub role: Role,
    pub text: String,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    #[default]
    Passage,
    StructuredLookup,
    CorpusAggregate,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AskRequest {
    pub question: String,
    #[serde(default)]
    pub history: Vec<Turn>,
    pub fields: BTreeMap<String, FieldSpec>,
    #[serde(default)]
    pub filter: Filter,
    #[serde(default)]
    pub scope: Scope,
    pub template: Option<String>,
    #[serde(default)]
    pub prose: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Evidence {
    pub id: String,
    pub key: ChunkKey,
    pub text: String,
    pub sources: Vec<SourceRef>,
    pub spans: Vec<BlockSpan>,
    pub labels: Vec<String>,
    /// This value never makes a round trip through Python before validation.
    pub record: Option<Value>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AnswerInput {
    pub question: String,
    pub history: Vec<Turn>,
    pub fields: BTreeMap<String, FieldSpec>,
    pub evidence: Vec<Evidence>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub constrain_pointers: bool,
}
fn is_false(value: &bool) -> bool {
    !value
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Supported,
    Ambiguous,
    InsufficientEvidence,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FieldAnswer {
    pub value: Value,
    pub evidence_id: String,
    pub quote: String,
    pub pointer: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Answer {
    pub status: Status,
    pub fields: BTreeMap<String, FieldAnswer>,
}
impl Answer {
    fn empty(status: Status) -> Self {
        Self {
            status,
            fields: BTreeMap::new(),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Extraction {
    pub answer: Answer,
    pub audit: Value,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Rerank {
    pub scores: Vec<f64>,
    pub pair_tokens: Vec<usize>,
    pub identity: Value,
}
pub trait AnswerModels: Encoder {
    fn rerank(&self, query: &str, passages: &[String]) -> Result<Rerank>;
    fn answer_tokens(&self, input: &AnswerInput) -> Result<usize>;
    fn extract(&self, input: &AnswerInput) -> Result<Extraction>;
    fn rewrite(&self, question: &str, answer: &Answer) -> Result<Value>;
}
impl AnswerModels for ModelWorker {
    fn rerank(&self, query: &str, passages: &[String]) -> Result<Rerank> {
        Ok(serde_json::from_value(self.call(
            json!({"op":"rerank", "input":{"query":query,"passages":passages}}),
        )?)?)
    }
    fn answer_tokens(&self, input: &AnswerInput) -> Result<usize> {
        Ok(serde_json::from_value(
            self.call(json!({"op":"answer_tokens","input":input}))?,
        )?)
    }
    fn extract(&self, input: &AnswerInput) -> Result<Extraction> {
        Ok(serde_json::from_value(
            self.call(json!({"op":"answer","input":input}))?,
        )?)
    }
    fn rewrite(&self, question: &str, answer: &Answer) -> Result<Value> {
        let literals: BTreeMap<_, _> = answer
            .fields
            .iter()
            .map(|(name, proof)| {
                (
                    name,
                    proof
                        .value
                        .as_str()
                        .map(String::from)
                        .unwrap_or_else(|| proof.value.to_string()),
                )
            })
            .collect();
        self.call(json!({"op":"rewrite","input":{"question":question,"field_literals":literals}}))
    }
}
#[derive(Clone, Debug, Serialize)]
pub struct Ranked {
    pub key: ChunkKey,
    pub score: f64,
    pub pair_tokens: usize,
}
#[derive(Clone, Debug, Serialize)]
pub struct Skipped {
    pub key: ChunkKey,
    pub reason: String,
}
#[derive(Clone, Debug, Serialize)]
pub struct AnswerReport {
    pub version: String,
    pub generation: u64,
    pub embedding_space_id: String,
    pub request: AskRequest,
    pub search_text: String,
    pub retrieval: Option<SearchResponse>,
    pub reranker: Option<Value>,
    pub ranked: Vec<Ranked>,
    pub evidence: Vec<Evidence>,
    pub skipped: Vec<Skipped>,
    pub prompt_tokens: Option<usize>,
    pub input_limit: usize,
    pub output_limit: usize,
    pub answer: Answer,
    pub formatted: Option<String>,
    pub presentation_draft: Option<Value>,
    pub audit: Value,
    pub validation: Value,
    pub timings_ms: BTreeMap<String, f64>,
    pub options: AnswerOptions,
    #[serde(skip_serializing_if = "Value::is_null")]
    pub selection: Value,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceStrategy {
    #[default]
    Ranked,
    CoverageV1,
    FacetCoverageV1,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct AnswerOptions {
    pub candidates: usize,
    pub rerank_limit: usize,
    pub primary_limit: usize,
    pub rerank: bool,
    pub evidence_strategy: EvidenceStrategy,
}
impl Default for AnswerOptions {
    fn default() -> Self {
        Self {
            candidates: 30,
            rerank_limit: 20,
            primary_limit: 5,
            rerank: true,
            evidence_strategy: EvidenceStrategy::Ranked,
        }
    }
}
impl AnswerOptions {
    pub(crate) fn validate(&self) -> Result<()> {
        require(
            self.evidence_strategy != EvidenceStrategy::FacetCoverageV1
                || (self.rerank && self.rerank_limit <= 20 && self.primary_limit <= 5),
            "facet_coverage_v1 requires reranking, at most 20 candidates and five primary passages",
        )?;
        require(
            self.evidence_strategy != EvidenceStrategy::CoverageV1
                || (self.rerank && self.rerank_limit <= 20),
            "coverage_v1 requires reranking and at most 20 candidates",
        )?;
        require(
            (1..=100).contains(&self.candidates)
                && (1..=100).contains(&self.rerank_limit)
                && self.rerank_limit <= 2 * self.candidates
                && (1..=20).contains(&self.primary_limit)
                && self.primary_limit <= self.rerank_limit,
            "invalid answer retrieval budgets",
        )
    }
}
fn elapsed(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1000.0
}

pub(crate) fn validate_request(r: &AskRequest) -> Result<()> {
    require(
        !r.question.trim().is_empty() && r.question.len() <= 8192,
        "invalid question length",
    )?;
    require(
        r.history.len() <= 8 && r.history.iter().all(|t| t.text.len() <= 4096),
        "conversation exceeds bounds",
    )?;
    require(
        !r.fields.is_empty() && r.fields.len() <= 12,
        "request needs 1..12 fields",
    )?;
    for (name, spec) in &r.fields {
        require(
            !name.is_empty()
                && name.len() <= 64
                && name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_'),
            "invalid field name",
        )?;
        require(spec.description.len() <= 256, "field description too long")?;
        if let Some(p) = &spec.pointer {
            crate::ingestion::pointer_parts(p)?;
        }
    }
    r.filter.validate()?;
    require(
        r.template.as_ref().is_none_or(|t| t.len() <= 4096),
        "template too long",
    )?;
    require(
        r.scope != Scope::CorpusAggregate,
        "corpus aggregation is not implemented; top-k passages cannot establish totals",
    )?;
    let q = r.question.to_lowercase();
    require(
        ![
            "in total",
            "total number",
            "sum of",
            "average",
            "across all",
            "how many matches",
            "how many records",
            "how many documents",
        ]
        .iter()
        .any(|s| q.contains(s)),
        "aggregate question requires an unsupported corpus aggregation operation",
    )?;
    Ok(())
}

pub fn ask(
    index: &SearchIndex,
    models: &dyn AnswerModels,
    request: AskRequest,
) -> Result<AnswerReport> {
    ask_with_options(index, models, request, AnswerOptions::default())
}
pub fn ask_with_options(
    index: &SearchIndex,
    models: &dyn AnswerModels,
    request: AskRequest,
    options: AnswerOptions,
) -> Result<AnswerReport> {
    let total = Instant::now();
    validate_request_options(&request, &options)?;
    let facet_queries = if options.evidence_strategy == EvidenceStrategy::FacetCoverageV1 {
        require(
            request.scope == Scope::Passage,
            "facet_coverage_v1 requires passage scope",
        )?;
        facets::queries(&request)?
    } else {
        vec![]
    };
    let mut query = request.question.clone();
    if options.evidence_strategy != EvidenceStrategy::Ranked {
        if let Some(turn) = request
            .history
            .iter()
            .rev()
            .find(|t| matches!(t.role, Role::User))
        {
            query.push_str("\nPrevious user question for reference resolution (not evidence):\n");
            query.push_str(&turn.text);
        }
    } else if !request.history.is_empty() {
        query.push_str("\nConversation for reference resolution (not evidence):\n");
        query.push_str(&serde_json::to_string(&request.history)?);
    }
    let mut report = AnswerReport {
        version: "answers-v1".into(),
        generation: index.generation(),
        embedding_space_id: index.space_id().into(),
        request: request.clone(),
        search_text: query.clone(),
        retrieval: None,
        reranker: None,
        ranked: vec![],
        evidence: vec![],
        skipped: vec![],
        prompt_tokens: None,
        input_limit: INPUT_TOKENS,
        output_limit: OUTPUT_TOKENS,
        answer: Answer::empty(Status::InsufficientEvidence),
        formatted: None,
        presentation_draft: None,
        audit: json!({"operation":"no_evidence"}),
        validation: Value::Null,
        timings_ms: BTreeMap::from([("resolution_validation".into(), elapsed(total))]),
        options: options.clone(),
        selection: Value::Null,
    };
    let stage = Instant::now();
    if request.scope == Scope::StructuredLookup {
        structured_lookup(index, &request, &mut report)?;
        report
            .timings_ms
            .insert("structured_lookup".into(), elapsed(stage));
    } else {
        let space = models.space();
        require(
            space.id() == index.space_id(),
            "answer model/index embedding spaces differ",
        )?;
        let encoder_input = format!("{}{}", space.query_prefix, query);
        require(
            models.count_tokens(&encoder_input)? <= space.max_tokens,
            "question/history exceeds encoder budget; shorten explicitly",
        )?;
        let mut search = SearchRequest::hybrid(
            &query,
            QueryVector {
                space_id: space.id(),
                values: models.embed(&encoder_input)?,
            },
        );
        search.dense_k = options.candidates;
        search.keyword_k = options.candidates;
        search.limit = options.rerank_limit;
        search.filter = request.filter.clone();
        report
            .timings_ms
            .insert("query_embedding_and_tokens".into(), elapsed(stage));
        let (retrieval, search_times) = index.search_measured(&search)?;
        report.timings_ms.extend(search_times);
        let stage = Instant::now();
        let hits = if options.evidence_strategy == EvidenceStrategy::FacetCoverageV1 {
            let (hits, audit) = facets::retrieve(index, models, &facet_queries, &retrieval)?;
            report.selection = audit;
            report
                .timings_ms
                .insert("facet_candidate_expansion".into(), elapsed(stage));
            hits
        } else {
            retrieval.results.clone()
        };
        let stage = Instant::now();
        if !hits.is_empty() {
            // Rerank original evidence with source-backed structure, never generated context.
            let passages: Vec<_> = hits
                .iter()
                .map(|h| {
                    let (doc, chunk) = index.resolve(&h.key).unwrap();
                    let bundle = bundle(doc, chunk, &h.key, "rank".into());
                    // Complete JSON may be much larger than a chunk. Rerank the selected original subtree.
                    if bundle.record.is_some() {
                        chunk.evidence.clone()
                    } else {
                        bundle.text
                    }
                })
                .collect();
            let ranked = if options.rerank {
                models.rerank(&query, &passages)?
            } else {
                Rerank {
                    scores: retrieval.results.iter().map(|h| h.score).collect(),
                    pair_tokens: vec![0; passages.len()],
                    identity: json!({"reranking":"disabled","score":"rrf"}),
                }
            };
            require(
                ranked.scores.len() == passages.len()
                    && ranked.pair_tokens.len() == passages.len()
                    && ranked.scores.iter().all(|s| s.is_finite())
                    && ranked.pair_tokens.iter().all(|t| *t <= 512),
                "invalid reranker result",
            )?;
            report.reranker = Some(ranked.identity);
            report.ranked = hits
                .iter()
                .zip(ranked.scores)
                .zip(ranked.pair_tokens)
                .map(|((hit, score), pair_tokens)| Ranked {
                    key: hit.key.clone(),
                    score,
                    pair_tokens,
                })
                .collect();
            report
                .ranked
                .sort_by(|a, b| b.score.total_cmp(&a.score).then_with(|| a.key.cmp(&b.key)));
            report
                .timings_ms
                .insert("reranking_with_preparation".into(), elapsed(stage));
            let stage = Instant::now();
            let selected = if options.evidence_strategy == EvidenceStrategy::CoverageV1 {
                let (keys, audit) = coverage::select(
                    models,
                    &request,
                    &query,
                    &retrieval,
                    &passages,
                    &report.ranked,
                    options.primary_limit,
                )?;
                report.selection = audit;
                Some(keys)
            } else if options.evidence_strategy == EvidenceStrategy::FacetCoverageV1 {
                Some(facets::select(
                    index,
                    models,
                    &hits,
                    &passages,
                    &report.ranked,
                    options.primary_limit,
                    &mut report.selection,
                )?)
            } else {
                None
            };
            if selected.is_some() {
                report
                    .timings_ms
                    .insert("field_coverage_selection".into(), elapsed(stage));
            }
            let stage = Instant::now();
            let mut input = AnswerInput {
                question: request.question.clone(),
                history: request.history.clone(),
                fields: request.fields.clone(),
                evidence: vec![],
                constrain_pointers: options.evidence_strategy != EvidenceStrategy::Ranked,
            };
            require(
                models.answer_tokens(&input)? <= INPUT_TOKENS,
                "question/schema alone exceeds generation budget",
            )?;
            let mut seen = BTreeSet::new();
            let mut primary = vec![];
            let order: Vec<_> =
                selected.unwrap_or_else(|| report.ranked.iter().map(|h| h.key.clone()).collect());
            for key in &order {
                if primary.len() >= options.primary_limit {
                    report.skipped.push(Skipped {
                        key: key.clone(),
                        reason: "primary limit".into(),
                    });
                    continue;
                }
                if add_evidence(
                    index,
                    models,
                    key,
                    &mut input,
                    &mut seen,
                    &mut report.skipped,
                )? {
                    primary.push(key.clone());
                }
            }
            // Expansion has lower priority than primary evidence and respects the same filter.
            if options.evidence_strategy != EvidenceStrategy::Ranked {
                report.selection["admitted_primary_keys"] = json!(primary);
                report.selection["neighbor_expansion"] = json!("disabled; source labels retained");
                for hit in &report.ranked {
                    if !order.contains(&hit.key) {
                        report.skipped.push(Skipped {
                            key: hit.key.clone(),
                            reason: "outside field coverage selection".into(),
                        });
                    }
                }
            }
            for key in primary
                .into_iter()
                .filter(|_| options.evidence_strategy == EvidenceStrategy::Ranked)
            {
                let (_, chunk) = index.resolve(&key).unwrap();
                for id in [&chunk.previous, &chunk.next].into_iter().flatten() {
                    let neighbor = ChunkKey {
                        chunk_id: id.clone(),
                        ..key.clone()
                    };
                    let (doc, other) = index
                        .resolve(&neighbor)
                        .ok_or_else(|| crate::Error::Invalid("missing neighbor".into()))?;
                    if other.parent == chunk.parent
                        && request.filter.test(doc, other)? == Truth::True
                    {
                        add_evidence(
                            index,
                            models,
                            &neighbor,
                            &mut input,
                            &mut seen,
                            &mut report.skipped,
                        )?;
                    } else {
                        report.skipped.push(Skipped {
                            key: neighbor,
                            reason: "neighbor excluded by section or filter".into(),
                        });
                    }
                }
            }
            report.prompt_tokens = Some(models.answer_tokens(&input)?);
            report
                .timings_ms
                .insert("assembly_and_model_tokenization".into(), elapsed(stage));
            if !input.evidence.is_empty() {
                let stage = Instant::now();
                let extraction = models.extract(&input)?;
                report
                    .timings_ms
                    .insert("answer_model_calls".into(), elapsed(stage));
                report.answer = extraction.answer;
                report.audit = extraction.audit;
                let resolved =
                    resolve_json_values(&input, &mut report.answer).map_err(|error| {
                        rejected(&report, &input.evidence, "resolve_json_values", &error)
                    })?;
                if !resolved.is_empty() {
                    if !report.audit.is_object() {
                        report.audit = json!({"model_audit":report.audit});
                    }
                    report.audit["json_values_resolved_from_source"] = json!(resolved);
                }
            }
            report.evidence = input.evidence;
        }
        report.retrieval = Some(retrieval);
    }
    let stage = Instant::now();
    if report.answer.status == Status::Supported
        && report.answer.fields.iter().any(|(name, proof)| {
            proof.value.is_null() && request.fields.get(name).is_some_and(|f| !f.nullable)
        })
    {
        // Validate the complete candidate, including exact source-null pointers,
        // before using source types to determine answerability. Missing is not null.
        let mut source_types = request.fields.clone();
        for field in source_types.values_mut() {
            field.nullable = true;
        }
        validate_answer(&source_types, &report.evidence, &report.answer)
            .map_err(|error| rejected(&report, &report.evidence, "validate_source_null", &error))?;
        if !report.audit.is_object() {
            report.audit = json!({"model_audit":report.audit});
        }
        report.audit["source_null_abstention"] = json!({"reason":"requested non-nullable field is explicitly null in the source", "verified_source_fields":report.answer.fields});
        report.answer = Answer::empty(Status::InsufficientEvidence);
    }
    validate_answer(&request.fields, &report.evidence, &report.answer)
        .map_err(|error| rejected(&report, &report.evidence, "validate_answer", &error))?;
    report.validation = json!({"schema":"passed", "source_references":"passed", "mechanical_support":"passed", "semantic_correctness":"not_automatically_established"});
    if report.answer.status == Status::Supported {
        report.formatted = Some(render(&report.answer, request.template.as_deref())?);
        if request.prose {
            let draft_start = Instant::now();
            match models.rewrite(&request.question, &report.answer) {
                Ok(draft) => report.presentation_draft = Some(draft),
                Err(error) => {
                    report.audit["presentation_error"] = json!(error.to_string());
                }
            }
            report
                .timings_ms
                .insert("presentation_model_calls".into(), elapsed(draft_start));
        }
    }
    report
        .timings_ms
        .insert("validation_and_presentation".into(), elapsed(stage));
    report
        .timings_ms
        .insert("answer_total".into(), elapsed(total));
    Ok(report)
}

/// Deterministic request admission, also used before enqueueing any model work.
pub fn validate_request_options(request: &AskRequest, options: &AnswerOptions) -> Result<()> {
    options.validate()?;
    validate_request(request)?;
    if options.evidence_strategy == EvidenceStrategy::FacetCoverageV1 {
        require(
            request.scope == Scope::Passage,
            "facet_coverage_v1 requires passage scope",
        )?;
        facets::queries(request)?;
    }
    Ok(())
}

fn rejected(report: &AnswerReport, evidence: &[Evidence], stage: &str, error: &Error) -> Error {
    // Diagnostics remain inside an error envelope and can never be used as an answer.
    let draft = serde_json::to_value(&report.answer).unwrap_or(Value::Null);
    let raw = draft.to_string();
    let draft = if raw.len() <= 32768 {
        draft
    } else {
        json!({"truncated":true,"json_preview":raw.chars().take(8192).collect::<String>()})
    };
    let selected: Vec<_> = evidence.iter().take(10).map(|e| json!({
        "id":e.id,"key":e.key,"text_preview":e.text.chars().take(1200).collect::<String>(),
        "text_truncated":e.text.chars().count()>1200,"sources":e.sources.iter().take(12).collect::<Vec<_>>(),
        "source_count":e.sources.len()
    })).collect();
    let mut diagnostics = json!({
        "outcome":"rejected","stage":stage,"generation":report.generation,
        "question":report.request.question,"requested_fields":report.request.fields,
        "unvalidated_draft":draft,"evidence":selected,"evidence_count":evidence.len(),
        "assessment":report.audit.get("assessment"),
        "next_action":"Inspect selected evidence, field quotes and JSON pointers. This draft failed validation and is not a supported answer."
    });
    if report.options.evidence_strategy == EvidenceStrategy::FacetCoverageV1 {
        diagnostics["selection"] = report.selection.clone();
        diagnostics["timings_ms"] = json!(report.timings_ms);
        diagnostics["skipped"] = json!(report.skipped);
    }
    Error::AnswerRejected {
        message: error.to_string(),
        diagnostics: Box::new(diagnostics),
    }
}

// The model selects a JSON location; it never transcribes the authoritative value.
// A null placeholder is required by the candidate schema, distinct from source null.
fn resolve_json_values(input: &AnswerInput, answer: &mut Answer) -> Result<Vec<String>> {
    let mut resolved = vec![];
    if answer.status != Status::Supported {
        return Ok(resolved);
    }
    require(
        answer.fields.keys().eq(input.fields.keys()),
        "supported answer must contain exactly the requested fields",
    )?;
    for (name, proof) in &mut answer.fields {
        let e = input
            .evidence
            .iter()
            .find(|e| e.id == proof.evidence_id)
            .ok_or_else(|| crate::Error::Invalid("unknown answer evidence ID".into()))?;
        if let Some(record) = &e.record {
            require(
                proof.value.is_null() && proof.quote.is_empty(),
                "JSON selection requires a null placeholder and empty quote",
            )?;
            let pointer = proof
                .pointer
                .as_deref()
                .ok_or_else(|| crate::Error::Invalid("JSON evidence requires a pointer".into()))?;
            crate::ingestion::pointer_parts(pointer)?;
            require(
                input.fields[name]
                    .pointer
                    .as_deref()
                    .is_none_or(|p| p == pointer),
                "answer changed the requested JSON pointer",
            )?;
            proof.value = record
                .pointer(pointer)
                .cloned()
                .ok_or_else(|| crate::Error::Invalid("selected JSON pointer is missing".into()))?;
            resolved.push(name.clone());
        }
    }
    Ok(resolved)
}

fn source_attribute<'a>(chunk: &'a Chunk, name: &str) -> Option<&'a Attribute> {
    chunk
        .attributes
        .get(name)
        .filter(|a| !matches!(a.derivation, Derivation::Generated { .. }))
}
fn add_sources(target: &mut Vec<SourceRef>, sources: &[SourceRef]) {
    for source in sources {
        if !target.contains(source) {
            target.push(source.clone());
        }
    }
}
fn bundle(doc: &DocumentRevision, chunk: &Chunk, key: &ChunkKey, id: String) -> Evidence {
    if let Some(record) = source_attribute(chunk, "record") {
        return Evidence {
            id,
            key: key.clone(),
            text: record.value.to_string(),
            sources: record.sources.clone(),
            spans: vec![],
            labels: vec![],
            record: Some(record.value.clone()),
        };
    }
    let mut text = vec![];
    let mut labels = vec![];
    let mut sources = vec![];
    let mut spans = vec![];
    let blocks: BTreeMap<_, _> = doc.blocks.iter().map(|b| (b.id.as_str(), b)).collect();
    let mut parents = vec![];
    for span in &chunk.spans {
        let mut parent = blocks[span.block_id.as_str()].parent.as_deref();
        while let Some(id) = parent {
            let block = blocks[id];
            if !parents.contains(&id) {
                parents.push(id);
            }
            parent = block.parent.as_deref();
        }
    }
    // Document order places ancestor headings before body content.
    for block in &doc.blocks {
        if block.kind == BlockKind::Heading && parents.contains(&block.id.as_str()) {
            text.push(block.text.clone());
            add_sources(&mut sources, &block.sources);
            spans.push(BlockSpan {
                block_id: block.id.clone(),
                bytes: ByteRange {
                    start: 0,
                    end: block.text.len() as u64,
                },
            });
        }
    }
    if let Some(context) = source_attribute(chunk, "pdf_context") {
        if let Some(s) = context.value.as_str() {
            for line in s.lines().filter(|s| !s.trim().is_empty()) {
                if !text.iter().any(|v| v == line) {
                    text.push(line.into());
                    labels.push(line.into());
                }
            }
        }
        add_sources(&mut sources, &context.sources);
    }
    for span in &chunk.spans {
        if !spans.contains(span) {
            let b = blocks[span.block_id.as_str()];
            text.push(b.text[span.bytes.start as usize..span.bytes.end as usize].to_string());
            spans.push(span.clone());
        }
    }
    add_sources(&mut sources, &chunk.sources);
    Evidence {
        id,
        key: key.clone(),
        text: text.join("\n\n"),
        sources,
        spans,
        labels,
        record: None,
    }
}
fn identity(e: &Evidence) -> String {
    // Record copies across subtree chunks represent one record. Text bundles include headers.
    serde_json::to_string(&(
        &e.key.document_id,
        &e.key.revision,
        &e.sources,
        &e.spans,
        &e.labels,
        &e.record,
    ))
    .unwrap()
}
fn add_evidence(
    index: &SearchIndex,
    models: &dyn AnswerModels,
    key: &ChunkKey,
    input: &mut AnswerInput,
    seen: &mut BTreeSet<String>,
    skipped: &mut Vec<Skipped>,
) -> Result<bool> {
    let (doc, chunk) = index.resolve(key).unwrap();
    let next_id = input
        .evidence
        .iter()
        .filter_map(|e| e.id.strip_prefix('E')?.parse::<usize>().ok())
        .max()
        .unwrap_or(0)
        + 1;
    let mut e = bundle(doc, chunk, key, format!("E{next_id}"));
    let fingerprint = identity(&e);
    let same_source: Vec<_> = input
        .evidence
        .iter()
        .filter(|old| old.key.document_id == key.document_id && old.key.revision == key.revision)
        .collect();
    let covered = !e.spans.is_empty()
        && e.sources
            .iter()
            .all(|s| same_source.iter().any(|old| old.sources.contains(s)))
        && e.labels
            .iter()
            .all(|s| same_source.iter().any(|old| old.labels.contains(s)))
        && e.spans.iter().all(|s| {
            input
                .evidence
                .iter()
                .filter(|old| {
                    old.key.document_id == key.document_id && old.key.revision == key.revision
                })
                .flat_map(|old| &old.spans)
                .any(|old| {
                    old.block_id == s.block_id
                        && old.bytes.start <= s.bytes.start
                        && old.bytes.end >= s.bytes.end
                })
        });
    if seen.contains(&fingerprint) || covered {
        skipped.push(Skipped {
            key: key.clone(),
            reason: "duplicate evidence".into(),
        });
        return Ok(false);
    }
    let previous = input.evidence.clone();
    if e.record.is_none() {
        // Merge intersecting source intervals (including shared headings). Text comes
        // from the original blocks again, never by string matching across documents.
        let mut merged = true;
        while merged {
            merged = false;
            for i in (0..input.evidence.len()).rev() {
                let old = &input.evidence[i];
                if old.record.is_none()
                    && old.key.document_id == key.document_id
                    && old.key.revision == key.revision
                    && (old.spans.iter().any(|a| {
                        e.spans.iter().any(|b| {
                            a.block_id == b.block_id
                                && a.bytes.start < b.bytes.end
                                && b.bytes.start < a.bytes.end
                        })
                    }) || (e.labels.iter().any(|label| old.labels.contains(label))
                        && e.sources.iter().any(|source| old.sources.contains(source))))
                {
                    let old = input.evidence.remove(i);
                    e.id = old.id;
                    e.spans.extend(old.spans);
                    add_sources(&mut e.sources, &old.sources);
                    for label in old.labels {
                        if !e.labels.contains(&label) {
                            e.labels.push(label);
                        }
                    }
                    merged = true;
                }
            }
        }
        let mut spans = vec![];
        let mut text = vec![];
        for block in &doc.blocks {
            let mut ranges: Vec<_> = e
                .spans
                .iter()
                .filter(|s| s.block_id == block.id)
                .map(|s| s.bytes.clone())
                .collect();
            ranges.sort_by_key(|r| r.start);
            let mut union: Vec<ByteRange> = vec![];
            for range in ranges {
                if let Some(last) = union.last_mut().filter(|last| last.end >= range.start) {
                    last.end = last.end.max(range.end);
                } else {
                    union.push(range);
                }
            }
            for bytes in union {
                text.push(block.text[bytes.start as usize..bytes.end as usize].to_string());
                spans.push(BlockSpan {
                    block_id: block.id.clone(),
                    bytes,
                });
            }
        }
        e.spans = spans;
        e.labels.retain(|s| !text.contains(s));
        text.splice(0..0, e.labels.clone());
        e.text = text.join("\n\n");
    }
    let previous_constraints = input.constrain_pointers;
    // Ranked JSON uses the same record/type-bound schema as coverage. Enable it
    // before token counting so its visible catalog consumes the prompt budget.
    input.constrain_pointers |= e.record.is_some();
    input.evidence.push(e);
    if models.answer_tokens(input)? > INPUT_TOKENS {
        input.evidence = previous;
        input.constrain_pointers = previous_constraints;
        skipped.push(Skipped {
            key: key.clone(),
            reason: "mandatory evidence exceeds remaining prompt budget".into(),
        });
        return Ok(false);
    }
    seen.insert(fingerprint);
    Ok(true)
}

fn structured_lookup(index: &SearchIndex, r: &AskRequest, report: &mut AnswerReport) -> Result<()> {
    require(
        r.filter != Filter::default(),
        "structured lookup requires an explicit record-selection filter",
    )?;
    require(
        r.fields.values().all(|s| s.pointer.is_some()),
        "structured lookup requires a JSON pointer for every field",
    )?;
    let mut records = BTreeMap::new();
    for (key, doc, chunk) in index.records() {
        if source_attribute(chunk, "record").is_some() && r.filter.test(doc, chunk)? == Truth::True
        {
            let e = bundle(doc, chunk, key, "E1".into());
            records.entry(identity(&e)).or_insert(e);
        }
    }
    report.audit = json!({"operation":"complete_filtered_record_scan_v1", "eligible_records":records.len(), "aggregation":false});
    if records.len() > 1 {
        report.answer = Answer::empty(Status::Ambiguous);
        return Ok(());
    }
    if let Some(e) = records.into_values().next() {
        let mut fields = BTreeMap::new();
        for (name, spec) in &r.fields {
            let pointer = spec.pointer.as_deref().unwrap();
            let Some(value) = e.record.as_ref().unwrap().pointer(pointer) else {
                report.evidence.push(e);
                return Ok(());
            };
            if !valid_type(spec, value) {
                report.evidence.push(e);
                return Ok(());
            }
            fields.insert(
                name.clone(),
                FieldAnswer {
                    value: value.clone(),
                    evidence_id: e.id.clone(),
                    quote: String::new(),
                    pointer: Some(pointer.into()),
                },
            );
        }
        report.evidence.push(e);
        report.answer = Answer {
            status: Status::Supported,
            fields,
        };
    }
    Ok(())
}
fn valid_type(spec: &FieldSpec, v: &Value) -> bool {
    if v.is_null() {
        return spec.nullable;
    }
    match spec.kind {
        FieldKind::String => v.is_string(),
        FieldKind::Boolean => v.is_boolean(),
        FieldKind::Number => v.is_number(),
        FieldKind::Integer => v
            .as_number()
            .is_some_and(|n| !n.to_string().contains(['.', 'e', 'E'])),
    }
}
pub fn validate_answer(
    fields: &BTreeMap<String, FieldSpec>,
    evidence: &[Evidence],
    answer: &Answer,
) -> Result<()> {
    if answer.status != Status::Supported {
        return require(
            answer.fields.is_empty(),
            "non-answer must have empty fields",
        );
    }
    require(
        answer.fields.keys().eq(fields.keys()),
        "supported answer must contain exactly the requested fields",
    )?;
    for (name, proof) in &answer.fields {
        require(
            valid_type(&fields[name], &proof.value),
            "answer field type/nullability mismatch",
        )?;
        let e = evidence
            .iter()
            .find(|e| e.id == proof.evidence_id)
            .ok_or_else(|| crate::Error::Invalid("unknown answer evidence ID".into()))?;
        require(
            !e.sources.is_empty(),
            "answer evidence has no source references",
        )?;
        if let Some(record) = &e.record {
            let pointer = proof
                .pointer
                .as_deref()
                .ok_or_else(|| crate::Error::Invalid("JSON evidence requires a pointer".into()))?;
            crate::ingestion::pointer_parts(pointer)?;
            require(
                fields[name].pointer.as_deref().is_none_or(|p| p == pointer),
                "answer changed the requested JSON pointer",
            )?;
            require(
                record.pointer(pointer) == Some(&proof.value),
                "JSON answer differs from the exact source value or pointer is missing",
            )?;
        } else {
            require(
                proof.pointer.is_none() && !proof.quote.is_empty() && e.text.contains(&proof.quote),
                "prose proof must quote supplied source evidence exactly",
            )?;
            require(
                !proof.value.is_null(),
                "raw null requires an explicit JSON source value",
            )?;
            let literal = proof
                .value
                .as_str()
                .map(String::from)
                .unwrap_or_else(|| proof.value.to_string());
            require(
                if let Some(number) = proof.value.as_number() {
                    numeric::supported(&e.text, &proof.quote, number)
                } else {
                    !literal.is_empty()
                        && proof.quote.match_indices(&literal).any(|(i, _)| {
                            let before = proof.quote[..i].chars().next_back();
                            let after = proof.quote[i + literal.len()..].chars().next();
                            !before.is_some_and(char::is_alphanumeric)
                                && !after.is_some_and(char::is_alphanumeric)
                        })
                },
                "quoted source does not contain the exact answer value",
            )?;
        }
    }
    Ok(())
}
pub fn render(answer: &Answer, template: Option<&str>) -> Result<String> {
    let values: BTreeMap<_, _> = answer
        .fields
        .iter()
        .map(|(k, v)| {
            (
                k.as_str(),
                v.value
                    .as_str()
                    .map(String::from)
                    .unwrap_or_else(|| v.value.to_string()),
            )
        })
        .collect();
    let Some(template) = template else {
        return Ok(values
            .iter()
            .map(|(k, v)| format!("{k}: {v}"))
            .collect::<Vec<_>>()
            .join(", "));
    };
    let mut out = String::new();
    let mut rest = template;
    while let Some(pos) = rest.find('{') {
        require(!rest[..pos].contains('}'), "invalid template brace")?;
        out.push_str(&rest[..pos]);
        rest = &rest[pos + 1..];
        let end = rest
            .find('}')
            .ok_or_else(|| crate::Error::Invalid("unclosed template field".into()))?;
        out.push_str(
            values
                .get(&rest[..end])
                .ok_or_else(|| crate::Error::Invalid("unknown template field".into()))?,
        );
        rest = &rest[end + 1..];
    }
    require(!rest.contains('}'), "invalid template brace")?;
    out.push_str(rest);
    Ok(out)
}
