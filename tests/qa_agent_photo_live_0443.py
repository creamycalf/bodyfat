"""Actual service acceptance with disposable fictional data and a CC0 photo."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
FOCUS='--focus' in sys.argv
sys.path.insert(0,str(ROOT));OUTPUT=ROOT/('tmp/agent-photo-live-0.4.43-focus.json' if FOCUS else 'tmp/agent-photo-live-0.4.43.json');rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-photo-live-0443-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    actual=server.call_ai;captured=[];payloads=[]
    def model(messages,*args,**kwargs):
        payloads.append(messages)
        value=actual(messages,*args,**kwargs)
        captured.append({'raw':server.parse_json(value) or value,'meta':server.ai_meta()})
        return value
    server.call_ai=model
    def reset(profile=None):
        for path,value in ((server.PROFILE,profile or {}),(server.RECORDS,[]),(server.MEDIA,[]),
                           (server.CONVERSATIONS,[]),(server.DATA/'workspace.json',{})):
            server.save_json(path,value)
    def save(row):
        rows.append(row);OUTPUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:row[k] for k in ('name','reply','seconds','error','checks')},ensure_ascii=False),flush=True)
    def turn(name,text,cid='photo-live',check=None,**extra):
        captured.clear();payloads.clear();start=time.monotonic()
        result=product.chat(server,{'text':text,'conversation_id':cid,'client_message_id':'0443-'+name,**extra})
        state=product.snapshot(server)
        facts=next((server.parse_json(m.get('content')) for m in (payloads[0] if payloads else [])
                    if m.get('role')=='system' and isinstance(m.get('content'),str) and m['content'].startswith('{')), {}) or {}
        checks={'completed':not result.get('ai_error')}
        if check:checks.update(check(result,state,facts))
        save({'name':name,'user':text,'reply':result['reply'],'seconds':round(time.monotonic()-start,3),
              'error':result.get('ai_error'),'checks':checks,'raw':captured.copy(),
              'model_calls':len(captured),'reply_source':result.get('reply_source'),
              'profile':state['profile'],'records':state['records'],'facts':facts})
        return result,state
    def vision(name,data,context,category,cid,check):
        captured.clear();payloads.clear();start=time.monotonic()
        result=server.analyze_image({'data':base64.b64encode(data).decode(),'mime':'image/jpeg' if category=='food' else 'image/png',
            'context':context,'category':category,'conversation_id':cid})
        review=result.get('review',{})
        checks={'completed':not result.get('ai_error'),**check(review)}
        save({'name':name,'reply':product.image_report_reply(review),'review':review,'seconds':round(time.monotonic()-start,3),
              'error':result.get('ai_error'),'checks':checks,'raw':captured.copy(),'model_calls':len(captured)})
        before=len(captured)
        published=product.chat(server,{'text':context,'media_id':result['media']['id'],'conversation_id':cid,
            'client_message_id':'0443-publish-'+name},image_review_only=True)
        assert len(captured)==before,'Publishing an analyzed image unexpectedly called a second model'
        assert not published.get('ai_error'),published.get('ai_error')
        return result['media']['id']
    if FOCUS:
        reset({'allergies':['对花生过敏']})
        previous=json.loads((ROOT/'tmp/agent-photo-live-0.4.43.json').read_text(encoding='utf-8'))
        review=next(row['review'] for row in previous if row['name']=='public_food_photo')
        server.save_json(server.MEDIA,[{'id':'focus-photo','type':'food','review':review}])
        turn('focus_half','这份只吃一半，蛋白质多少？',media_id='focus-photo',check=lambda r,s,f:{
            'local_no_transport':not captured and r.get('photo_calculation',{}).get('fraction')=='1/2'})
        for name,text in (('focus_protein','蛋白质够吗？'),('focus_fat','脂肪会不会太多？')):
            turn(name,text,check=lambda r,s,f:{'photo_context':bool(f.get('linked_images')),
                'calculated_half_kept':'蛋白质约 15–29 克' in r['reply'],
                'share_persists':r.get('photo_calculation',{}).get('fraction')=='1/2','no_intake':not s['records']})
        raise SystemExit(0 if all(all(row['checks'].values()) for row in rows) else 1)
    reset({'age':38,'sex':'男','height_cm':175,'allergies':['对花生过敏']})
    photo=vision('public_food_photo',(ROOT/'tmp/public-meal-upload.jpg').read_bytes(),
        '我在决定这顿怎么吃，分析营养范围、吃多少和吃完整份的考虑，只分析不要记摄入。','food','photo-live',
        lambda review:{'main_foods':all(any(word in json.dumps(review,ensure_ascii=False) for word in group)
                                      for group in (('米饭','白饭'),('牛肉',),('西兰花','花椰菜'))),
            'no_eaten_question':not any(word in json.dumps(review,ensure_ascii=False) for word in ('吃了吗','吃过了吗','是否已经吃')),
            'no_intake':not server.records()})
    turn('whole_numeric','这份热量和蛋白质各是多少？',media_id=photo,check=lambda r,s,f:{
        'local_no_transport':not captured and r.get('reply_source')=='portion_calculator','no_intake':not s['records']})
    turn('half_numeric','如果这份只吃一半，热量和蛋白质各是多少？只是分析，不要记录。',media_id=photo,check=lambda r,s,f:{
        'local_no_transport':not captured and r.get('reply_source')=='portion_calculator','no_intake':not s['records']})
    turn('implicit_protein','蛋白质够吗？',check=lambda r,s,f:{
        'photo_context_kept':bool(f.get('linked_images')),
        'answers_protein':'蛋白' in r['reply'],'no_repeat_basics':not any(x in r['reply'] for x in ('你多大','年龄是多少','身高多少')),
        'no_intake':not s['records']})
    turn('topic_switch','先不聊吃的了。我膝盖有旧伤，走路正常，但跑步会疼。应该怎样开始活动？',check=lambda r,s,f:{
        'photo_not_stuck':not f.get('linked_images'),'current_issue_first':'膝' in r['reply'],
        'no_food_intake':not any(x['type']=='meal' for x in s['records'])})
    turn('actual_half','这份我吃了一半，请记录。',media_id=photo,check=lambda r,s,f:{
        'one_meal':len([x for x in s['records'] if x['type']=='meal'])==1})
    turn('other_person_correction','更正，这份是同事吃的，我没吃。',media_id=photo,check=lambda r,s,f:{
        'no_self_meal':not any(x['type']=='meal' and x.get('status') not in ('retracted','corrected') for x in s['records'])})
    reset()
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1300,610),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',33)
    lines=['SYNTHETIC LAB REPORT - SOFTWARE TEST ONLY','Date: 2026-10-18',
        'Test                 Result       Unit          Reference',
        'ApoB                 1.3          g/L           0.6-1.1',
        'LDL-C                4.2          mmol/L        <3.4',
        'Urine glucose        0            mmol/L        0']
    for i,line in enumerate(lines):draw.text((32,30+90*i),line,font=font,fill='black')
    stream=io.BytesIO();image.save(stream,format='PNG')
    def report_checks(review):
        tests=(review.get('report') or {}).get('tests',[])
        return {'apob_value_unit':any('1.3'==str(x.get('value')) and x.get('unit')=='g/L' for x in tests),
                'zero_kept':any(str(x.get('value')) in ('0','0.0') for x in tests),'no_intake':not server.records()}
    report=vision('synthetic_report',stream.getvalue(),
        '这是虚构软件测试报告，请整理可读的原值、单位、参考范围和日期，不诊断。','report','report-live',report_checks)
    turn('report_apob','请解释这张报告的ApoB，列原结果、单位和参考范围。',cid='report-live',media_id=report,check=lambda r,s,f:{
        'source_values_preserved':all(x in r['reply'] for x in ('1.3','g/L'))})
    reset()
    turn('weight_start','我想减肥，先帮我了解起点和目标。',cid='weight-live',check=lambda r,s,f:{
        'combined_basics':sum(word in r['reply'] for word in ('年龄','多大','性别','身高','体重'))>=3})
    turn('weight_full_answer','我38岁，男，身高175厘米，体重85公斤，想先减到78公斤。没有确诊疾病、用药、手术和食物过敏。常吃外卖，晚八点下班，每天有20分钟活动。',cid='weight-live',check=lambda r,s,f:{
        'basics_extracted':s['profile'].get('age')==38 and s['profile'].get('height_cm')==175 and s['profile'].get('sex')=='男',
        'weight_saved':any(x['type']=='weight' and x.get('value',{}).get('kg')==85 for x in s['records']),
        'no_repeated_basics':not any(x in r['reply'] for x in ('年龄是多少','你多大','身高多少','体重多少','性别是什么'))})
if not all(all(row['checks'].values()) for row in rows):raise SystemExit(1)
