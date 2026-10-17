"""Project complete durable UI jobs into the frozen value/grounding scorer.

The caller supplies an ingestion-bound snapshot and byte-verified source context.
Raw job/report bytes remain the authoritative export. Rejected drafts never enter
the scored final fields. No inference or request rewriting occurs here.
"""
from decimal import Decimal
import json

from .capture_grounding import cell_coordinate, prose_coordinates, table_coordinates
from .families import digest
from .internal_custody import require


def exact_json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result, 'Duplicate capture key')
            result[key] = value
        return result
    return json.loads(raw, parse_float=Decimal, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite capture number')))


def project(job_raw, question, context):
    """Context keys: descriptor, snapshot, binding, original, representation, text,
    and annotation for tables. Their file hashes are checked by the run freeze.
    """
    job = exact_json(job_raw)
    capture = {'status':'error', 'fields':[], 'job_sha256':digest(job_raw),
               'original_job_state':job.get('state'), 'grounding_observations':[]}
    require(job.get('terminal') is True, 'Cannot score an unfinished job')
    require(job.get('mode') == 'nuextract', 'Strategy job crossed model modes')
    if job.get('state') != 'completed':
        capture['failure_stage'] = 'answer_job'
        return capture
    view = job.get('result')
    if not isinstance(view,dict) or 'outcome' not in view:
        capture['failure_stage'] = 'planning_or_application'
        capture['status_code'] = job.get('status_code')
        return capture
    outcome = view['outcome']
    capture['original_outcome'] = outcome
    require(outcome in ('supported','ambiguous','insufficient_evidence','rejected'),
            'Unknown browser answer outcome')
    capture['status'] = outcome
    if outcome != 'supported':
        require(view.get('fields') == [], 'Non-answer contains factual fields')
        # In particular, raw_report.unvalidated_draft remains opaque diagnostics.
        return capture
    report = exact_json(view['raw_report'])
    require(report['request']['question'] == question, 'Answer question changed')
    require(report['answer']['status'] == 'supported', 'Report/view outcome differs')
    binding, descriptor, document = context['binding'], context['descriptor'], context['snapshot']
    require(binding['state'] == 'committed' and document['document_id'] == binding['document_id']
            and document['revision'] == binding['revision'], 'Snapshot differs from ingestion binding')
    rep = descriptor['representations'][context['representation']]
    require(document['original']['sha256'] == rep['sha256'], 'Snapshot source representation differs')
    require(digest(context['original']) == descriptor['original_sha256'], 'Original source bytes changed')
    require(digest(context['text'].encode('utf8')) == descriptor['review_text_sha256'], 'Review text changed')
    evidence = {e['id']:e for e in report['evidence']}
    require(len(evidence) == len(report['evidence']), 'Duplicate evidence identity')
    fields = report['answer']['fields']
    require(len(view['fields']) == len(fields) and
            {f['name'] for f in view['fields']} == set(fields), 'View/report fields differ')
    observations = {}
    for item in view['fields']:
        name = item['name']; raw_field = fields[name]
        require(item['evidence_id'] == raw_field['evidence_id'] and
                item['pointer'] == raw_field['pointer'] and item['quote'] == raw_field['quote'],
                'View/report source proof differs')
        # Scoring never re-serializes a JSON number. Browser value_text is exact;
        # non-string values fail D4's string type requirement without rounding.
        kind = item['kind']
        if isinstance(raw_field['value'],str):
            require(kind == 'string' and item['value_text'] == raw_field['value'],
                    'String projection differs from exact answer')
        else:
            require(kind != 'string', 'Non-string materialized value labelled string')
        field = {'name':name,'type':kind,'value_text':item['value_text'],'proofs':[]}
        e = evidence.get(item['evidence_id'])
        require(e is not None, 'Field references missing evidence')
        require(e['key']['chunk_id'] in {c['id'] for c in document['chunks']},
                'Evidence chunk absent from frozen snapshot')
        if e['id'] not in observations:
            if descriptor['format'] == 'json':
                observations[e['id']] = table_coordinates(context['original'], context['annotation'],
                    context['representation'], e, binding['document_id'], binding['revision'])
            else:
                observations[e['id']] = prose_coordinates(context['text'], descriptor['review_text_sha256'],
                    descriptor['original_sha256'], e, document, binding['document_id'], binding['revision'])
        observed = observations[e['id']]
        if descriptor['format'] == 'json':
            field['evidence_coordinates'] = observed['visible_coordinates']
            try:
                field['value_coordinate'] = cell_coordinate(context['original'], context['annotation'],
                                                           observed['record_index'], item['pointer'])
            except (ValueError,TypeError):
                field['value_coordinate'] = None
                field['coordinate_gap'] = 'selected_pointer_not_an_original_value_cell'
        else:
            field['proofs'] = observed['proofs']
        capture['fields'].append(field)
    capture['grounding_observations'] = [{'evidence_id':key, **value} for key,value in observations.items()]
    capture['report_sha256'] = digest(view['raw_report'].encode('utf8'))
    return capture
