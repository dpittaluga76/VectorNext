"""Separate T28 application verification and fresh frozen checks before the 208-request replay."""
import json
import os
from pathlib import Path
import subprocess
import time

from experiments.t28.preflight import ROOT, COMPOSE, NORMAL, http, ready, shell, write, Samples
from experiments.t28.fresh_check import validate


def main():
    validate()
    target = ROOT/'data/t28/application-v1'
    target.mkdir(exist_ok=False)
    env = os.environ | {'VECTORNEXT_GENERATOR_PROFILE': '12b',
        'T28_DATABASE': '/storage/application-v1', 'T28_CACHE': '/cache/application-v1/12b'}
    result = {'checks': {}, 'finished': False}
    stopped = False
    sampler = Samples(services=('vectornext', 'processor', 'llm'))

    def compose(*args):
        return shell(COMPOSE+list(args), env)

    def run_check(name, args):
        print('Starting '+name, flush=True)
        start = time.monotonic()
        value = shell(args, check=False)
        (target/(name+'.log')).write_text(value.stdout+'\n'+value.stderr, encoding='utf-8')
        result['checks'][name] = {'exit_code': value.returncode, 'seconds': time.monotonic()-start}
        write(target/'progress.json', result)
        print('Finished',name,value.returncode,round(time.monotonic()-start,2),flush=True)

    client = ['docker','run','--rm','--network','vectornext-t28_local',
        '--mount',f'type=bind,source={ROOT.as_posix()},target=/checks,readonly',
        '--mount',f'type=bind,source={(ROOT/"data/t28").as_posix()},target=/out',
        '-w','/checks','--entrypoint','python','vectornext-app-processor:t28']
    try:
        status, raw = http('/scheduler', base='docker://'+NORMAL)
        state = json.loads(raw)
        assert status == 200 and not any(state[k] for k in ('active','interactive_waiting','background_waiting'))
        status, library = http('/v1/ui/library',base='http://127.0.0.1:8088')
        assert status == 200
        (target/'normal-library-before.json').write_bytes(library)
        shell(['docker','stop',NORMAL])
        stopped = True
        compose('up','-d','--no-build','--pull','never','--force-recreate','llm','processor','vectornext')
        result['startup_seconds'] = ready(base='http://127.0.0.1:8098',path='/readyz')
        (target/'compose.json').write_text(compose('config','--format','json').stdout,encoding='utf-8')
        sampler.thread.start()
        run_check('planner',client+['-m','experiments.t26.planner_check','--url','http://processor:8090',
            '--output','/out/application-v1/planner','--cases','experiments/t26/cases-v3.json',
            '--freeze','experiments/t26/input-freeze-v3.json'])
        run_check('regressions',client+['-m','experiments.t26.planner_check','--url','http://processor:8090',
            '--output','/out/application-v1/regressions','--cases','experiments/t26/regressions.json',
            '--freeze','experiments/t26/regression-freeze.json'])
        run_check('source',client+['-m','experiments.t26.live_check','--url','http://vectornext:8088',
            '--output','/out/application-v1/source','--cases','experiments/t26/live-v3.json',
            '--fixtures','tests/fixtures/planning-v3','--freeze','experiments/t26/input-freeze-v3.json',
            '--version','field-planning-v3'])
        run_check('browser',['docker','run','--name','vectornext-t28-browser',
            '--network','container:vectornext-t28-vectornext-1',
            '-e','VECTORNEXT_PLANNING_URL=http://localhost:8088','vectornext-ui-test:t28',
            'npm','run','e2e','--','planning-live.spec.ts'])
        for source in ('/tmp/t26-browser-diagnostics.json','/tmp/t26-browser.png','/app/test-results'):
            value = shell(['docker','cp','vectornext-t28-browser:'+source,str(target/Path(source).name)],check=False)
            if value.returncode:
                result.setdefault('missing_browser_artifacts',[]).append(source)
        # New source fixtures use a separate database from the unchanged T26 replay.
        env.update(T28_DATABASE='/storage/application-v1/fresh', T28_CACHE='/cache/application-v1/fresh')
        compose('up','-d','--no-build','--pull','never','--force-recreate','vectornext','processor')
        ready(base='http://127.0.0.1:8098',path='/readyz')
        run_check('fresh',client+['-m','experiments.t28.fresh_check','--url','http://vectornext:8088',
            '--processor','http://processor:8090','--output','/out/application-v1/fresh'])
        env.update(T28_DATABASE='/storage/application-v1/browser', T28_CACHE='/cache/application-v1/browser')
        compose('up','-d','--no-build','--pull','never','--force-recreate','vectornext','processor')
        ready(base='http://127.0.0.1:8098',path='/readyz')
        from deployment.client import Client
        import base64
        c=Client('http://127.0.0.1:8098')
        for name,media in [('ridge.txt','Txt'),('precision.json','Json')]:
            code,job=c.request('/v1/ingest',{'job_id':'browser-'+name,'document_id':name,
                'media_type':media,'policy':'structural','record_pointer':'',
                'source_base64':base64.b64encode((ROOT/'experiments/t28/fixtures'/name).read_bytes()).decode()})
            if code!=202: raise ValueError(('browser upload',code,job))
            _,saved=c.wait('browser-'+name,seconds=240)
            if saved.get('stage')!='Committed': raise ValueError(('browser ingestion',saved))
        run_check('ranked-browser',['docker','run','--name','vectornext-t28-ranked-browser',
            '--network','container:vectornext-t28-vectornext-1',
            '-e','VECTORNEXT_T28_URL=http://localhost:8088','vectornext-ui-test:t28',
            'npm','run','e2e','--','pointers-live.spec.ts'])
        for source in ('/tmp/t28-browser-diagnostics.json','/tmp/t28-browser.png','/app/test-results'):
            destination=target/('ranked-'+Path(source).name)
            value=shell(['docker','cp','vectornext-t28-ranked-browser:'+source,str(destination)],check=False)
            if value.returncode: result.setdefault('missing_browser_artifacts',[]).append(source)
        wrong = {'model':'vectornext-gemma4-26b-a4b','messages':[{'role':'user','content':'Return 7.'}],
            'max_tokens':16,'temperature':0,'seed':42,'reasoning':'off'}
        status, raw = http('/v1/chat/completions',wrong)
        (target/'wrong-alias.json').write_bytes(raw)
        result['wrong_alias_rejected'] = status == 503 and 'invalid model' in raw.decode()
        compose('stop','llm')
        status, raw = http('/readyz',base='http://127.0.0.1:8098')
        (target/'outage-readiness.json').write_bytes(raw)
        result['outage_not_ready'] = status == 503
        status, raw = http('/v1/ui/library',base='http://127.0.0.1:8098')
        (target/'outage-library.json').write_bytes(raw)
        result['outage_library_available'] = status == 200
        scope=[d['document_id'] for d in json.loads(raw)['documents'] if d['filename']=='ridge.txt']
        if not scope: raise ValueError('Missing outage fixture scope')
        status, raw = http('/v1/ui/ask',{'question':'How many probes does the Ridge expedition have?',
            'document_ids':scope},base='http://127.0.0.1:8098')
        (target/'outage-answer.json').write_bytes(raw)
        result['outage_answer_unavailable'] = status == 503
        compose('start','llm')
        result['restart_seconds'] = ready(base='http://127.0.0.1:8098',path='/readyz')
        result['finished'] = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
        print(result['error'],flush=True)
    finally:
        sampler.stop.set()
        if sampler.thread.is_alive(): sampler.thread.join(10)
        write(target/'samples.json',sampler.values)
        for name in ('llm','processor','vectornext'):
            (target/(name+'.log')).write_text(compose('logs','--no-color',name).stdout,encoding='utf-8')
        compose('stop','llm','processor','vectornext')
        if stopped:
            shell(['docker','start',NORMAL])
            result['normal_restore_seconds'] = ready(base='http://127.0.0.1:8088',path='/readyz')
            status, raw = http('/v1/ui/library',base='http://127.0.0.1:8088')
            (target/'normal-library-after.json').write_bytes(raw)
            result['normal_library_unchanged'] = status == 200 and raw == library
        write(target/'result.json',result)
        print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__': main()
