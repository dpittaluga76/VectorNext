#![allow(dead_code)]
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use tempfile::TempDir;
use vectornext::{Database, contracts::*};

pub fn space(dimensions: usize) -> EmbeddingSpace {
    EmbeddingSpace {
        model: "synthetic/supplied-search-vectors".into(),
        revision: "t04-v1".into(),
        artifact_sha256: "b".repeat(64),
        tokenizer: "none-supplied-vectors-v1".into(),
        preprocessing: "identity-v1".into(),
        dimensions,
        max_tokens: 256,
        query_prefix: String::new(),
        document_prefix: String::new(),
        normalization: Normalization::None,
    }
}

pub fn database() -> (TempDir, Database) {
    let dir = TempDir::new().unwrap();
    let db = Database::open(dir.path()).unwrap();
    (dir, db)
}

pub fn document(
    db: &mut Database,
    id: &str,
    revision: &str,
    texts: &[&str],
    vectors: Vec<Vec<f32>>,
    space: &EmbeddingSpace,
) -> DocumentRevision {
    assert_eq!(texts.len(), vectors.len());
    let original = db.put_original(texts.join("\n").as_bytes()).unwrap();
    let mut blocks = vec![];
    let mut chunks = vec![];
    let mut start = 0;
    for (i, (text, vector)) in texts.iter().zip(vectors).enumerate() {
        let source = SourceRef {
            revision: revision.into(),
            locator: Locator::Text {
                encoding: "UTF-8".into(),
                bytes: ByteRange {
                    start,
                    end: start + text.len() as u64,
                },
                line_start: (i + 1) as u64,
                line_end: (i + 1) as u64,
                mappings: vec![TextMapping {
                    normalized: ByteRange {
                        start,
                        end: start + text.len() as u64,
                    },
                    original: ByteRange {
                        start,
                        end: start + text.len() as u64,
                    },
                }],
            },
        };
        let block_id = format!("b{i}");
        blocks.push(Block {
            id: block_id.clone(),
            kind: BlockKind::Paragraph,
            parent: None,
            text: (*text).into(),
            sources: vec![source.clone()],
        });
        chunks.push(Chunk {
            id: format!("c{i}"),
            spans: vec![BlockSpan {
                block_id,
                bytes: ByteRange {
                    start: 0,
                    end: text.len() as u64,
                },
            }],
            evidence: (*text).into(),
            representation: Representation::NormalizedText,
            sources: vec![source],
            structural_context: String::new(),
            generated_context: None,
            attributes: BTreeMap::new(),
            parent: None,
            previous: None,
            next: None,
            vectors: BTreeMap::from([(space.id(), vector)]),
        });
        start += text.len() as u64 + 1;
    }
    DocumentRevision {
        document_id: id.into(),
        revision: revision.into(),
        original,
        media_type: MediaType::Txt,
        processing: BTreeMap::from([(
            "fixture".into(),
            json!("t04-prepared-synthetic-records-v1"),
        )]),
        required_spaces: BTreeSet::from([space.id()]),
        blocks,
        chunks,
    }
}

pub fn attribute(document: &mut DocumentRevision, chunk: usize, key: &str, value: Value) {
    let chunk = &mut document.chunks[chunk];
    chunk.attributes.insert(
        key.into(),
        Attribute {
            value,
            sources: chunk.sources.clone(),
            derivation: Derivation::Source,
        },
    );
}

pub fn publish(
    db: &mut Database,
    document: DocumentRevision,
    space: &EmbeddingSpace,
    expected: Option<&str>,
) {
    db.commit(Batch {
        operation_id: format!("{}-{}", document.document_id, document.revision),
        spaces: vec![space.clone()],
        mutations: vec![Mutation::Replace {
            expected_revision: expected.map(str::to_owned),
            document: Box::new(document),
        }],
    })
    .unwrap();
}

pub const NEAR: &str = "Synthetic match: Pelé scored 3 goals against Argentina in 1955.";
pub const TARGET: &str = "Synthetic match: Pelé scored 3 goals against Argentina in 1954.";
pub const RIVAL: &str = "Synthetic match: Pelé scored 2 goals against Uruguay in 1954.";
pub const UNIT: &str = "Torque unit: N m.";
pub const VALUE: &str = "Connector J2 tightening value: 6.";
pub const ZERO: &str = "Synthetic match: Ivo scored 0 goals against Argentina in 1954.";

/// Prepared algorithm fixtures, not an ingestion adapter or embedding-quality benchmark.
pub fn diagnostic_corpus() -> (TempDir, Database, EmbeddingSpace) {
    let (dir, mut db) = database();
    let space = space(3);
    for (id, texts, vectors, year) in [
        ("a-near", vec![NEAR], vec![vec![1., 0., 0.]], Some(1955)),
        (
            "b-target",
            vec![TARGET],
            vec![vec![0.8, 0.6, 0.]],
            Some(1954),
        ),
        ("c-rival", vec![RIVAL], vec![vec![0.6, 0.8, 0.]], Some(1954)),
        (
            "d-maintenance",
            vec![UNIT, VALUE],
            vec![vec![0., 0., 1.], vec![0., 0.1, 0.99]],
            None,
        ),
        ("e-zero", vec![ZERO], vec![vec![0.5, 0.5, 0.2]], Some(1954)),
        (
            "f-copy",
            vec![TARGET],
            vec![vec![0.7, 0.5, 0.1]],
            Some(1954),
        ),
    ] {
        let mut doc = document(&mut db, id, "r1", &texts, vectors, &space);
        if let Some(year) = year {
            attribute(&mut doc, 0, "match.year", json!(year));
        }
        if id == "e-zero" {
            attribute(&mut doc, 0, "goals", json!(0));
        }
        if id == "b-target" {
            let mut duplicate = doc.chunks[0].clone();
            duplicate.id = "c-duplicate".into();
            doc.chunks.push(duplicate);
        }
        publish(&mut db, doc, &space, None);
    }
    (dir, db, space)
}
