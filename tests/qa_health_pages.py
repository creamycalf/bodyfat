"""Temporary health-page fixture with deterministic replies; no upstream calls."""
import copy
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import product
import server
import storage

with tempfile.TemporaryDirectory(prefix='zhiheng-health-pages-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
        setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    server.save_json(server.PROFILE,{'age':35,'height_cm':175,'food_habits':'外卖为主，也可以自己做','occupation':'久坐工作'})
    plan={'title':'第一周轻松开始','goal':'建立规律饮食和轻量活动','items':[
        {'title':'午餐：主食、蛋白质与蔬菜','when':'每天','detail':'选择简单搭配，按饥饿和饱腹情况调整。','meal_options':{
            'cook':{'dish':'番茄炒蛋配米饭','ingredients':['番茄、鸡蛋','米饭和一份蔬菜'],'steps':['番茄切块，鸡蛋打散','鸡蛋炒熟后加入番茄，再充分炒熟','搭配米饭和蔬菜']},
            'takeout':{'dish':'鸡肉饭配蔬菜','search':'鸡肉饭 蔬菜套餐','ordering':'酱汁分装，搭配一份蔬菜'}}},
        {'title':'午休轻松散步','when':'每天','detail':'舒适步行15分钟。','minimum':'先从5分钟开始'}]}
    w=product.workspace(server)
    source={'conversation_id':'health-qa-conversation','message_id':'health-qa-original','text':'隔离测试：建立计划','at':product.now()}
    old=product.normalize_plan(plan,'今天',w,source);old.update(status='replaced',replaced_from=product.today())
    current=product.normalize_plan(plan,'今天',w,source,old);current['status']='active'
    w['plans']=[old,current]
    w['feedback']=[{'id':'qa-feedback','task_id':f"{old['id']}:1:{old['items'][0]['id']}:{product.today()}",'status':'done','note':'历史打卡','created_at':product.now()}]
    server.save_json(server.DATA/'workspace.json',w)
    server.save_json(server.RECORDS,[server.prepare_record({'type':'weight','value':{'kg':82.4}})])
    def reply(messages,*args,**kwargs):
        text=messages[-1]['content'];facts=json.loads(messages[1]['content'])
        result={'reply':'把番茄切块，鸡蛋打散，炒熟后搭配米饭与蔬菜。','decision':{'action':'none','reason':'查看做法'},'plan':None}
        if '午休散步完成了' in text:
            task=next(t for t in facts['today_tasks'] if '散步' in t['title'])
            result.update(reply='已收到散步反馈。',feedback=[{'task_id':task['task_id'],'status':'done','evidence':'午休散步完成了'}])
        return json.dumps(result,ensure_ascii=False)
    server.call_ai=reply
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-health-pages']}
    print('Isolated health pages ready on 8795',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler).serve_forever()
