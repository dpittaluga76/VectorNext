//! T24 isolated final selection experiment. Historical T23 tooling stays frozen.
#[path = "support/final_selection.rs"]
mod final_selection;
use final_selection::Candidate;
use serde::Deserialize;
use serde_json::{Value, json};
use std::{collections::BTreeSet, env, fs, io::Write, path::Path, time::Instant};
use vectornext::{
    Database, Error, Result,
    answers::AnswerModels,
    contracts::{BlockKind, Chunk, DocumentRevision, MediaType},
    ingestion::{context::*, worker::ModelWorker, *},
    search::{ChunkKey, KeywordConfig, QueryVector, SearchIndex, SearchRequest},
};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Query {
    id: String,
    question: String,
    hints: Vec<String>,
}

fn round_robin<T: Clone + Ord>(lists: &[Vec<T>], limit: usize) -> Vec<T> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for rank in 0..lists.iter().map(Vec::len).max().unwrap_or(0) {
        for list in lists {
            if let Some(key) = list.get(rank) {
                if result.len() < limit && seen.insert(key.clone()) {
                    result.push(key.clone());
                }
            }
        }
    }
    result
}

// TXT subset of answers::bundle: original ancestor headings, then exact spans.
fn passage(doc: &DocumentRevision, chunk: &Chunk) -> String {
    let blocks: std::collections::BTreeMap<_, _> =
        doc.blocks.iter().map(|b| (b.id.as_str(), b)).collect();
    let mut parents = BTreeSet::new();
    for span in &chunk.spans {
        let mut parent = blocks[span.block_id.as_str()].parent.as_deref();
        while let Some(id) = parent {
            parents.insert(id);
            parent = blocks[id].parent.as_deref();
        }
    }
    let mut text = Vec::new();
    let mut included = Vec::new();
    for block in &doc.blocks {
        if block.kind == BlockKind::Heading && parents.contains(block.id.as_str()) {
            text.push(block.text.clone());
            included.push(vectornext::contracts::BlockSpan {
                block_id: block.id.clone(),
                bytes: vectornext::contracts::ByteRange {
                    start: 0,
                    end: block.text.len() as u64,
                },
            });
        }
    }
    for span in &chunk.spans {
        if !included.contains(span) {
            text.push(
                blocks[span.block_id.as_str()].text
                    [span.bytes.start as usize..span.bytes.end as usize]
                    .to_string(),
            );
            included.push(span.clone());
        }
    }
    text.join("\n\n")
}

fn emit(file: &mut fs::File, value: Value) -> Result<()> {
    writeln!(file, "{}", serde_json::to_string(&value)?)?;
    file.flush()?;
    Ok(())
}

fn query(index: &SearchIndex, worker: &ModelWorker, q: &Query, arm: &str) -> Result<Value> {
    if q.hints.len() > 4
        || q.question.trim().is_empty()
        || q.hints.iter().any(|s| s.trim().is_empty())
    {
        return Err(Error::Invalid("invalid experimental query".into()));
    }
    let started = Instant::now();
    let mut probes = vec![q.question.as_str()];
    probes.extend(q.hints.iter().map(String::as_str));
    let mut searches = Vec::new();
    let mut lists = Vec::new();
    let mut raw = BTreeSet::new();
    let mut embedding_ms = 0.0;
    let mut search_ms = 0.0;
    for probe in probes {
        let clock = Instant::now();
        let values = worker.embed(&format!("{}{probe}", worker.space().query_prefix))?;
        embedding_ms += clock.elapsed().as_secs_f64() * 1000.0;
        let mut request = SearchRequest::hybrid(
            probe,
            QueryVector {
                space_id: worker.space().id(),
                values,
            },
        );
        request.limit = 20;
        let clock = Instant::now();
        let response = index.search(&request)?;
        search_ms += clock.elapsed().as_secs_f64() * 1000.0;
        raw.extend(response.deduplicated.iter().map(|h| h.key.clone()));
        lists.push(response.results.iter().map(|h| h.key.clone()).collect());
        searches.push(response);
    }
    let selected: Vec<ChunkKey> = round_robin(&lists, 20);
    if selected.is_empty() {
        return Err(Error::Invalid("no candidates".into()));
    }
    let passages: Vec<_> = selected
        .iter()
        .map(|key| {
            let (doc, chunk) = index.resolve(key).expect("index key resolves");
            passage(doc, chunk)
        })
        .collect();
    let clock = Instant::now();
    let rerank = worker.rerank(&q.question, &passages)?;
    let rerank_ms = clock.elapsed().as_secs_f64() * 1000.0;
    validate_rerank(&rerank, selected.len())?;
    let candidates: Vec<_> = selected
        .iter()
        .map(|key| {
            let (doc, chunk) = index.resolve(key).expect("candidate resolves");
            Candidate {
                key: key.clone(),
                spans: chunk
                    .spans
                    .iter()
                    .filter(|span| {
                        doc.blocks
                            .iter()
                            .any(|b| b.id == span.block_id && b.kind != BlockKind::Heading)
                    })
                    .cloned()
                    .collect(),
            }
        })
        .collect();
    let mut facet_scores = Vec::new();
    let mut facet_audit = Vec::new();
    let facet_clock = Instant::now();
    if arm == "facets" {
        for hint in &q.hints {
            let scored = worker.rerank(hint, &passages)?;
            validate_rerank(&scored, selected.len())?;
            facet_scores.push(scored.scores.clone());
            facet_audit.push(json!({"query":hint,"rerank":scored}));
        }
    }
    let facet_rerank_ms = facet_clock.elapsed().as_secs_f64() * 1000.0;
    let selection_clock = Instant::now();
    let (primary, selection): (Vec<ChunkKey>, Value) = if arm == "facets" {
        let result = final_selection::select(&candidates, &rerank.scores, &facet_scores, 5)?;
        (
            result
                .indices
                .iter()
                .map(|i| selected[*i].clone())
                .collect(),
            result.audit,
        )
    } else {
        (
            final_selection::ranking(&candidates, &rerank.scores)?
                .into_iter()
                .take(5)
                .map(|i| selected[i].clone())
                .collect(),
            json!({"strategy":"ranked"}),
        )
    };
    let selection_ms = selection_clock.elapsed().as_secs_f64() * 1000.0;
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
    Ok(
        json!({"id":q.id,"status":"ok","question":q.question,"arm":arm,
        "raw":raw,"selected":selected,"primary":primary,"searches":searches,
        "rerank":rerank,"passages":passages,"embedding_ms":embedding_ms,"search_ms":search_ms,
        "rerank_ms":rerank_ms,"facet_rerank_ms":facet_rerank_ms,"selection_ms":selection_ms,"facet_audit":facet_audit,"selection":selection,"pair_evaluations":selected.len()*(1+facet_audit.len()),"elapsed_ms":elapsed_ms}),
    )
}

fn validate_rerank(r: &vectornext::answers::Rerank, count: usize) -> Result<()> {
    if r.scores.len() != count
        || r.pair_tokens.len() != count
        || r.scores.iter().any(|s| !s.is_finite())
        || r.pair_tokens.iter().any(|t| *t > 512)
    {
        return Err(Error::Invalid(
            "invalid experimental reranker result".into(),
        ));
    }
    Ok(())
}

fn run() -> Result<()> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 5 || !["ingest", "ranked", "facets"].contains(&args[0].as_str()) {
        return Err(Error::Invalid(
            "usage: final_passages <ingest|ranked|facets> <db> <input-dir> <output-jsonl> <python>"
                .into(),
        ));
    }
    let mut output = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&args[3])?;
    let started = Instant::now();
    let mut db = Database::open(&args[1])?;
    let worker = ModelWorker::start(&args[4])?;
    emit(
        &mut output,
        json!({"kind":"startup","arm":args[0],"elapsed_ms":started.elapsed().as_secs_f64()*1000.0,"profile":worker.profile()}),
    )?;
    let input = Path::new(&args[2]);
    if args[0] == "ingest" {
        if db.snapshot().documents().next().is_some() || !db.ingestion_jobs()?.is_empty() {
            return Err(Error::Invalid(
                "experiment requires a fresh database".into(),
            ));
        }
        let sources: Value = serde_json::from_slice(&fs::read(input.join("sources.json"))?)?;
        let mut config = IngestConfig::new(worker.space());
        config.context = Some(ContextConfig::new(Policy::Structural, None));
        config.target_tokens = 180.min(config.chunk_limit());
        let processor = ContextProcessor {
            base: LocalProcessor { encoder: &worker },
            generator: &worker,
        };
        for source in sources["sources"]
            .as_array()
            .ok_or_else(|| Error::Invalid("sources missing".into()))?
        {
            let id = source["id"]
                .as_str()
                .ok_or_else(|| Error::Invalid("source id missing".into()))?;
            let path = source["file"]
                .as_str()
                .ok_or_else(|| Error::Invalid("source file missing".into()))?;
            let clock = Instant::now();
            let result = (|| -> Result<Value> {
                let mut job = db.submit_ingestion(
                    IngestRequest {
                        job_id: format!("t24-{id}"),
                        document_id: id.into(),
                        expected_revision: None,
                        media_type: MediaType::Txt,
                        config: config.clone(),
                    },
                    &fs::read(input.join(path))?,
                )?;
                while job.stage != Stage::Committed {
                    job = db.advance_ingestion(&format!("t24-{id}"), &processor)?;
                }
                Ok(
                    json!({"status":"ok","chunks":job.draft.document.chunks.len(),"revision":job.draft.document.revision}),
                )
            })();
            emit(
                &mut output,
                json!({"kind":"ingestion","id":id,"result":result.unwrap_or_else(|e| json!({"status":"error","error":e.to_string()})),"elapsed_ms":clock.elapsed().as_secs_f64()*1000.0}),
            )?;
        }
        db.checkpoint()?;
    } else {
        let clock = Instant::now();
        let index =
            SearchIndex::build(db.snapshot(), worker.space().id(), KeywordConfig::default())?;
        emit(
            &mut output,
            json!({"kind":"index","generation":db.snapshot().generation(),"build_ms":clock.elapsed().as_secs_f64()*1000.0}),
        )?;
        let requests: Vec<Query> = serde_json::from_slice(&fs::read(input.join("requests.json"))?)?;
        for q in requests {
            let clock = Instant::now();
            let record=query(&index,&worker,&q,&args[0]).unwrap_or_else(|e|json!({"id":q.id,"arm":args[0],"status":"error","error":e.to_string(),"elapsed_ms":clock.elapsed().as_secs_f64()*1000.0}));
            eprintln!("{} {} {}", args[0], q.id, record["status"]);
            emit(&mut output, record)?;
        }
    }
    emit(
        &mut output,
        json!({"kind":"finish","stats":worker.stats()?,"documents":db.snapshot().documents().collect::<Vec<_>>()}),
    )?;
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn malformed_pair_budgets_and_scores_fail_before_selection() {
        let mut result = vectornext::answers::Rerank {
            scores: vec![1.0],
            pair_tokens: vec![512],
            identity: json!({}),
        };
        assert!(validate_rerank(&result, 1).is_ok());
        result.pair_tokens[0] = 513;
        assert!(validate_rerank(&result, 1).is_err());
        result.pair_tokens.clear();
        assert!(validate_rerank(&result, 1).is_err());
        result.pair_tokens.push(12);
        result.scores[0] = f64::NAN;
        assert!(validate_rerank(&result, 1).is_err());
    }
    #[test]
    fn round_robin_preserves_original_first_and_deduplicates() {
        assert_eq!(
            round_robin(&[vec![1, 2, 3], vec![1, 4, 5], vec![6]], 5),
            vec![1, 6, 2, 4, 3]
        );
        assert_eq!(round_robin(&[vec![1, 2, 3]], 20), vec![1, 2, 3]);
        assert!(round_robin::<usize>(&[], 20).is_empty());
        assert!(round_robin(&[vec![1]], 0).is_empty());
    }
}
