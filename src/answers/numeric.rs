//! Mechanical prose support, using exact spellings rather than floating point.
//! English comma grouping is the only numeric spelling transformation. Dates
//! supply a boundary exception, not an inferred value or a source rewrite.
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
                })
            })
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
