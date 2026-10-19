"""Two accelerated days of synthetic data using the configured real model.
Run once, then --serve to inspect the persistent isolated result on port 8797.
"""
import base64
import copy
import json
import sys
import time
import os
from datetime import datetime as RealDatetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import product
import workbench
import storage

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp'/os.environ.get('TWO_DAY_RUN','two-day-live-20260916')
OUT.mkdir(parents=True,exist_ok=True)
server.DATA=OUT/'data';server.DATA.mkdir(exist_ok=True)
server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
    setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA)
class Clock(RealDatetime):
    current=RealDatetime(2026,9,15,8,0)
    @classmethod
    def now(cls,tz=None):return cls.current if tz is None else cls.current.astimezone(tz)
server.datetime=Clock;product.datetime=Clock;workbench.datetime=Clock
def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
if '--serve' in sys.argv:
    Clock.current=RealDatetime(2026,9,16,20,0)
    server.STARTUP_STATUS={'ok':True,'checks':['SYNTHETIC two-day live-model test; isolated data']}
    print('Two-day synthetic result: http://127.0.0.1:8797/',flush=True)
    class PreviewHandler(server.Handler):
        def do_GET(self):
            if self.path=='/report.html' or self.path in {f'/{v}-{width}.png' for v in ('dashboard','plan','archive','chat') for width in (1280,390)}:
                target=OUT/self.path.lstrip('/')
                if target.is_file():return self.send_bytes(200,target.read_bytes(),'text/html; charset=utf-8' if target.suffix=='.html' else 'image/png')
                return self.send_json(404,{'error':'test_artifact_not_ready'})
            if self.path=='/':
                html=(ROOT/'index.html').read_text(encoding='utf-8').replace('<body>','<body><p style="padding:12px;margin:0;background:#fff2c6;color:#493d17;text-align:center">两天流程验收 · 全部为虚构资料 · 当前模拟日期 2026-09-16 · 独立测试环境</p>')
                return self.send_bytes(200,html.encode(),'text/html; charset=utf-8')
            return super().do_GET()
    server.ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('TWO_DAY_PORT','8797'))),PreviewHandler).serve_forever()
    sys.exit()
if product.snapshot(server)['conversations']:
    raise SystemExit('Existing run preserved. Use --serve; do not overwrite.')
steps=[];checks=[]
real_call_ai=server.call_ai
def captured_call(messages,*args,**kwargs):
    raw=real_call_ai(messages,*args,**kwargs)
    dump(f'model-response-{len(list(OUT.glob("model-response-*.json")))+1:02}.json',{'response':raw,'meta':server.ai_meta()})
    return raw
server.call_ai=captured_call
def check(name,condition,detail=''):
    checks.append({'name':name,'passed':bool(condition),'detail':detail});dump('checks.json',checks)
def chat(label,text,**extra):
    started=time.monotonic();p={'text':text,'conversation_id':'two-day-synthetic-user',
        'client_message_id':f'two-day-step-{len(steps)+1:03}',**extra}
    print('START '+label,flush=True)
    try:r=product.chat(server,p)
    except Exception as e:r={'error':str(e),'exception':type(e).__name__}
    steps.append({'label':label,'at':Clock.now().isoformat(),'input':p,'result':r,'seconds':round(time.monotonic()-started,1)})
    dump('steps.json',steps);dump(f'state-{len(steps):02}.json',product.snapshot(server))
    print(json.dumps({'step':label,'seconds':steps[-1]['seconds'],'ai_status':r.get('ai_status'),'error':r.get('error') or r.get('ai_error'),'receipts':r.get('receipts')},ensure_ascii=False),flush=True)
    return p,r

chat('第一天：首次了解','以下是软件验收用的虚构人物，不是真实用户。我今年35岁，身高175厘米，今天82.4公斤。希望逐步改善饮食和活动习惯，请先了解我，只问最有价值的一个问题。')
chat('第一天：补充档案和建立计划','我是久坐办公，通常23点睡7点起，午餐点外卖，晚上自己做饭，每晚有20分钟散步时间。自述没有已知疾病、过敏和用药。请根据已知资料制定从今天开始执行的一周计划，包含具体午餐和晚饭后散步，未知资料标明。')
snap=product.snapshot(server)
for pending in list(snap['pending']):
    if pending['kind']=='profile':
        product.action(server,{'action':'pending','id':pending['id'],'accept':True})
if not product.snapshot(server)['plans']:
    chat('第一天：资料确认后重试计划','已在档案确认资料，请根据已保存资料生成从今天开始执行的一周计划，午餐和晚间散步各一项。')
snap=product.snapshot(server);check('第一天档案和计划实际保存',bool(snap['profile']) and bool(snap['plans']))
if snap['plans'] and snap['plans'][-1]['status']=='suggested':
    product.action(server,{'action':'plan_status','id':snap['plans'][-1]['id'],'version':snap['plans'][-1]['version'],'status':'active'})
Clock.current=RealDatetime(2026,9,15,12,0)
image=ROOT/'tmp/workbench-v3-qa/synthetic-menu.png'
mid=None
if image.exists():
    print('START synthetic image recognition',flush=True)
    try:
        result=server.analyze_image({'data':base64.b64encode(image.read_bytes()).decode(),'mime':'image/png','category':'food','context':'虚构软件测试营养标签，并非真实餐食。目前还没吃。'})
        dump('image-result.json',result);mid=result.get('media',{}).get('id')
        check('真实视觉返回可用候选',bool(result.get('review',{}).get('record_candidates')))
    except Exception as e:check('真实视觉返回可用候选',False,str(e))
else:check('真实视觉返回可用候选',False,'缺少合成标签图')
if mid:
    chat('第一天：照片未吃','这份还没吃，只看一下营养。',media_id=mid)
    check('未吃照片不计入摄入',not [r for r in server.records() if r.get('media_id')==mid])
    Clock.current=RealDatetime(2026,9,15,12,30)
    payload,result=chat('第一天：确认半份','刚才那份我吃了一半，请记录。',media_id=mid)
    before=copy.deepcopy(server.records())
    try:product.chat(server,payload)
    except Exception as e:check('消息重试幂等',False,str(e))
    else:check('消息重试幂等',before==server.records())
    check('半份只产生一条餐次',len([r for r in server.records() if r.get('media_id')==mid])==1)
Clock.current=RealDatetime(2026,9,15,19,30)
chat('第一天：晚餐记录','晚饭我吃了番茄炒蛋、半碗米饭和一份青菜，请记录为今天的晚餐。')
tasks=product.snapshot(server)['tasks']
if tasks:
    task=next((t for t in tasks if '散步' in t['title']),tasks[-1])
    chat('第一天：对话打卡',task['title']+'完成了。')
    check('对话打卡落到同一任务',any(t['task_id']==task['task_id'] and t['status']=='done' for t in product.snapshot(server)['tasks']))
dump('day1.json',product.snapshot(server))
Clock.current=RealDatetime(2026,9,16,8,0)
chat('第二天：体重与睡眠','今天体重82.1公斤，昨晚睡了7小时。请记录，不用重新制定计划。')
check('两天体重均保留',len([r for r in server.records() if r['type']=='weight'])==2)
check('第二天不会继承昨天完成状态',all(t['status']!='done' for t in product.snapshot(server)['tasks']))
chat('第二天：早餐记录','今天早餐我吃了一个鸡蛋、一片全麦面包，喝了一杯无糖豆浆，请记录早餐。')
Clock.current=RealDatetime(2026,9,16,12,0)
before=copy.deepcopy(server.records())
chat('第二天：跨餐次表达','昨天那份午饭我吃了一半，今天午饭还没吃。不要更改昨天的摄入记录。',**({'media_id':mid} if mid else {}))
check('跨天表达不改已有摄入',before==server.records())
chat('第二天：工作变化调整计划','更正，每天可用时间现在是午休20分钟，晚上加班到21点30分。请把晚间散步调整到午休，饮食安排保持不变，并同步档案。')
snap=product.snapshot(server);check('调整保留旧计划版本',len(snap['plans'])>=2)
Clock.current=RealDatetime(2026,9,16,18,0)
meal=next((r for r in server.records() if r['type']=='meal' and str(r.get('occurred_at','')).startswith('2026-09-15')),None)
if meal:
    before=copy.deepcopy(server.records());payload={'id':meal['id'],'operation':'edit','date':'2026-09-15',
        'description':meal['value'].get('description','测试餐食')+'（手动核对份量）','nutrition_mode':'scale','factor':0.5}
    preview=product.action(server,{'action':'meal_preview',**payload})
    check('历史餐次修正预览无写入',before==server.records())
    saved=product.action(server,{'action':'meal_commit',**payload,'token':preview['token']})
    check('修正原记录不新增餐次',len(before)==len(server.records()))
    product.action(server,{'action':'meal_undo','correction_id':saved['correction_id']})
    check('撤销精确恢复原餐次',before==server.records())
snap=product.snapshot(server)
if snap['tasks']:
    product.action(server,{'action':'feedback','task_id':snap['tasks'][0]['task_id'],'status':'partial','note':'虚构测试：只执行一部分'})
    check('页面部分完成打卡可保存',product.snapshot(server)['tasks'][0]['status']=='partial')
Clock.current=RealDatetime(2026,9,16,20,0)
dump('day2.json',product.snapshot(server));dump('checks.json',checks)
print(json.dumps({'complete':True,'passed':sum(c['passed'] for c in checks),'total':len(checks),'output':str(OUT)},ensure_ascii=False),flush=True)
