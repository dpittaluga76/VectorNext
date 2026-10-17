"""Run the frozen internal pilot serially, then restore normal NuExtract service."""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time

from .families import load
from .internal_evaluate import controls, oracles, strategies, verified
from .internal_results import select
from .internal_runtime import docker, save


def sample(root,stop):
    with (root/'resources.jsonl').open('a',encoding='utf8') as stream:
        while not stop.is_set():
            row={'unix':time.time()}
            for name,command in [('gpu',['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu',
                                        '--format=csv,noheader,nounits']),
                                 ('containers',['docker','stats','--no-stream','--format','{{json .}}',
                                   'vectornext-t39-internal-vectornext-1','vectornext-t39-internal-processor-1',
                                   'vectornext-t39-internal-llm-1'])]:
                try:row[name]=subprocess.check_output(command,text=True,timeout=15).strip()
                except Exception as error:row[name+'_error']=str(error)
            stream.write(json.dumps(row)+'\n');stream.flush()
            stop.wait(20)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();_,package=verified(root)
    stop=threading.Event();sampler=threading.Thread(target=sample,args=(root,stop),daemon=True);sampler.start()
    try:
        controls(root,'nuextract')
        strategies(root,'development',['five','two','facet'])
        strategies(root,'development',['five'],'v1')
        decision=load(root/'selection.json') if (root/'selection.json').exists() else select(root,package)
        strategies(root,'exposed_candidates',['five',decision['candidate']] if decision['candidate'] else ['five'])
        oracles(root,'nuextract')
        controls(root,'gemma')
        oracles(root,'gemma')
        save(root/'execution-completed.json',{'unix':time.time(),'all_planned_phases_accounted':True,
                                             'default_model':'nuextract','default_strategy':'five'})
    finally:
        stop.set();sampler.join(timeout=30)
        # The user's app keeps its own unchanged image, volumes and saved mode.
        docker('stop','vectornext-t39-internal-llm-1')
        docker('start','vectornext-llm-1')


if __name__=='__main__':main()
