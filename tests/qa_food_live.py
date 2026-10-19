"""Opt-in isolated live image/context test against the synthetic QA server only."""
import base64
import json
import uuid
import urllib.request
import sys
import time
from pathlib import Path

def post(path,payload):
    request=urllib.request.Request('http://127.0.0.1:8795'+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=180) as response:return json.loads(response.read())

image=Path('tmp/workbench-v3-qa/synthetic-menu.png').read_bytes()
if '--background' in sys.argv:
    submitted=post('/api/analyze-image',{'data':base64.b64encode(image).decode(),'mime':'image/png','category':'food',
        'context':'这是虚构测试菜单，尚未吃。请读取测试营养标签。','background':True,'client_job_id':uuid.uuid4().hex,
        'followup':{'text':'这是测试菜单，还没吃，请看看是否适合午饭。','conversation_id':'synthetic-food-background'}})
    mid=submitted['job']['media_id'];job_id=submitted['job']['id'];last=None
    for _ in range(100):
        with urllib.request.urlopen('http://127.0.0.1:8795/api/work/image-jobs') as response:jobs=json.loads(response.read())['jobs']
        job=next(j for j in jobs if j['id']==job_id)
        stamp=(job['status'],job['stage'])
        if stamp!=last:print(json.dumps({'job':job},ensure_ascii=False),flush=True);last=stamp
        if job['status'] in ('succeeded','failed','partial'):break
        time.sleep(3)
    assert job['status'] in ('succeeded','partial'),job
    with urllib.request.urlopen('http://127.0.0.1:8795/api/work/state') as response:state=json.loads(response.read())
    media=next(m for m in state['media'] if m['id']==mid)
    result={'media':media,'review':media.get('review'),'ai_status':media.get('analysis_status'),'ai_error':media.get('analysis_error')}
elif '--context-only' in sys.argv:
    with urllib.request.urlopen('http://127.0.0.1:8795/api/work/state') as response:state=json.loads(response.read())
    media=next(m for m in reversed(state['media']) if m.get('type')=='food' and m.get('analysis_status')=='connected')
    result={'media':media,'review':media.get('review'),'ai_status':media.get('analysis_status')}
elif '--retry' in sys.argv:
    with urllib.request.urlopen('http://127.0.0.1:8795/api/work/state') as response:state=json.loads(response.read())
    mid=next(m['id'] for m in reversed(state['media']) if m.get('type')=='food')
    result=post('/api/analyze-image',{'retry_id':mid,'context':'这是虚构测试菜单，尚未吃。请读取包装上的测试营养标签。'})
else:result=post('/api/analyze-image',{'data':base64.b64encode(image).decode(),'mime':'image/png','category':'food','context':'这是虚构测试菜单，尚未吃。请读取包装上的测试营养标签。'})
mid=result['media']['id']
print(json.dumps({'image_status':result.get('ai_status'),'image_error':result.get('ai_error'),'review':result.get('review')},ensure_ascii=False),flush=True)
for text in ['这是测试菜单，还没吃，请看看是否适合午饭。','虚构测试继续：刚才那个吃了一半，请记录实际食用量。']:
    r=post('/api/work/chat',{'text':text,'media_id':mid,'conversation_id':'synthetic-food-background' if '--background' in sys.argv else 'synthetic-food','client_message_id':uuid.uuid4().hex})
    with urllib.request.urlopen('http://127.0.0.1:8795/api/work/state') as response:state=json.loads(response.read())
    records=[x for x in state['records'] if x.get('media_id')==mid]
    print(json.dumps({'text':text,'status':r.get('ai_status'),'food_error':r.get('food_error'),'reply':r.get('reply'),'receipts':r.get('receipts'),'food_records':records},ensure_ascii=False),flush=True)
    if '还没吃' in text:assert not records,'Reference image was counted as consumption'
    else:
        assert len(records)==1,'Explicit consumption was not recorded exactly once'
        assert records[0]['value']['nutrition']['kcal']==[300,300],'Half of the explicit 600 kcal reference must be 300 kcal'
