"""Isolated browser fixture for persistent chat failure recovery."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,storage,product
with tempfile.TemporaryDirectory(prefix='zhiheng-recovery-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    server.call_ai=lambda *a,**kw:None
    server.ai_meta=lambda:{'ai_status':'fallback','ai_error':'AI_TIMEOUT'}
    product.chat(server,{'text':'今天体重82公斤，请安排今天开始的计划','conversation_id':'recovery-conversation','client_message_id':'recovery-original'})
    def reply(*args,**kwargs):
        return json.dumps({'reply':'请查看计划','decision':{'action':'update','reason':'完成之前请求'},
            'plan':{'title':'隔离恢复测试计划','goal':'规律活动','items':[{'title':'午休散步','when':'每天','detail':'舒适步行'}]},
            'record_events':[{'type':'weight','value':{'kg':82},'evidence':'体重82公斤'}]},ensure_ascii=False)
    server.call_ai=reply;server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-recovery']}
    print('Recovery fixture ready on 8795',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler).serve_forever()
