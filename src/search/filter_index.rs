//! Bounded immutable scalar postings. Unsupported predicates retain the scan oracle.
use super::{AttributeTrust, Filter, Predicate, Row, Truth, filter::numeric_cmp};
use crate::contracts::{Derivation, MediaType};
use serde::Serialize;
use serde_json::{Number, Value};
use std::{
    cmp::Ordering,
    collections::{BTreeMap, BTreeSet},
};

const MAX_COLUMNS: usize = 32;
const MAX_VALUES: usize = 4096;
const MAX_KEY_BYTES: usize = 16 * 1024;
const MAX_TOTAL_KEY_BYTES: usize = 1024 * 1024;
const MAX_POSTINGS: usize = 1_000_000;

#[derive(Clone, Debug)]
enum Scalar {
    Null,
    Bool(bool),
    Number(Number),
    String(String),
}
impl Scalar {
    fn from(value: &Value) -> Option<Self> {
        Some(match value {
            Value::Null => Self::Null,
            Value::Bool(v) => Self::Bool(*v),
            Value::Number(v) => Self::Number(v.clone()),
            Value::String(v) if v.len() <= MAX_KEY_BYTES => Self::String(v.clone()),
            _ => return None,
        })
    }
    fn bytes(&self) -> usize {
        match self {
            Self::Null | Self::Bool(_) => 1,
            Self::Number(v) => v.to_string().len(),
            Self::String(v) => v.len(),
        }
    }
    fn tag(&self) -> u8 {
        match self {
            Self::Null => 0,
            Self::Bool(_) => 1,
            Self::Number(_) => 2,
            Self::String(_) => 3,
        }
    }
}
impl Ord for Scalar {
    fn cmp(&self, other: &Self) -> Ordering {
        match (self, other) {
            (Self::Number(a), Self::Number(b)) => numeric_cmp(a, b),
            (Self::Bool(a), Self::Bool(b)) => a.cmp(b),
            (Self::String(a), Self::String(b)) => a.cmp(b),
            _ => self.tag().cmp(&other.tag()),
        }
    }
}
impl PartialOrd for Scalar {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl PartialEq for Scalar {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}
impl Eq for Scalar {}

#[derive(Default)]
struct Column {
    values: BTreeMap<Scalar, Vec<usize>>,
    generated: Vec<usize>,
    postings: usize,
    key_bytes: usize,
}
#[derive(Debug, Default, Serialize)]
pub struct FilterIndexStats {
    pub indexed_columns: usize,
    pub attribute_postings: usize,
    pub scalar_key_bytes: usize,
    pub document_postings: usize,
    pub media_postings: usize,
}
#[derive(Default)]
pub(super) struct FilterIndex {
    documents: BTreeMap<String, Vec<usize>>,
    media: [Vec<usize>; 3],
    columns: BTreeMap<String, Column>,
    stats: FilterIndexStats,
}
fn media_id(media: &MediaType) -> usize {
    match media {
        MediaType::Txt => 0,
        MediaType::Pdf => 1,
        MediaType::Json => 2,
    }
}
impl FilterIndex {
    pub(super) fn stats(&self) -> &FilterIndexStats {
        &self.stats
    }
    pub(super) fn build(rows: &[Row]) -> Self {
        let mut index = Self::default();
        let mut names = BTreeSet::new();
        for (i, row) in rows.iter().enumerate() {
            index
                .documents
                .entry(row.document.document_id.clone())
                .or_default()
                .push(i);
            index.media[media_id(&row.document.media_type)].push(i);
            for name in row.chunk().attributes.keys() {
                if name.len() <= MAX_KEY_BYTES {
                    names.insert(name.clone());
                    if names.len() > MAX_COLUMNS {
                        names.pop_last();
                    }
                }
            }
        }
        index.stats.document_postings = rows.len();
        index.stats.media_postings = rows.len();
        for name in names {
            if let Some(column) = Self::column(rows, &name, &index.stats) {
                index.stats.attribute_postings += column.postings;
                index.stats.scalar_key_bytes += column.key_bytes;
                index.columns.insert(name, column);
            }
        }
        index.stats.indexed_columns = index.columns.len();
        index
    }
    fn column(rows: &[Row], name: &str, used: &FilterIndexStats) -> Option<Column> {
        let mut column = Column {
            key_bytes: name.len(),
            ..Default::default()
        };
        for (i, row) in rows.iter().enumerate() {
            let Some(attribute) = row.chunk().attributes.get(name) else {
                continue;
            };
            let key = Scalar::from(&attribute.value)?;
            let bytes = key.bytes();
            if bytes > MAX_KEY_BYTES {
                return None;
            }
            if !column.values.contains_key(&key) {
                column.key_bytes += bytes;
            }
            column.postings += 1;
            if matches!(attribute.derivation, Derivation::Generated { .. }) {
                column.generated.push(i);
                column.postings += 1;
            }
            if column.key_bytes + used.scalar_key_bytes > MAX_TOTAL_KEY_BYTES
                || column.postings + used.attribute_postings > MAX_POSTINGS
            {
                return None;
            }
            column.values.entry(key).or_default().push(i);
            if column.values.len() > MAX_VALUES {
                return None;
            }
        }
        Some(column)
    }
    pub(super) fn evaluate(&self, filter: &Filter, rows: &[Row]) -> Vec<Truth> {
        match filter {
            Filter::All(children) | Filter::Any(children) => {
                let all = matches!(filter, Filter::All(_));
                let mut result = vec![if all { Truth::True } else { Truth::False }; rows.len()];
                for child in children {
                    let decisions = self.evaluate(child, rows);
                    for (a, b) in result.iter_mut().zip(decisions) {
                        *a = match (*a, b, all) {
                            (Truth::False, _, true) | (_, Truth::False, true) => Truth::False,
                            (Truth::True, _, false) | (_, Truth::True, false) => Truth::True,
                            (Truth::Unknown, _, _) | (_, Truth::Unknown, _) => Truth::Unknown,
                            _ => {
                                if all {
                                    Truth::True
                                } else {
                                    Truth::False
                                }
                            }
                        };
                    }
                }
                result
            }
            Filter::Not(child) => self
                .evaluate(child, rows)
                .into_iter()
                .map(|v| match v {
                    Truth::True => Truth::False,
                    Truth::False => Truth::True,
                    Truth::Unknown => Truth::Unknown,
                })
                .collect(),
            Filter::DocumentIds(ids) => {
                let mut result = vec![Truth::False; rows.len()];
                for id in ids {
                    if let Some(postings) = self.documents.get(id) {
                        for &i in postings {
                            result[i] = Truth::True;
                        }
                    }
                }
                result
            }
            Filter::MediaType(media) => {
                let mut result = vec![Truth::False; rows.len()];
                for &i in &self.media[media_id(media)] {
                    result[i] = Truth::True;
                }
                result
            }
            Filter::Attribute {
                key,
                pointer,
                predicate,
                trust,
            } if pointer.is_empty() => {
                if let Some(column) = self.columns.get(key) {
                    if let Some(mut result) = column.evaluate(predicate, rows.len()) {
                        if *trust == AttributeTrust::SourceOrDeterministic {
                            for &i in &column.generated {
                                result[i] = Truth::Unknown;
                            }
                        }
                        return result;
                    }
                }
                Self::scan(filter, rows)
            }
            _ => Self::scan(filter, rows),
        }
    }
    fn scan(filter: &Filter, rows: &[Row]) -> Vec<Truth> {
        rows.iter()
            .map(|r| filter.evaluate(&r.document, r.chunk()))
            .collect()
    }
}
impl Column {
    fn evaluate(&self, predicate: &Predicate, count: usize) -> Option<Vec<Truth>> {
        let mut result = vec![
            match predicate {
                Predicate::Exists => Truth::False,
                Predicate::Missing => Truth::True,
                _ => Truth::Unknown,
            };
            count
        ];
        match predicate {
            Predicate::Exists | Predicate::Missing => {
                for postings in self.values.values() {
                    for &i in postings {
                        result[i] = if matches!(predicate, Predicate::Exists) {
                            Truth::True
                        } else {
                            Truth::False
                        };
                    }
                }
            }
            Predicate::Eq(value) => {
                let key = Scalar::from(value)?;
                for postings in self.values.values() {
                    for &i in postings {
                        result[i] = Truth::False;
                    }
                }
                if let Some(postings) = self.values.get(&key) {
                    for &i in postings {
                        result[i] = Truth::True;
                    }
                }
            }
            Predicate::NumericRange { min, max } => {
                for (key, postings) in &self.values {
                    let Scalar::Number(number) = key else {
                        continue;
                    };
                    let lower = min.as_ref().is_none_or(|b| {
                        let o = numeric_cmp(number, &b.value);
                        o == Ordering::Greater || (o == Ordering::Equal && b.inclusive)
                    });
                    let upper = max.as_ref().is_none_or(|b| {
                        let o = numeric_cmp(number, &b.value);
                        o == Ordering::Less || (o == Ordering::Equal && b.inclusive)
                    });
                    for &i in postings {
                        result[i] = (lower && upper).into();
                    }
                }
            }
        }
        Some(result)
    }
}
