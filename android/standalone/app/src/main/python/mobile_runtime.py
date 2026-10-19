"""Run the unmodified product engine inside this Android process."""
import json
import os
import re
import sys
import threading
import secrets
import hmac
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

_service=None
_lock=threading.Lock()

def android_urlopen(request,timeout):
    import io,urllib.error
    from java import jclass
    result=json.loads(str(jclass('cn.zhiheng.mobile.ModelTransport').request(
        request.full_url,json.dumps(dict(request.header_items())),request.data.decode('utf-8'),int(timeout*1000))))
    if result.get('error'):raise urllib.error.URLError(result['error'])
    body=io.BytesIO(result.get('body','').encode('utf-8'))
    if not 200<=result['status']<300:
        raise urllib.error.HTTPError(request.full_url,result['status'],'Upstream HTTP error',{},body)
    return body

def check_connection():
    import server
    reply=server.call_ai([{'role':'user','content':'Reply with OK only.'}])
    meta=server.ai_meta()
    return json.dumps({'ok':bool(reply) and meta.get('ai_status')=='connected','error':meta.get('ai_error'),
                      'elapsed_ms':meta.get('elapsed_ms',0)},ensure_ascii=False)

def validate_config(raw):
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('模型设置格式无效')
    ai=value.get('ai',value)
    if not isinstance(ai,dict):raise ValueError('模型设置格式无效')
    base=str(ai.get('base_url','')).strip().rstrip('/')
    model=str(ai.get('model','')).strip()
    key=str(ai.get('api_key','')).strip()
    if not base and not model and not key:return {'ai':{'enabled':False}}
    url=urlsplit(base)
    approved_test_http=url.scheme=='http' and url.hostname=='47.110.38.211' and url.port==8080
    if (url.scheme!='https' and not approved_test_http) or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('模型地址须为 HTTPS，或已指定的测试 HTTP 地址')
    if approved_test_http and url.path in ('','/'):base='http://47.110.38.211:8080/v1'
    if not model or not key:raise ValueError('请填写模型名称和 API 密钥')
    protocol=ai.get('protocol','chat_completions')
    if protocol not in ('chat_completions','responses','auto'):raise ValueError('不支持的模型协议')
    normalized={'enabled':True,'base_url':base,'model':model,'vision_model':str(ai.get('vision_model') or model),
                'api_key':key,'protocol':protocol,'timeout_seconds':75,'vision_timeout_seconds':180,'retry_count':1}
    for field,minimum,maximum in (('timeout_seconds',5,120),('vision_timeout_seconds',5,240),
                                  ('retry_count',0,2),('max_tokens',1,None),('max_output_tokens',1,None)):
        if field not in ai:continue
        number=ai[field]
        if isinstance(number,bool) or not isinstance(number,(int,float,str)):
            raise ValueError(field+' 必须是有效整数')
        if isinstance(number,str) and not re.fullmatch(r'[+-]?\d+',number.strip()):
            raise ValueError(field+' 必须是有效整数')
        try:integer=int(number)
        except (TypeError,ValueError,OverflowError):raise ValueError(field+' 必须是有效整数') from None
        if isinstance(number,float) and integer!=number:
            raise ValueError(field+' 必须是有效整数')
        if integer<minimum or (maximum is not None and integer>maximum):
            raise ValueError(field+' 超出支持范围')
        normalized[field]=integer
    return {'ai':normalized}

def configure(raw):
    config=validate_config(raw)
    import server
    with server.DATA_LOCK:server.CONFIG=config
    return json.dumps(config,ensure_ascii=False)

def start(engine_path,data_path,raw_config='{}'):
    global _service
    with _lock:
        if _service:return json.dumps(_service)
        engine=Path(engine_path);data=Path(data_path);data.mkdir(parents=True,exist_ok=True)
        os.environ['ZHIHENG_DATA_DIR']=str(data)
        sys.path.insert(0,str(engine))
        import server,storage,image_jobs
        if sys.platform=='android' or 'ANDROID_ROOT' in os.environ:
            server.model_urlopen=android_urlopen
        server.ROOT=engine
        server.CONFIG=validate_config(raw_config)
        server.STARTUP_STATUS=server.startup_check()
        server.STARTUP_STATUS['migration']=server.migrate_data()
        storage.initialize(data)
        token=secrets.token_urlsafe(32)
        class PrivateHandler(server.Handler):
            def authenticated(self):
                cookies=SimpleCookie()
                try:cookies.load(self.headers.get('Cookie',''))
                except Exception:pass
                supplied=cookies.get('zhiheng_local')
                if not supplied or not hmac.compare_digest(supplied.value,token):
                    self.send_json(403,{'error':'private_app_session_required'});return False
                expected=f'127.0.0.1:{self.server.server_port}'
                origin=self.headers.get('Origin')
                if self.headers.get('Host')!=expected or (origin and origin!='http://'+expected):
                    self.send_json(403,{'error':'invalid_origin'});return False
                return True
            def do_GET(self):
                if self.authenticated():super().do_GET()
            def do_POST(self):
                if self.authenticated():super().do_POST()
            def do_OPTIONS(self):self.send_json(403,{'error':'cross_origin_disabled'})
        # Stable loopback origin preserves WebView localStorage across app restarts.
        httpd=server.ThreadingHTTPServer(('127.0.0.1',18787),PrivateHandler)
        image_jobs.ensure_worker(server)
        threading.Thread(target=httpd.serve_forever,daemon=True,name='zhiheng-local').start()
        _service={'url':f'http://127.0.0.1:{httpd.server_port}/','cookie':'zhiheng_local='+token}
        return json.dumps(_service)
