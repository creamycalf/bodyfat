"""Targeted retest with fictional saved context and a synthetic report image."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
prior=json.loads((ROOT/'tmp/agent-journey-live-0.4.39.json').read_text(encoding='utf-8'))
history=[row for row in prior if row.get('turn')]
with tempfile.TemporaryDirectory(prefix='zhiheng-agent-followup-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    server.save_json(server.PROFILE,history[-1]['profile'])
    server.save_json(server.RECORDS,[{'id':'fictional-weight','type':'weight','value':{'kg':85},
        'status':'confirmed','observed_at':'2026-10-16T08:00:00','memory_enabled':True}])
    cid='agent-followup-fictional'
    server.save_json(server.CONVERSATIONS,[{'id':cid,'messages':[
        {'id':f'{i}-{role}','role':role,'text':row['user'] if role=='user' else row['reply']}
        for i,row in enumerate(history) for role in ('user','assistant')]}])
    results=[]
    start=time.monotonic()
    answer=product.chat(server,{'text':'请具体比较晚餐盖饭和炒面怎么选，说明搭配和份量，不用再问我的基础资料。',
        'conversation_id':cid,'client_message_id':'agent-followup-meal'})
    results.append({'kind':'meal_comparison','reply':answer['reply'],'error':answer.get('ai_error'),
        'elapsed_seconds':round(time.monotonic()-start,2)})
    assert not answer.get('ai_error')
    assert '盖饭' in answer['reply'] and '炒面' in answer['reply']
    assert '是在食堂、点外卖还是自己做' not in answer['reply']
    image=Image.new('RGB',(1200,700),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32)
    lines=['SYNTHETIC LAB REPORT - TEST DATA ONLY','Date: 2026-10-16','',
        'Test                      Value       Unit       Reference       Flag',
        'ALT                         56          U/L         0 - 40            H',
        'Fasting glucose        5.3        mmol/L       3.9 - 6.1',
        '', 'No diagnosis. Fictional software test fixture.']
    for i,line in enumerate(lines):draw.text((35,35+i*70),line,fill='black',font=font)
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    start=time.monotonic()
    result=server.analyze_image({'data':base64.b64encode(buffer.getvalue()).decode(),'mime':'image/png',
        'category':'report','conversation_id':cid,
        'context':'这是一份合成验收报告，帮我解读可读指标和值，哪些值得关注，合理下一步是什么，不要凭单项指标诊断。'})
    review=result['review']
    results.append({'kind':'synthetic_report','reply':product.image_report_reply(review),'review':review,
        'error':result.get('ai_error'),'elapsed_seconds':round(time.monotonic()-start,2)})
    path=ROOT/'tmp/agent-followup-live-0.4.39.json'
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in results:print(json.dumps(row,ensure_ascii=False),flush=True)
    assert not result.get('ai_error')
    assert review['report']['kind']=='report'
    assert any('ALT' in row['name'] and '56' in row['value'] for row in review['report']['tests'])
