//! T25 production copy of the frozen T24 selector. Scores are relevance signals, never evidence proofs.
use crate::{Error, Result, contracts::BlockSpan, search::ChunkKey};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
pub struct Candidate {
    pub key: ChunkKey,
    /// Original non-heading spans only; ancestor labels are deliberately absent.
    pub spans: Vec<BlockSpan>,
}

pub struct Selection {
    pub indices: Vec<usize>,
    pub audit: Value,
}

pub fn ranking(candidates: &[Candidate], scores: &[f64]) -> Result<Vec<usize>> {
    if scores.len() != candidates.len() || scores.iter().any(|s| !s.is_finite()) {
        return Err(Error::Invalid("invalid facet reranker scores".into()));
    }
    let mut indices: Vec<_> = (0..candidates.len()).collect();
    indices.sort_by(|a, b| {
        scores[*b]
            .total_cmp(&scores[*a])
            .then_with(|| candidates[*a].key.cmp(&candidates[*b].key))
    });
    Ok(indices)
}

type Ranges = BTreeMap<String, Vec<(u64, u64)>>;
fn canonical(spans: &[BlockSpan]) -> Result<Ranges> {
    let mut grouped: Ranges = BTreeMap::new();
    for span in spans {
        if span.bytes.end <= span.bytes.start {
            return Err(Error::Invalid("invalid facet body span".into()));
        }
        grouped
            .entry(span.block_id.clone())
            .or_default()
            .push((span.bytes.start, span.bytes.end));
    }
    for ranges in grouped.values_mut() {
        ranges.sort_unstable();
        let mut merged: Vec<(u64, u64)> = Vec::new();
        for (start, end) in ranges.iter().copied() {
            if let Some(last) = merged.last_mut() {
                if start <= last.1 {
                    last.1 = last.1.max(end);
                    continue;
                }
            }
            merged.push((start, end));
        }
        *ranges = merged;
    }
    Ok(grouped)
}

fn overlapping(a: &Candidate, ar: &Ranges, b: &Candidate, br: &Ranges) -> bool {
    if a.key.document_id != b.key.document_id || a.key.revision != b.key.revision {
        return false;
    }
    let size = |ranges: &Ranges| -> u128 {
        ranges
            .values()
            .flatten()
            .map(|(s, e)| u128::from(e - s))
            .sum()
    };
    let smaller = size(ar).min(size(br));
    if smaller == 0 {
        return false;
    }
    let mut intersection = 0u128;
    for (block, left) in ar {
        if let Some(right) = br.get(block) {
            for (a, b) in left {
                for (c, d) in right {
                    intersection += u128::from((*b).min(*d).saturating_sub((*a).max(*c)));
                }
            }
        }
    }
    intersection * 5 >= smaller * 4
}

pub fn select(
    candidates: &[Candidate],
    general: &[f64],
    facets: &[Vec<f64>],
    limit: usize,
) -> Result<Selection> {
    if candidates.len() > 20
        || facets.len() > 4
        || limit > 5
        || candidates
            .iter()
            .map(|c| &c.key)
            .collect::<BTreeSet<_>>()
            .len()
            != candidates.len()
    {
        return Err(Error::Invalid(
            "facet selection bounds or duplicate keys".into(),
        ));
    }
    let general_order = ranking(candidates, general)?;
    let orders = facets
        .iter()
        .map(|scores| ranking(candidates, scores))
        .collect::<Result<Vec<_>>>()?;
    let ranges = candidates
        .iter()
        .map(|c| canonical(&c.spans))
        .collect::<Result<Vec<_>>>()?;
    let mut chosen = Vec::new();
    let mut decisions = Vec::new();
    let mut attempt = |index: usize, reason: Value| -> bool {
        if chosen.contains(&index) {
            decisions.push(json!({"candidate":index,"reason":reason,"decision":"reused"}));
            return true;
        }
        if ranges[index].is_empty() {
            decisions.push(json!({"candidate":index,"reason":reason,"decision":"heading_only"}));
            return false;
        }
        if let Some(other) = chosen.iter().copied().find(|other| {
            overlapping(
                &candidates[index],
                &ranges[index],
                &candidates[*other],
                &ranges[*other],
            )
        }) {
            decisions
                .push(json!({"candidate":index,"reason":reason,"decision":"overlap","with":other}));
            return false;
        }
        if chosen.len() >= limit {
            return true;
        }
        chosen.push(index);
        decisions.push(json!({"candidate":index,"reason":reason,"decision":"selected"}));
        true
    };
    for (facet, order) in orders.iter().enumerate() {
        for &index in order {
            if attempt(index, json!({"facet":facet})) {
                break;
            }
        }
    }
    for index in &general_order {
        attempt(*index, json!({"general":true}));
    }
    Ok(Selection {
        indices: chosen.clone(),
        audit: json!({"strategy":"facet_primary_v1","indices":chosen,"facet_orders":orders,"general_order":general_order,"decisions":decisions,"overlap_fraction":"4/5 of shorter non-heading span union","coverage_claim":"heuristic only"}),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contracts::ByteRange;
    fn candidate(doc: &str, chunk: &str, start: u64, end: u64) -> Candidate {
        Candidate {
            key: ChunkKey {
                document_id: doc.into(),
                revision: "r1".into(),
                chunk_id: chunk.into(),
            },
            spans: vec![BlockSpan {
                block_id: "body".into(),
                bytes: ByteRange { start, end },
            }],
        }
    }
    #[test]
    fn facets_recover_distinct_candidates_and_reuse_shared_best() {
        let c = vec![
            candidate("a", "1", 0, 10),
            candidate("b", "1", 0, 10),
            candidate("c", "1", 0, 10),
        ];
        let result = select(
            &c,
            &[9., 8., 1.],
            &[vec![1., 2., 9.], vec![9., 1., 0.], vec![0., 1., 9.]],
            3,
        )
        .unwrap();
        assert_eq!(result.indices, vec![2, 0, 1]);
        assert!(
            result.audit["decisions"]
                .as_array()
                .unwrap()
                .iter()
                .any(|d| d["decision"] == "reused")
        );
    }
    #[test]
    fn skips_headings_and_overlap_without_suppressing_other_documents() {
        let mut heading = candidate("a", "heading", 0, 100);
        heading.spans.clear();
        let c = vec![
            heading,
            candidate("a", "1", 0, 100),
            candidate("a", "2", 20, 100),
            candidate("b", "1", 0, 100),
            candidate("a", "3", 100, 150),
        ];
        let selected = select(&c, &[5., 4., 3., 2., 1.], &[vec![5., 4., 3., 2., 1.]], 5).unwrap();
        assert_eq!(selected.indices, vec![1, 3, 4]);
    }
    #[test]
    fn overlap_uses_union_exact_boundary_and_revision_scope() {
        let mut a = candidate("a", "1", 0, 100);
        a.spans.push(a.spans[0].clone());
        let mut b = candidate("a", "2", 20, 120);
        assert!(overlapping(
            &a,
            &canonical(&a.spans).unwrap(),
            &b,
            &canonical(&b.spans).unwrap()
        ));
        b.spans[0].bytes = ByteRange {
            start: 21,
            end: 121,
        };
        assert!(!overlapping(
            &a,
            &canonical(&a.spans).unwrap(),
            &b,
            &canonical(&b.spans).unwrap()
        ));
        b.spans[0].bytes = ByteRange { start: 0, end: 100 };
        b.key.revision = "r2".into();
        assert!(!overlapping(
            &a,
            &canonical(&a.spans).unwrap(),
            &b,
            &canonical(&b.spans).unwrap()
        ));
        b.key.revision = "r1".into();
        b.spans[0].block_id = "other".into();
        assert!(!overlapping(
            &a,
            &canonical(&a.spans).unwrap(),
            &b,
            &canonical(&b.spans).unwrap()
        ));
    }
    #[test]
    fn canonical_merges_adjacent_ranges_and_large_offsets_without_overflow() {
        let mut c = candidate("a", "1", u64::MAX - 100, u64::MAX - 50);
        c.spans.push(BlockSpan {
            block_id: "body".into(),
            bytes: ByteRange {
                start: u64::MAX - 50,
                end: u64::MAX,
            },
        });
        let ranges = canonical(&c.spans).unwrap();
        assert_eq!(ranges["body"].len(), 1);
        assert!(overlapping(&c, &ranges, &c, &ranges));
    }
    #[test]
    fn invalid_scores_bounds_duplicate_keys_and_spans_fail() {
        let c = vec![candidate("a", "1", 0, 10)];
        for scores in [vec![], vec![f64::NAN], vec![f64::INFINITY]] {
            assert!(select(&c, &scores, &[], 5).is_err());
        }
        assert!(select(&c, &[1.], &[vec![]], 5).is_err());
        assert!(select(&c, &[1.], &vec![vec![1.]; 5], 5).is_err());
        assert!(select(&c, &[1.], &[], 6).is_err());
        assert!(select(&[c[0].clone(), c[0].clone()], &[1., 1.], &[], 5).is_err());
        assert!(select(&[candidate("a", "1", 10, 10)], &[1.], &[], 5).is_err());
    }
    #[test]
    fn ties_use_keys_and_empty_or_zero_budget_is_safe() {
        let c = vec![candidate("b", "1", 0, 10), candidate("a", "1", 0, 10)];
        assert_eq!(ranking(&c, &[1., 1.]).unwrap(), vec![1, 0]);
        assert!(
            select(&c, &[1., 1.], &[vec![1., 1.]], 0)
                .unwrap()
                .indices
                .is_empty()
        );
        assert!(select(&[], &[], &[], 5).unwrap().indices.is_empty());
        let mut heading = c[0].clone();
        heading.spans.clear();
        assert!(
            select(&[heading], &[1.], &[vec![1.]], 5)
                .unwrap()
                .indices
                .is_empty()
        );
    }
}
