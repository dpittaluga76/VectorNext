//! Bounded field-derived retrieval aids; these queries are never source evidence.
use super::*;
use final_selection::Candidate;

pub(super) fn queries(request: &AskRequest) -> Result<Vec<String>> {
    require(
        (1..=4).contains(&request.fields.len()),
        "facet_coverage_v1 supports 1..4 answer fields; use ranked for larger questions",
    )?;
    Ok(request
        .fields
        .iter()
        .map(|(name, field)| {
            let name = name.replace('_', " ");
            if field.description.trim().is_empty() {
                name
            } else {
                format!("{name}: {}", field.description)
            }
        })
        .collect())
}

pub(super) fn retrieve(
    index: &SearchIndex,
    models: &dyn AnswerModels,
    facets: &[String],
    original: &SearchResponse,
) -> Result<(Vec<FusedHit>, Value)> {
    let space = models.space();
    let mut searches = Vec::new();
    for facet in facets {
        let input = format!("{}{facet}", space.query_prefix);
        require(
            models.count_tokens(&input)? <= space.max_tokens,
            "facet exceeds encoder budget; shorten the field description explicitly",
        )?;
        let mut request = original.request.clone();
        request.text = facet.clone();
        request.vector = Some(QueryVector {
            space_id: space.id(),
            values: models.embed(&input)?,
        });
        searches.push(index.search(&request)?);
    }
    let lists: Vec<_> = std::iter::once(&original.results)
        .chain(searches.iter().map(|r| &r.results))
        .collect();
    let mut seen = BTreeSet::new();
    let mut merged = Vec::new();
    for depth in 0..lists.iter().map(|l| l.len()).max().unwrap_or(0) {
        for list in &lists {
            if let Some(hit) = list.get(depth) {
                if merged.len() < original.request.limit && seen.insert(hit.key.clone()) {
                    merged.push(hit.clone());
                }
            }
        }
    }
    let audit = json!({"strategy":"facet_coverage_v1","facet_queries":facets,
        "facet_origin":"requested field names and descriptions; not evidence",
        "candidate_searches":searches,"candidate_keys":merged.iter().map(|h| &h.key).collect::<Vec<_>>(),
        "merge":"round_robin_original_then_fields","field_rankings":[],
        "planned_primary_keys":[],"admitted_primary_keys":[],
        "neighbor_expansion":"disabled; source labels retained",
        "coverage_claim":"heuristic only; semantic coverage not established"});
    Ok((merged, audit))
}

pub(super) fn select(
    index: &SearchIndex,
    models: &dyn AnswerModels,
    hits: &[FusedHit],
    passages: &[String],
    general: &[Ranked],
    limit: usize,
    audit: &mut Value,
) -> Result<Vec<ChunkKey>> {
    let candidates: Vec<_> = hits
        .iter()
        .map(|h| {
            let (doc, chunk) = index.resolve(&h.key).expect("snapshot candidate resolves");
            Candidate {
                key: h.key.clone(),
                spans: chunk
                    .spans
                    .iter()
                    .filter(|span| {
                        doc.blocks
                            .iter()
                            .any(|b| b.id == span.block_id && b.kind != BlockKind::Heading)
                    })
                    .cloned()
                    .collect(),
            }
        })
        .collect();
    let general_scores: Vec<_> = hits
        .iter()
        .map(|h| {
            general
                .iter()
                .find(|r| r.key == h.key)
                .expect("candidate was reranked")
                .score
        })
        .collect();
    let mut scores = Vec::new();
    let mut rankings = Vec::new();
    for facet in audit["facet_queries"].as_array().expect("recorded facets") {
        let query = facet.as_str().expect("facet text");
        let result = models.rerank(query, passages)?;
        require(
            result.scores.len() == passages.len()
                && result.pair_tokens.len() == passages.len()
                && result.scores.iter().all(|s| s.is_finite())
                && result.pair_tokens.iter().all(|t| *t <= 512),
            "invalid facet reranker result",
        )?;
        scores.push(result.scores.clone());
        rankings.push(json!({"query":query,"rerank":result}));
    }
    let selected = final_selection::select(&candidates, &general_scores, &scores, limit)?;
    let keys: Vec<_> = selected
        .indices
        .iter()
        .map(|i| hits[*i].key.clone())
        .collect();
    audit["field_rankings"] = json!(rankings);
    audit["selector"] = selected.audit;
    audit["planned_primary_keys"] = json!(keys);
    audit["requested_rerank_pairs"] = json!(hits.len() * (1 + scores.len()));
    Ok(keys)
}
