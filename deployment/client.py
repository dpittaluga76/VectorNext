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


class Client:
    def __init__(self, url=None):
        self.url = (url or os.environ.get('VECTORNEXT_URL','http://127.0.0.1:8088')).rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.raw = b''
    def request(self, path, body=None, timeout=900):
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
            if status != 200 or value.get('last_failure') or value.get('stage') == 'Committed': return status,value
            time.sleep(.5)
        raise TimeoutError('job wait expired; the durable job remains available')


def main():
    p=argparse.ArgumentParser(); p.add_argument('--url')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('health','ready','documents','jobs'): sub.add_parser(name)
    for name in ('job','retry','wait','document'):
        s=sub.add_parser(name); s.add_argument('id')
    s=sub.add_parser('ingest'); s.add_argument('source',type=Path); s.add_argument('--document',required=True); s.add_argument('--job',required=True)
    s.add_argument('--policy',choices=['plain','structural','generated'],default='structural'); s.add_argument('--record-pointer',default='')
    s.add_argument('--expected-revision'); s.add_argument('--allow-partial',action='store_true'); s.add_argument('--wait',action='store_true')
    s=sub.add_parser('search'); s.add_argument('text'); s.add_argument('--mode',choices=['keyword','hybrid'],default='hybrid'); s.add_argument('--space-id'); s.add_argument('--limit',type=int,default=10)
    s=sub.add_parser('ask'); s.add_argument('request',type=Path); s.add_argument('--space-id')
    a=p.parse_args(); client=Client(a.url)
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
        payload=('{"request":'+raw+',"space_id":'+json.dumps(a.space_id)+'}').encode()
        request=urllib.request.Request(client.url+'/v1/ask',data=payload,headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
        try:
            with client.opener.open(request,timeout=900) as response:
                sys.stdout.buffer.write(response.read()); sys.stdout.buffer.write(b'\n'); return
        except urllib.error.HTTPError as error:
            with error:
                client.raw=error.read(); status,result=error.code,json.loads(client.raw)
    # Print the server bytes, preserving exact JSON numbers in every command.
    sys.stdout.buffer.write(client.raw); sys.stdout.buffer.write(b'\n')
    if status>=400 or result.get('last_failure'): raise SystemExit(1)

if __name__ == '__main__': main()
