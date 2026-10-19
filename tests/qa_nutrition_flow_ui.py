"""Isolated HTTP fixture for archive, next-day guide and real JPEG upload."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,storage,product,intake
with tempfile.TemporaryDirectory(prefix='zhiheng-flow-ui-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    profile={k:'明确回答的测试资料' for k in intake.QUESTIONS if k not in ('age','weight_kg')}
    profile.update(sex='男',height_cm=175,breakfast_habit='一杯牛奶两个鸡蛋',lunch_habit='一碗米饭和鸡肉蔬菜',dinner_habit='一碗面条',conditions=['没有'],allergies=['没有'],medications=['没有'],surgeries=['没有'])
    server.save_json(server.PROFILE,profile)
    r=server.prepare_record({'type':'weight','value':{'kg':80}});r.update(created_at=product.now(),occurred_at=product.now());server.save_json(server.RECORDS,[r])
    server.save_json(server.CONVERSATIONS,[
        {'id':'older-conversation','created_at':product.now(),'messages':[{'id':'older-message','role':'user','text':'这是一条独立的虚构历史对话。'}]},
        {'id':'flow-conversation','created_at':product.now(),'messages':[{'id':'age-question','role':'assistant','text':'你今年多大？'}]}])
    def model(*args,**kwargs):
        if kwargs.get('vision') or (len(args)>1 and args[1]):return json.dumps({'category':'food','summary':'识别到米饭与鸡肉，份量需要核对。','foods':[{'name':'米饭','grams':[150,200],'per_100g':{'kcal':[110,120],'protein_g':[2,3],'carbs_g':[25,28],'fat_g':[.2,.5]}},{'name':'鸡肉','grams':[80,100],'per_100g':{'kcal':[160,200],'protein_g':[25,30],'carbs_g':[0,2],'fat_g':[4,8]}}],'advice':['请补充是否有额外酱料。'],'questions':['这份食物是准备吃还是已经吃过？']},ensure_ascii=False)
        return json.dumps({'reply':'先从简单的习惯开始。','decision':{'action':'update','reason':'根据已知档案'},'plan':{'title':'独立流程测试计划','goal':'规律饮食','items':[{'title':'舒适散步','when':'每天下班后','detail':'身体舒适时轻松活动'}]}},ensure_ascii=False)
    server.call_ai=model;server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-nutrition-flow']}
    print('Flow fixture on 8798',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8798),server.Handler).serve_forever()
