use super::{KeywordConfig, KeywordField, TermContribution};
use std::collections::BTreeMap;
use unicode_normalization::{UnicodeNormalization, char::is_combining_mark};

pub const TOKENIZER: &str = "nfkd-lower-alnum-v1";

pub fn tokenize(text: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut word = String::new();
    for ch in text.nfkd().flat_map(char::to_lowercase) {
        if is_combining_mark(ch) {
            continue;
        }
        if ch.is_alphanumeric() {
            word.push(ch);
        } else if !word.is_empty() {
            tokens.push(std::mem::take(&mut word));
        }
    }
    if !word.is_empty() {
        tokens.push(word);
    }
    tokens
}

struct Posting {
    row: usize,
    frequency: usize,
}

pub(super) struct FieldIndex {
    field: KeywordField,
    postings: BTreeMap<String, Vec<Posting>>,
    lengths: Vec<usize>,
    average: f64,
}

impl FieldIndex {
    pub(super) fn build<'a>(field: KeywordField, texts: impl Iterator<Item = &'a str>) -> Self {
        let mut postings: BTreeMap<String, Vec<Posting>> = BTreeMap::new();
        let mut lengths = Vec::new();
        let mut total = 0.0;
        for (row, text) in texts.enumerate() {
            let tokens = tokenize(text);
            lengths.push(tokens.len());
            total += tokens.len() as f64;
            let mut frequencies = BTreeMap::new();
            for term in tokens {
                *frequencies.entry(term).or_insert(0) += 1;
            }
            for (term, frequency) in frequencies {
                postings
                    .entry(term)
                    .or_default()
                    .push(Posting { row, frequency });
            }
        }
        let average = if lengths.is_empty() {
            0.0
        } else {
            total / lengths.len() as f64
        };
        Self {
            field,
            postings,
            lengths,
            average,
        }
    }

    pub(super) fn score(
        &self,
        terms: &[String],
        eligible: &[bool],
        config: &KeywordConfig,
        scores: &mut [f64],
        details: &mut BTreeMap<usize, Vec<TermContribution>>,
    ) {
        let weight = config.weight(self.field);
        if weight == 0.0 || self.average == 0.0 {
            return;
        }
        let n = self.lengths.len();
        for term in terms {
            let Some(postings) = self.postings.get(term) else {
                continue;
            };
            let df = postings.len();
            let idf = (1.0 + (n as f64 - df as f64 + 0.5) / (df as f64 + 0.5)).ln();
            for posting in postings {
                if !eligible[posting.row] {
                    continue;
                }
                let length = self.lengths[posting.row];
                let tf = posting.frequency as f64;
                let score = weight * idf * tf * (config.k1 + 1.0)
                    / (tf + config.k1 * (1.0 - config.b + config.b * length as f64 / self.average));
                scores[posting.row] += score;
                details
                    .entry(posting.row)
                    .or_default()
                    .push(TermContribution {
                        field: self.field,
                        term: term.clone(),
                        frequency: posting.frequency,
                        document_frequency: df,
                        corpus_chunks: n,
                        length,
                        average_length: self.average,
                        idf,
                        score,
                    });
            }
        }
    }
}
