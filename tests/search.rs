#![cfg(target_os = "linux")]
mod support;
use serde_json::{Number, Value, json};
use std::{collections::BTreeSet, str::FromStr};
use support::*;
use vectornext::{Database, contracts::*, search::*};

fn index(db: &Database, space: &EmbeddingSpace) -> SearchIndex {
    SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap()
}
fn dense(space: &EmbeddingSpace, values: Vec<f32>) -> SearchRequest {
    let mut request = SearchRequest::hybrid(
        "",
        QueryVector {
            space_id: space.id(),
            values,
        },
    );
    request.keyword_k = 0;
    request.dense_k = usize::MAX;
    request.limit = usize::MAX;
    request
}
fn eq(key: &str, value: Value) -> Filter {
    Filter::Attribute {
        key: key.into(),
        pointer: String::new(),
        predicate: Predicate::Eq(value),
        trust: AttributeTrust::default(),
    }
}
fn keys(hits: &[FusedHit]) -> Vec<&str> {
    hits.iter().map(|h| h.key.document_id.as_str()).collect()
}
fn number(value: &str) -> Number {
    Number::from_str(value).unwrap()
}

#[test]
fn exact_dense_matches_independently_normalized_reference_on_filtered_corpus() {
    let (_dir, mut db) = database();
    let space = space(7);
    let mut state = 47_u64;
    let mut reference = vec![];
    for i in 0..64 {
        let vector: Vec<f32> = (0..7)
            .map(|_| {
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
                ((state >> 33) % 2001) as f32 / 1000. - 1.
            })
            .collect();
        let id = format!("doc-{i:02}");
        let doc = document(
            &mut db,
            &id,
            "r1",
            &["independent vector fixture"],
            vec![vector.clone()],
            &space,
        );
        publish(&mut db, doc, &space, None);
        reference.push((id, vector));
    }
    let query = vec![0.1_f32, -0.7, 0.3, 0.9, -0.5, 0.4, 0.2];
    let mut request = dense(&space, query.clone());
    request.dense_k = 13;
    let selected: BTreeSet<_> = reference
        .iter()
        .enumerate()
        .filter(|(i, _)| i % 3 != 0)
        .map(|(_, (id, _))| id.clone())
        .collect();
    request.filter = Filter::DocumentIds(selected.clone());
    // Independent reference normalizes each vector first, then takes its dot product.
    let unit = |v: &[f32]| {
        let length = v.iter().fold(0_f64, |acc, &x| acc.hypot(f64::from(x)));
        v.iter().map(|&x| f64::from(x) / length).collect::<Vec<_>>()
    };
    let query = unit(&query);
    let mut expected: Vec<_> = reference
        .iter()
        .filter(|(id, _)| selected.contains(id))
        .map(|(id, v)| {
            (
                id.clone(),
                unit(v).iter().zip(&query).map(|(a, b)| a * b).sum::<f64>(),
            )
        })
        .collect();
    expected.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    expected.truncate(13);
    let result = index(&db, &space).search(&request).unwrap();
    assert_eq!(result.dense_scored, selected.len());
    for (actual, (id, score)) in result.dense.iter().zip(expected) {
        assert_eq!(actual.key.document_id, id);
        assert!((actual.score - score).abs() < 1e-12);
    }
    assert_eq!(result.dense.len(), 13);
}

#[test]
fn cosine_ties_extreme_magnitudes_zero_and_negative_scores_are_stable() {
    let (_dir, mut db) = database();
    let space = space(2);
    for (id, vector) in [
        ("b", vec![2., 0.]),
        ("a", vec![1e-30, 0.]),
        ("c", vec![1e30, 0.]),
        ("d", vec![0., 1.]),
        ("e", vec![-1., 0.]),
    ] {
        let doc = document(&mut db, id, "r1", &["ties"], vec![vector], &space);
        publish(&mut db, doc, &space, None);
    }
    let result = index(&db, &space)
        .search(&dense(&space, vec![1., 0.]))
        .unwrap();
    assert_eq!(keys(&result.results), ["a", "b", "c", "d", "e"]);
    assert_eq!(
        result.dense.iter().map(|h| h.score).collect::<Vec<_>>(),
        [1., 1., 1., 0., -1.]
    );
}

#[test]
fn filters_apply_before_branch_budgets_and_not_after_top_k() {
    let (_dir, db, space) = diagnostic_corpus();
    let mut query = SearchRequest::hybrid(
        "Argentina",
        QueryVector {
            space_id: space.id(),
            values: vec![1., 0., 0.],
        },
    );
    query.filter = Filter::DocumentIds(BTreeSet::from(["e-zero".into()]));
    query.dense_k = 1;
    query.keyword_k = 1;
    let result = index(&db, &space).search(&query).unwrap();
    assert_eq!(keys(&result.results), ["e-zero"]);
    assert_eq!(result.eligible_chunks, 1);
    assert_eq!(result.dense[0].key.document_id, "e-zero");
    assert_eq!(result.keyword[0].key.document_id, "e-zero");
}

#[test]
fn bm25_scores_match_hand_calculation_and_filter_keeps_corpus_statistics() {
    let (_dir, mut db) = database();
    let space = space(2);
    for (id, text) in [
        ("a", "alpha alpha beta"),
        ("b", "alpha gamma"),
        ("c", "beta"),
    ] {
        let doc = document(&mut db, id, "r1", &[text], vec![vec![1., 0.]], &space);
        publish(&mut db, doc, &space, None);
    }
    let index = index(&db, &space);
    let result = index.search(&SearchRequest::keyword("alpha beta")).unwrap();
    let idf = (1.0_f64 + 1.5 / 2.5).ln(); // N=3; df(alpha)=df(beta)=2; avg length=2.
    let expected = [
        (
            "a",
            idf * (2. * 2.2 / (2. + 1.2 * (0.25 + 0.75 * 1.5))
                + 2.2 / (1. + 1.2 * (0.25 + 0.75 * 1.5))),
        ),
        ("b", idf),
        ("c", idf * 2.2 / (1. + 1.2 * (0.25 + 0.75 * 0.5))),
    ];
    assert_eq!(result.keyword.len(), 3);
    for hit in &result.keyword {
        let score = expected
            .iter()
            .find(|(id, _)| *id == hit.key.document_id)
            .unwrap()
            .1;
        assert!((hit.score - score).abs() < 1e-12);
        assert!((hit.terms.iter().map(|t| t.score).sum::<f64>() - hit.score).abs() < 1e-12);
        assert!(
            hit.terms.iter().all(|t| t.corpus_chunks == 3
                && t.document_frequency == 2
                && t.average_length == 2.)
        );
    }
    let mut filtered = SearchRequest::keyword("alpha beta");
    filtered.filter = Filter::DocumentIds(BTreeSet::from(["a".into()]));
    assert_eq!(
        index.search(&filtered).unwrap().keyword[0],
        result
            .keyword
            .iter()
            .find(|h| h.key.document_id == "a")
            .unwrap()
            .clone()
    );
}

#[test]
fn unicode_tokenization_and_unique_query_terms_are_versioned() {
    assert_eq!(
        tokenize("Pelé PELE\u{301} ＡＢＣ J2 007 foo-bar İstanbul"),
        ["pele", "pele", "abc", "j2", "007", "foo", "bar", "istanbul"]
    );
    let (_dir, db, space) = diagnostic_corpus();
    let index = index(&db, &space);
    let one = index.search(&SearchRequest::keyword("Pele")).unwrap();
    let repeated = index
        .search(&SearchRequest::keyword("PELÉ pele Pelé"))
        .unwrap();
    assert_eq!(one.keyword, repeated.keyword);
    assert_eq!(one.tokenizer, TOKENIZER);
    assert!(!one.keyword.is_empty());
}

#[test]
fn keyword_fields_are_independent_and_generated_context_is_opt_in() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut doc = document(
        &mut db,
        "a",
        "r1",
        &["original evidence"],
        vec![vec![1., 0.]],
        &space,
    );
    doc.chunks[0].structural_context = "headinglabel".into();
    doc.chunks[0].generated_context = Some(GeneratedContext {
        text: "generatedlabel".into(),
        model: "fixture@v1".into(),
        prompt_version: "v1".into(),
        source_scope: doc.chunks[0].sources.clone(),
    });
    publish(&mut db, doc, &space, None);
    let plain = index(&db, &space);
    assert!(
        plain
            .search(&SearchRequest::keyword("generatedlabel"))
            .unwrap()
            .results
            .is_empty()
    );
    let result = plain
        .search(&SearchRequest::keyword("headinglabel"))
        .unwrap();
    assert_eq!(result.keyword[0].terms[0].field, KeywordField::Structural);
    let enabled = SearchIndex::build(
        db.snapshot(),
        space.id(),
        KeywordConfig {
            generated_weight: 0.5,
            ..KeywordConfig::default()
        },
    )
    .unwrap();
    let result = enabled
        .search(&SearchRequest::keyword("generatedlabel"))
        .unwrap();
    assert_eq!(result.keyword[0].terms[0].field, KeywordField::Generated);
    assert_eq!(
        enabled.resolve(&result.results[0].key).unwrap().1.evidence,
        "original evidence"
    );
    let disabled = SearchIndex::build(
        db.snapshot(),
        space.id(),
        KeywordConfig {
            evidence_weight: 0.,
            structural_weight: 0.,
            ..KeywordConfig::default()
        },
    )
    .unwrap();
    assert!(
        disabled
            .search(&SearchRequest::keyword("original headinglabel"))
            .unwrap()
            .results
            .is_empty()
    );
}

#[test]
fn rrf_matches_known_ranks_and_weighted_contributions_without_double_counting() {
    let (_dir, mut db) = database();
    let space = space(2);
    for (id, text, vector) in [
        ("a", "unrelated", vec![1., 0.]),
        ("b", "target", vec![0.8, 0.6]),
        ("c", "target", vec![0., 1.]),
    ] {
        let doc = document(&mut db, id, "r1", &[text], vec![vector], &space);
        publish(&mut db, doc, &space, None);
    }
    let index = index(&db, &space);
    let mut request = SearchRequest::hybrid(
        "target",
        QueryVector {
            space_id: space.id(),
            values: vec![1., 0.],
        },
    );
    let result = index.search(&request).unwrap();
    assert_eq!(keys(&result.fused), ["b", "c", "a"]);
    assert_eq!(result.fused.len(), 3);
    let expected = [1. / 62. + 1. / 61., 1. / 63. + 1. / 62., 1. / 61.];
    for (hit, score) in result.fused.iter().zip(expected) {
        assert!((hit.score - score).abs() < 1e-15);
    }
    assert_eq!(
        (result.fused[0].dense_rank, result.fused[0].keyword_rank),
        (Some(2), Some(1))
    );
    request.dense_weight = 3.;
    request.keyword_weight = 0.5;
    let result = index.search(&request).unwrap();
    let b = result
        .fused
        .iter()
        .find(|h| h.key.document_id == "b")
        .unwrap();
    assert_eq!(b.dense_contribution, 3. / 62.);
    assert_eq!(b.keyword_contribution, 0.5 / 61.);
    request.dense_weight = 0.;
    let keyword_only = index.search(&request).unwrap();
    assert!(keyword_only.dense.is_empty());
    assert_eq!(keys(&keyword_only.results), ["b", "c"]);
}

#[test]
fn dedup_preserves_document_identity_different_locations_and_provenance() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut doc = document(
        &mut db,
        "a",
        "r1",
        &["same text", "same text"],
        vec![vec![1., 0.], vec![1., 0.]],
        &space,
    );
    let mut duplicate = doc.chunks[0].clone();
    duplicate.id = "duplicate".into();
    duplicate.generated_context = Some(GeneratedContext {
        text: "different generated context".into(),
        model: "fixture@v1".into(),
        prompt_version: "v1".into(),
        source_scope: duplicate.sources.clone(),
    });
    doc.chunks.push(duplicate);
    let mut different = doc.chunks[0].clone();
    different.id = "different-attribute".into();
    doc.chunks.push(different);
    attribute(&mut doc, 3, "flag", json!(true));
    publish(&mut db, doc, &space, None);
    let copy = document(
        &mut db,
        "b",
        "r1",
        &["same text"],
        vec![vec![1., 0.]],
        &space,
    );
    publish(&mut db, copy, &space, None);
    let index = index(&db, &space);
    let mut request = dense(&space, vec![1., 0.]);
    let result = index.search(&request).unwrap();
    assert_eq!(result.fused.len(), 5);
    assert_eq!(result.results.len(), 4);
    assert_eq!(result.suppressed.len(), 1);
    assert_eq!(result.suppressed[0].removed.chunk_id, "duplicate");
    assert_eq!(result.suppressed[0].kept.chunk_id, "c0");
    assert_eq!(
        result
            .results
            .iter()
            .filter(|h| h.key.document_id == "a")
            .count(),
        3
    );
    request.deduplication = Deduplication::None;
    assert_eq!(index.search(&request).unwrap().results.len(), 5);
}

#[test]
fn partial_overlaps_are_not_discarded() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut doc = document(
        &mut db,
        "a",
        "r1",
        &["first middle last"],
        vec![vec![1., 0.]],
        &space,
    );
    doc.chunks[0].evidence = "first middle".into();
    doc.chunks[0].spans[0].bytes.end = 12;
    let mut tail = doc.chunks[0].clone();
    tail.id = "tail".into();
    tail.evidence = "middle last".into();
    tail.spans[0].bytes = ByteRange { start: 6, end: 17 };
    doc.chunks.push(tail);
    publish(&mut db, doc, &space, None);
    let result = index(&db, &space)
        .search(&dense(&space, vec![1., 0.]))
        .unwrap();
    assert_eq!(result.results.len(), 2);
    assert!(result.suppressed.is_empty());
}

#[test]
fn exact_numeric_filters_preserve_integers_decimals_exponents_and_types() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut doc = document(&mut db, "a", "r1", &["numbers"], vec![vec![1., 0.]], &space);
    for (key, value) in [
        ("big", "9007199254740993"),
        ("decimal", "0.12345678901234567890123456789"),
        ("huge", "1e999999999999999999999"),
        ("small", "-1e-999999999999999999999"),
        ("zero", "-0.0"),
    ] {
        attribute(&mut doc, 0, key, Value::Number(number(value)));
    }
    attribute(&mut doc, 0, "id", json!("007"));
    attribute(&mut doc, 0, "null", Value::Null);
    attribute(&mut doc, 0, "nested", json!({"a": [1, {"b": 100}]}));
    let chunk = &doc.chunks[0];
    for (key, value) in [
        ("big", "9007199254740993.00"),
        ("decimal", "1.2345678901234567890123456789e-1"),
        ("huge", "10e999999999999999999998"),
        ("small", "-10e-1000000000000000000000"),
        ("zero", "0e1234"),
    ] {
        assert_eq!(
            eq(key, Value::Number(number(value)))
                .test(&doc, chunk)
                .unwrap(),
            Truth::True,
            "{key}"
        );
    }
    assert_eq!(
        eq("big", json!(9007199254740992_u64))
            .test(&doc, chunk)
            .unwrap(),
        Truth::False
    );
    assert_eq!(eq("id", json!(7)).test(&doc, chunk).unwrap(), Truth::False);
    assert_eq!(
        eq("id", json!("007")).test(&doc, chunk).unwrap(),
        Truth::True
    );
    assert_eq!(
        eq("null", Value::Null).test(&doc, chunk).unwrap(),
        Truth::True
    );
    assert_eq!(
        eq("missing", Value::Null).test(&doc, chunk).unwrap(),
        Truth::Unknown
    );
    assert_eq!(
        eq(
            "nested",
            serde_json::from_str(r#"{"a":[1.0,{"b":1e2}]}"#).unwrap()
        )
        .test(&doc, chunk)
        .unwrap(),
        Truth::True
    );
    for (key, min, max) in [
        ("big", "9007199254740992", "9007199254740994"),
        (
            "decimal",
            "0.12345678901234567890123456788",
            "0.12345678901234567890123456790",
        ),
        ("small", "-2e-999999999999999999999", "0"),
    ] {
        let filter = Filter::Attribute {
            key: key.into(),
            pointer: "".into(),
            predicate: Predicate::NumericRange {
                min: Some(Bound {
                    value: number(min),
                    inclusive: false,
                }),
                max: Some(Bound {
                    value: number(max),
                    inclusive: false,
                }),
            },
            trust: AttributeTrust::default(),
        };
        assert_eq!(filter.test(&doc, chunk).unwrap(), Truth::True);
    }
    publish(&mut db, doc, &space, None);
    let mut query = SearchRequest::keyword("numbers");
    query.filter = eq("big", Value::Number(number("9007199254740993")));
    assert_eq!(index(&db, &space).search(&query).unwrap().results.len(), 1);
}

#[test]
fn missing_null_negation_generated_trust_and_nested_paths_are_explicit() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut doc = document(&mut db, "a", "r1", &["fields"], vec![vec![1., 0.]], &space);
    attribute(
        &mut doc,
        0,
        "record",
        json!({"match":{"year":1954}, "publication":{"year":2026}, "a/b":{"~id":[null,"007"]}}),
    );
    attribute(&mut doc, 0, "guess", json!(1954));
    doc.chunks[0]
        .attributes
        .get_mut("guess")
        .unwrap()
        .derivation = Derivation::Generated {
        model: "fixture@1".into(),
        prompt_version: "v1".into(),
    };
    let chunk = &doc.chunks[0];
    let nested = |pointer: &str, predicate| Filter::Attribute {
        key: "record".into(),
        pointer: pointer.into(),
        predicate,
        trust: AttributeTrust::default(),
    };
    assert_eq!(
        nested("/match/year", Predicate::Eq(json!(1954)))
            .test(&doc, chunk)
            .unwrap(),
        Truth::True
    );
    assert_eq!(
        nested("/publication/year", Predicate::Eq(json!(1954)))
            .test(&doc, chunk)
            .unwrap(),
        Truth::False
    );
    assert_eq!(
        nested("/a~1b/~0id/0", Predicate::Eq(Value::Null))
            .test(&doc, chunk)
            .unwrap(),
        Truth::True
    );
    assert_eq!(
        nested("/a~1b/~0id/1", Predicate::Eq(json!("007")))
            .test(&doc, chunk)
            .unwrap(),
        Truth::True
    );
    assert_eq!(
        nested("/missing", Predicate::Missing)
            .test(&doc, chunk)
            .unwrap(),
        Truth::True
    );
    assert_eq!(
        nested("/missing", Predicate::Exists)
            .test(&doc, chunk)
            .unwrap(),
        Truth::False
    );
    assert_eq!(
        Filter::Not(Box::new(eq("missing", json!(3))))
            .test(&doc, chunk)
            .unwrap(),
        Truth::Unknown
    );
    assert_eq!(
        Filter::Not(Box::new(eq("guess", json!(1954))))
            .test(&doc, chunk)
            .unwrap(),
        Truth::Unknown
    );
    let mut explicit = eq("guess", json!(1954));
    if let Filter::Attribute { trust, .. } = &mut explicit {
        *trust = AttributeTrust::Any;
    }
    assert_eq!(explicit.test(&doc, chunk).unwrap(), Truth::True);
    let unknown = eq("missing", json!(3));
    assert_eq!(
        Filter::All(vec![unknown.clone(), Filter::Any(vec![])])
            .test(&doc, chunk)
            .unwrap(),
        Truth::False
    );
    assert_eq!(
        Filter::Any(vec![unknown, Filter::All(vec![])])
            .test(&doc, chunk)
            .unwrap(),
        Truth::True
    );
    publish(&mut db, doc, &space, None);
    let mut query = SearchRequest::keyword("fields");
    query.filter = eq("guess", json!(1954));
    query.trace_eligibility = true;
    let result = index(&db, &space).search(&query).unwrap();
    assert!(result.results.is_empty());
    assert_eq!(result.unknown_filter_chunks, 1);
    assert_eq!(result.eligibility.unwrap()[0].decision, Truth::Unknown);
}

#[test]
fn invalid_filters_and_ranges_are_rejected() {
    for pointer in ["bad", "/bad~", "/bad~2"] {
        let filter = Filter::Attribute {
            key: "k".into(),
            pointer: pointer.into(),
            predicate: Predicate::Exists,
            trust: AttributeTrust::default(),
        };
        assert!(filter.validate().is_err());
    }
    for (min, max, inclusive) in [("3", "2", true), ("3", "3", false)] {
        let filter = Filter::Attribute {
            key: "k".into(),
            pointer: "".into(),
            predicate: Predicate::NumericRange {
                min: Some(Bound {
                    value: number(min),
                    inclusive,
                }),
                max: Some(Bound {
                    value: number(max),
                    inclusive,
                }),
            },
            trust: AttributeTrust::default(),
        };
        assert!(filter.validate().is_err());
    }
    let mut deep = Filter::default();
    for _ in 0..32 {
        deep = Filter::Not(Box::new(deep));
    }
    assert!(deep.validate().is_err());
    assert!(
        Filter::All(vec![Filter::default(); 1024])
            .validate()
            .is_err()
    );
}

#[test]
fn embedding_spaces_are_isolated_even_with_identical_dimensions() {
    let (_dir, mut db) = database();
    let space_a = space(2);
    let mut space_b = space(2);
    space_b.preprocessing = "changed-v2".into();
    for (id, space) in [("a", &space_a), ("b", &space_b)] {
        let doc = document(
            &mut db,
            id,
            "r1",
            &["shared keyword"],
            vec![vec![1., 0.]],
            space,
        );
        publish(&mut db, doc, space, None);
    }
    let index = index(&db, &space_a);
    assert_eq!(
        keys(
            &index
                .search(&SearchRequest::keyword("shared"))
                .unwrap()
                .results
        ),
        ["a"]
    );
    assert!(index.search(&dense(&space_b, vec![1., 0.])).is_err());
    assert!(SearchIndex::build(db.snapshot(), "unknown", KeywordConfig::default()).is_err());
}

#[test]
fn malformed_vectors_and_nonfinite_or_disabled_settings_fail_explicitly() {
    let (_dir, db, space) = diagnostic_corpus();
    let index = index(&db, &space);
    for values in [
        vec![1.],
        vec![0.; 3],
        vec![f32::NAN; 3],
        vec![f32::INFINITY; 3],
    ] {
        assert!(index.search(&dense(&space, values)).is_err());
    }
    let mut missing = SearchRequest::keyword("x");
    missing.dense_k = 1;
    assert!(index.search(&missing).is_err());
    for value in [f64::NAN, f64::INFINITY, -1., 0., 1_000_001.] {
        let mut query = SearchRequest::keyword("x");
        query.rrf_k = value;
        assert!(index.search(&query).is_err());
    }
    let mut disabled = SearchRequest::keyword("x");
    disabled.keyword_weight = 0.;
    assert!(index.search(&disabled).is_err());
    for value in [f64::NAN, f64::INFINITY, -1., 1001.] {
        let mut query = SearchRequest::keyword("x");
        query.keyword_weight = value;
        assert!(index.search(&query).is_err());
        assert!(
            SearchIndex::build(
                db.snapshot(),
                space.id(),
                KeywordConfig {
                    generated_weight: value,
                    ..KeywordConfig::default()
                }
            )
            .is_err()
        );
    }
}

#[test]
fn empty_index_unknown_terms_zero_result_limit_and_l2_validation() {
    let (_dir, mut db) = database();
    let mut space = space(2);
    space.normalization = Normalization::L2;
    db.commit(Batch {
        operation_id: "register".into(),
        spaces: vec![space.clone()],
        mutations: vec![],
    })
    .unwrap();
    let empty = index(&db, &space);
    assert!(
        empty
            .search(&SearchRequest::keyword("anything"))
            .unwrap()
            .results
            .is_empty()
    );
    assert!(empty.search(&dense(&space, vec![2., 0.])).is_err());
    let doc = document(&mut db, "a", "r1", &["alpha"], vec![vec![1., 0.]], &space);
    publish(&mut db, doc, &space, None);
    let index = index(&db, &space);
    for text in ["", "   !", "unseen"] {
        assert!(
            index
                .search(&SearchRequest::keyword(text))
                .unwrap()
                .results
                .is_empty()
        );
    }
    let mut query = SearchRequest::keyword("alpha");
    query.limit = 0;
    let result = index.search(&query).unwrap();
    assert!(result.results.is_empty());
    assert_eq!(result.fused.len(), 1);
}

#[test]
fn replacement_deletion_and_recovery_publish_consistent_search_generations() {
    let (dir, mut db) = database();
    let space = space(2);
    let old_doc = document(
        &mut db,
        "a",
        "r1",
        &["old keyword"],
        vec![vec![1., 0.]],
        &space,
    );
    publish(&mut db, old_doc, &space, None);
    let old = index(&db, &space);
    let replacement = document(
        &mut db,
        "a",
        "r2",
        &["new keyword"],
        vec![vec![0., 1.]],
        &space,
    );
    publish(&mut db, replacement, &space, Some("r1"));
    let current = index(&db, &space);
    assert!(
        current
            .search(&SearchRequest::keyword("old"))
            .unwrap()
            .results
            .is_empty()
    );
    assert_eq!(
        old.search(&SearchRequest::keyword("old")).unwrap().results[0]
            .key
            .revision,
        "r1"
    );
    let expected = current.search(&dense(&space, vec![0., 1.])).unwrap();
    assert_eq!(expected.results[0].key.revision, "r2");
    db.checkpoint().unwrap();
    drop(db);
    let mut db = Database::open(dir.path()).unwrap();
    assert_eq!(
        index(&db, &space)
            .search(&dense(&space, vec![0., 1.]))
            .unwrap(),
        expected
    );
    db.commit(Batch {
        operation_id: "delete".into(),
        spaces: vec![],
        mutations: vec![Mutation::Delete {
            document_id: "a".into(),
            expected_revision: "r2".into(),
        }],
    })
    .unwrap();
    assert!(
        index(&db, &space)
            .search(&SearchRequest::keyword("keyword"))
            .unwrap()
            .results
            .is_empty()
    );
    assert_eq!(
        current
            .search(&SearchRequest::keyword("new"))
            .unwrap()
            .results
            .len(),
        1
    );
    let old_key = old.search(&SearchRequest::keyword("old")).unwrap().results[0]
        .key
        .clone();
    assert!(current.resolve(&old_key).is_none());
    drop(db);
    assert_eq!(
        index(&Database::open(dir.path()).unwrap(), &space)
            .records()
            .count(),
        0
    );
}

#[test]
fn uncommitted_or_invalid_revision_never_enters_a_new_index() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut staged = document(
        &mut db,
        "staged",
        "r1",
        &["hidden word"],
        vec![vec![1., 0.]],
        &space,
    );
    db.commit(Batch {
        operation_id: "space".into(),
        spaces: vec![space.clone()],
        mutations: vec![],
    })
    .unwrap();
    assert!(
        index(&db, &space)
            .search(&SearchRequest::keyword("hidden"))
            .unwrap()
            .results
            .is_empty()
    );
    staged.chunks[0].vectors.clear();
    assert!(
        db.commit(Batch {
            operation_id: "bad".into(),
            spaces: vec![],
            mutations: vec![Mutation::Replace {
                expected_revision: None,
                document: Box::new(staged)
            }]
        })
        .is_err()
    );
    assert_eq!(index(&db, &space).records().count(), 0);
}

#[test]
fn search_is_read_only_and_shareable_between_threads() {
    let (_dir, db, space) = diagnostic_corpus();
    let index = std::sync::Arc::new(index(&db, &space));
    let query = SearchRequest::keyword("Argentina 1954");
    let expected = index.search(&query).unwrap();
    let threads: Vec<_> = (0..4)
        .map(|_| {
            let index = index.clone();
            let query = query.clone();
            std::thread::spawn(move || index.search(&query).unwrap())
        })
        .collect();
    for thread in threads {
        assert_eq!(thread.join().unwrap(), expected);
    }
    assert_eq!(db.snapshot().generation(), expected.generation);
}
