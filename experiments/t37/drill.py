"""Separate bounded switching/outage/restart checks on the isolated T37 project."""
import json
from pathlib import Path
import subprocess
import threading
import time
from .run import ROOT, call, now, write, digest

CONTAINER = 'vectornext-t37-llm-1'
PROC = "import os,json; from pathlib import Path; rows=[]\nfor p in Path('/proc').iterdir():\n if p.name.isdigit():\n  try:\n   if (p/'exe').readlink().name=='llama-server': rows.append({'pid':int(p.name),'args':(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode()})\n  except (OSError,PermissionError): pass\nprint(json.dumps(rows))"


def backends():
    return json.loads(subprocess.check_output(['docker','exec',CONTAINER,'python','-c',PROC],text=True))


def wait_job(identifier):
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        code,raw,job=call('/v1/answer-jobs/'+identifier)
        if code==200 and job['terminal']: return raw,job
        time.sleep(.2)
    raise TimeoutError(identifier)


def active(identifier):
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        _,_,job=call('/v1/answer-jobs/'+identifier)
        if job['terminal']: raise AssertionError('attempt finished before fault injection')
        _,_,state=call('/readyz')
        if state.get('processor',{}).get('generation',{}).get('scheduler',{}).get('active'): return
        time.sleep(.05)
    raise TimeoutError('active inference not observed')


def main():
    root=ROOT/'data/t37/operational/drill-v1'
    if root.exists(): raise SystemExit('Drill already exists; retain it and explicitly use a new attempt')
    root.mkdir(parents=True)
    write(root/'freeze.json',{'created':now(),'script_sha256':digest(Path(__file__).read_bytes()),
        'candidate_freeze_sha256':digest((ROOT/'data/t37/pilot-v1/execution-freeze.json').read_bytes()),
        'checks':['NuExtract/Gemma/NuExtract','queued cancellation','backend loss to one fallback','API restart without replay']})
    source=b'The rehearsal unit has 4 channels. This record describes only the rehearsal unit.'
    import base64
    code,raw,job=call('/v1/ingest',{'job_id':'t37-drill-source','document_id':'t37-drill','media_type':'Txt','policy':'structural','source_base64':base64.b64encode(source).decode()})
    assert code==202,(code,job)
    for _ in range(120):
        _,_,job=call('/v1/job',{'job_id':'t37-drill-source'})
        if job['stage']=='Committed': break
        if job.get('last_failure'): raise AssertionError(job['last_failure'])
        time.sleep(.2)
    assert job['stage']=='Committed'
    payload={'question':'How many channels does the rehearsal unit have?','document_ids':['t37-drill'],
             'fields':{'channels':{'kind':'integer','nullable':False,'description':'Reported rehearsal unit channel count'}}}
    observations=[];stop=threading.Event()
    def monitor():
        while not stop.is_set():
            try: observations.append({'at':now(),'backends':backends()})
            except Exception as error: observations.append({'at':now(),'error':str(error)})
            stop.wait(1)
    sampler=threading.Thread(target=monitor);sampler.start()
    results=[]
    def submit(identifier,mode):
        value={'request_id':identifier,'kind':'ui','mode':mode,'payload':payload}
        code,raw,job=call('/v1/answer-jobs',value)
        (root/(identifier+'.submission.json')).write_bytes(raw)
        assert code==202,(code,job)
    def finish(identifier,expected):
        raw,job=wait_job(identifier);(root/(identifier+'.result.json')).write_bytes(raw)
        models=[a['model'] for a in job['attempts']]
        assert models==expected,(identifier,models,job['state'])
        assert job['result']['outcome']=='supported',job.get('response_text')
        assert job['result']['fields'][0]['value_text']=='4'
        results.append({'id':identifier,'models':models,'state':job['state'],'fallback_reason':job.get('fallback_reason')})
        print(identifier,'passed',models,flush=True)
        return job
    try:
        for i,mode in enumerate(['nuextract','gemma','nuextract']):
            identifier=f't37-switch-drill-{i:02}'
            submit(identifier,mode)
            if i==1:
                queued='t37-queued-cancellation'
                submit(queued,'gemma')
                code,raw,value=call('/v1/answer-jobs/'+queued+'/cancel',{})
                (root/'cancelled.json').write_bytes(raw)
                assert code==200 and value['state']=='cancelled' and value['attempt_count']==0
                results.append({'id':queued,'state':'cancelled','attempts':0})
            finish(identifier,[mode])
        identifier='t37-backend-loss-hybrid'
        submit(identifier,'hybrid');active(identifier)
        processes=backends();assert len(processes)==1,processes
        subprocess.check_call(['docker','exec',CONTAINER,'python','-c',f"import os,signal;os.kill({processes[0]['pid']},signal.SIGKILL)"])
        result=finish(identifier,['nuextract','gemma'])
        assert result['attempts'][0]['status_code']!=200
        identifier='t37-api-restart-hybrid'
        submit(identifier,'hybrid');active(identifier)
        subprocess.check_call(['docker','kill','--signal','KILL','vectornext-t37-vectornext-1'])
        subprocess.check_call(['docker','start','vectornext-t37-vectornext-1'])
        # Compose restart policy restores the same frozen image and durable volume.
        for _ in range(80):
            try:
                if call('/healthz')[0]==200: break
            except Exception: pass
            time.sleep(.5)
        result=finish(identifier,['nuextract','gemma'])
        assert result['attempts'][0]['state']=='interrupted_uncertain'
        assert 'no replay' in result['fallback_reason']
    finally:
        stop.set();sampler.join();write(root/'backend-processes.json',observations);write(root/'checks.json',results)
    assert observations and all(len(v.get('backends',[]))<=1 for v in observations)
    assert not any('error' in v for v in observations)
    write(root/'success.json',{'checks':results,'samples':len(observations),'maximum_simultaneous_backends':max(len(v['backends']) for v in observations)})
    print('All bounded operational checks passed',flush=True)


if __name__=='__main__': main()
