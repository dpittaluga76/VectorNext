"""Small local API client. Standard library only; also runs on the host."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid


class Client:
    def __init__(self, url=None):
        self.url = (url or os.environ.get('VECTORNEXT_URL','http://127.0.0.1:8088')).rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.raw = b''
        self.busy_retries = 0
        self.admission_attempts = []
    def request(self, path, body=None, timeout=900):
        budget = self.busy_retries if path in ('/v1/ingest','/v1/retry') else 0
        for attempt in range(budget+1):
            status,value = self.request_once(path,body,timeout)
            error = value.get('error',{})
            if status != 503 or not isinstance(error,dict) or error.get('code') != 'busy':
                return status,value
            delay = min(2**attempt,4) if attempt<budget else None
            event = {'path':path,'attempt':attempt+1,'http_status':status,'code':'busy',
                'message':error.get('message','Admission busy'),'retry_in_seconds':delay}
            self.admission_attempts.append(event)
            print('Admission rejected: '+json.dumps(event,ensure_ascii=True),file=sys.stderr,flush=True)
            if delay is None: return status,value
            time.sleep(delay)
    def request_once(self, path, body=None, timeout=900):
        payload = None if body is None else json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        request = urllib.request.Request(self.url+path,data=payload,headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
        try:
            with self.opener.open(request,timeout=timeout) as response:
                self.raw = response.read()
                return response.status,json.loads(self.raw)
        except urllib.error.HTTPError as error:
            with error:
                self.raw = error.read()
                return error.code,json.loads(self.raw)
    def wait(self, job_id, seconds=1200):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            status, value = self.request('/v1/job',{'job_id':job_id})
            if status != 200 or value.get('last_failure') or value.get('stage') == 'Committed' or coordinator_stopped(value): return status,value
            time.sleep(.5)
        raise TimeoutError('job wait expired; the durable job remains available')

    def answer(self, payload_text, mode='nuextract', request_id=None):
        request_id = request_id or str(uuid.uuid4())
        if not 16 <= len(request_id) <= 128 or not all(c.isascii() and (c.isalnum() or c == '-') for c in request_id):
            raise ValueError('invalid answer request ID')
        print(f'Answer job: {request_id}. Resume with answer-job {request_id}.', file=sys.stderr, flush=True)
        path = '/v1/answer-jobs/' + request_id
        # Submitting the same identity is safe only with identical exact payload bytes.
        envelope = ('{"request_id":'+json.dumps(request_id)+',"mode":'+json.dumps(mode)+
                    ',"kind":"structured","payload":'+payload_text+'}').encode()
        req = urllib.request.Request(self.url+'/v1/answer-jobs', data=envelope,
                                     headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
        try:
            try: response = self.opener.open(req, timeout=30)
            except urllib.error.HTTPError as error: response = error
            with response:
                self.raw = response.read(); status, job = response.status, json.loads(self.raw)
            if status != 202: return status, job
        except (OSError, TimeoutError):
            status, job = self.request_once(path, timeout=30)
            if status != 200:
                raise OSError(f'Submission outcome uncertain. No question was resent. Reconcile answer-job {request_id}; reuse --request-id only with the same request.')
        while not job.get('terminal'):
            time.sleep(.5)
            status, job = self.request_once(path, timeout=30)
            if status != 200: return status, job
        if 'response_text' in job:
            self.raw = job['response_text'].encode('utf-8')
            return job['status_code'], json.loads(self.raw)
        return 503, job


def main():
    p=argparse.ArgumentParser(); p.add_argument('--url')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('health','ready','documents','jobs','answer-jobs'): sub.add_parser(name)
    for name in ('answer-job','cancel-answer','clear-answer'):
        sub.add_parser(name).add_argument('id')
    for name in ('job','retry','wait','document'):
        s=sub.add_parser(name); s.add_argument('id')
        if name!='document': workflow_options(s)
        if name=='retry': retry_options(s)
    s=sub.add_parser('ingest'); s.add_argument('source',type=Path); s.add_argument('--document',required=True); s.add_argument('--job',required=True)
    s.add_argument('--policy',choices=['plain','structural','generated'],default='structural'); s.add_argument('--record-pointer',default='')
    s.add_argument('--expected-revision'); s.add_argument('--allow-partial',action='store_true'); s.add_argument('--wait',action='store_true')
    workflow_options(s)
    retry_options(s)
    s=sub.add_parser('search'); s.add_argument('text'); s.add_argument('--mode',choices=['keyword','hybrid'],default='hybrid'); s.add_argument('--space-id'); s.add_argument('--limit',type=int,default=10)
    workflow_options(s)
    s=sub.add_parser('ask'); s.add_argument('request',type=Path); s.add_argument('--space-id')
    s.add_argument('--answer-mode', choices=['hybrid','gemma','nuextract'], default='nuextract')
    s.add_argument('--request-id', help='retain/reuse this identity to reconcile an interrupted submission')
    s.add_argument('--evidence-strategy', choices=['ranked', 'coverage_v1', 'facet_coverage_v1'], help='opt-in field/facet coverage; ranked is the default')
    workflow_options(s)
    s=sub.add_parser('explain',help='render saved workflow captures without calling the API or a model')
    s.add_argument('captures',type=Path,nargs='+'); s.add_argument('--report',type=Path)
    a=p.parse_args()
    for name in ('report','capture'):
        path=getattr(a,name,None)
        if path and path.exists(): p.error(f'{name} output already exists; choose a new path: {path}')
        if path and not path.parent.is_dir(): p.error(f'{name} parent directory does not exist: {path.parent}')
    if getattr(a,'report',None) and getattr(a,'capture',None) and a.report.resolve()==a.capture.resolve():
        p.error('report and capture require different paths')
    if a.command=='explain':
        from .workflow import render_many
        report=render_many([json.loads(path.read_text(encoding='utf-8-sig')) for path in a.captures])
        if a.report: save_text(a.report,report)
        sys.stdout.buffer.write(report.encode('utf-8')); return
    client=Client(a.url)
    client.busy_retries=getattr(a,'busy_retries',0)
    readable=any(getattr(a,name,None) for name in ('explain','report','capture'))
    started=time.perf_counter()
    try:
        status,result=execute(a,client)
    except (OSError,ValueError) as error:
        if not readable: raise
        status=0;result={'error':{'message':str(error)}}
        client.raw=json.dumps(result,ensure_ascii=False).encode('utf-8')
    elapsed=time.perf_counter()-started
    raw=client.raw
    if readable:
        from .workflow import capture, document_summary, render
        context={}
        if a.command=='ingest': context={'source':str(a.source),'document_id':a.document,
            'media_type':{'.txt':'Txt','.json':'Json','.pdf':'Pdf'}.get(a.source.suffix.lower()),'policy':a.policy}
        if a.command=='search': context={'question':a.text}
        if a.command=='ask':
            try: context={'question':json.loads(a.request.read_text(encoding='utf-8-sig')).get('question','')}
            except (OSError,ValueError): pass
        if client.admission_attempts: context['admission_attempts']=client.admission_attempts
        doc=None
        if a.command in ('ingest','job','wait','retry') and 200<=status<300 and result.get('stage')=='Committed':
            try:
                code,details=client.request('/v1/document',{'document_id':result['document_id']})
                candidate=details.get('document',{})
                if code==200 and candidate.get('revision')==result.get('revision') and candidate.get('document_id')==result.get('document_id'):
                    doc=document_summary(candidate)
                else: context['document_note']='Matching document revision unavailable; counts and model details are unrecorded.'
            except (OSError,ValueError) as error: context['document_note']='Inspection unavailable: '+str(error)
        entry=capture(a.command,raw,status,context,elapsed,doc,
            invocation={'arguments':sys.argv[1:],'origin':'recorded'})
        report=render(entry)
        if a.capture: save_text(a.capture,json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
        if a.report: save_text(a.report,report)
        if a.explain: sys.stdout.buffer.write(report.encode('utf-8'))
        else: sys.stdout.buffer.write(raw+b'\n')
    else: sys.stdout.buffer.write(raw+b'\n')
    if status==0 or status>=400 or result.get('last_failure') or coordinator_stopped(result): raise SystemExit(1)


def coordinator_stopped(value):
    return value.get('stage')!='Committed' and value.get('coordinator',{}).get('state') in ('failed','stopped')


def retry_options(parser):
    parser.add_argument('--busy-retries',type=int,choices=range(6),default=3,
        help='retry explicit busy admission up to 0..5 times (default 3); never retries unknown transport outcomes or saved job failures')


def workflow_options(parser):
    parser.add_argument('--explain',action='store_true',help='print a human-readable workflow instead of JSON')
    parser.add_argument('--report',type=Path,help='save a UTF-8 Markdown workflow report to a new file')
    parser.add_argument('--capture',type=Path,help='save an exact-response capture for offline explanation')


def save_text(path,content):
    with path.open('x',encoding='utf-8',newline='\n') as stream: stream.write(content)


def execute(a,client):
    if a.command == 'answer-jobs': return client.request('/v1/answer-jobs')
    if a.command in ('answer-job','cancel-answer','clear-answer'):
        if not 16 <= len(a.id) <= 128 or not all(c.isascii() and (c.isalnum() or c=='-') for c in a.id): raise ValueError('invalid answer job ID')
        suffix = {'answer-job':'','cancel-answer':'/cancel','clear-answer':'/clear'}[a.command]
        return client.request('/v1/answer-jobs/'+a.id+suffix, None if not suffix else {})
    if a.command in ('health','ready','documents','jobs'):
        status,result=client.request({'health':'/healthz','ready':'/readyz','documents':'/v1/documents','jobs':'/v1/jobs'}[a.command])
    elif a.command == 'wait': status,result=client.wait(a.id)
    elif a.command in ('job','retry','document'):
        status,result=client.request('/v1/'+a.command,{('document_id' if a.command=='document' else 'job_id'):a.id})
    elif a.command == 'ingest':
        if not 0 < a.source.stat().st_size <= 16*1024*1024: raise ValueError('source requires 1..16 MiB')
        media={'.txt':'Txt','.json':'Json','.pdf':'Pdf'}.get(a.source.suffix.lower())
        if media is None: raise ValueError('expected TXT, JSON, or PDF')
        status,result=client.request('/v1/ingest',{'job_id':a.job,'document_id':a.document,'expected_revision':a.expected_revision,
            'media_type':media,'policy':a.policy,'record_pointer':a.record_pointer,'allow_partial':a.allow_partial,
            'source_base64':base64.b64encode(a.source.read_bytes()).decode()})
        if status==202 and a.wait: status,result=client.wait(a.job)
    elif a.command == 'search':
        status,result=client.request('/v1/search',{'text':a.text,'mode':a.mode,'space_id':a.space_id,'limit':a.limit})
    else:
        # Preserve exact JSON numeric literals in caller filters rather than re-encoding through floats.
        raw=a.request.read_text(encoding='utf-8-sig'); json.loads(raw)
        options = ',"options":'+json.dumps({'evidence_strategy':a.evidence_strategy}) if getattr(a,'evidence_strategy',None) else ''
        payload='{"request":'+raw+',"space_id":'+json.dumps(a.space_id)+options+'}'
        status,result=client.answer(payload,getattr(a,'answer_mode','nuextract'),getattr(a,'request_id',None))
    return status,result

if __name__ == '__main__': main()
