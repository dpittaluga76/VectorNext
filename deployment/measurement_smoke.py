"""Bounded synthetic default/instrumentation smoke. Requires an EMPTY isolated API."""
import json
import os
from pathlib import Path
import time
import urllib.request
import uuid


def run():
    url = os.environ['VECTORNEXT_TEST_URL']
    processor = os.environ['VECTORNEXT_PROCESSOR_URL']
    output = Path(os.environ.get('VECTORNEXT_SMOKE_OUTPUT', '/tmp/measurement-smoke'))
    output.mkdir(parents=True, exist_ok=False)
    captures = []
    def call(base, path, value=None, raw=None, kind='application/json'):
        body = json.dumps(value).encode() if value is not None else raw
        request = urllib.request.Request(base+path, data=body,
            headers={'Content-Type':kind,'X-VectorNext-Client':'1'})
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=450) as reply:
            data = reply.read()
        captures.append({'path':path,'seconds':time.monotonic()-start,'response_text':data.decode()})
        # Preserve partial/failed attempts as they happen, including polling.
        with (output/'calls.jsonl').open('a') as stream:
            stream.write(json.dumps(captures[-1])+'\n')
        return json.loads(data)
    library = call(url,'/v1/ui/library')
    assert not library['documents'] and not library['jobs'], 'must use a fresh isolated API'
    ready = call(url,'/readyz')
    assert ready['default_answer_mode'] == 'nuextract'
    identity = str(uuid.uuid4())
    text = b'Farpoint station has 8 probes. Its director is Milan Reed.'
    metadata = json.dumps({'upload_id':identity,'filename':'measurement-fixture.txt'}).encode()
    raw = b'--fixture\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'+metadata+b'\r\n--fixture\r\nContent-Disposition: form-data; name="file"; filename="measurement-fixture.txt"\r\n\r\n'+text+b'\r\n--fixture--\r\n'
    ingest = call(url,'/v1/ui/upload',raw=raw,kind='multipart/form-data; boundary=fixture')
    deadline = time.monotonic()+120
    while True:
        saved = call(url,'/v1/job',{'job_id':ingest['job_id']})
        assert not saved['last_failure'], saved['last_failure']
        if saved['stage']=='Committed': break
        assert time.monotonic()<deadline, 'ingestion timeout'
        time.sleep(1)
    answers = []
    for question, expected, history in [
        ('How many probes does Farpoint station have?', '8', []),
        ('Who is its director?', 'Milan Reed', [
            {'role':'user','text':'How many probes does Farpoint station have?'},
            {'role':'assistant','text':'probe_count: 8 (integer)'}]),
    ]:
        # Mode deliberately omitted: exercises the new server default, not a forced override.
        job = call(url,'/v1/answer-jobs',{'request_id':str(uuid.uuid4()),'kind':'ui',
                   'payload':{'question':question,'history':history,'document_ids':[ingest['document_id']]}})
        deadline = time.monotonic()+450
        while not job['terminal']:
            assert time.monotonic()<deadline, 'answer timeout'
            time.sleep(1)
            job = call(url,'/v1/answer-jobs/'+job['request_id'])
        assert job['mode']=='nuextract' and job['attempt_count']==1, job
        answer = job.get('result') or {}
        job['smoke_expected_value_match'] = (answer.get('outcome')=='supported'
            and [f['value_text'] for f in answer.get('fields',[])]==[expected])
        measured = [c for op in job['attempts'][0]['operations'] for c in op.get('model_measurement',{}).get('calls',[])]
        expected_stages = ['planning','assessment'] + (['extraction'] if answer.get('outcome')=='supported' else [])
        assert [c['stage'] for c in measured]==expected_stages, measured
        assert all(c['state']=='completed' and c['input_tokens']>0 and c['output_tokens']>0 for c in measured)
        answers.append(job)
    profile = call(processor,'/rpc/background',{'op':'profile'})['result']
    assert profile['generator']['temperature']==.2
    context = {'space':profile['space'],'config':{'policy':'generated','version':'prose-scope8000-reserve64-v1','generator':profile['generator']},
               'evidence':'He directs the station.','structural_context':'Farpoint station',
               'scope':[{'span':{'block_id':'b0','bytes':{'start':0,'end':len(text)}},'text':text.decode(),'sources':[]}]}
    generated = call(processor,'/rpc/background',{'op':'generate','input':context})
    assert 'result' in generated and (generated['result'] is None or isinstance(generated['result'],str)), generated
    result = {'answers':answers,'enrichment':generated,'captures':captures,'verification_only':True}
    (output/'capture.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'answers':len(answers),'default':'nuextract','stages':'planning,assessment,extraction',
                      'expected_value_matches':sum(a['smoke_expected_value_match'] for a in answers),
                      'generated_context':'accepted','output':str(output)}))


if __name__ == '__main__': run()
