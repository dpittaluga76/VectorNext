"""Frozen T18 HTTP boundary observations; run only against an isolated API.

Capture is an explicit command, never part of tests. No model service is needed.
"""
import argparse
import http.client
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit

FIXTURE = Path(__file__).parents[1] / 'tests/fixtures/http/t18-boundaries.json'
JSON_HEADERS = [('Content-Type', 'application/json'), ('X-VectorNext-Client', '1')]
OBSERVED_HEADERS = ('content-type', 'cache-control', 'content-security-policy', 'x-content-type-options')


def cases():
    result = []
    def add(name, method='GET', path='/v1/documents', body=None, headers=None, length=True):
        result.append((name, method, path, body, headers or [], length))
    for path in ['/v1/documents', '/v1/jobs', '/v1/ui/library', '/v1/unknown',
                 '/v1/documents?x=1', '/v1/documents/', '/healthz?x=1',
                 '/unknown', '/../Cargo.toml', '/%2e%2e/Cargo.toml']:
        add('get ' + path, path=path)
    for method in ['HEAD', 'OPTIONS', 'PUT', 'DELETE', 'PATCH']:
        for path in ['/v1/documents', '/v1/unknown', '/']:
            add(method + ' ' + path, method, path)
    for path in ['/v1/ingest', '/v1/document', '/v1/job', '/v1/retry', '/v1/search',
                 '/v1/ask', '/v1/ui/upload-status', '/v1/ui/remove', '/v1/ui/source',
                 '/v1/ui/ask', '/v1/unknown', '/v1/ui/ask?x=1']:
        add('empty object ' + path, 'POST', path, b'{}', JSON_HEADERS)
    for name, body, headers, length in [
        ('missing content type', b'{}', [], True),
        ('missing client header', b'{}', [('Content-Type', 'application/json')], True),
        ('wrong content type', b'{}', [('Content-Type', 'text/plain'), ('X-VectorNext-Client', '1')], True),
        ('json charset', b'{}', [('Content-Type', 'application/json; charset=utf-8'), ('X-VectorNext-Client', '1')], True),
        ('missing length', None, JSON_HEADERS, False),
        ('zero length', b'', JSON_HEADERS, True),
        ('invalid json', b'{', JSON_HEADERS, True),
        ('json boundary', b'{}' + b' ' * (65536 - 2), JSON_HEADERS, True),
        ('json over boundary', b'{}' + b' ' * (65537 - 2), JSON_HEADERS, True),
    ]:
        add(name, 'POST', '/v1/unknown', body, headers, length)
    add('base64 boundary', 'POST', '/v1/ingest', b'{}' + b' ' * (23*1024*1024-2), JSON_HEADERS)
    add('base64 over boundary', 'POST', '/v1/ingest', b'{}', JSON_HEADERS + [('Content-Length', str(23*1024*1024+1))], False)
    for origin in ['http://localhost:8099', 'null', 'https://localhost:8099',
                   'http://localhost:8088', 'http://evil.test', 'http://localhost:8099.evil.test']:
        add('origin ' + origin, headers=[('Origin', origin)])
    add('cross site', headers=[('Sec-Fetch-Site', 'cross-site')])
    add('rebinding', headers=[('Host', 'evil.test'), ('Sec-Fetch-Site', 'same-origin')])
    add('duplicate origins', headers=[('Origin', 'http://localhost:8099')]*2)
    for query in ['', '?', '?document_id=x', '?revision=x', '?document_id=%FF&revision=x',
                  '?document_id=missing&revision=x', '?document_id=a&document_id=b&revision=x']:
        add('original ' + query, path='/v1/ui/original' + query)
    multipart_headers = [('Content-Type', 'multipart/form-data; boundary=x'), ('X-VectorNext-Client', '1')]
    def part(name, value):
        return b'--x\r\nContent-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n' + value + b'\r\n'
    metadata = part('metadata', b'{"upload_id":"1234567890123456","filename":"a.txt"}')
    for name, body in [
        ('missing parts', b'--x--\r\n'),
        ('missing file', metadata + b'--x--\r\n'),
        ('empty file', metadata + part('file', b'') + b'--x--\r\n'),
        ('duplicate metadata', metadata*2 + b'--x--\r\n'),
        ('unknown part', part('surprise', b'x') + b'--x--\r\n'),
        ('metadata over limit', part('metadata', b' '*8193) + b'--x--\r\n'),
        ('file over limit', metadata + part('file', b'x'*(16*1024*1024+1)) + b'--x--\r\n'),
    ]:
        add(name, 'POST', '/v1/ui/upload', body, multipart_headers)
    return result


def observe(url, case):
    _, method, path, body, headers, length = case
    target = urlsplit(url)
    conn = http.client.HTTPConnection(target.hostname, target.port, timeout=20)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    if not any(k.lower() == 'host' for k, _ in headers):
        conn.putheader('Host', 'localhost:8099')
    conn.putheader('Connection', 'close')
    for key, value in headers:
        conn.putheader(key, value)
    if length and body is not None:
        conn.putheader('Content-Length', str(len(body)))
    conn.endheaders()
    if body:
        try:
            conn.send(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Early rejection may close the request body stream.
    response = conn.getresponse()
    observed = {'status': response.status,
                'headers': {k.lower(): v for k, v in response.getheaders() if k.lower() in OBSERVED_HEADERS},
                'body': response.read().decode('utf-8')}
    conn.close()
    return observed


@unittest.skipUnless(os.environ.get('VECTORNEXT_TEST_URL'), 'isolated API URL required')
class HttpCompatibilityTests(unittest.TestCase):
    def test_frozen_t18_boundaries(self):
        expected = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
        for case in cases():
            with self.subTest(case=case[0]):
                self.assertEqual(observe(os.environ['VECTORNEXT_TEST_URL'], case), expected[case[0]])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--url')
    args = parser.parse_args()
    if args.capture:
        if not args.url or FIXTURE.exists():
            parser.error('capture requires --url and a new fixture path; existing baseline is never overwritten')
        captured = {case[0]: observe(args.url, case) for case in cases()}
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps({'source_commit': 'ae0abc41233dc194c6431d81f2478da296ca445f',
                                      'image': 'vectornext-app:t18', 'cases': captured}, indent=2) + '\n',
                           encoding='utf-8', newline='\n')
        print(f'Captured {len(captured)} HTTP boundaries in {FIXTURE}')
    else:
        unittest.main(argv=['test_http_compatibility'])
