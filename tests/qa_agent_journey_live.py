"""Fictional end-to-end conversation against the configured model, no real data."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
output=ROOT/'tmp/agent-journey-live-0.4.39.json'
rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-agent-journey-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    turns=[
        '我想减肥。',
        '我38岁，男，身高1.75米，85公斤，想减到75公斤。没有确诊疾病，没有手术史，没有过敏，没有用药。平时久坐上班，晚上八点下班只能点外卖。',
        '早餐通常一杯牛奶两个鸡蛋，午餐食堂一碗饭一荤两素，晚餐经常一大盒炒面。不喝含糖饮料，不吃零食。23点睡7点起，平时不运动，周末可以走路，去年80公斤。先帮我比较晚餐怎么选，别继续查户口。',
        '你还记得我的身高体重和下班时间吗？按这个情况，盖饭和炒面怎么选？',
        '我想开始运动，工作日每天有20分钟，家里没器械，没有运动时不适。请告诉我从什么开始合适，需要再了解的关键情况可以一起问。',
    ]
    for index,text in enumerate(turns):
        started=time.monotonic()
        answer=product.chat(server,{'text':text,'conversation_id':'agent-live-fictional',
            'client_message_id':f'agent-journey-{index}'})
        row={'turn':index+1,'user':text,'reply':answer['reply'],'error':answer.get('ai_error'),
             'elapsed_seconds':round(time.monotonic()-started,2),'adjustments':answer.get('reply_adjustments'),
             'profile':product.snapshot(server)['profile']}
        rows.append(row);output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        if row['error']:raise SystemExit('Live model failed; see fictional acceptance artifact')
    image=ROOT/'tmp/workbench-v3-qa/synthetic-menu.png'
    if image.exists():
        started=time.monotonic()
        result=server.analyze_image({'data':base64.b64encode(image.read_bytes()).decode(),
            'mime':'image/png','category':'auto','conversation_id':'agent-live-fictional',
            'context':'这是合成测试菜单，请帮我选一餐，说明怎么搭配、建议份量和吃完整份要考虑什么，不是要记摄入。'})
        status,payload=200,result
        review=(payload.get('media') or payload).get('review',{})
        rows.append({'vision_status':status,'reply':product.image_report_reply(review),
            'review':review,'elapsed_seconds':round(time.monotonic()-started,2)})
        output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    assert product.snapshot(server)['profile']['height_cm']==175
    assert not any(r['type']=='meal' for r in product.snapshot(server)['records'])
