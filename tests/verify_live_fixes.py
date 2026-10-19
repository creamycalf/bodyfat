"""Real-model spot checks of fixes, using a fresh synthetic fixture only."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import storage
import product

out=Path(sys.argv[1] if len(sys.argv)>1 else 'tmp/live-fixes-20260916');out.mkdir(parents=True,exist_ok=True)
server.DATA=out/'data';server.DATA.mkdir(exist_ok=True);server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
    setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA)
if server.records():raise SystemExit('Existing run preserved')
w=product.workspace(server)
source={'text':'虚构测试预置任务','at':product.now(),'conversation_id':'live-fix-synthetic','message_id':'fixture-only'}
plan=product.normalize_plan({'title':'虚构测试计划','goal':'测试记录一致性','items':[{'title':'工作日饮水提醒','when':'每天','detail':'测试事项'}]},'今天',w,source)
plan['status']='active';w['plans']=[plan]
server.save_json(server.DATA/'workspace.json',w)
results=[]
for text in ['以下是虚构软件测试资料：我通常23点睡7点起，请记住这个作息习惯，不是昨晚的实际记录。',
             '工作日饮水提醒完成了。',
             '今天早餐我吃了一个鸡蛋、一片全麦面包，喝了一杯无糖豆浆，请记录。']:
    print('START '+str(len(results)+1),flush=True);start=time.monotonic()
    r=product.chat(server,{'text':text,'conversation_id':'live-fix-synthetic','client_message_id':f'live-fix-message-{len(results)+1}'})
    results.append({'input':text,'seconds':round(time.monotonic()-start,1),'result':r,'state':product.snapshot(server)})
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'step':len(results),'status':r.get('ai_status'),'error':r.get('ai_error'),'receipts':r.get('receipts')},ensure_ascii=False),flush=True)
checks={
    'habit_not_actual_sleep':not any(r['type']=='sleep' for r in results[0]['state']['records']),
    'checkin_persisted':any(t['status']=='done' for t in results[1]['state']['tasks']),
    'no_false_occupation_pending':not any(x.get('field')=='occupation' for x in results[1]['state']['pending']),
    'breakfast_saved':any(r['type']=='meal' for r in results[2]['state']['records']),
    'breakfast_nutrition_valid':all(v is None or isinstance(v,list) for r in results[2]['state']['records'] if r['type'] in ('meal','beverage') for v in r['value'].get('nutrition',{}).values()),
}
(out/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(checks),flush=True)
