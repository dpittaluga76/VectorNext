//! Mechanical prose support, using exact spellings rather than floating point.
//! English comma grouping is the only numeric spelling transformation. Dates
//! and complete unsigned ranges supply boundary exceptions, never inferred values.
use serde_json::Number;

pub(super) fn supported(source: &str, quote: &str, value: &Number) -> bool {
    let literal = value.to_string();
    let grouped = grouped_spelling(&literal);
    source.match_indices(quote).any(|(offset, _)| {
        [Some(literal.as_str()), grouped.as_deref()]
            .into_iter()
            .flatten()
            .any(|spelling| {
                quote.match_indices(spelling).any(|(start, _)| {
                    let start = offset + start;
                    boundaries(source, start, start + spelling.len())
                        || range_endpoint(source, start, start + spelling.len())
                })
            })
    })
}

// Inspect full source spans, including characters clipped out of the proof quote.
// Only two unsigned endpoints are admitted. Signs, identifiers, dates and longer
// numeric chains fail the same outer-boundary checks as standalone numbers.
fn range_endpoint(source: &str, start: usize, end: usize) -> bool {
    source.char_indices().any(|(left, c)| {
        if !c.is_ascii_digit()
            || source[..left]
                .chars()
                .next_back()
                .is_some_and(|p| word(p) || matches!(p, '.' | ','))
        {
            return false;
        }
        let left_end = unsigned_end(source, left);
        let rest = &source[left_end..];
        let trimmed = rest.trim_start_matches(horizontal);
        let after_separator = if let Some(tail) = trimmed.strip_prefix(['-', '\u{2013}']) {
            tail
        } else if rest.len() != trimmed.len() {
            match trimmed.strip_prefix("to") {
                Some(tail) if tail.chars().next().is_some_and(horizontal) => tail,
                _ => return false,
            }
        } else {
            return false;
        };
        let right_text = after_separator.trim_start_matches(horizontal);
        let right = source.len() - right_text.len();
        let right_end = unsigned_end(source, right);
        right_end > right
            && ((start == left && end == left_end) || (start == right && end == right_end))
            && boundaries(source, left, right_end)
            && !word_range_before(&source[..left])
            && !word_range_after(&source[right_end..])
    })
}

fn unsigned_end(source: &str, start: usize) -> usize {
    let bytes = source.as_bytes();
    let mut end = start;
    while bytes.get(end).is_some_and(u8::is_ascii_digit) {
        end += 1;
    }
    if end == start {
        return start;
    }
    // Grouped integers require a 1–3 digit first group and exactly three thereafter.
    if end - start <= 3 {
        while bytes.get(end) == Some(&b',')
            && bytes
                .get(end + 1..end + 4)
                .is_some_and(|group| group.iter().all(u8::is_ascii_digit))
            && !bytes.get(end + 4).is_some_and(u8::is_ascii_digit)
        {
            end += 4;
        }
    }
    if bytes.get(end) == Some(&b'.') && bytes.get(end + 1).is_some_and(u8::is_ascii_digit) {
        end += 1;
        while bytes.get(end).is_some_and(u8::is_ascii_digit) {
            end += 1;
        }
    }
    end
}

fn word_range_before(before: &str) -> bool {
    before
        .trim_end_matches(horizontal)
        .strip_suffix("to")
        .is_some_and(|s| {
            s.chars().next_back().is_some_and(horizontal)
                && s.trim_end_matches(horizontal)
                    .chars()
                    .next_back()
                    .is_some_and(char::is_numeric)
        })
}

fn word_range_after(after: &str) -> bool {
    after
        .trim_start_matches(horizontal)
        .strip_prefix("to")
        .is_some_and(|s| {
            s.chars().next().is_some_and(horizontal)
                && s.trim_start_matches(horizontal)
                    .chars()
                    .next()
                    .is_some_and(char::is_numeric)
        })
}

fn grouped_spelling(literal: &str) -> Option<String> {
    let (sign, unsigned) = literal
        .strip_prefix('-')
        .map_or(("", literal), |rest| ("-", rest));
    let split = unsigned.find(['.', 'e', 'E']).unwrap_or(unsigned.len());
    let (integer, suffix) = unsigned.split_at(split);
    if integer.len() <= 3 {
        return None;
    }
    let mut result = String::from(sign);
    for (i, digit) in integer.char_indices() {
        if i > 0 && (integer.len() - i) % 3 == 0 {
            result.push(',');
        }
        result.push(digit);
    }
    result.push_str(suffix);
    Some(result)
}

fn horizontal(c: char) -> bool {
    c.is_whitespace() && !matches!(c, '\r' | '\n')
}

fn sign(c: char) -> bool {
    matches!(c, '-' | '+' | '\u{2212}' | '\u{00b1}')
}

fn word(c: char) -> bool {
    c.is_alphanumeric() || c == '_' || unicode_normalization::char::is_combining_mark(c)
}

// Reject fragments across decimal/grouping punctuation, fractions, times,
// ranges and space/apostrophe grouping. Unsupported/ambiguous notation fails
// closed, including when the submitted quote clips away that notation.
fn separator(c: char) -> bool {
    horizontal(c)
        || sign(c)
        || matches!(
            c,
            '.' | ','
                | ':'
                | '/'
                | '\''
                | '\u{2019}'
                | '\u{2044}'
                | '\u{2215}'
                | '\u{2013}'
                | '\u{2014}'
                | '\u{066b}'
                | '\u{066c}'
        )
}

fn boundaries(source: &str, start: usize, end: usize) -> bool {
    let before = &source[..start];
    let after = &source[end..];
    if after.chars().next().is_some_and(word)
        || (after.chars().next().is_some_and(separator)
            && after
                .trim_start_matches(separator)
                .chars()
                .next()
                .is_some_and(char::is_numeric))
    {
        return false;
    }
    // A trailing sentence period/comma is fine; an unfinished exponent is not.
    if after.starts_with(".e") || after.starts_with(".E") {
        return false;
    }
    if date_year(source, start, end) {
        return true;
    }
    !(before.chars().next_back().is_some_and(word)
        || before
            .trim_end_matches(horizontal)
            .chars()
            .next_back()
            .is_some_and(sign)
        || before
            .chars()
            .next_back()
            .is_some_and(|c| matches!(c, '.' | ',' | '\u{066b}' | '\u{066c}'))
        || (before.chars().next_back().is_some_and(separator)
            && before
                .trim_end_matches(separator)
                .chars()
                .next_back()
                .is_some_and(char::is_numeric)))
}

fn date_year(source: &str, start: usize, end: usize) -> bool {
    let year = &source[start..end];
    if year.len() != 4 || !year.bytes().all(|b| b.is_ascii_digit()) {
        return false;
    }
    let prefix = source[..start].trim_end_matches(horizontal);
    let Some(prefix) = prefix.strip_suffix(',') else {
        return false;
    };
    let prefix = prefix.trim_end_matches(horizontal);
    let day_start = prefix
        .rfind(|c: char| !c.is_ascii_digit())
        .map_or(0, |i| i + prefix[i..].chars().next().unwrap().len_utf8());
    let day = &prefix[day_start..];
    if day.is_empty() || day.len() > 2 {
        return false;
    }
    let month = &prefix[..day_start];
    if !month.chars().next_back().is_some_and(horizontal) {
        return false;
    }
    let month = month.trim_end_matches(horizontal);
    let month = month.strip_suffix('.').unwrap_or(month);
    let month_start = month
        .rfind(|c: char| !c.is_ascii_alphabetic())
        .map_or(0, |i| i + month[i..].chars().next().unwrap().len_utf8());
    if month[..month_start].chars().next_back().is_some_and(word) {
        return false;
    }
    let year: u16 = year.parse().unwrap();
    let max_day = match month[month_start..].to_ascii_lowercase().as_str() {
        "jan" | "january" | "mar" | "march" | "may" | "jul" | "july" | "aug" | "august" | "oct"
        | "october" | "dec" | "december" => 31,
        "apr" | "april" | "jun" | "june" | "sep" | "sept" | "september" | "nov" | "november" => 30,
        "feb" | "february" => {
            if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) {
                29
            } else {
                28
            }
        }
        _ => return false,
    };
    let day: u8 = day.parse().unwrap();
    year != 0 && day > 0 && day <= max_day
}

#[cfg(test)]
mod tests {
    use super::*;

    fn check(source: &str, quote: &str, value: &str) -> bool {
        supported(source, quote, &serde_json::from_str(value).unwrap())
    }

    #[test]
    fn exact_unsigned_range_endpoints_preserve_quotes_and_values() {
        for separator in ["-", "–", " - ", " – ", " to "] {
            let source = format!("Mission operated (1977{separator}1980).");
            for endpoint in ["1977", "1980"] {
                assert!(check(&source, endpoint, endpoint), "{source}: {endpoint}");
                assert!(check(&source, &source, endpoint));
            }
            assert!(!check(&source, "197", "197"));
            assert!(!check(&source, &source, "1978"));
        }
        for (source, quote, value) in [
            ("Range 0–3.", "0", "0"),
            ("Range 1.25–2.75.", "2.75", "2.75"),
            ("Range 1,000–2,000.", "1,000", "1000"),
            (
                "Range 9007199254740993–9007199254740999.",
                "9007199254740993",
                "9007199254740993",
            ),
        ] {
            assert!(check(source, quote, value), "{source}");
        }
    }

    #[test]
    fn range_exceptions_do_not_admit_signs_dates_identifiers_or_clipped_numbers() {
        for (source, quote, value) in [
            ("-1977–1980", "1980", "1980"),
            ("+1977–1980", "1977", "1977"),
            ("−1977–1980", "1980", "1980"),
            ("1977–-1980", "1977", "1977"),
            ("-10--5", "5", "5"),
            ("1977-01-01", "1977", "1977"),
            ("1977-01-01", "01", "1"),
            ("1977–1980–1982", "1980", "1980"),
            ("1977–1980 to 1982", "1977", "1977"),
            ("1970 to 1977–1980", "1980", "1980"),
            ("ID1977–1980", "1980", "1980"),
            ("1977–1980x", "1977", "1977"),
            ("id_1977–1980", "1980", "1980"),
            ("é1977–1980", "1980", "1980"),
            ("1.25–2.75", "25", "25"),
            ("1.25–2.75", "2", "2"),
            ("1,000–2,000", "1", "1"),
            ("1,00–2,000", "2,000", "2000"),
            ("3e-4", "4", "4"),
            ("1.2.3-4", "4", "4"),
            ("1977–1980/2", "1977", "1977"),
        ] {
            assert!(!check(source, quote, value), "{source}: {quote} -> {value}");
        }
    }
}
