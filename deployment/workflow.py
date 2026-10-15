"""Plain-language views of recorded workflow data. No network or model calls."""
from collections import Counter
from decimal import Decimal
import html
import json
import re
import shlex

FORMAT = 'vectornext-workflow-v1'
STAGES = ['Uploaded', 'Parsed', 'Chunked', 'Contextualized', 'Embedded', 'Committed']
OUTCOMES = {'supported': 'Supported answer', 'ambiguous': 'Clarification needed',
            'insufficient_evidence': 'Not enough evidence'}
HANDLERS = {
    'ingest': 'POST /v1/ingest → Application::upload()',
    'job': 'POST /v1/job → Application::job()',
    'wait': 'Client.wait() → POST /v1/job → Application::job()',
    'retry': 'POST /v1/retry → Application::retry()',
    'search': 'POST /v1/search → Application::search()',
    'ask': 'POST /v1/ask → Application::ask() → answers::ask_with_options()',
}


def loads(raw):
    return json.loads(raw, parse_float=Decimal)


def literal(value):
    if value is None: return 'null'
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, (int, Decimal)): return str(value)
    if isinstance(value, str): return value
    return 'structured value'


def value_type(value):
    if value is None: return 'null'
    if isinstance(value,bool): return 'boolean'
    if isinstance(value,int): return 'integer'
    if isinstance(value,Decimal): return 'number'
    if isinstance(value,str): return 'string'
    return 'structured value'


def text(value, limit=700):
    """Keep source content as inert, bounded Markdown text."""
    value = re.sub(r'\s+', ' ', literal(value)).strip()
    if len(value) > limit: value = value[:limit] + '… [preview shortened]'
    value = html.escape(value, quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+!|])', r'\\\1', value)


def seconds(value):
    return 'not recorded' if value is None else f'{Decimal(str(value)):.3f} s'


def locations(sources):
    lines, others = [], []
    for source in sources:
        locator = source.get('locator', {})
        if 'Text' in locator:
            p = locator['Text']; lines.append((p['line_start'], p['line_end']))
        if 'Pdf' in locator:
            p = locator['Pdf']; others.append(f"page {p['page']} ({'OCR' if p.get('extraction') == 'Ocr' else 'native text'})")
        if 'Json' in locator:
            others.append('JSON ' + (locator['Json']['pointer'] or '/ (root)'))
    merged = []
    for lo, hi in sorted(set(lines)):
        if merged and lo <= merged[-1][1] + 1: merged[-1][1] = max(hi, merged[-1][1])
        else: merged.append([lo, hi])
    labels = [f'lines {lo}–{hi}' if lo != hi else f'line {lo}' for lo, hi in merged]
    if len(labels)>6: labels = [f'{len(merged)} text spans within lines {merged[0][0]}–{merged[-1][1]}']
    labels += list(dict.fromkeys(others))
    return ', '.join(labels[:6]) + (f'; {len(labels)-6} more locations' if len(labels)>6 else '') if labels else 'source location not recorded'


def document_summary(document):
    """Keep counts/configuration/quality, not a second copy of vectors or text."""
    processing = document.get('processing', {})
    ingestion = processing.get('ingestion', {})
    pdf = processing.get('pdf', {})
    methods = Counter()
    for block in document.get('blocks', []):
        for source in block.get('sources', []):
            p = source.get('locator', {}).get('Pdf')
            if p: methods[p.get('extraction', 'unknown')] += 1
    return {'document_id':document.get('document_id'), 'revision':document.get('revision'),
        'media_type':document.get('media_type'), 'source_bytes':document.get('original', {}).get('bytes'),
        'blocks':len(document.get('blocks', [])), 'chunks':len(document.get('chunks', [])),
        'records':sum(b.get('kind')=='JsonSubtree' for b in document.get('blocks', [])),
        'policy':ingestion.get('context', {}).get('policy'),
        'embedding_model':ingestion.get('space', {}).get('model'),
        'pdf_status':pdf.get('status'), 'pdf_pages':len(pdf.get('pages', [])) if pdf else None,
        'pdf_methods':dict(methods), 'warnings':pdf.get('warnings', []),
        'generated_context_outcomes':dict(Counter(r.get('outcome','unknown') for r in processing.get('context', {}).values()))}


def capture(operation, raw, status=200, context=None, elapsed=None, document=None, note=None, invocation=None):
    loads(raw)  # Reject corrupt captures; preserve the original numeric literals.
    return {'format':FORMAT, 'operation':operation, 'http_status':status,
        'response_json':raw.decode('utf-8') if isinstance(raw, bytes) else raw,
        'context':context or {}, 'elapsed_seconds':elapsed, 'document':document,
        'note':note or 'Captured from a local API operation.', 'invocation':invocation}


class Report:
    def __init__(self, title): self.lines = ['# '+title, '']
    def paragraph(self, value): self.lines += [value, '']
    def step(self, name, state, detail, elapsed=None, calls=()):
        timing = f' ({seconds(elapsed)})' if elapsed is not None else ''
        code = '\n  Code: '+ ' → '.join('`'+c+'`' for c in calls)+'.' if calls and state in ('completed','failed') else ''
        self.paragraph(f'- **{name} — {state}{timing}.** {detail}'+code)
    def heading(self, title): self.lines += ['## '+title, '']
    def finish(self): return '\n'.join(self.lines).rstrip()+'\n'


def invocation(r, entry):
    r.heading('Invocation')
    recorded = entry.get('invocation')
    if recorded is None:
        r.paragraph('Original client arguments were not recorded in this capture.')
    else:
        args = recorded.get('arguments')
        origin = recorded.get('origin')
        if not isinstance(args,list) or not all(isinstance(a,str) for a in args) or origin not in ('recorded','saved_run_record'):
            raise ValueError('invalid workflow invocation metadata')
        label = 'Recorded client arguments' if origin=='recorded' else 'Operation arguments recovered from the saved run record (report/capture switches omitted)'
        r.paragraph(label+'. Equivalent Python invocation, with POSIX shell quoting; outer Docker commands and environment are not captured:')
        command = shlex.join(['python','-m','deployment.client',*args])
        # An argument containing Markdown fences must stay inside the command block.
        fence = '`' * max(3, 1+max((len(m) for m in re.findall(r'`+',command)),default=0))
        r.paragraph(fence+'sh\n'+command+'\n'+fence)
    r.paragraph('API handler reference: `'+HANDLERS[entry['operation']]+'`.')
    r.paragraph('Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.')
    r.heading('Workflow')


def error_message(value):
    err = value.get('error', value.get('last_failure', {}))
    return err.get('message', 'Error details not recorded.') if isinstance(err, dict) else err


def ingestion(r, value, entry):
    c = entry.get('context', {}); d = entry.get('document') or {}
    # A later revision must never be presented as this job's output.
    if d.get('revision') != value.get('revision') or d.get('document_id') != value.get('document_id'): d = {}
    media = d.get('media_type') or c.get('media_type') or ('Pdf' if value.get('pdf_diagnostics') else None)
    r.paragraph('Document: **'+text(value.get('document_id', c.get('document_id','not recorded')))+'**'
        + ('; file: '+text(c['source']) if c.get('source') else '')
        + '; format: '+text(media or 'not recorded')+'.')
    stage = value.get('stage'); failure = value.get('last_failure')
    current = STAGES.index(stage) if stage in STAGES else -1
    result = 'Failed' if failure else ('Stored and searchable' if stage=='Committed' else 'In progress / last saved stage: '+str(stage or 'not recorded'))
    coordinator = value.get('coordinator',{})
    if not failure and stage!='Committed' and coordinator.get('state') in ('failed','stopped'):
        result = 'Ingestion stopped: coordinator '+coordinator['state']+'; restart required'
    r.paragraph('**Outcome: '+text(result)+'.**')
    if coordinator.get('state') in ('failed','stopped'):
        r.step('Ingestion coordinator','failed',text(coordinator.get('last_error') or 'Coordinator stopped.'))
        r.paragraph(text(coordinator.get('recovery') or 'Restart the API to resume unfinished durable jobs.'))
    r.paragraph('Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.')
    calls = [
        ('Database::submit_ingestion()',),
        ('PdfProcessor::process()',) if media=='Pdf' else ('ingestion::prepare::parse()',) if media in ('Txt','Json') else (),
        ('ingestion::pdf::chunk()',) if media=='Pdf' else ('ingestion::prepare::chunk()',) if media in ('Txt','Json') else (),
        ('ContextProcessor::process()',),
        ('ingestion::configured_input()', 'RemoteModels::embed()'),
        ('Database::commit_ingestion()',),
    ]
    details = [
        ('Save original', 'The original source was accepted and saved.'),
        ('Read document', {'Txt':'Read UTF-8 text and its structure.', 'Json':'Read JSON records while preserving their stored types.',
            'Pdf':'Processed PDF text and available OCR/layout evidence.'}.get(media,'Document format was not recorded.')),
        ('Create chunks', f"Prepared {d['blocks']} blocks and {d['chunks']} searchable chunks." if d else 'Block and chunk counts were not recorded in this job response.'),
        ('Prepare context', 'Context policy: '+text(d.get('policy') or c.get('policy') or 'not recorded')+'.'),
        ('Create embeddings', 'Embedding model: '+text(d.get('embedding_model') or 'not recorded')+'.'),
        ('Publish document', 'Published the complete document revision for search.'),
    ]
    for i,(name,detail) in enumerate(details):
        state = 'completed' if current >= i else 'not reached'
        if current < 0: state = 'not recorded'
        if failure and i == current+1:
            state = 'failed'; detail = text(failure.get('message','Reason not recorded.'))
        r.step(name,state,detail if state in ('completed','failed') else 'No completed result recorded for this step.',calls=calls[i])
        if i==1 and current>=1 and media=='Pdf':
            r.paragraph('PDF details: '+text(d.get('pdf_status') or 'not recorded')
                + (f"; {d['pdf_pages']} pages" if d.get('pdf_pages') is not None else '')
                + '; extraction methods: '+text(', '.join(d.get('pdf_methods', {})) or 'not recorded')+'.')
        if i==2 and current>=2 and media=='Json' and d:
            r.paragraph(f"Prepared JSON record blocks: {d['records']}.")
        if i==3 and current>=3:
            policy = d.get('policy') or c.get('policy')
            state = 'skipped' if media=='Json' or policy in ('plain','structural') else 'not recorded'
            outcomes = d.get('generated_context_outcomes', {})
            if outcomes: state = 'completed'
            r.step('Optional generated context',state,
                text(', '.join(f'{k}: {v}' for k,v in outcomes.items())) if outcomes else 'No generated annotation details recorded.' if state=='not recorded' else 'This format or policy does not request generated annotations.',
                calls=('ContextProcessor::process()',))
    if failure: r.paragraph('Recorded failure: '+text(failure.get('message')))
    if value.get('failure_count'): r.paragraph(f"Saved failed attempts: {value['failure_count']}.")
    warnings = d.get('warnings', [])
    if warnings:
        r.heading('Extraction warnings')
        for w in warnings[:8]: r.paragraph('- '+text(w.get('message',str(w)) if isinstance(w,dict) else w))
        if len(warnings)>8: r.paragraph(f'{len(warnings)-8} additional warnings remain in the structured capture.')
    if c.get('document_note'): r.paragraph('Document details: '+text(c['document_note']))
    pdf = value.get('pdf_diagnostics')
    if pdf:
        r.heading('PDF diagnostics before publication')
        r.paragraph('Extraction: '+text(pdf.get('status'))+'; partial text allowed: '+text(pdf.get('allow_partial'))
            +f"; pages: {len(pdf.get('pages',[]))}; warnings: {pdf.get('warning_count','not recorded')}.")
        for warning in pdf.get('warnings',[])[:8]:
            r.paragraph('- Page '+text(warning.get('page'))+': '+text(warning.get('code'))+' — '+text(warning.get('message')))
        if pdf.get('warning_count',0)>8: r.paragraph('Additional warnings remain in the structured job response.')
        r.paragraph(text(pdf.get('next_action','Review extraction warnings.')))


def retrieval(r, trace):
    if not trace:
        r.step('Search','not recorded','No retrieval trace is available.'); return
    req = trace.get('request', {})
    filtered = req.get('filter') not in (None, {'All':[]})
    r.step('Filter documents','completed' if filtered else 'skipped',
        f"{trace.get('eligible_chunks','Unrecorded')} of {trace.get('corpus_chunks','unrecorded')} chunks eligible."
        + (' Explicit source filters applied.' if filtered else ' No explicit source filter requested.'),calls=('SearchIndex::search_measured()',))
    has_vector = req.get('vector') is not None
    r.step('Semantic search','completed' if has_vector else 'skipped',
        f"Compared meanings using a query embedding; retained {len(trace.get('dense',[]))} candidates." if has_vector else 'Keyword-only search; no query embedding used.',
        calls=('RemoteModels::embed()', 'SearchIndex::search_measured()'))
    r.step('Keyword search','completed',f"Matched the query terms; retained {len(trace.get('keyword',[]))} candidates.",calls=('FieldIndex::score()',))
    r.step('Combine rankings and remove duplicates','completed',
        f"Combined {len(trace.get('fused',[]))} candidates; suppressed {len(trace.get('suppressed',[]))} duplicates; returned {len(trace.get('results',[]))} candidates.",
        calls=('SearchIndex::search_measured()',))


def evidence(r, items, fields=None):
    r.heading('Selected evidence')
    if not items: r.paragraph('No source passages were returned.'); return
    for i,item in enumerate(items[:10],1):
        key = item.get('key', {}); label = item.get('id',f'Hit {i}')
        r.paragraph('**'+text(label)+' — '+text(key.get('document_id','document not recorded'))+'**, '+text(locations(item.get('sources',[])))+'.')
        body = item.get('text', item.get('evidence',''))
        quotes = [p.get('quote','') for p in (fields or {}).values() if p.get('evidence_id')==label and p.get('quote')]
        if quotes:
            for quote in dict.fromkeys(quotes): r.paragraph('> '+text(quote,300))
        else: r.paragraph('> '+text(body,300))
    if len(items)>10: r.paragraph(f'{len(items)-10} additional results remain in the structured capture.')
    r.paragraph('Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.')


def answer(r, value):
    req = value.get('request', {}); audit = value.get('audit', {}); timings=value.get('timings_ms', {})
    status = value.get('answer',{}).get('status')
    r.paragraph('Question: **'+text(req.get('question','not recorded'))+'**')
    r.paragraph('**Outcome: '+text(OUTCOMES.get(status, status or 'not recorded'))+'.**')
    r.step('Prepare question','completed','Preserved the original question.'+f" Conversation messages: {len(req.get('history',[]))}.",calls=('answers::ask_with_options()',))
    for turn in req.get('history', [])[-4:]: r.paragraph('Context ('+text(turn['role'])+'): '+text(turn['text']))
    if value.get('search_text') and value['search_text'] != req.get('question'):
        r.paragraph('Search text with conversation context: '+text(value['search_text']))
    lookup = req.get('scope') == 'structured_lookup'
    if lookup:
        r.step('Structured lookup','completed',f"Scanned {audit.get('eligible_records','unrecorded')} eligible records using explicit filters; no semantic search or reranking.",calls=('answers::structured_lookup()',))
    else:
        retrieval(r,value.get('retrieval'))
        reranker = value.get('reranker')
        disabled = bool(reranker and reranker.get('reranking')=='disabled')
        r.step('Rerank passages','completed' if reranker and not disabled else 'skipped',
            'Reranking was disabled; kept the fused search scores.' if disabled else f"Ranked {len(value.get('ranked',[]))} candidates with "+text(reranker.get('repo','local reranker'))+'.' if reranker else 'No reranker result recorded.',
            Decimal(str(timings['reranking_with_preparation']))/1000 if 'reranking_with_preparation' in timings else None,calls=('RemoteModels::rerank()',))
    selection = value.get('selection')
    if selection:
        r.step('Select evidence for requested fields', 'completed',
            f"Ranked candidates for {len(selection.get('field_rankings',{}))} fields; planned {len(selection.get('planned_primary_keys',[]))} primary passages and admitted {len(selection.get('admitted_primary_keys',[]))}. "
            + 'Automatic neighbor expansion disabled; original source labels retained. Coverage is a heuristic, not a correctness guarantee.',
            Decimal(str(timings['field_coverage_selection']))/1000 if 'field_coverage_selection' in timings else None,
            calls=('answers::coverage::select()', 'RemoteModels::rerank()'))
    groups=len(value.get('evidence',[]))
    r.step('Assemble source context','completed',f"Prepared {groups} evidence group"+('s' if groups!=1 else '')
        + (f" within a limit of {value['options']['primary_limit']} primary passages" if value.get('options') else '')
        + '. Groups can combine overlapping or neighboring passages.',
        calls=(('answers::structured_lookup()', 'answers::bundle()') if lookup else ('answers::add_evidence()', 'answers::bundle()')) if groups else ())
    if value.get('skipped'):
        counts=Counter(s['reason'] for s in value['skipped'])
        r.paragraph('Passage omissions: '+text('; '.join(f'{k}: {v}' for k,v in counts.items()))+'.')
    assessment=audit.get('assessment'); assessment_audit=audit.get('assessment_audit',{})
    model=audit.get('model',assessment_audit.get('model',{})).get('model')
    if model: r.paragraph('Local generation model: '+text(model)+'.')
    r.step('Assess answerability','completed' if assessment else 'skipped' if lookup or audit.get('operation')=='no_evidence' else 'not recorded',
        text(OUTCOMES.get(assessment.get('status'),assessment.get('status'))) + '.' if assessment else 'No model assessment recorded.',assessment_audit.get('elapsed_seconds'),
        calls=('RemoteModels::extract()', 'model_worker.answers.generate(..., ASSESS_PROMPT)'))
    extraction = 'model' in audit
    r.step('Extract fields','completed' if extraction or lookup else 'skipped' if assessment or audit.get('operation')=='no_evidence' else 'not recorded',
        'Read exact fields from the selected evidence.' if extraction or lookup else 'No field-extraction result recorded.',audit.get('elapsed_seconds'),
        calls=('answers::structured_lookup()',) if lookup else ('model_worker.answers.generate(..., PROMPT)',))
    if audit.get('json_values_resolved_from_source'):
        r.step('Resolve JSON source values','completed','JSON values were read directly from selected source pointers, preserving numeric precision, zero and null.',calls=('answers::resolve_json_values()',))
    if audit.get('source_null_abstention'):
        r.paragraph('The source contains null for a required value. The system returned insufficient evidence instead of inventing a number.')
    validation=value.get('validation',{})
    passed=all(validation.get(k)=='passed' for k in ('schema','source_references','mechanical_support'))
    r.step('Validate answer','completed' if passed else 'not recorded',
        'Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.' if passed else 'Complete validation results were not recorded.',calls=('answers::validate_answer()',))
    r.step('Format answer','completed' if value.get('formatted') is not None else 'skipped',
        'Applied the requested template.' if value.get('formatted') is not None and req.get('template') else 'Rendered the validated fields.' if value.get('formatted') is not None else 'No supported formatted answer returned.',calls=('answers::render()',))
    draft=value.get('presentation_draft')
    r.step('Optional prose rewrite','completed' if draft is not None else 'skipped','A separate draft was returned.' if draft is not None else 'No prose rewrite returned; it was not used for retrieval.',calls=('RemoteModels::rewrite()',))
    if draft:
        r.heading('Optional presentation draft')
        for key,v in draft.items():
            if isinstance(v,str):r.paragraph(text(key)+': '+text(v))
    r.heading('Result')
    if value.get('formatted') is not None: r.paragraph('**'+text(value['formatted'])+'**')
    else: r.paragraph(text(OUTCOMES.get(status,status or 'No answer recorded'))+'.')
    fields=value.get('answer',{}).get('fields',{})
    for key,proof in fields.items():
        r.paragraph('- '+text(key)+': **'+text(proof.get('value'))+'** ('+value_type(proof.get('value'))+'); source '+text(proof.get('evidence_id','not recorded'))
            + ('; record pointer '+text(proof['pointer']) if proof.get('pointer') is not None else '')+'.')
    evidence(r,value.get('evidence',[]),fields)
    r.heading('Timing and reuse')
    r.paragraph('Application elapsed: '+seconds(Decimal(str(timings['application_total']))/1000 if 'application_total' in timings else None)+'. Stage times can overlap; do not add them.')
    uses=[a.get('usage',{}).get('prompt_tokens_details',{}).get('cached_tokens') for a in (assessment_audit,audit)]
    known=[u for u in uses if u is not None]
    r.paragraph(('Reported cached prompt tokens: '+str(sum(known))+'. ' if known else '')+'Embedding/reranking cache hits were not recorded per request.')


def render(entry):
    if entry.get('format') != FORMAT: raise ValueError('expected a vectornext-workflow-v1 capture')
    value=loads(entry['response_json']); op=entry['operation']
    if op not in ('ingest','job','wait','retry','search','ask'): raise ValueError('unsupported workflow operation')
    r=Report('VectorNext workflow — '+('ingestion' if op in ('ingest','job','wait','retry') else 'answering' if op=='ask' else op))
    r.paragraph(text(entry.get('note','Captured API operation.')))
    if entry.get('elapsed_seconds') is not None:r.paragraph('Client elapsed: '+seconds(entry['elapsed_seconds'])+' (including API wait; report rendering and extra document inspection excluded).')
    invocation(r,entry)
    attempts=entry.get('context',{}).get('admission_attempts',[])
    for event in attempts:
        r.step('Admission attempt '+str(event['attempt']),'rejected',text(event['message'])
            + (f" Retrying in {event['retry_in_seconds']} s." if event.get('retry_in_seconds') is not None else 'Retry budget exhausted.'))
    failed=entry.get('http_status',200)>=400 or entry.get('http_status')==0
    if failed:
        c=entry.get('context',{})
        if c.get('question') or c.get('source'):r.paragraph('Input: '+text(c.get('question') or c.get('source')))
        r.step('Request','failed',text(error_message(value)))
        diagnostic=value.get('error',{}).get('diagnostics') if isinstance(value.get('error'),dict) else None
        if diagnostic:
            r.heading('Rejected answer diagnostics')
            r.paragraph('Stopped at: '+text(diagnostic.get('stage'))+'. **The draft failed validation; it is not a supported answer.**')
            r.paragraph('Question: '+text(diagnostic.get('question')))
            draft=diagnostic.get('unvalidated_draft',{})
            for name,proof in draft.get('fields',{}).items():
                r.paragraph('- Unvalidated '+text(name)+': '+text(proof.get('value'))+' ('+value_type(proof.get('value'))+'); evidence '+text(proof.get('evidence_id'))
                    + ('; pointer '+text(proof['pointer']) if proof.get('pointer') is not None else '')
                    + ('; quoted text: '+text(proof['quote'],200) if proof.get('quote') else '')+'.')
            if draft.get('truncated'): r.paragraph('Large draft omitted from this summary; a labeled preview remains in the capture.')
            evidence(r,[dict(e,text=e.get('text_preview','')) for e in diagnostic.get('evidence',[])])
            r.paragraph(text(diagnostic.get('next_action')))
        else:
            r.paragraph('No completed workflow trace was returned. Parsing, retrieval, model work and validation details are unrecorded; this does not mean they never ran. No supported result is available from this response.')
    elif op in ('ingest','job','wait','retry'): ingestion(r,value,entry)
    elif op=='search':
        r.paragraph('Search: **'+text(value.get('trace',{}).get('request',{}).get('text','not recorded'))+'**')
        retrieval(r,value.get('trace'))
        r.step('Rerank and answer','skipped','Standalone search returns passages without reranking or answer generation.')
        evidence(r,value.get('hits',[]))
        r.paragraph('Per-stage timing and cache reuse were not recorded for standalone search.')
    else: answer(r,value)
    return r.finish()


def render_many(entries):
    return '\n\n---\n\n'.join(render(e).rstrip() for e in entries)+'\n'
