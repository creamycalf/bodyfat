"""End-to-end regression against the controlled service, fictional data only."""
import base64
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
phase=sys.argv[1] if len(sys.argv)>1 else 'initial'
if phase not in ('initial','final'):raise SystemExit('Expected initial or final')
OUTPUT=ROOT/('tmp/agent-reliability-live-0.4.41-final.json' if phase=='final' else 'tmp/agent-reliability-live-0.4.41.json')
rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-reliability-live-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    actual=server.call_ai;captured=[]
    def model(*args,**kwargs):
        raw=actual(*args,**kwargs);captured.append(server.parse_json(raw) or raw);return raw
    server.call_ai=model
    def reset(profile=None):
        for path,value in [(server.PROFILE,profile or {}),(server.RECORDS,[]),(server.CONVERSATIONS,[]),
                           (server.MEDIA,[]),(server.DATA/'workspace.json',{})]:server.save_json(path,value)
    def save(row):
        rows.append(row);OUTPUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:row[k] for k in ('name','reply','error','seconds','checks')},ensure_ascii=False),flush=True)
    def turn(name,text,cid='reliability-main',check=None,**extra):
        captured.clear();started=time.monotonic()
        result=product.chat(server,{'text':text,'conversation_id':cid,'client_message_id':'reliability-'+name,**extra})
        state=product.snapshot(server)
        checks={'model_completed':not bool(result.get('ai_error'))}
        if check:checks.update(check(result,state))
        row={'name':name,'user':text,'reply':result['reply'],'raw':captured.copy(),'error':result.get('ai_error'),
             'seconds':round(time.monotonic()-started,2),'checks':checks,'profile':state['profile'],
             'records':state['records'],'pending':state['pending'],'receipts':result.get('receipts')}
        save(row);return result,state
    reset({'age':38,'sex':'男','height_cm':175,'allergies':['对花生过敏']})
    turn('negated_delete','不要删除我的年龄记录。',check=lambda r,s:{'age_kept':s['profile'].get('age')==38})
    turn('hypothetical_delete','如果删除我的过敏记录，之后还会提醒我吗？',check=lambda r,s:{'allergy_kept':'花生' in str(s['profile'].get('allergies'))})
    turn('spouse_facts','我老公40岁，有糖尿病，身高180厘米，体重90公斤。这说的是他。',check=lambda r,s:{
        'self_unchanged':s['profile'].get('height_cm')==175 and not s['profile'].get('conditions'),
        'no_spouse_weight':not s['records'],'no_spouse_pending':not s['pending']})
    turn('facts_and_hypothesis','我男，38岁，身高175厘米，体重85公斤，对花生过敏。如果我想减脂，先从饮食还是运动开始更合适？',check=lambda r,s:{
        'facts_kept':s['profile'].get('age')==38 and s['profile'].get('height_cm')==175 and any(x.get('value',{}).get('kg')==85 for x in s['records'])})
    turn('new_chat_recall','你记得我的年龄、身高、体重和过敏吗？',cid='reliability-new-chat',check=lambda r,s:{
        'recalls_values':all(x in r['reply'] for x in ('38','175','85','花生'))})
    turn('height_correction','更正一下，身高是168厘米，之前175记错了。现在下午三点到晚上十一点上班。',check=lambda r,s:{
        'height_updated':s['profile'].get('height_cm')==168,
        'no_unrequested_questionnaire':not any(x in r['reply'] for x in ('还要先了解','一起说下确诊','为了让建议适合你'))})
    turn('corrected_new_chat','你记住的身高和上班时间是什么？',cid='reliability-corrected',check=lambda r,s:{
        'current_height_used':'168' in r['reply'],'no_old_conflict':not any(x in r['reply'] for x in ('冲突','不一致','175'))})
    turn('allergy_menu','食堂有宫保鸡丁、清炒豆腐和炒面，你建议怎么选？',check=lambda r,s:{
        'allergy_used':any(x in r['reply'] for x in ('花生','过敏'))})
    turn('explicit_delete','请删除我的年龄记录。',check=lambda r,s:{'age_removed':'age' not in s['profile']})
    reset()
    day=datetime.now().date().isoformat()
    turn('dated_weights','2026年9月1日体重85公斤，今天体重82公斤。请记录这两个测量值。',check=lambda r,s:{
        'two_weights':len([x for x in s['records'] if x['type']=='weight'])==2,
        'historical_date':any(x.get('value',{}).get('kg')==85 and str(x.get('occurred_at','')).startswith('2026-09-01') for x in s['records']),
        'current_date':any(x.get('value',{}).get('kg')==82 and str(x.get('occurred_at','')).startswith(day) for x in s['records']),
        'consistent_save_reply':not any(x in r['reply'] for x in ('未保存新的记录','没有保存','没有记录'))})
    turn('latest_weight_question','我最近一次体重是多少，和9月相比有什么变化？',check=lambda r,s:{'current_weight_answered':'82' in r['reply']})
    reset()
    review=server.normalize_image_analysis({'category':'food','summary':'隔离合成餐盘',
        'foods':[{'name':'测试餐食','nutrition_basis':'portion_estimate',
            'nutrition':{'kcal':[600,900],'protein_g':[30,45],'carbs_g':[60,90],'fat_g':[20,30]}}]},'food')
    server.save_json(server.MEDIA,[{'id':'reliability-food','type':'food','review':review,'confirmed':False}])
    turn('photo_third','如果这份只吃三分之一，热量和蛋白质是多少？只是分析，不要记录。',media_id='reliability-food',check=lambda r,s:{
        'computed_values':all(x in r['reply'] for x in ('200','300','10','15')),'no_intake':not s['records']})
    turn('photo_half_numeric','只吃这份的1/2，热量和蛋白质分别是多少？',media_id='reliability-food',check=lambda r,s:{
        'computed_values':all(x in r['reply'] for x in ('300','450','15','22.5')),'no_intake':not s['records']})
    turn('photo_actual_half','这份我吃了一半，请记录。',media_id='reliability-food',check=lambda r,s:{'one_intake':len(s['records'])==1})
    reset()
    from PIL import Image,ImageDraw,ImageFont
    for label,date,ldl in [('old','2026-09-01','4.2'),('new','2026-10-17','3.0')]:
        canvas=Image.new('RGB',(1200,600),'white');draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',34)
        lines=['SYNTHETIC LAB REPORT - SOFTWARE TEST ONLY',f'Date: {date}',
               'Test              Result        Unit             Reference',
               f'LDL-C              {ldl}         mmol/L           <3.4',
               'Urine glucose       0          mmol/L             0']
        for i,line in enumerate(lines):draw.text((35,35+i*85),line,font=font,fill='black')
        buffer=io.BytesIO();canvas.save(buffer,format='PNG');captured.clear();started=time.monotonic()
        result=server.analyze_image({'data':base64.b64encode(buffer.getvalue()).decode(),'mime':'image/png',
            'category':'report','conversation_id':'reliability-report-chat',
            'context':'这是虚构的软件测试报告，请整理可读指标、单位、参考范围和日期，不要诊断。'})
        media_id=result['media']['id'];tests=(result.get('review',{}).get('report') or {}).get('tests',[])
        save({'name':'vision-report-'+label,'reply':product.image_report_reply(result['review']),
            'raw':captured.copy(),'error':result.get('ai_error'),'seconds':round(time.monotonic()-started,2),
            'checks':{'model_completed':not bool(result.get('ai_error')),'ldl_read':any(ldl in str(x.get('value')) for x in tests),
                'zero_preserved':any(str(x.get('value')) in ('0','0.0') for x in tests)},'review':result['review']})
        product.chat(server,{'text':'帮我看看这份报告','media_id':media_id,'conversation_id':'reliability-report-chat',
            'client_message_id':'reliability-report-publish-'+label},image_review_only=True)
    turn('compare_reports','这两次检查报告相比有什么变化？请按日期比较LDL，不要再让我上传已经发过的报告。',
         cid='reliability-report-chat',media_id=media_id,check=lambda r,s:{'both_values_used':'4.2' in r['reply'] and ('3.0' in r['reply'] or '3' in r['reply'])})
    reset({'age':38,'sex':'男','height_cm':175,'allergies':['对花生过敏']})
    old={'id':'old-retina','type':'lab_or_measurement','value':{'description':'眼底检查提示需要复查，运动限制尚未询问医生。'},
         'confirmed':True,'memory_enabled':True,'status':'confirmed','created_at':'2026-09-01T12:00:00'}
    meals=[{'id':f'old-meal-{i}','type':'meal','value':{'description':'普通午餐'},'confirmed':True,'memory_enabled':True,
           'created_at':'2026-10-16T12:00:00'} for i in range(16)]
    server.save_json(server.RECORDS,[old,*meals])
    turn('old_health_retrieval','你还记得我以前眼底检查的问题吗？我想开始运动，应该如何考虑这件事？',
         cid='reliability-old-record',check=lambda r,s:{'old_fact_used':'眼底' in r['reply'] and '复查' in r['reply']})
    reset()
    turn('injury_exercise','我38岁，男，175厘米，85公斤。想开始健身，每天20分钟，家里没有器械，膝盖旧伤下蹲会痛。给一个适合的运动起步安排，不要让我填减肥问卷。',
         check=lambda r,s:{'injury_remembered':'膝' in str(s['profile'].get('conditions')),
             'no_weight_questionnaire':'公斤或斤' not in r['reply'],
             'timing_checked':any(x in r.get('reply_adjustments',[]) for x in ('exercise_timing_calculated','unchecked_exercise_timing_removed'))})
    failures=[{'name':row['name'],'failed':[k for k,v in row['checks'].items() if not v]} for row in rows if not all(row['checks'].values())]
    print(json.dumps({'calls_or_turns':len(rows),'failed_checks':failures,'output':str(OUTPUT)},ensure_ascii=False),flush=True)
    if failures:raise SystemExit(1)
