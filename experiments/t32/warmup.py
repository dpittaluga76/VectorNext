"""Separate synthetic engineering warmup, executed inside the test processor."""
import json
import urllib.request


def call(op, value):
    body = json.dumps({'op': op, 'input': value}, separators=(',', ':')).encode()
    req = urllib.request.Request('http://127.0.0.1:8090/rpc/interactive', data=body,
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=900) as response: result=json.load(response)
    if 'error' in result: raise RuntimeError(result)
    return result['result']


def main():
    profile = call('profile', None)
    call('embed', 'Synthetic warmup about a yellow token.')
    rerank = call('rerank', {'query':'What color is the token?',
        'passages':['The token is yellow.', 'The chair is wooden.']})
    answer = call('answer', {'question':'What color is the token?', 'history':[],
        'fields':{'color':{'kind':'string','nullable':False,'description':'Token color'}},
        'evidence':[{'id':'E1','key':{'document_id':'synthetic-warmup','revision':'r1','chunk_id':'c1'},
                     'text':'The token is yellow.','record':None,'sources':[],'spans':[],'labels':[]}]})
    if answer['answer']['status'] != 'supported' or answer['answer']['fields']['color']['value'] != 'yellow':
        raise ValueError('synthetic warmup failed')
    print(json.dumps({'profile':profile,'rerank':rerank,'answer':answer}))


if __name__ == '__main__': main()
