"""Focused live integration checks. Uses a fresh, isolated deployment and capture folder."""
import argparse
import json
from pathlib import Path
import time
import uuid
import urllib.request
import urllib.error

def run(url, output, fixtures, resume=None):
    output.mkdir(parents=True, exist_ok=False)
    counter = 0
    def call(path, value=None, headers=None, raw=None, kind='application/json'):
        nonlocal counter
        body = raw if raw is not None else json.dumps(value).encode() if value is not None else None
        req = urllib.request.Request(url + path, data=body, headers={**({'Content-Type':kind,'X-VectorNext-Client':'1'} if body is not None else {}), **(headers or {})})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=900) as response: status, content = response.status, response.read()
        except urllib.error.HTTPError as error: status, content = error.code, error.read()
        counter += 1
        (output / f'{counter:03d}-response.bin').write_bytes(content)
        (output / f'{counter:03d}-request.json').write_text(json.dumps({'path':path,'request':value,'status':status,'seconds':time.monotonic()-start}, indent=2))
        if kind == 'pdf-read': return status, content
        return status, json.loads(content)
    def upload(filename, document=None):
        identity = str(uuid.uuid4())
        metadata={'upload_id':identity,'filename':filename,'record_pointer':'','allow_partial':False}
        if document: metadata.update(document_id=document['document_id'],expected_revision=document['revision'])
        source=(fixtures/filename).read_bytes();boundary='vectornext-'+identity
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()+json.dumps(metadata).encode()+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+source+f'\r\n--{boundary}--\r\n'.encode())
        for _ in range(20):
            status,job=call('/v1/ui/upload',raw=body,kind=f'multipart/form-data; boundary={boundary}')
            if status==503 and job.get('error',{}).get('code')=='busy':time.sleep(1);continue
            assert status==202,job
            break
        else: raise AssertionError('upload stayed busy')
        # Retrying the same identity returns the same durable job, not another document.
        status,again=call('/v1/ui/upload',raw=body,kind=f'multipart/form-data; boundary={boundary}')
        assert status==202 and again['job_id']==job['job_id'],again
        assert call('/v1/ui/upload-status',{'upload_id':identity})[1]['state']=='acknowledged'
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            _,saved=call('/v1/job',{'job_id':job['job_id']})
            assert not saved['last_failure'],saved
            if saved['stage']=='Committed':break
            time.sleep(1)
        else:raise AssertionError('ingestion timeout')
        _,library=call('/v1/ui/library')
        doc=next(d for d in library['documents'] if d['document_id']==job['document_id'])
        assert doc['filename']==filename
        print(f'Uploaded {filename}: {doc["chunks"]} chunks',flush=True)
        return doc
    def ask(doc, question, expected=None, **extra):
        status,result=call('/v1/ui/ask',{'question':question,'document_ids':[doc['document_id']],**extra})
        assert status==200,result
        print(f'Answer: {question} -> {result["outcome"]} {[(f["name"],f["value_text"]) for f in result["fields"]]}',flush=True)
        if expected is not None:
            assert result['outcome']=='supported',result
            assert [f['value_text'] for f in result['fields']]==expected,result
        assert isinstance(result['raw_report'],str)
        return result
    for _ in range(120):
        status,ready=call('/readyz')
        if ready['ready']:break
        time.sleep(2)
    else:raise AssertionError('models did not become ready')
    assert call('/v1/ui/library',headers={'Origin':'http://unrelated.invalid'})[0]==403
    assert call('/v1/ui/library',headers={'Origin':url})[0]==200
    if resume:
        previous=[]
        for record in sorted(resume.glob('*-request.json')):
            meta=json.loads(record.read_text())
            if meta['path']=='/v1/ui/ask' and meta['status']==200:
                previous.append(json.loads(record.with_name(record.name.replace('-request.json','-response.bin')).read_bytes()))
        assert len(previous)==5 and all(r['outcome']=='supported' for r in previous)
        first,follow,_,_,exact=previous
        _,library=call('/v1/ui/library')
        txt=next(d for d in library['documents'] if d['document_id']==first['evidence'][0]['key']['document_id'])
        pdf,structured,precise=[next(d for d in library['documents'] if d['filename']==name) for name in ('apollo11.pdf','apollo11.json','exact.json')]
    else:
        txt=upload('apollo11.txt'); pdf=upload('apollo11.pdf'); structured=upload('apollo11.json'); precise=upload('exact.json')
        first=ask(txt,'In which year did Apollo 11 launch?',['1969'])
        follow=ask(txt,'Who commanded that mission?',['Neil Armstrong'],history=[{'role':'user','text':'In which year did Apollo 11 launch?'},{'role':'assistant','text':'launch_year: 1969 (integer)'}])
        assert json.loads(first['raw_report'])['planning']['plan']['status']=='ready'
        ask(pdf,'In which year did Apollo 11 launch?',['1969'])
        ask(structured,'How many astronauts were in the Apollo 11 crew?',['3'])
        exact=ask(precise,'What are the amount, zero and unknown values in precision-check?', ['9007199254740993.00000000000001','null','0'],fields={'amount':{'kind':'number','pointer':'/amount'},'zero':{'kind':'integer','pointer':'/zero'},'unknown':{'kind':'integer','nullable':True,'pointer':'/unknown'}})
        assert json.loads(exact['raw_report'])['planning'] is None
    missing=ask(txt,'What was the Apollo 11 launch mass in kilograms?',fields={'launch_mass':{'kind':'number','description':'Launch mass in kilograms'}})
    assert missing['outcome']=='insufficient_evidence',missing
    status,original=call(f'/v1/ui/original?document_id={pdf["document_id"]}&revision={pdf["revision"]}',kind='pdf-read')
    assert status==200 and original==(fixtures/'apollo11.pdf').read_bytes()
    assert call('/v1/ui/remove',{'document_id':txt['document_id'],'revision':'stale'})[0]==409
    replacement=upload('apollo11.json',txt)
    assert call('/v1/ui/source',{'document_id':txt['document_id'],'revision':txt['revision']})[0]==409
    assert call('/v1/ui/remove',{'document_id':replacement['document_id'],'revision':replacement['revision']})[0]==200
    assert call('/v1/ui/source',{'document_id':replacement['document_id'],'revision':replacement['revision']})[0]==409
    (output/'summary.json').write_text(json.dumps({'passed':True,'continued_from':str(resume) if resume else None,'requests':counter,'documents':[pdf,structured,precise],'first_answer':first,'follow_up':follow},indent=2))
    print('Live UI API checks passed.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://localhost:8098');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--fixtures',type=Path,default=Path('tests/fixtures/ui'));parser.add_argument('--resume',type=Path);args=parser.parse_args();run(args.url,args.output,args.fixtures,args.resume)
