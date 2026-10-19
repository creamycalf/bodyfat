"""Disposable UI fixture; synthetic records and a deterministic model response."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,storage,product
with tempfile.TemporaryDirectory(prefix='zhiheng-intake-ui-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    server.call_ai=lambda *a,**kw:json.dumps({'reply':'先试一个小改变，再反馈感受。','decision':{'action':'update','reason':'用户请求初步计划'},'plan':{'title':'隔离测试计划','goal':'建立习惯','items':[{'title':'下班后散步','when':'每天·下班后','detail':'轻松散步'}]}},ensure_ascii=False)
    server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-intake-ui']}
    print('Intake UI fixture on 8796',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8796),server.Handler).serve_forever()
