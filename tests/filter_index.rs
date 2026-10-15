#![cfg(target_os = "linux")]
mod support;
use serde_json::{Number, Value, json};
use std::{collections::BTreeSet, str::FromStr, sync::Arc};
use support::*;
use vectornext::{contracts::*, search::*};

fn atom(predicate: Predicate, trust: AttributeTrust) -> Filter {
    Filter::Attribute {
        key: "root".into(),
        pointer: String::new(),
        predicate,
        trust,
    }
}
fn fallback(filter: &Filter) -> Filter {
    match filter {
        Filter::Attribute {
            key,
            pointer,
            predicate,
            trust,
        } if key == "root" && pointer.is_empty() => Filter::Attribute {
            key: "copy".into(),
            pointer: "/v".into(),
            predicate: predicate.clone(),
            trust: *trust,
        },
        Filter::All(v) => Filter::All(v.iter().map(fallback).collect()),
        Filter::Any(v) => Filter::Any(v.iter().map(fallback).collect()),
        Filter::Not(v) => Filter::Not(Box::new(fallback(v))),
        _ => filter.clone(),
    }
}
fn verify(index: &SearchIndex, filter: Filter) {
    let expected: Vec<_> = index
        .records()
        .map(|(key, doc, chunk)| Eligibility {
            key: key.clone(),
            decision: filter.test(doc, chunk).unwrap(),
        })
        .collect();
    for trace in [false, true] {
        let mut request = SearchRequest::keyword("common evidence");
        request.filter = filter.clone();
        request.trace_eligibility = trace;
        let actual = index.search(&request).unwrap();
        assert_eq!(
            actual.eligible_chunks,
            expected
                .iter()
                .filter(|x| x.decision == Truth::True)
                .count()
        );
        assert_eq!(
            actual.unknown_filter_chunks,
            expected
                .iter()
                .filter(|x| x.decision == Truth::Unknown)
                .count()
        );
        if trace {
            assert_eq!(actual.eligibility.as_ref().unwrap(), &expected);
        }
        request.filter = fallback(&filter);
        let mut scanned = index.search(&request).unwrap();
        scanned.request = actual.request.clone();
        assert_eq!(actual, scanned);
    }
}

#[test]
fn indexed_scalar_boolean_and_trust_results_equal_scan_with_exact_values() {
    let (_dir, mut db) = database();
    let space = space(2);
    let values: Vec<Option<Value>> = vec![
        None,
        Some(Value::Null),
        Some(json!(false)),
        Some(json!(true)),
        Some(json!("007")),
        Some(json!("")),
        Some(json!(0)),
        Some(json!(-7)),
        Some(json!(7)),
        Some(serde_json::from_str("9007199254740993.00").unwrap()),
        Some(serde_json::from_str("0.12345678901234567890123456789").unwrap()),
        Some(serde_json::from_str("1e99999999999999999999").unwrap()),
        Some(serde_json::from_str("-1e-99999999999999999999").unwrap()),
        Some(serde_json::from_str("0e99999999999999999").unwrap()),
    ];
    for generated in [false, true] {
        let texts = vec!["common evidence"; values.len()];
        let mut doc = document(
            &mut db,
            if generated { "generated" } else { "source" },
            "r1",
            &texts,
            vec![vec![1., 0.]; values.len()],
            &space,
        );
        for (i, value) in values.iter().enumerate() {
            if let Some(value) = value {
                attribute(&mut doc, i, "root", value.clone());
                attribute(&mut doc, i, "copy", json!({"v":value}));
                if generated {
                    for a in doc.chunks[i].attributes.values_mut() {
                        a.derivation = Derivation::Generated {
                            model: "fixture".into(),
                            prompt_version: "v1".into(),
                        };
                    }
                }
            }
        }
        publish(&mut db, doc, &space, None);
    }
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    assert_eq!(index.filter_index_stats().indexed_columns, 1);
    let mut atoms = vec![
        Filter::default(),
        Filter::Any(vec![]),
        Filter::MediaType(MediaType::Txt),
        Filter::MediaType(MediaType::Json),
        Filter::DocumentIds(BTreeSet::from(["source".into()])),
    ];
    for trust in [AttributeTrust::Any, AttributeTrust::SourceOrDeterministic] {
        for value in values.iter().flatten().cloned().chain([
            json!([]),
            json!({"x":1}),
            serde_json::from_str("9007199254740993").unwrap(),
            serde_json::from_str("1.2345678901234567890123456789e-1").unwrap(),
        ]) {
            atoms.push(atom(Predicate::Eq(value), trust));
        }
        atoms.push(atom(Predicate::Exists, trust));
        atoms.push(atom(Predicate::Missing, trust));
        for (min, max, inclusive) in [
            (Some("0"), Some("7"), true),
            (Some("0"), Some("7"), false),
            (None, Some("0"), true),
            (Some("9007199254740993"), None, true),
        ] {
            atoms.push(atom(
                Predicate::NumericRange {
                    min: min.map(|v| Bound {
                        value: Number::from_str(v).unwrap(),
                        inclusive,
                    }),
                    max: max.map(|v| Bound {
                        value: Number::from_str(v).unwrap(),
                        inclusive,
                    }),
                },
                trust,
            ));
        }
    }
    for a in &atoms {
        verify(&index, a.clone());
        verify(&index, Filter::Not(Box::new(a.clone())));
        for b in &atoms {
            verify(&index, Filter::All(vec![a.clone(), b.clone()]));
            verify(
                &index,
                Filter::Any(vec![a.clone(), Filter::Not(Box::new(b.clone()))]),
            );
        }
    }
}

#[test]
fn scalar_index_budget_falls_back_without_partial_columns() {
    for scenario in [
        "cardinality",
        "key_bytes",
        "key_size",
        "column_count",
        "container",
    ] {
        let (_dir, mut db) = database();
        let space = space(2);
        let count = match scenario {
            "cardinality" => 4097,
            "key_bytes" => 70,
            _ => 2,
        };
        let mut doc = document(
            &mut db,
            "budget",
            "r1",
            &vec!["common evidence"; count],
            vec![vec![1., 0.]; count],
            &space,
        );
        for i in 0..count {
            let value = match scenario {
                "key_bytes" => json!(format!("{i:03}{}", "x".repeat(16000))),
                "key_size" => json!("x".repeat(16385)),
                "container" if i == 1 => json!({"v":1}),
                _ => json!(i),
            };
            attribute(&mut doc, i, "root", value.clone());
            attribute(&mut doc, i, "copy", json!({"v":value}));
            if scenario == "column_count" {
                for n in 0..33 {
                    attribute(&mut doc, i, &format!("a{n:02}"), json!(n));
                }
            }
        }
        publish(&mut db, doc, &space, None);
        let index =
            SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
        assert_eq!(
            index.filter_index_stats().indexed_columns,
            if scenario == "column_count" { 32 } else { 0 },
            "{scenario}"
        );
        verify(&index, atom(Predicate::Exists, AttributeTrust::Any));
        verify(&index, atom(Predicate::Eq(json!(0)), AttributeTrust::Any));
    }
}

#[test]
fn indexed_filters_remain_revision_scoped_across_replacement_deletion_and_threads() {
    let (_dir, mut db) = database();
    let space = space(2);
    let mut retained = Vec::new();
    for (revision, value, expected) in [("r1", 1, None), ("r2", 2, Some("r1"))] {
        let mut doc = document(
            &mut db,
            "changing",
            revision,
            &["common evidence"],
            vec![vec![1., 0.]],
            &space,
        );
        attribute(&mut doc, 0, "root", json!(value));
        attribute(&mut doc, 0, "copy", json!({"v":value}));
        publish(&mut db, doc, &space, expected);
        let index = Arc::new(
            SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap(),
        );
        let threads: Vec<_> = (0..4)
            .map(|_| {
                let index = index.clone();
                std::thread::spawn(move || {
                    verify(
                        &index,
                        atom(Predicate::Eq(json!(value)), AttributeTrust::Any),
                    )
                })
            })
            .collect();
        for thread in threads {
            thread.join().unwrap();
        }
        retained.push((value, index.clone()));
        if revision == "r2" {
            db.commit(Batch {
                operation_id: "remove".into(),
                spaces: vec![],
                mutations: vec![Mutation::Delete {
                    document_id: "changing".into(),
                    expected_revision: "r2".into(),
                }],
            })
            .unwrap();
            verify(&index, atom(Predicate::Eq(json!(2)), AttributeTrust::Any));
            let empty =
                SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
            assert_eq!(empty.filter_index_stats().attribute_postings, 0);
            verify(&empty, atom(Predicate::Eq(json!(2)), AttributeTrust::Any));
        }
    }
    for (value, index) in retained {
        verify(
            &index,
            atom(Predicate::Eq(json!(value)), AttributeTrust::Any),
        );
        let mut request = SearchRequest::keyword("common");
        request.filter = atom(Predicate::Eq(json!(value)), AttributeTrust::Any);
        assert_eq!(index.search(&request).unwrap().eligible_chunks, 1);
    }
}
