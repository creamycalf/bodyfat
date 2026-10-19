import http.client
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import mobile_gateway

class Backend(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers();self.wfile.write(b'{"ok":true}\n');self.wfile.flush()

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.backend=ThreadingHTTPServer(('127.0.0.1',0),Backend)
        self.gateway=mobile_gateway.create_server('127.0.0.1',0,'test-secret',self.backend.server_port)
        for s in (self.backend,self.gateway):threading.Thread(target=s.serve_forever,daemon=True).start()
    def tearDown(self):
        for s in (self.gateway,self.backend):s.shutdown();s.server_close()
    def get(self,path,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.gateway.server_port);c.request('GET',path,headers=headers or {});r=c.getresponse();out=(r.status,r.read(),dict(r.getheaders()));c.close();return out
    def test_pairing_required_and_proxy_streams(self):
        self.assertEqual(self.get('/api/work/state')[0],401)
        self.assertEqual(self.get('/connect?token=wrong')[0],403)
        status,body,headers=self.get('/connect?token=test-secret');self.assertEqual(status,303)
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        auth={'Cookie':'zhiheng_mobile=test-secret'}
        self.assertEqual(self.get('/api/health',auth)[:2],(200,b'{"ok":true}\n'))
        self.assertEqual(self.get('/api/health',{**auth,'Origin':'http://evil.example'})[0],403)
        self.assertEqual(self.get('/api/health',{**auth,'Host':'evil.example'})[0],403)
