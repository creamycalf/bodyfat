"""Disposable recipe browser fixture; never uses formal data."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,storage,product
with tempfile.TemporaryDirectory(prefix='zhiheng-recipe-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    server.call_ai=lambda *a,**kw:json.dumps({'reply':'初版计划','decision':{'action':'update','reason':'建立计划'},'plan':{'title':'隔离食谱测试','goal':'规律饮食','items':[{'title':'午餐','when':'每天'}]}},ensure_ascii=False)
    server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    product.chat(server,{'text':'从今天开始执行计划','conversation_id':'recipe-conversation','client_message_id':'recipe-original'})
    server.call_ai=lambda *a,**kw:json.dumps({'reply':'这是做法草稿，请检查后保存。','decision':{'action':'none','reason':'查看做法'},'recipe_option':{'dish':'米饭配蒸蛋','ingredients':'米饭一碗，鸡蛋一个','steps':'1. 加热米饭。2. 鸡蛋蒸熟后搭配。'}},ensure_ascii=False)
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-recipe']}
    print('Recipe fixture ready on 8795',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler).serve_forever()
