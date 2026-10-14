use super::*;
use crate::{Error, contracts::*};
use serde::de::{self, MapAccess, SeqAccess, Visitor};
use std::{
    collections::{BTreeMap, BTreeSet},
    fmt,
};

fn range(start: usize, end: usize) -> ByteRange {
    ByteRange {
        start: start as u64,
        end: end as u64,
    }
}
fn escape(key: &str) -> String {
    key.replace('~', "~0").replace('/', "~1")
}

pub(super) fn parse(draft: &mut Draft, bytes: &[u8], config: &IngestConfig) -> Result<()> {
    require(
        sha256(bytes) == draft.document.original.sha256
            && bytes.len() as u64 == draft.document.original.bytes,
        "processor source hash mismatch",
    )?;
    match draft.document.media_type {
        MediaType::Txt => parse_text(draft, bytes),
        MediaType::Json => parse_json(draft, bytes, config),
        _ => Err(Error::Invalid("unsupported ingestion format".into())),
    }
}

fn normalize(bytes: &[u8]) -> Result<(String, Vec<TextMapping>)> {
    let start = if bytes.starts_with(&[0xef, 0xbb, 0xbf]) {
        3
    } else {
        0
    };
    let input = std::str::from_utf8(&bytes[start..])
        .map_err(|_| Error::Invalid("TXT must be valid UTF-8 (optional BOM)".into()))?;
    let mut output = String::new();
    let mut mappings: Vec<TextMapping> = vec![];
    let mut chars = input.char_indices().peekable();
    while let Some((offset, ch)) = chars.next() {
        let old_start = start + offset;
        let mut old_end = old_start + ch.len_utf8();
        let new_start = output.len();
        if ch == '\r' {
            if chars.peek().is_some_and(|(_, c)| *c == '\n') {
                chars.next();
                old_end += 1;
            }
            output.push('\n');
        } else {
            output.push(ch);
        }
        let mapping = TextMapping {
            normalized: range(new_start, output.len()),
            original: range(old_start, old_end),
        };
        if let Some(last) = mappings.last_mut() {
            // Identity runs can be clipped at any UTF-8 boundary. Nonidentity
            // CRLF mappings stay indivisible, mapping one LF to both source bytes.
            if last.normalized.end - last.normalized.start
                == last.original.end - last.original.start
                && mapping.normalized.end - mapping.normalized.start
                    == mapping.original.end - mapping.original.start
                && last.original.end == mapping.original.start
            {
                last.normalized.end = mapping.normalized.end;
                last.original.end = mapping.original.end;
                continue;
            }
        }
        mappings.push(mapping);
    }
    Ok((output, mappings))
}

fn clip_mappings(mappings: &[TextMapping], start: u64, end: u64) -> Vec<TextMapping> {
    mappings
        .iter()
        .filter_map(|m| {
            let lo = start.max(m.normalized.start);
            let hi = end.min(m.normalized.end);
            if lo >= hi {
                return None;
            }
            let original =
                if m.original.end - m.original.start == m.normalized.end - m.normalized.start {
                    ByteRange {
                        start: m.original.start + lo - m.normalized.start,
                        end: m.original.start + hi - m.normalized.start,
                    }
                } else {
                    m.original.clone()
                };
            Some(TextMapping {
                normalized: ByteRange { start: lo, end: hi },
                original,
            })
        })
        .collect()
}

fn text_source(
    revision: &str,
    normalized: &str,
    mappings: &[TextMapping],
    start: usize,
    end: usize,
) -> SourceRef {
    let maps = clip_mappings(mappings, start as u64, end as u64);
    SourceRef {
        revision: revision.into(),
        locator: Locator::Text {
            encoding: "UTF-8".into(),
            bytes: ByteRange {
                start: maps[0].original.start,
                end: maps.last().unwrap().original.end,
            },
            line_start: normalized[..start].bytes().filter(|b| *b == b'\n').count() as u64 + 1,
            line_end: normalized[..end - 1]
                .bytes()
                .filter(|b| *b == b'\n')
                .count() as u64
                + 1,
            mappings: maps,
        },
    }
}

fn heading(line: &str) -> Option<(usize, &str)> {
    let count = line.bytes().take_while(|b| *b == b'#').count();
    if (1..=6).contains(&count)
        && line.as_bytes().get(count) == Some(&b' ')
        && !line[count + 1..].trim().is_empty()
    {
        Some((count, line[count + 1..].trim()))
    } else {
        None
    }
}
fn list(line: &str) -> bool {
    let line = line.trim_start();
    if ["- ", "+ ", "* "].iter().any(|p| line.starts_with(p)) {
        return true;
    }
    let n = line.bytes().take_while(u8::is_ascii_digit).count();
    n > 0 && line[n..].starts_with(". ")
}

fn parse_text(draft: &mut Draft, bytes: &[u8]) -> Result<()> {
    let (text, mappings) = normalize(bytes)?;
    let mut lines = vec![];
    let mut offset = 0;
    for line in text.split_inclusive('\n') {
        lines.push((offset, offset + line.trim_end_matches('\n').len()));
        offset += line.len();
    }
    let mut sections: Vec<(usize, String, String)> = vec![];
    let mut i = 0;
    while i < lines.len() {
        require(
            draft.document.blocks.len() < 10_000,
            "TXT exceeds 10000 parsed blocks",
        )?;
        let (start, mut end) = lines[i];
        let line = &text[start..end];
        if line.trim().is_empty() {
            i += 1;
            continue;
        }
        let title = heading(line);
        let kind = if title.is_some() {
            BlockKind::Heading
        } else if list(line) {
            BlockKind::List
        } else {
            BlockKind::Paragraph
        };
        if let Some((level, _)) = title {
            while sections.last().is_some_and(|s| s.0 >= level) {
                sections.pop();
            }
        }
        let context = sections
            .iter()
            .map(|s| s.2.as_str())
            .collect::<Vec<_>>()
            .join(" > ");
        let parent = sections.last().map(|s| s.1.clone());
        i += 1;
        if kind != BlockKind::Heading {
            while i < lines.len() {
                let (next_start, next_end) = lines[i];
                let next = &text[next_start..next_end];
                if next.trim().is_empty()
                    || heading(next).is_some()
                    || (list(next) && kind != BlockKind::List)
                {
                    break;
                }
                end = next_end;
                i += 1;
            }
        }
        let id = format!("b{}", draft.document.blocks.len());
        draft.document.blocks.push(Block {
            id: id.clone(),
            kind,
            parent: parent.clone(),
            text: text[start..end].into(),
            sources: vec![text_source(
                &draft.document.revision,
                &text,
                &mappings,
                start,
                end,
            )],
        });
        draft.units.push(ParsedUnit {
            block_id: id.clone(),
            context,
            section: parent,
            record: None,
            pointer: None,
            value: None,
            pdf: None,
        });
        if let Some((level, title)) = title {
            sections.push((level, id, title.into()));
        }
    }
    require(
        !draft.document.blocks.is_empty(),
        "TXT contains no nonblank text",
    )
}

// A separate visitor checks duplicate keys at every depth. Value's normal
// arbitrary-precision deserializer then preserves numeric spelling and types.
struct Unique;
impl<'de> Deserialize<'de> for Unique {
    fn deserialize<D: de::Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct Check;
        impl<'de> Visitor<'de> for Check {
            type Value = Unique;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "JSON without duplicate keys")
            }
            fn visit_map<A: MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                let mut keys = BTreeSet::new();
                while let Some(key) = a.next_key::<String>()? {
                    if !keys.insert(key) {
                        return Err(de::Error::custom("duplicate JSON object key"));
                    }
                    a.next_value::<Unique>()?;
                }
                Ok(Unique)
            }
            fn visit_seq<A: SeqAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                while a.next_element::<Unique>()?.is_some() {}
                Ok(Unique)
            }
            fn visit_bool<E: de::Error>(self, _: bool) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
            fn visit_i64<E: de::Error>(self, _: i64) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
            fn visit_u64<E: de::Error>(self, _: u64) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
            fn visit_f64<E: de::Error>(self, _: f64) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
            fn visit_str<E: de::Error>(self, _: &str) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
            fn visit_unit<E: de::Error>(self) -> std::result::Result<Unique, E> {
                Ok(Unique)
            }
        }
        d.deserialize_any(Check)
    }
}

fn json_source(revision: &str, pointer: &str, record: &Option<Record>) -> SourceRef {
    SourceRef {
        revision: revision.into(),
        locator: Locator::Json {
            pointer: pointer.into(),
            record_id: record.as_ref().and_then(|r| r.id.clone()),
        },
    }
}
fn json_text(value: &Value) -> Result<String> {
    // String leaves are decoded narrative. Empty strings remain searchable as JSON "".
    match value {
        Value::String(s) if !s.is_empty() => Ok(s.clone()),
        _ => Ok(serde_json::to_string(value)?),
    }
}
fn json_unit(
    draft: &mut Draft,
    pointer: String,
    value: Value,
    record: Option<Record>,
) -> Result<()> {
    require(
        draft.document.blocks.len() < 10_000,
        "JSON exceeds 10000 parsed blocks",
    )?;
    let id = format!("b{}", draft.document.blocks.len());
    draft.document.blocks.push(Block {
        id: id.clone(),
        kind: BlockKind::JsonSubtree,
        parent: None,
        text: json_text(&value)?,
        sources: vec![json_source(&draft.document.revision, &pointer, &record)],
    });
    draft.units.push(ParsedUnit {
        block_id: id,
        context: String::new(),
        section: None,
        record,
        pointer: Some(pointer),
        value: Some(value),
        pdf: None,
    });
    Ok(())
}

fn parse_json(draft: &mut Draft, bytes: &[u8], config: &IngestConfig) -> Result<()> {
    let mut decoder = serde_json::Deserializer::from_slice(bytes);
    Unique::deserialize(&mut decoder)?;
    decoder.end()?;
    reject_reserved_json_keys(bytes)?;
    let root: Value = serde_json::from_slice(bytes)?;
    let target = root
        .pointer(&config.record_pointer)
        .ok_or_else(|| Error::Invalid("JSON record pointer not found".into()))?;
    require(
        config.record_pointer.is_empty() || target.is_array(),
        "configured record pointer must select an array",
    )?;
    let mut records = vec![];
    if let Value::Array(values) = target {
        require(
            values.len() <= 10_000,
            "JSON exceeds 10000 selected records",
        )?;
        if values.is_empty() {
            json_unit(draft, config.record_pointer.clone(), target.clone(), None)?;
        }
        for (i, value) in values.iter().enumerate() {
            records.push((format!("{}/{i}", config.record_pointer), value));
        }
    } else {
        records.push((String::new(), target));
    }
    let mut ids = BTreeSet::new();
    for (pointer, value) in records {
        let id = value
            .pointer(&config.record_id_pointer)
            .filter(|v| !v.is_null())
            .cloned();
        if let Some(id) = &id {
            require(
                id.is_string() || id.is_number(),
                "JSON record ID must be string or number",
            )?;
            require(
                ids.insert(serde_json::to_string(id)?),
                "duplicate JSON record ID",
            )?;
        }
        let record = Record {
            pointer: pointer.clone(),
            id,
            value: value.clone(),
        };
        json_unit(draft, pointer, value.clone(), Some(record))?;
    }
    // Preserve metadata outside a selected array without copying that array into
    // another record or pretending metadata is a field of each selected record.
    if !config.record_pointer.is_empty() {
        let parts = pointer_parts(&config.record_pointer)?;
        let mut current = &root;
        let mut path = String::new();
        for part in parts {
            match current {
                Value::Object(map) => {
                    for (key, value) in map {
                        if key != &part {
                            json_unit(
                                draft,
                                format!("{path}/{}", escape(key)),
                                value.clone(),
                                None,
                            )?;
                        }
                    }
                    current = &map[&part];
                }
                Value::Array(array) => {
                    let index: usize = part
                        .parse()
                        .map_err(|_| Error::Invalid("invalid array pointer index".into()))?;
                    for (i, value) in array.iter().enumerate() {
                        if i != index {
                            json_unit(draft, format!("{path}/{i}"), value.clone(), None)?;
                        }
                    }
                    current = &array[index];
                }
                _ => return Err(Error::Invalid("record path crosses scalar".into())),
            }
            path = format!("{path}/{}", escape(&part));
        }
    }
    Ok(())
}

fn reject_reserved_json_keys(bytes: &[u8]) -> Result<()> {
    // serde_json's arbitrary_precision Value decoder treats this private object
    // key as a number wrapper. Reject it explicitly, including escaped spellings,
    // so both ingestion and later job/WAL deserialization preserve JSON types.
    // Syntax was already validated; this scan only identifies quoted object keys.
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] != b'"' {
            i += 1;
            continue;
        }
        let start = i;
        i += 1;
        while i < bytes.len() {
            match bytes[i] {
                b'\\' => i += 2,
                b'"' => {
                    i += 1;
                    break;
                }
                _ => i += 1,
            }
        }
        let end = i;
        while bytes.get(i).is_some_and(u8::is_ascii_whitespace) {
            i += 1;
        }
        if bytes.get(i) == Some(&b':') {
            let key: String = serde_json::from_slice(&bytes[start..end])?;
            require(
                key != "$serde_json::private::Number",
                "JSON key $serde_json::private::Number is reserved by the storage serializer",
            )?;
        }
    }
    Ok(())
}

pub(super) fn blank_chunk(block: &Block, context: &str, representation: Representation) -> Chunk {
    Chunk {
        id: String::new(),
        spans: vec![BlockSpan {
            block_id: block.id.clone(),
            bytes: range(0, block.text.len()),
        }],
        evidence: block.text.clone(),
        representation,
        sources: block.sources.clone(),
        structural_context: context.into(),
        generated_context: None,
        attributes: BTreeMap::new(),
        parent: None,
        previous: None,
        next: None,
        vectors: BTreeMap::new(),
    }
}
fn tokens<E: Encoder>(chunk: &Chunk, config: &IngestConfig, encoder: &E) -> Result<usize> {
    encoder.count_tokens(&configured_input(config, chunk))
}

pub(super) fn split<E: Encoder>(
    base: Chunk,
    block: &Block,
    config: &IngestConfig,
    encoder: &E,
    budget: &mut usize,
) -> Result<Vec<Chunk>> {
    if tokens(&base, config, encoder)? <= config.target_tokens {
        reserve(&base, budget)?;
        return Ok(vec![base]);
    }
    let mut chunks = vec![];
    let mut start = 0;
    while start < block.text.len() {
        let rest = &block.text[start..];
        let mut piece = base.clone();
        piece.evidence = rest.chars().next().unwrap().to_string();
        let limit = if tokens(&piece, config, encoder)? > config.target_tokens {
            config.chunk_limit()
        } else {
            config.target_tokens
        };
        // Token counts need not be monotonic (BPE merges). Test actual candidate
        // inputs; use a bounded prefix window and never infer a count from chars.
        let mut fitting = None;
        let mut sentence = None;
        let mut word = None;
        for (offset, ch) in rest.char_indices() {
            let end = start + offset + ch.len_utf8();
            piece.evidence = block.text[start..end].into();
            let count = tokens(&piece, config, encoder)?;
            if count <= limit {
                fitting = Some(end);
                if ch.is_whitespace() {
                    word = Some(end);
                }
                if matches!(ch, '.' | '!' | '?')
                    && block.text[end..]
                        .chars()
                        .next()
                        .is_none_or(char::is_whitespace)
                {
                    sentence = Some(end);
                }
            }
            // A fixed lookahead bounds tokenization cost without assuming strict
            // monotonicity. Any chosen endpoint was checked including context.
            if fitting.is_some_and(|fit| end.saturating_sub(fit) > 64) {
                break;
            }
            if fitting.is_none() && offset > 256 {
                break;
            }
        }
        let mut end = fitting
            .ok_or_else(|| Error::Invalid("context/prefix leaves no budget for evidence".into()))?;
        if end != block.text.len() {
            end = sentence.or(word).unwrap_or(end);
        }
        piece.evidence = block.text[start..end].into();
        piece.spans = vec![BlockSpan {
            block_id: block.id.clone(),
            bytes: range(start, end),
        }];
        if let Locator::Text {
            encoding,
            mappings,
            line_start,
            ..
        } = &block.sources[0].locator
        {
            let block_start = mappings[0].normalized.start;
            let maps = clip_mappings(
                mappings,
                block_start + start as u64,
                block_start + end as u64,
            );
            piece.sources = vec![SourceRef {
                revision: block.sources[0].revision.clone(),
                locator: Locator::Text {
                    encoding: encoding.clone(),
                    bytes: ByteRange {
                        start: maps[0].original.start,
                        end: maps.last().unwrap().original.end,
                    },
                    line_start: line_start
                        + block.text[..start].bytes().filter(|b| *b == b'\n').count() as u64,
                    line_end: line_start
                        + block.text[..end - 1]
                            .bytes()
                            .filter(|b| *b == b'\n')
                            .count() as u64,
                    mappings: maps,
                },
            }];
        }
        require(
            tokens(&piece, config, encoder)? <= config.chunk_limit(),
            "split input exceeds token limit",
        )?;
        reserve(&piece, budget)?;
        chunks.push(piece);
        start = end;
    }
    Ok(chunks)
}

fn json_chunks<E: Encoder>(
    draft: &mut Draft,
    unit: &ParsedUnit,
    node: (&str, &str, &Value),
    config: &IngestConfig,
    encoder: &E,
    budget: &mut usize,
) -> Result<()> {
    let (block_id, pointer, value) = node;
    let block = draft
        .document
        .blocks
        .iter()
        .find(|b| b.id == block_id)
        .unwrap()
        .clone();
    let identity = match &unit.record {
        Some(record) => format!(
            "record {}{}; ",
            record.pointer,
            record
                .id
                .as_ref()
                .map(|id| format!(" id={id}"))
                .unwrap_or_default()
        ),
        None => String::new(),
    };
    let context = format!("{identity}field {pointer}");
    let mut candidate = blank_chunk(&block, &context, Representation::JsonSerialization);
    let attribute = |value: Value, pointer: &str| Attribute {
        value,
        sources: vec![json_source(&draft.document.revision, pointer, &unit.record)],
        derivation: Derivation::Source,
    };
    candidate
        .attributes
        .insert("value".into(), attribute(value.clone(), pointer));
    if let Some(record) = &unit.record {
        candidate.attributes.insert(
            "record".into(),
            attribute(record.value.clone(), &record.pointer),
        );
    }
    if tokens(&candidate, config, encoder)? <= config.chunk_limit() {
        reserve(&candidate, budget)?;
        draft.document.chunks.push(candidate);
        return Ok(());
    }
    let children: Vec<(String, &Value)> = match value {
        Value::Object(map) => map
            .iter()
            .map(|(key, v)| (format!("{pointer}/{}", escape(key)), v))
            .collect(),
        Value::Array(array) => array
            .iter()
            .enumerate()
            .map(|(i, v)| (format!("{pointer}/{i}"), v))
            .collect(),
        Value::String(_) => {
            draft
                .document
                .chunks
                .extend(split(candidate, &block, config, encoder, budget)?);
            return Ok(());
        }
        _ => vec![],
    };
    require(
        !children.is_empty(),
        "indivisible JSON value/context exceeds token limit",
    )?;
    for (path, child) in children {
        require(
            draft.document.blocks.len() < 10_000,
            "JSON exceeds 10000 derived blocks",
        )?;
        let id = format!("b{}", draft.document.blocks.len());
        draft.document.blocks.push(Block {
            id: id.clone(),
            kind: BlockKind::JsonSubtree,
            parent: Some(block.id.clone()),
            text: json_text(child)?,
            sources: vec![json_source(&draft.document.revision, &path, &unit.record)],
        });
        reserve(draft.document.blocks.last().unwrap(), budget)?;
        json_chunks(draft, unit, (&id, &path, child), config, encoder, budget)?;
    }
    Ok(())
}

pub(super) fn chunk<E: Encoder>(
    draft: &mut Draft,
    config: &IngestConfig,
    encoder: &E,
) -> Result<()> {
    let mut budget = remaining_budget(draft)?;
    let mut sections = vec![];
    for unit in draft.units.clone() {
        let start = draft.document.chunks.len();
        if let (Some(pointer), Some(value)) = (&unit.pointer, &unit.value) {
            json_chunks(
                draft,
                &unit,
                (&unit.block_id, pointer, value),
                config,
                encoder,
                &mut budget,
            )?;
        } else {
            let block = draft
                .document
                .blocks
                .iter()
                .find(|b| b.id == unit.block_id)
                .unwrap();
            let base = blank_chunk(block, &unit.context, Representation::NormalizedText);
            let pieces = split(base, block, config, encoder, &mut budget)?;
            // Merge complete adjacent prose/list blocks only in the same section.
            if pieces.len() == 1
                && block.kind != BlockKind::Heading
                && sections.last() == Some(&unit.section)
            {
                if let Some(last) = draft.document.chunks.last_mut() {
                    let last_is_heading =
                        draft.document.blocks.iter().any(|b| {
                            b.id == last.spans[0].block_id && b.kind == BlockKind::Heading
                        });
                    let mut combined = last.clone();
                    combined.evidence.push_str("\n\n");
                    combined.evidence.push_str(&pieces[0].evidence);
                    if !last_is_heading
                        && combined.structural_context == pieces[0].structural_context
                        && tokens(&combined, config, encoder)? <= config.target_tokens
                    {
                        combined.spans.extend(pieces[0].spans.clone());
                        combined.sources.extend(pieces[0].sources.clone());
                        *last = combined;
                        continue;
                    }
                }
            }
            draft.document.chunks.extend(pieces);
        }
        for _ in start..draft.document.chunks.len() {
            sections.push(unit.section.clone());
        }
    }
    for (i, c) in draft.document.chunks.iter_mut().enumerate() {
        c.id = format!("c{i}");
    }
    let heading_chunks: BTreeMap<_, _> = draft
        .document
        .chunks
        .iter()
        .filter_map(|c| {
            let block = draft
                .document
                .blocks
                .iter()
                .find(|b| b.id == c.spans[0].block_id)?;
            (block.kind == BlockKind::Heading).then(|| (block.id.clone(), c.id.clone()))
        })
        .collect();
    for i in 0..draft.document.chunks.len() {
        let c = &mut draft.document.chunks[i];
        c.parent = sections[i]
            .as_ref()
            .and_then(|s| heading_chunks.get(s).cloned());
        // JSON neighbors remain within the exact record; metadata never leaks in.
        let same_group = |a: usize, b: usize| {
            if draft.document.media_type == MediaType::Txt {
                sections[a] == sections[b]
            } else {
                let record = |index: usize| {
                    draft.document.chunks[index]
                        .attributes
                        .get("record")
                        .map(|a| &a.sources)
                };
                record(a).is_some() && record(a) == record(b)
            }
        };
        let previous = (i > 0 && same_group(i - 1, i)).then(|| format!("c{}", i - 1));
        let next = (i + 1 < draft.document.chunks.len() && same_group(i, i + 1))
            .then(|| format!("c{}", i + 1));
        draft.document.chunks[i].previous = previous;
        draft.document.chunks[i].next = next;
    }
    require(!draft.document.chunks.is_empty(), "no chunks produced")
}
