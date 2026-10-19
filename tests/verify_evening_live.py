"""Late first use: synthetic completed profile, real model, isolated storage."""
import json,sys,time
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,product,storage,workbench
source=Path(sys.argv[1]);profile=json.loads(source.read_text(encoding='utf-8'))['profile']
profile.setdefault('activity_baseline','白天久坐，目前没有固定运动')
out=Path('tmp')/('evening-live-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
server.DATA=out/'data';server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA);server.save_json(server.PROFILE,profile)
class Evening(datetime):
    @classmethod
    def now(cls,tz=None):return datetime.now(tz).replace(hour=21,minute=30,second=0)
product.datetime=server.datetime=workbench.datetime=Evening
server.CONFIG['ai']['base_url']='http://47.110.38.211:8080/v1'
r=server.prepare_record({'type':'weight','value':{'kg':80}});r.update(occurred_at=product.now(),created_at=product.now());server.save_json(server.RECORDS,[r])
results=[]
real_call=server.call_ai
def capture(*args,**kwargs):
    raw=real_call(*args,**kwargs)
    (out/f'raw-{len(results)+1}.json').write_text(json.dumps({'raw':raw,'meta':server.ai_meta()},ensure_ascii=False,indent=2),encoding='utf-8')
    return raw
server.call_ai=capture
for n,text in enumerate(['请制定从今天开始执行的减脂计划','早餐吃了两个鸡蛋和牛奶，午餐吃过一碗米饭和鸡肉蔬菜，晚餐已吃完一碗面条。接下来不再吃正餐，凌晨2点睡，今天只想轻松散步。']):
    print('START evening',n+1,flush=True)
    result=product.chat(server,{'text':text,'conversation_id':'evening-synthetic','client_message_id':f'evening-message-{n}'})
    results.append({'input':text,'result':result})
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result.get('ai_status')=='connected' and not result.get('ai_error'),result.get('ai_error')
    if n==0:assert result['plan'] is None and '吃喝' in result['reply']
    else:
        assert result['plan'] is not None,result['reply']
        tasks=product.snapshot(server)['tasks']
        assert tasks
        assert not any(any(meal in task['title'] for meal in ('早餐','午餐','晚餐')) for task in tasks),tasks
        assert not any('上午' in task['when'] or '全天' in task['when'] for task in tasks),tasks
print('PASS evening remaining-time plan:',out,flush=True)
