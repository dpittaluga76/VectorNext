//! Experimental field-focused ordering. No labels, inferred filters or generated evidence.
use super::*;

pub(super) fn select(
    models: &dyn AnswerModels,
    request: &AskRequest,
    query: &str,
    retrieval: &SearchResponse,
    passages: &[String],
    general: &[Ranked],
    limit: usize,
) -> Result<(Vec<ChunkKey>, Value)> {
    let mut rankings = vec![];
    let mut audit = BTreeMap::new();
    for (name, field) in &request.fields {
        let focus = format!(
            "{}: {}\nQuestion: {}",
            name.replace('_', " "),
            field.description,
            query
        );
        let ranked = models.rerank(&focus, passages)?;
        require(
            ranked.scores.len() == passages.len()
                && ranked.pair_tokens.len() == passages.len()
                && ranked.scores.iter().all(|s| s.is_finite())
                && ranked.pair_tokens.iter().all(|t| *t <= 512),
            "invalid field reranker result",
        )?;
        let mut order: Vec<_> = (0..passages.len()).collect();
        order.sort_by(|a, b| {
            ranked.scores[*b]
                .total_cmp(&ranked.scores[*a])
                .then_with(|| retrieval.results[*a].key.cmp(&retrieval.results[*b].key))
        });
        audit.insert(name, json!({"query":focus, "identity":ranked.identity,
            "ranked":order.iter().map(|i| json!({"key":retrieval.results[*i].key,
                "score":ranked.scores[*i],"pair_tokens":ranked.pair_tokens[*i]})).collect::<Vec<_>>()}));
        rankings.push(
            order
                .into_iter()
                .map(|i| retrieval.results[i].key.clone())
                .collect::<Vec<_>>(),
        );
    }
    let keys = round_robin(&rankings, general, limit);
    let selection = json!({"strategy":"coverage_v1", "retrieval_focus":"current question and latest user turn",
        "field_rankings":audit,"planned_primary_keys":keys,
        "coverage_claim":"heuristic only; semantic coverage not established"});
    Ok((keys, selection))
}

fn round_robin(rankings: &[Vec<ChunkKey>], general: &[Ranked], limit: usize) -> Vec<ChunkKey> {
    let mut keys = vec![];
    for depth in 0..2 {
        for ranking in rankings {
            if let Some(key) = ranking.get(depth) {
                if keys.len() < limit && !keys.contains(key) {
                    keys.push(key.clone());
                }
            }
        }
    }
    for hit in general {
        if keys.len() >= 2.min(limit) {
            break;
        }
        if !keys.contains(&hit.key) {
            keys.push(hit.key.clone());
        }
    }
    keys
}

#[cfg(test)]
mod tests {
    use super::*;
    fn key(doc: &str, chunk: &str) -> ChunkKey {
        ChunkKey {
            document_id: doc.into(),
            revision: "r1".into(),
            chunk_id: chunk.into(),
        }
    }
    #[test]
    fn round_robin_preserves_each_field_before_second_choices_and_limits() {
        let a = key("a", "1");
        let b = key("b", "1");
        let c = key("a", "2");
        let rankings = vec![vec![a.clone(), c.clone()], vec![b.clone(), a.clone()]];
        assert_eq!(
            round_robin(&rankings, &[], 5),
            vec![a.clone(), b.clone(), c]
        );
        assert_eq!(round_robin(&rankings, &[], 2), vec![a, b]);
    }
    #[test]
    fn round_robin_deduplicates_keys_but_not_distant_same_document_evidence() {
        let a = key("a", "1");
        let b = key("a", "2");
        let rankings = vec![vec![a.clone(), b.clone()], vec![a.clone(), b.clone()]];
        assert_eq!(round_robin(&rankings, &[], 5), vec![a, b]);
    }
}
