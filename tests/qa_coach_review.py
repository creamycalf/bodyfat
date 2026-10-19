"""Disposable HTTP fixture: never uses production data or a remote model."""
import sys
import json
import tempfile
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,product,storage

with tempfile.TemporaryDirectory(prefix='coach-review-ui-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
        setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    w=product.workspace(server)
    plan=product.normalize_plan({'title':'测试阶段行动','goal':'记录感受','items':[{'title':'记录感受','detail':'记录食物与感受','minimum':'只记一句感受','alternatives':'用语音记下感受'}]},'今天',w,None)
    plan.update(status='active',start_date=(product.datetime.now().date()-timedelta(days=7)).isoformat())
    w['plans']=[plan]
    for offset in range(1,8):
        day=(product.datetime.now().date()-timedelta(days=offset)).isoformat()
        product.set_feedback(w,product.tasks_for(w,day)[0]['task_id'],'partial')
    server.save_json(server.DATA/'workspace.json',w)
    server.call_ai=lambda *a,**k:(_ for _ in ()).throw(KeyboardInterrupt())
    try:product.chat(server,{'text':'我今年38岁，今天体重80公斤','conversation_id':'coach-ui-conversation','client_message_id':'coach-ui-interrupted'})
    except KeyboardInterrupt:pass
    server.call_ai=lambda *a,**k:json.dumps({'reply':'本轮资料已核对','plan':None,'decision':{'action':'none','reason':'记录'}})
    server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-coach-review']}
    print('Coach UI fixture on 8802',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8802),server.Handler).serve_forever()
