"""Capture one approved oracle-evidence attempt; never retry an attempted call.

Run against a dedicated evaluation processor/supervisor. This is not an API
endpoint or a production validation bypass. The separate Rust tool observes
the same saved candidate with/without mechanical validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path,raw):
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        import os
        os.fsync(f.fileno())


def encoded(value): return json.dumps(value,ensure_ascii=False,allow_nan=False).encode()


def approved_input(path,approval,case_id):
    raw=path.read_bytes()
    review=json.loads(approval.read_text(encoding='utf-8'))
    if review.get('approved') is not True or review.get('independent_of_implementation') is not True:
        raise ValueError('independent input/evidence review required before oracle inference')
    if not review.get('reviewer') or not review.get('date') or review.get('split')!='development':
        raise ValueError('named dated development-input review required; sealed oracles are not authorized')
    if review.get('approved_inputs',{}).get(case_id)!=sha(raw):
        raise ValueError('input differs from independently reviewed bytes')
    value=json.loads(raw)
    if set(value)-{'question','history','fields','evidence','constrain_pointers'}:
        raise ValueError('oracle input must contain only AnswerInput fields')
    if not value.get('question') or not value.get('fields') or not isinstance(value.get('evidence'),list):
        raise ValueError('incomplete oracle input')
    ids=[e['id'] for e in value['evidence']]
    if len(ids)!=len(set(ids)):
        raise ValueError('duplicate evidence identity')
    if any(e.get('record') is not None for e in value['evidence']) and value.get('constrain_pointers') is not True:
        raise ValueError('JSON oracle input requires normal pointer constraints')
    return raw,review


def capture(input_path,approval,case_id,model,processor,output,*,transport=None):
    if model not in ('nuextract','gemma'):
        raise ValueError('unsupported generator')
    parsed=urllib.parse.urlparse(processor)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','processor') or parsed.path not in ('','/'):
        raise ValueError('use an explicit local evaluation processor address')
    raw,review=approved_input(input_path,approval,case_id)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'input.json',raw)
    save(output/'approval.json',approval.read_bytes())
    token=str(uuid.uuid4())
    lease={'model':model,'token':token,'owner':'oracle-'+str(uuid.uuid4()),'priority':'background'}
    save(output/'started.json',encoded({'case_id':case_id,'model':model,'lease':lease,'input_sha256':sha(raw),
        'reviewer':review['reviewer'],'classification':'oracle_diagnostic','runner_sha256':sha(Path(__file__).read_bytes())}))
    calls=[]
    if transport is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def transport(path,body,timeout):
            req=urllib.request.Request(processor.rstrip('/')+path,data=body,headers={'Content-Type':'application/json'})
            with opener.open(req,timeout=timeout) as response:
                data=response.read(4*1024*1024+1)
                if len(data)>4*1024*1024: raise ValueError('processor reply exceeds normal bound')
                return data
    def call(name,path,body,timeout):
        save(output/(name+'.request.json'),body)
        start=time.monotonic()
        try:
            reply=transport(path,body,timeout)
            save(output/(name+'.response.json'),reply)
            result=json.loads(reply)
            if isinstance(result,dict) and 'error' in result: raise RuntimeError('processor recorded an error; see raw response')
            calls.append({'operation':name,'state':'completed','elapsed_ms':(time.monotonic()-start)*1000})
            return result
        except Exception as error:
            calls.append({'operation':name,'state':'failed_or_uncertain','elapsed_ms':(time.monotonic()-start)*1000,
                          'error':str(error)})
            raise
    state='failed_or_uncertain'
    error=None
    try:
        identity=call('acquire','/generation/acquire',encoded(lease),300)
        if identity.get('model')!=model or identity.get('token')!=token:
            raise ValueError('leased model identity mismatch')
        # Embed the original JSON bytes verbatim: never parse/re-encode exact
        # source decimals or large integers through Python floats.
        def rpc(operation):
            return b'{"op":'+encoded(operation)+b',"input":'+raw+b',"lease":'+encoded(lease)+b'}'
        count=call('tokens','/rpc/interactive',rpc('answer_tokens'),450)['result']
        if type(count) is not int or count>3328 or count<0:
            raise ValueError('gold evidence exceeds normal token limit or invalid token reply')
        call('answer','/rpc/interactive',rpc('answer'),750)
        state='captured'
    except Exception as exc:
        error=str(exc)
    finally:
        try:
            call('release','/generation/release',encoded({'token':token}),300)
        except Exception as exc:
            state='failed_or_uncertain'; error=(error or '')+'; release: '+str(exc)
        summary={'state':state,'error':error,'calls':calls,'input_sha256':sha(raw),
                 'no_retries':True,'validation':'not_an_application_answer'}
        save(output/'finished.json',encoded(summary))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--approval',type=Path,required=True)
    p.add_argument('--case-id',required=True)
    p.add_argument('--model',choices=['nuextract','gemma'],required=True)
    p.add_argument('--processor',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=capture(a.input,a.approval,a.case_id,a.model,a.processor,a.output)
    print(json.dumps(result,indent=2))
    if result['state']!='captured': raise SystemExit(1)


if __name__=='__main__': main()
