//! Snapshot-scoped exact dense and keyword retrieval; no inference or persistent index format.
mod filter;
mod filter_index;
mod keyword;

use crate::{
    ReadSnapshot, Result,
    contracts::{Chunk, DocumentRevision},
    require, sha256,
};
pub use filter::{AttributeTrust, Bound, Filter, Predicate, Truth};
use filter_index::FilterIndex;
pub use filter_index::FilterIndexStats;
use keyword::FieldIndex;
pub use keyword::{TOKENIZER, tokenize};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::Arc,
    time::Instant,
};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct ChunkKey {
    pub document_id: String,
    pub revision: String,
    pub chunk_id: String,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum KeywordField {
    Evidence,
    Structural,
    Generated,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct KeywordConfig {
    pub k1: f64,
    pub b: f64,
    pub evidence_weight: f64,
    pub structural_weight: f64,
    pub generated_weight: f64,
}

impl Default for KeywordConfig {
    fn default() -> Self {
        Self {
            k1: 1.2,
            b: 0.75,
            evidence_weight: 1.0,
            structural_weight: 1.0,
            generated_weight: 0.0,
        }
    }
}

impl KeywordConfig {
    fn validate(&self) -> Result<()> {
        require(
            self.k1.is_finite() && (0.0..=1000.0).contains(&self.k1),
            "invalid BM25 k1",
        )?;
        require(
            self.b.is_finite() && (0.0..=1.0).contains(&self.b),
            "invalid BM25 b",
        )?;
        for field in [
            KeywordField::Evidence,
            KeywordField::Structural,
            KeywordField::Generated,
        ] {
            require(
                valid_weight(self.weight(field)),
                "invalid keyword field weight",
            )?;
        }
        Ok(())
    }
    fn weight(&self, field: KeywordField) -> f64 {
        match field {
            KeywordField::Evidence => self.evidence_weight,
            KeywordField::Structural => self.structural_weight,
            KeywordField::Generated => self.generated_weight,
        }
    }
}

fn valid_weight(weight: f64) -> bool {
    weight.is_finite() && (0.0..=1000.0).contains(&weight)
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct QueryVector {
    pub space_id: String,
    pub values: Vec<f32>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Deduplication {
    None,
    ExactEvidence,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SearchRequest {
    pub text: String,
    pub vector: Option<QueryVector>,
    pub filter: Filter,
    pub dense_k: usize,
    pub keyword_k: usize,
    pub limit: usize,
    pub rrf_k: f64,
    pub dense_weight: f64,
    pub keyword_weight: f64,
    pub deduplication: Deduplication,
    pub trace_eligibility: bool,
}

impl SearchRequest {
    pub fn keyword(text: impl Into<String>) -> Self {
        Self {
            text: text.into(),
            vector: None,
            filter: Filter::default(),
            dense_k: 0,
            keyword_k: 30,
            limit: 10,
            rrf_k: 60.0,
            dense_weight: 1.0,
            keyword_weight: 1.0,
            deduplication: Deduplication::ExactEvidence,
            trace_eligibility: false,
        }
    }
    pub fn hybrid(text: impl Into<String>, vector: QueryVector) -> Self {
        Self {
            vector: Some(vector),
            dense_k: 30,
            ..Self::keyword(text)
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DenseHit {
    pub key: ChunkKey,
    pub score: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TermContribution {
    pub field: KeywordField,
    pub term: String,
    pub frequency: usize,
    pub document_frequency: usize,
    pub corpus_chunks: usize,
    pub length: usize,
    pub average_length: f64,
    pub idf: f64,
    pub score: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct KeywordHit {
    pub key: ChunkKey,
    pub score: f64,
    pub terms: Vec<TermContribution>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct FusedHit {
    pub key: ChunkKey,
    pub score: f64,
    pub dense_rank: Option<usize>,
    pub keyword_rank: Option<usize>,
    pub dense_contribution: f64,
    pub keyword_contribution: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Suppression {
    pub removed: ChunkKey,
    pub kept: ChunkKey,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Eligibility {
    pub key: ChunkKey,
    pub decision: Truth,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SearchResponse {
    pub generation: u64,
    pub space_id: String,
    pub tokenizer: String,
    pub keyword_config: KeywordConfig,
    pub request: SearchRequest,
    pub query_terms: Vec<String>,
    pub corpus_chunks: usize,
    pub eligible_chunks: usize,
    pub unknown_filter_chunks: usize,
    pub dense_scored: usize,
    pub keyword_matched: usize,
    pub eligibility: Option<Vec<Eligibility>>,
    pub dense: Vec<DenseHit>,
    pub keyword: Vec<KeywordHit>,
    pub fused: Vec<FusedHit>,
    pub deduplicated: Vec<FusedHit>,
    pub suppressed: Vec<Suppression>,
    pub results: Vec<FusedHit>,
}

struct Row {
    key: ChunkKey,
    document: Arc<DocumentRevision>,
    chunk: usize,
    norm: f64,
    fingerprint: String,
}

impl Row {
    fn chunk(&self) -> &Chunk {
        &self.document.chunks[self.chunk]
    }
}

pub struct SearchIndex {
    snapshot: ReadSnapshot,
    space_id: String,
    config: KeywordConfig,
    rows: Vec<Row>,
    lookup: BTreeMap<ChunkKey, usize>,
    fields: [FieldIndex; 3],
    filters: FilterIndex,
}

impl SearchIndex {
    pub fn build(
        snapshot: ReadSnapshot,
        space_id: impl Into<String>,
        config: KeywordConfig,
    ) -> Result<Self> {
        config.validate()?;
        let space_id = space_id.into();
        require(
            snapshot.space(&space_id).is_some(),
            "unknown index embedding space",
        )?;
        let mut rows = Vec::new();
        for document in snapshot.shared_documents() {
            if !document.required_spaces.contains(&space_id) {
                continue;
            }
            for (chunk_index, chunk) in document.chunks.iter().enumerate() {
                let key = ChunkKey {
                    document_id: document.document_id.clone(),
                    revision: document.revision.clone(),
                    chunk_id: chunk.id.clone(),
                };
                let fingerprint = sha256(&serde_json::to_vec(&(
                    &document.document_id,
                    &document.revision,
                    &chunk.evidence,
                    &chunk.representation,
                    &chunk.sources,
                    &chunk.spans,
                    &chunk.structural_context,
                    &chunk.attributes,
                ))?);
                let norm = norm(&chunk.vectors[&space_id]);
                rows.push(Row {
                    key,
                    document: document.clone(),
                    chunk: chunk_index,
                    norm,
                    fingerprint,
                });
            }
        }
        rows.sort_by(|a, b| a.key.cmp(&b.key));
        let lookup = rows
            .iter()
            .enumerate()
            .map(|(i, row)| (row.key.clone(), i))
            .collect();
        let fields = [
            FieldIndex::build(
                KeywordField::Evidence,
                rows.iter().map(|r| r.chunk().evidence.as_str()),
            ),
            FieldIndex::build(
                KeywordField::Structural,
                rows.iter().map(|r| r.chunk().structural_context.as_str()),
            ),
            FieldIndex::build(
                KeywordField::Generated,
                rows.iter().map(|r| {
                    r.chunk()
                        .generated_context
                        .as_ref()
                        .map_or("", |c| c.text.as_str())
                }),
            ),
        ];
        let filters = FilterIndex::build(&rows);
        Ok(Self {
            snapshot,
            space_id,
            config,
            rows,
            lookup,
            fields,
            filters,
        })
    }

    /// Construction counters for disposable filter indexes, not resident bytes.
    pub fn filter_index_stats(&self) -> &FilterIndexStats {
        self.filters.stats()
    }

    pub fn generation(&self) -> u64 {
        self.snapshot.generation()
    }
    pub fn space_id(&self) -> &str {
        &self.space_id
    }
    pub fn records(&self) -> impl Iterator<Item = (&ChunkKey, &DocumentRevision, &Chunk)> {
        self.rows
            .iter()
            .map(|r| (&r.key, r.document.as_ref(), r.chunk()))
    }
    pub fn resolve(&self, key: &ChunkKey) -> Option<(&DocumentRevision, &Chunk)> {
        self.lookup.get(key).map(|&i| {
            let row = &self.rows[i];
            (row.document.as_ref(), row.chunk())
        })
    }

    pub fn search(&self, request: &SearchRequest) -> Result<SearchResponse> {
        self.search_measured(request).map(|(response, _)| response)
    }
    pub fn search_measured(
        &self,
        request: &SearchRequest,
    ) -> Result<(SearchResponse, BTreeMap<String, f64>)> {
        let started = Instant::now();
        let mut times = BTreeMap::new();
        request.filter.validate()?;
        require(
            request.rrf_k.is_finite() && request.rrf_k > 0.0 && request.rrf_k <= 1_000_000.0,
            "invalid RRF k",
        )?;
        require(
            valid_weight(request.dense_weight) && valid_weight(request.keyword_weight),
            "invalid fusion weight",
        )?;
        let dense_enabled = request.dense_k > 0 && request.dense_weight > 0.0;
        let keyword_enabled = request.keyword_k > 0 && request.keyword_weight > 0.0;
        require(
            dense_enabled || keyword_enabled,
            "at least one retrieval branch must be enabled",
        )?;
        if let Some(vector) = &request.vector {
            require(
                vector.space_id == self.space_id,
                "query/index embedding spaces differ",
            )?;
            self.snapshot
                .validate_query_vector(&vector.space_id, &vector.values)?;
        }
        require(
            !dense_enabled || request.vector.is_some(),
            "dense retrieval requires a query vector",
        )?;
        let decisions = self.filters.evaluate(&request.filter, &self.rows);
        let eligible: Vec<_> = decisions.iter().map(|d| *d == Truth::True).collect();
        let eligible_chunks = eligible.iter().filter(|&&v| v).count();
        let query_terms: Vec<_> = tokenize(&request.text)
            .into_iter()
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect();
        times.insert(
            "search_filter_tokenize".into(),
            started.elapsed().as_secs_f64() * 1000.0,
        );
        let stage = Instant::now();
        let mut dense = Vec::new();
        if dense_enabled {
            let query = &request
                .vector
                .as_ref()
                .expect("validated query vector")
                .values;
            let query_norm = norm(query);
            for (i, row) in self.rows.iter().enumerate() {
                if !eligible[i] {
                    continue;
                }
                let vector = &row.chunk().vectors[&self.space_id];
                let dot: f64 = vector
                    .iter()
                    .zip(query)
                    .map(|(&a, &b)| f64::from(a) * f64::from(b))
                    .sum();
                let score = (dot / (row.norm * query_norm)).clamp(-1.0, 1.0);
                dense.push(DenseHit {
                    key: row.key.clone(),
                    score: if score == 0.0 { 0.0 } else { score },
                });
            }
            dense.sort_by(|a, b| b.score.total_cmp(&a.score).then_with(|| a.key.cmp(&b.key)));
            dense.truncate(request.dense_k);
        }
        times.insert(
            "search_dense".into(),
            stage.elapsed().as_secs_f64() * 1000.0,
        );
        let stage = Instant::now();
        let mut scores = vec![0.0; self.rows.len()];
        let mut details = BTreeMap::new();
        if keyword_enabled {
            for field in &self.fields {
                field.score(
                    &query_terms,
                    &eligible,
                    &self.config,
                    &mut scores,
                    &mut details,
                );
            }
        }
        let keyword_matched = details.len();
        let mut keyword: Vec<_> = details
            .into_iter()
            .map(|(i, terms)| KeywordHit {
                key: self.rows[i].key.clone(),
                score: scores[i],
                terms,
            })
            .collect();
        keyword.sort_by(|a, b| b.score.total_cmp(&a.score).then_with(|| a.key.cmp(&b.key)));
        keyword.truncate(request.keyword_k);
        times.insert(
            "search_keyword".into(),
            stage.elapsed().as_secs_f64() * 1000.0,
        );
        let stage = Instant::now();
        let mut combined: BTreeMap<ChunkKey, FusedHit> = BTreeMap::new();
        for (dense_branch, keys, weight) in [
            (
                true,
                dense.iter().map(|h| &h.key).collect::<Vec<_>>(),
                request.dense_weight,
            ),
            (
                false,
                keyword.iter().map(|h| &h.key).collect::<Vec<_>>(),
                request.keyword_weight,
            ),
        ] {
            for (i, key) in keys.into_iter().enumerate() {
                let hit = combined.entry(key.clone()).or_insert_with(|| FusedHit {
                    key: key.clone(),
                    score: 0.0,
                    dense_rank: None,
                    keyword_rank: None,
                    dense_contribution: 0.0,
                    keyword_contribution: 0.0,
                });
                let contribution = weight / (request.rrf_k + (i + 1) as f64);
                if dense_branch {
                    hit.dense_rank = Some(i + 1);
                    hit.dense_contribution = contribution;
                } else {
                    hit.keyword_rank = Some(i + 1);
                    hit.keyword_contribution = contribution;
                }
                hit.score += contribution;
            }
        }
        let mut fused: Vec<_> = combined.into_values().collect();
        fused.sort_by(|a, b| b.score.total_cmp(&a.score).then_with(|| a.key.cmp(&b.key)));
        let mut representatives = BTreeMap::new();
        let mut deduplicated = Vec::new();
        let mut suppressed = Vec::new();
        for hit in &fused {
            let fingerprint = &self.rows[self.lookup[&hit.key]].fingerprint;
            if request.deduplication == Deduplication::ExactEvidence {
                if let Some(kept) = representatives.get(fingerprint) {
                    suppressed.push(Suppression {
                        removed: hit.key.clone(),
                        kept: Clone::clone(kept),
                    });
                    continue;
                }
                representatives.insert(fingerprint, hit.key.clone());
            }
            deduplicated.push(hit.clone());
        }
        let results = deduplicated.iter().take(request.limit).cloned().collect();
        times.insert(
            "search_fusion_dedup".into(),
            stage.elapsed().as_secs_f64() * 1000.0,
        );
        times.insert(
            "search_total".into(),
            started.elapsed().as_secs_f64() * 1000.0,
        );
        Ok((
            SearchResponse {
                generation: self.generation(),
                space_id: self.space_id.clone(),
                tokenizer: TOKENIZER.into(),
                keyword_config: self.config.clone(),
                request: request.clone(),
                query_terms,
                corpus_chunks: self.rows.len(),
                eligible_chunks,
                unknown_filter_chunks: decisions.iter().filter(|&&d| d == Truth::Unknown).count(),
                dense_scored: if dense_enabled { eligible_chunks } else { 0 },
                keyword_matched,
                eligibility: request.trace_eligibility.then(|| {
                    self.rows
                        .iter()
                        .zip(decisions)
                        .map(|(row, decision)| Eligibility {
                            key: row.key.clone(),
                            decision,
                        })
                        .collect()
                }),
                dense,
                keyword,
                fused,
                deduplicated,
                suppressed,
                results,
            },
            times,
        ))
    }
}

fn norm(vector: &[f32]) -> f64 {
    vector
        .iter()
        .map(|&v| f64::from(v).powi(2))
        .sum::<f64>()
        .sqrt()
}
