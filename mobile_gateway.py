"""Authenticated LAN bridge to the existing loopback service. No data store."""
import argparse
import hmac
import http.client
import json
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parent


class Gateway(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Pairing URLs and health data must not enter logs.

    def reply(self,status,body,headers=None):
        raw=body.encode('utf-8');self.send_response(status)
        self.send_header('Content-Type','text/plain; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.end_headers();self.wfile.write(raw)

    def forward(self):
        parsed=urlsplit(self.path)
        if parsed.scheme or parsed.netloc:return self.reply(400,'Invalid path')
        if parsed.path=='/connect' and self.command=='GET':
            token=parse_qs(parsed.query).get('token',[''])[0]
            if not hmac.compare_digest(token,self.server.token):return self.reply(403,'连接码无效，请使用电脑生成的连接地址。')
            return self.reply(303,'已连接',{'Location':'/','Set-Cookie':f'zhiheng_mobile={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000'})
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:pass
        supplied=cookie.get('zhiheng_mobile')
        if not supplied or not hmac.compare_digest(supplied.value,self.server.token):return self.reply(401,'请先在安卓连接页输入完整连接地址。')
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.server.public_host}':return self.reply(403,'Origin rejected')
        if self.headers.get('Host') not in (self.server.public_host,):return self.reply(403,'Host rejected')
        if self.headers.get('Transfer-Encoding'):return self.reply(400,'Chunked requests unsupported')
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.reply(400,'Invalid length')
        if not 0<=length<=256*1024*1024:return self.reply(413,'Request too large')
        self.connection.settimeout(180)
        connection=http.client.HTTPConnection('127.0.0.1',self.server.backend_port,timeout=180)
        started=False
        try:
            body=self.rfile.read(length) if length else None
            if body is not None and len(body)!=length:return self.reply(400,'Incomplete body')
            headers={k:v for k,v in self.headers.items() if k.lower() in ('content-type','accept','range','if-none-match')}
            connection.request(self.command,self.path,body=body,headers=headers)
            response=connection.getresponse();self.send_response(response.status);started=True
            for key,value in response.getheaders():
                if key.lower() not in ('connection','transfer-encoding','server','date','set-cookie','access-control-allow-origin'):self.send_header(key,value)
            self.send_header('Connection','close');self.end_headers()
            while True:
                chunk=response.read1(65536)
                if not chunk:break
                self.wfile.write(chunk);self.wfile.flush()
        except (OSError,http.client.HTTPException):
            if not started:self.reply(502,'电脑服务暂不可用，请先启动知衡服务，再点重试。')
        finally:connection.close();self.close_connection=True

    do_GET=forward
    do_POST=forward


def create_server(host,port,token,backend_port=8787):
    server=ThreadingHTTPServer((host,port),Gateway)
    server.token=token;server.backend_port=backend_port;server.public_host=f'{host}:{server.server_port}'
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',required=True);parser.add_argument('--port',type=int,default=8788)
    args=parser.parse_args()
    private=ROOT/'.mobile-private';private.mkdir(exist_ok=True)
    path=private/'pairing.json'
    config=json.loads(path.read_text('utf-8')) if path.exists() else {'token':secrets.token_urlsafe(32)}
    path.write_text(json.dumps(config),encoding='utf-8')
    url=f"http://{args.host}:{args.port}/connect?token={config['token']}"
    (private/'pairing-url.txt').write_text(url,encoding='utf-8')
    print('LAN bridge ready. Private pairing URL: .mobile-private/pairing-url.txt',flush=True)
    create_server(args.host,args.port,config['token']).serve_forever()
