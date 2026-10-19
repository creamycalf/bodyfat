"""Controlled-service checks; fictional records and a CC0 meal photograph only."""
import base64
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FINAL='--final' in sys.argv
FOCUS='--focus' in sys.argv
OUTPUT=ROOT/('tmp/agent-memory-live-0.4.42-focus.json' if FOCUS else
             'tmp/agent-memory-live-0.4.42-final.json' if FINAL else 'tmp/agent-memory-live-0.4.42.json')
rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-memory-live-0442-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage,nutrition_reports
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    actual=server.call_ai;captured=[];payloads=[]
    def model(messages,*args,**kwargs):
        payloads.append(messages)
        raw=actual(messages,*args,**kwargs)
        captured.append({'raw':server.parse_json(raw) or raw,'meta':server.ai_meta()})
        return raw
    server.call_ai=model
    def reset(profile=None):
        for path,value in ((server.PROFILE,profile or {}),(server.RECORDS,[]),(server.CONVERSATIONS,[]),
                           (server.MEDIA,[]),(server.DATA/'workspace.json',{})):
            server.save_json(path,value)
    def save(row):
        rows.append(row);OUTPUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:row[k] for k in ('name','reply','error','seconds','checks')},ensure_ascii=False),flush=True)
    def turn(name,text,cid='memory-live',check=None,**extra):
        if FOCUS and name!='forgotten_practical':return None,None
        captured.clear();payloads.clear();started=time.monotonic()
        result=product.chat(server,{'text':text,'conversation_id':cid,'client_message_id':'0442-'+name,**extra})
        state=product.snapshot(server)
        checks={'completed':not result.get('ai_error')}
        if check:checks.update(check(result,state))
        facts=next((server.parse_json(m['content']) for m in (payloads[0] if payloads else [])
                    if m.get('role')=='system' and isinstance(m.get('content'),str) and m['content'].startswith('{')),None)
        save({'name':name,'user':text,'reply':result['reply'],'raw':captured.copy(),'error':result.get('ai_error'),
              'seconds':round(time.monotonic()-started,2),'checks':checks,'profile':state['profile'],
              'records':state['records'],'context':facts,
              'request_chars':sum(len(json.dumps(p,ensure_ascii=False)) for p in payloads)})
        return result,state
    def old_lifestyle(extra=()):
        return {'id':'old-lifestyle','messages':[
            {'id':'practical','role':'user','text':'我家里没有冰箱，上班没法热饭，我不吃鱼。','created_at':'2026-09-01T12:00:00'},
            *[{'id':'noise-'+str(i),'role':'user' if i%2==0 else 'assistant','text':'聊聊当天的感受。',
                'created_at':'2026-10-01T12:00:00'} for i in range(40)],*extra]}
    reset()
    server.save_json(server.CONVERSATIONS,[old_lifestyle()])
    turn('old_practical','结合我以前说过的生活条件，今天晚饭怎么安排？',check=lambda r,s:{
        'uses_old_constraints':all(x in r['reply'] for x in ('冰箱','热饭','鱼')),
        'no_repeat_intake':not any(x in r['reply'] for x in ('家里有冰箱吗','能热饭吗','吃鱼吗'))})
    reset()
    server.save_json(server.CONVERSATIONS,[old_lifestyle([
        {'id':'new-practical','role':'user','text':'现在我有冰箱了，上班可以热饭了，我现在可以吃鱼了。','created_at':'2026-10-19T12:00:00'}])])
    turn('updated_practical','我现在做饭和吃鱼有什么条件或偏好？请只按我最后明确说的回答。',check=lambda r,s:{
        'new_values':all(x in r['reply'] for x in ('冰箱','鱼')),
        'no_old_restriction':not any(x in r['reply'] for x in ('没有冰箱','没法热饭','不吃鱼'))})
    reset()
    server.save_json(server.CONVERSATIONS,[old_lifestyle([
        {'id':'forget-fridge','role':'user','text':'请忘掉我的冰箱情况。','created_at':'2026-10-19T12:00:00'}])])
    turn('forgotten_practical','你还记得我家有没有冰箱、有什么忌口吗？不确定就说不知道。',check=lambda r,s:{
        # "这不代表家里没有冰箱" explicitly denies the inference, rather
        # than reviving the forgotten fact. Retain the raw reply for review.
        'no_retracted_fridge_fact':not re.search(r'家里(?:没有|没)冰箱',re.sub(r'不代表家里(?:没有|没)冰箱','',r['reply'])),
        'fish_preference_kept':'不吃鱼' in r['reply']})
    if FOCUS:raise SystemExit(0 if all(all(row['checks'].values()) for row in rows) else 1)
    if FINAL:
        reset({'food_habits':'家里没有冰箱。每餐预算20元。','preferences':['不吃鱼']})
        conversation=old_lifestyle()
        server.save_json(server.CONVERSATIONS,[conversation])
        w=product.workspace(server)
        w['profile_sources']['food_habits']={'source_message_id':'practical','message_id':'practical','at':'2026-09-01T12:00:00'}
        server.save_json(server.DATA/'workspace.json',w)
        turn('persisted_forget','请忘掉我的冰箱情况。',check=lambda r,s:{
            'removed_from_profile':'冰箱' not in str(s['profile']),
            'other_facts_kept':'20' in str(s['profile']) and '不吃鱼' in str(s['profile'])})
        turn('persisted_forget_new_chat','你记得我的预算、忌口和冰箱情况吗？不确定就说不知道。',cid='after-forget',check=lambda r,s:{
            'budget_and_fish':all(x in r['reply'] for x in ('20','不吃鱼')),
            'no_revived_fridge':not any(x in r['reply'] for x in ('家里没有冰箱','家里没冰箱'))})
    reset()
    server.save_json(server.RECORDS,[{'id':'eye','type':'lab_or_measurement','value':{'description':'视网膜复查待安排'},
        'confirmed':True,'created_at':'2026-01-01T12:00:00'},
        *[{'id':'noise-'+str(i),'type':'lab_or_measurement','value':{'description':'血常规化验'},
           'confirmed':True,'created_at':'2026-10-19T12:00:00'} for i in range(20)]])
    turn('eye_synonym','之前眼睛检查的情况，你还记得哪一项没安排吗？',check=lambda r,s:{
        'eye_recalled':any(x in r['reply'] for x in ('视网膜','眼底'))})
    def report(key,date,metric='LDL-C',value='4.2',unit='mmol/L',reference='<3.4'):
        return {'id':key,'type':'report','created_at':date+'T12:00:00','review':{'category':'report',
            'summary':'虚构的软件测试报告','report':nutrition_reports.report({'tests':[
                {'name':metric,'value':value,'unit':unit,'reference':reference,'date':date}]},'report')}}
    reset()
    noise=[report('unrelated-'+str(i),f'2026-{i+1:02d}-03','尿酸','400','μmol/L','200-420') for i in range(8)]
    server.save_json(server.MEDIA,[report('ldl-last-year','2025-09-03'),*noise,report('ldl-current','2026-10-01',value='3.0')])
    server.save_json(server.CONVERSATIONS,[{'id':'report-chat','messages':[
        {'role':'user','text':'两份其他报告','media_id':noise[-1]['id']},
        {'role':'user','text':'还有一份','media_id':noise[-2]['id']}]}])
    turn('historical_reports','去年9月与今年复查的LDL相比有什么变化？这两份都是我的，请按报告日期和单位说。',cid='report-chat',check=lambda r,s:{
        'both_values':all(x in r['reply'] for x in ('4.2','3.0')),
        'both_dates':'2025' in r['reply'] and '2026' in r['reply'],
        'no_reupload':not any(x in r['reply'] for x in ('请重新上传','再上传一次'))})
    reset()
    many=report('many-tests','2026-10-01')
    many['review']['report']=nutrition_reports.report({'tests':[
        *[{'name':f'其他指标{i}','value':i,'unit':'U/L','reference':'0-100','date':'2026-10-01'} for i in range(45)],
        {'name':'载脂蛋白B','value':'1.3','unit':'g/L','reference':'0.6-1.1','date':'2026-10-01'}]},'report')
    server.save_json(server.MEDIA,[many])
    turn('late_report_metric','请解释这张报告的载脂蛋白B，按原结果、单位和参考范围解释。',media_id='many-tests',check=lambda r,s:{
        'late_metric_kept':all(x in r['reply'] for x in ('1.3','g/L')),
        'no_missing_claim':not any(x in r['reply'] for x in ('没有载脂蛋白','没看到载脂蛋白'))})
    reset({'allergies':['对花生过敏']})
    captured.clear();payloads.clear();started=time.monotonic()
    photo_path=ROOT/('tmp/public-meal-upload.jpg' if FINAL else 'tmp/public-meal-cc0.jpg')
    image=server.analyze_image({'data':base64.b64encode(photo_path.read_bytes()).decode(),
        'mime':'image/jpeg','category':'food','conversation_id':'public-meal',
        'context':'我在决定这顿怎么吃，帮我分析食物、营养范围和吃多少合适，整份吃完有什么需要考虑？只是分析，不要记摄入。'})
    review=image.get('review',{});shown=product.image_report_reply(review);foodtext=json.dumps(review,ensure_ascii=False)
    save({'name':'public_food_photo','reply':shown,'review':review,'raw':captured.copy(),'error':image.get('ai_error'),
          'seconds':round(time.monotonic()-started,2),'checks':{'completed':not image.get('ai_error'),
          'rice_identified':any(x in foodtext for x in ('米饭','白饭')),'beef_identified':'牛肉' in foodtext,
          'vegetable_identified':any(x in foodtext for x in ('西兰花','花椰菜')),
          'no_eaten_question':not any(x in foodtext for x in ('吃了吗','吃过了吗','是否已经吃','有没有吃')),
          'no_intake':not server.records()},'provenance':{
              'url':'https://commons.wikimedia.org/wiki/File:Rice,_Beef_and_Broccoli_with_Soy_Sauce.jpg',
              'license':'CC0','author':'Adesolive','nutrition_ground_truth':False}})
    turn('public_photo_half','如果这份只吃一半，热量和蛋白质各是多少？只是分析，不要记录。',cid='public-meal',media_id=image['media']['id'],check=lambda r,s:{
        'portion_estimate':any(x in r['reply'] for x in ('一半','1/2')),'no_intake':not s['records']})
if not all(all(row['checks'].values()) for row in rows):raise SystemExit(1)
