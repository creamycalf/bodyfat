"""Synthetic text meal checks; real model, no formal data or measured accuracy claims."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import product
import server
import storage

sys.stdout.reconfigure(errors='backslashreplace')

out=Path('tmp')/('nutrition-live-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True,exist_ok=False)
server.DATA=out/'data';server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
    setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA)
checks=[];results=[]
def dump(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
real_call=server.call_ai
def capture(*args,**kwargs):
    raw=real_call(*args,**kwargs);dump(f'raw-{len(results)+1}.json',{'raw':raw,'meta':server.ai_meta()});return raw
server.call_ai=capture
def check(name,passed):
    checks.append({'name':name,'passed':bool(passed)});dump('checks.json',checks)
texts=[
 '以下是虚构测试资料：今天早餐我吃了一个约50克的水煮鸡蛋、两片共60克全麦面包，喝了250毫升无糖豆浆。请记录并给粗略营养范围，说明估算假设，不要编造数据库来源。',
 '今天晚餐我吃了自助餐，但已经记不清具体食物和份量。请只记录这件事，营养保持未知，不要猜测数值。'
]
for i,text in enumerate(texts):
    print('START meal '+str(i+1),flush=True);start=time.monotonic()
    r=product.chat(server,{'text':text,'conversation_id':'nutrition-synthetic','client_message_id':f'nutrition-message-{i+1}'})
    state=product.snapshot(server);results.append({'input':text,'seconds':round(time.monotonic()-start,1),'result':r,'state':state})
    dump('results.json',results)
    check(f'meal {i+1} connected',r.get('ai_status')=='connected')
    fresh=[x for x in state['records'] if x.get('source_message',{}).get('message_id')==f'nutrition-message-{i+1}']
    check(f'meal {i+1} saved',bool(fresh))
    if i==0:
        check('breakfast kcal range',any(x['value'].get('nutrition',{}).get('kcal') is not None for x in fresh))
        check('breakfast uncertainty',any(x['value'].get('uncertainty') for x in fresh))
    else:
        check('unspecified dinner remains unknown',bool(fresh) and all(all(v is None for v in x['value'].get('nutrition',{}).values()) for x in fresh))
    check(f'meal {i+1} has provenance',bool(fresh) and all(x['value'].get('nutrition_context') for x in fresh))
    print(json.dumps({'step':i+1,'status':r.get('ai_status'),'records':fresh},ensure_ascii=False),flush=True)
dump('final-state.json',product.snapshot(server))
print('OUTPUT '+str(out.resolve()),flush=True)
print(json.dumps(checks,ensure_ascii=False),flush=True)
sys.exit(0 if all(x['passed'] for x in checks) else 1)
