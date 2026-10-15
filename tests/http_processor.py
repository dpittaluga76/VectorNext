"""Offline T19 HTTP/browser plumbing substitute. Never use for model quality.

Explicitly start inside the isolated API container's network namespace. It has
no database handle and only implements deterministic test operations.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, body):
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply({'capabilities': dict.fromkeys(['embedding', 'reranking', 'generation', 'pdf'], True)})

    def do_POST(self):
        value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        op, data = value['op'], value.get('input')
        if op == 'profile':
            prompt = 'synthetic HTTP browser fixture'
            result = {'space': {'model': 'vectornext/t19-browser-NOT-semantic', 'revision': 'v1',
                               'artifact_sha256': hashlib.sha256(b't19-browser-fixture').hexdigest(),
                               'tokenizer': 'unicode-scalars-plus-two-specials-v1', 'preprocessing': 'fixture-v1',
                               'dimensions': 16, 'max_tokens': 256, 'query_prefix': '', 'document_prefix': '',
                               'normalization': 'L2'},
                      'generator': {'model': 'synthetic', 'revision': 'v1', 'artifact_sha256': 'a'*64,
                                    'runtime': 'test', 'prompt': prompt,
                                    'prompt_version': hashlib.sha256(prompt.encode()).hexdigest(),
                                    'temperature': 0, 'seed': 42, 'context_window': 4096,
                                    'output_tokens': 256, 'annotation_tokens': 60}}
        elif op == 'count':
            result = len(data) + 2
        elif op == 'embed':
            vector = [n+1 for n in hashlib.sha256(data.encode()).digest()[:16]]
            norm = math.sqrt(sum(n*n for n in vector))
            result = [n/norm for n in vector]
        elif op == 'rerank':
            result = {'scores': [1.0]*len(data['passages']), 'pair_tokens': [10]*len(data['passages']),
                      'identity': {'fixture': 'not-semantic'}}
        elif op == 'answer_tokens':
            result = 100
        elif op == 'plan_fields':
            result = {'plan': {'status': 'ready', 'fields': [{'name': 'amount', 'kind': 'number',
                       'nullable': False, 'description': 'Stored fixture amount'}]}}
        elif op == 'answer':
            evidence = data['evidence'][0]['id']
            fields = {name: {'value': None, 'evidence_id': evidence, 'quote': '',
                            'pointer': spec.get('pointer') or '/'+name}
                      for name, spec in data['fields'].items()}
            result = {'answer': {'status': 'supported', 'fields': fields}, 'audit': {'fixture': True}}
        else:
            raise ValueError(f'Unexpected fixture operation {op}')
        self.reply({'result': result})


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8090), Handler).serve_forever()
