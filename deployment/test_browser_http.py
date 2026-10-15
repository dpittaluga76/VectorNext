"""Read-only HTTP boundary checks against an explicitly selected running deployment."""
import json
import os
import unittest
import urllib.request
import urllib.error

@unittest.skipUnless(os.environ.get('VECTORNEXT_TEST_URL'), 'set VECTORNEXT_TEST_URL to an isolated running API')
class BrowserHttpTests(unittest.TestCase):
    def request(self, path, body=None, **headers):
        url=os.environ['VECTORNEXT_TEST_URL']
        headers={'Host':'localhost:8098', **headers}
        req=urllib.request.Request(url+path,data=body,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,r.read(),{k.lower():v for k,v in r.headers.items()}
        except urllib.error.HTTPError as e:return e.code,e.read(),{k.lower():v for k,v in e.headers.items()}

    def test_static_assets_and_cli_compatibility(self):
        status,body,headers=self.request('/')
        self.assertEqual(status,200);self.assertIn(b'VectorNext',body);self.assertIn("default-src 'self'",headers['content-security-policy'])
        self.assertEqual(self.request('/v1/documents')[0],200)
        self.assertEqual(self.request('/../Cargo.toml')[0],404)
        self.assertEqual(self.request('/%2e%2e/Cargo.toml')[0],404)

    def test_strict_browser_origins_and_rebinding(self):
        for origin in ('null','https://localhost:8098','http://localhost:8088','http://unrelated.test','http://localhost:8098.evil.test'):
            self.assertEqual(self.request('/v1/ui/library',Origin=origin)[0],403)
        self.assertEqual(self.request('/v1/ui/library',Origin='http://localhost:8098')[0],200)
        self.assertEqual(self.request('/v1/ui/library',**{'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/v1/ui/library',**{'Sec-Fetch-Site':'same-origin','Host':'unrelated.test'})[0],403)

    def test_post_requires_custom_header_and_json_limit(self):
        self.assertEqual(self.request('/v1/ui/upload-status',b'{}',**{'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.request('/v1/ui/ask',b' '*65537,**{'Content-Type':'application/json','X-VectorNext-Client':'1'})[0],400)
        self.assertEqual(self.request('/v1/ui/ask',b'{}',**{'Content-Type':'text/plain','X-VectorNext-Client':'1'})[0],400)

    def test_multipart_limit_unknown_parts_and_empty_files(self):
        headers={'Content-Type':'multipart/form-data; boundary=x','X-VectorNext-Client':'1'}
        metadata=b'--x\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{"upload_id":"1234567890123456","filename":"x.txt"}\r\n'
        for file in (b'',b'x'*(16*1024*1024+1)):
            body=metadata+b'--x\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'+file+b'\r\n--x--\r\n'
            self.assertEqual(self.request('/v1/ui/upload',body,**headers)[0],400)
        body=metadata+metadata+b'--x--\r\n'
        self.assertEqual(self.request('/v1/ui/upload',body,**headers)[0],400)

    def test_malformed_scope_history_and_aggregation_fail_before_inference(self):
        values=[{'question':'Year?','document_ids':[]},{'question':'Year?','document_ids':['missing'],'history':[{'role':'assistant','text':'Bad'}]}, {'question':'Sum of all records?','document_ids':['missing']}, {'question':'q'*8193,'document_ids':['missing']}]
        for value in values:
            self.assertEqual(self.request('/v1/ui/ask',json.dumps(value).encode(),**{'Content-Type':'application/json','X-VectorNext-Client':'1'})[0],400)
