use crate::{
    Result,
    contracts::{Chunk, Derivation, DocumentRevision, MediaType},
    require,
};
use num_bigint::BigInt;
use serde::{Deserialize, Serialize};
use serde_json::{Number, Value};
use std::{cmp::Ordering, collections::BTreeSet, str::FromStr};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Truth {
    True,
    False,
    Unknown,
}

impl From<bool> for Truth {
    fn from(value: bool) -> Self {
        if value { Self::True } else { Self::False }
    }
}

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub enum AttributeTrust {
    #[default]
    SourceOrDeterministic,
    Any,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Bound {
    pub value: Number,
    pub inclusive: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Predicate {
    Exists,
    Missing,
    Eq(Value),
    NumericRange {
        min: Option<Bound>,
        max: Option<Bound>,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Filter {
    All(Vec<Filter>),
    Any(Vec<Filter>),
    Not(Box<Filter>),
    DocumentIds(BTreeSet<String>),
    MediaType(MediaType),
    Attribute {
        key: String,
        pointer: String,
        predicate: Predicate,
        trust: AttributeTrust,
    },
}

impl Default for Filter {
    fn default() -> Self {
        Self::All(vec![])
    }
}

impl Filter {
    pub fn validate(&self) -> Result<()> {
        let mut pending = vec![(self, 1)];
        let mut nodes = 0;
        while let Some((filter, depth)) = pending.pop() {
            nodes += 1;
            require(
                nodes <= 1024 && depth <= 32,
                "filter exceeds node/depth limit",
            )?;
            match filter {
                Self::All(children) | Self::Any(children) => {
                    require(
                        nodes + pending.len() + children.len() <= 1024,
                        "filter exceeds node limit",
                    )?;
                    pending.extend(children.iter().map(|f| (f, depth + 1)));
                }
                Self::Not(child) => pending.push((child, depth + 1)),
                Self::Attribute {
                    pointer, predicate, ..
                } => {
                    let mut chars = pointer.chars();
                    require(
                        pointer.is_empty() || pointer.starts_with('/'),
                        "invalid filter JSON pointer",
                    )?;
                    while let Some(c) = chars.next() {
                        require(
                            c != '~' || matches!(chars.next(), Some('0' | '1')),
                            "invalid filter JSON pointer escape",
                        )?;
                    }
                    if let Predicate::NumericRange { min, max } = predicate {
                        require(
                            min.is_some() || max.is_some(),
                            "numeric range requires a bound",
                        )?;
                        if let (Some(min), Some(max)) = (min, max) {
                            let order = numeric_cmp(&min.value, &max.value);
                            require(
                                order == Ordering::Less
                                    || (order == Ordering::Equal && min.inclusive && max.inclusive),
                                "empty/reversed numeric range",
                            )?;
                        }
                    }
                }
                _ => (),
            }
        }
        Ok(())
    }

    pub fn test(&self, document: &DocumentRevision, chunk: &Chunk) -> Result<Truth> {
        self.validate()?;
        Ok(self.evaluate(document, chunk))
    }

    pub(super) fn evaluate(&self, document: &DocumentRevision, chunk: &Chunk) -> Truth {
        match self {
            Self::All(children) => {
                let mut result = Truth::True;
                for child in children {
                    match child.evaluate(document, chunk) {
                        Truth::False => return Truth::False,
                        Truth::Unknown => result = Truth::Unknown,
                        Truth::True => (),
                    }
                }
                result
            }
            Self::Any(children) => {
                let mut result = Truth::False;
                for child in children {
                    match child.evaluate(document, chunk) {
                        Truth::True => return Truth::True,
                        Truth::Unknown => result = Truth::Unknown,
                        Truth::False => (),
                    }
                }
                result
            }
            Self::Not(child) => match child.evaluate(document, chunk) {
                Truth::True => Truth::False,
                Truth::False => Truth::True,
                Truth::Unknown => Truth::Unknown,
            },
            Self::DocumentIds(ids) => ids.contains(&document.document_id).into(),
            Self::MediaType(media) => (&document.media_type == media).into(),
            Self::Attribute {
                key,
                pointer,
                predicate,
                trust,
            } => {
                let attribute = chunk.attributes.get(key);
                if *trust == AttributeTrust::SourceOrDeterministic
                    && attribute
                        .is_some_and(|a| matches!(a.derivation, Derivation::Generated { .. }))
                {
                    return Truth::Unknown;
                }
                let value = attribute.and_then(|a| a.value.pointer(pointer));
                match predicate {
                    Predicate::Exists => value.is_some().into(),
                    Predicate::Missing => value.is_none().into(),
                    Predicate::Eq(expected) => value.map_or(Truth::Unknown, |actual| {
                        exact_equal(actual, expected).into()
                    }),
                    Predicate::NumericRange { min, max } => {
                        let Some(Value::Number(number)) = value else {
                            return Truth::Unknown;
                        };
                        let lower = min.as_ref().is_none_or(|bound| {
                            let order = numeric_cmp(number, &bound.value);
                            order == Ordering::Greater
                                || (order == Ordering::Equal && bound.inclusive)
                        });
                        let upper = max.as_ref().is_none_or(|bound| {
                            let order = numeric_cmp(number, &bound.value);
                            order == Ordering::Less || (order == Ordering::Equal && bound.inclusive)
                        });
                        (lower && upper).into()
                    }
                }
            }
        }
    }
}

fn exact_equal(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(a), Value::Number(b)) => numeric_cmp(a, b) == Ordering::Equal,
        (Value::Array(a), Value::Array(b)) => {
            a.len() == b.len() && a.iter().zip(b).all(|(a, b)| exact_equal(a, b))
        }
        (Value::Object(a), Value::Object(b)) => {
            a.len() == b.len()
                && a.iter()
                    .all(|(key, a)| b.get(key).is_some_and(|b| exact_equal(a, b)))
        }
        _ => a == b,
    }
}

// Compare scientific decimal representations without rounding or expanding a
// potentially enormous exponent into zeros. BigInt is used only for the exponent.
pub(super) fn numeric_cmp(a: &Number, b: &Number) -> Ordering {
    fn parts(number: &Number) -> (i8, BigInt, String) {
        let text = number.to_string();
        let negative = text.starts_with('-');
        let unsigned = text.trim_start_matches('-');
        let (mantissa, exponent) = unsigned.split_once(['e', 'E']).unwrap_or((unsigned, "0"));
        let exponent =
            BigInt::from_str(exponent).expect("serde_json Number has a valid decimal exponent");
        let fraction = mantissa.split_once('.').map_or(0, |(_, part)| part.len());
        let digits = mantissa.replace('.', "").trim_start_matches('0').to_owned();
        if digits.is_empty() {
            return (0, BigInt::from(0), String::new());
        }
        let magnitude = exponent - BigInt::from(fraction) + BigInt::from(digits.len());
        (
            if negative { -1 } else { 1 },
            magnitude,
            digits.trim_end_matches('0').to_owned(),
        )
    }
    let (sign_a, magnitude_a, digits_a) = parts(a);
    let (sign_b, magnitude_b, digits_b) = parts(b);
    let signs = sign_a.cmp(&sign_b);
    if signs != Ordering::Equal || sign_a == 0 {
        return signs;
    }
    let absolute = magnitude_a.cmp(&magnitude_b).then_with(|| {
        let width = digits_a.len().max(digits_b.len());
        digits_a
            .bytes()
            .chain(std::iter::repeat(b'0'))
            .take(width)
            .cmp(digits_b.bytes().chain(std::iter::repeat(b'0')).take(width))
    });
    if sign_a < 0 {
        absolute.reverse()
    } else {
        absolute
    }
}
