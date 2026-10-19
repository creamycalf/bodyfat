"""Real model conversational acceptance using only fictional health facts."""
import json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
turns=[
    '我想减肥，你带着我一步步来。',
    '我38岁，男，身高175厘米，体重85公斤，想先减到78公斤，最难是加班后吃多，常吃外卖。',
    '没有确诊疾病，没有用药，没有手术史，没有食物过敏，平时运动也没有不舒服。',
    '早餐两个鸡蛋一杯牛奶；午餐一碗米饭、鸡肉和蔬菜；晚餐经常一份外卖炒面，份量一大盒；下午喝一杯奶茶，晚上偶尔吃薯片。',
    '平时凌晨一点睡，早上七点起。办公室久坐，一天走路约20分钟，晚上八点下班，每天可以抽20分钟活动。去年80公斤，现在85公斤，以前节食坚持不住，晚上饿得厉害。',
]
with tempfile.TemporaryDirectory(prefix='zhiheng-guidance-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,storage,product,intake
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    assert os.environ.get(server.CONFIG['ai'].get('api_key_env','ZHIHENG_AI_API_KEY'))
    storage.initialize(server.DATA)
    results=[]
    resume='--resume-fictional' in sys.argv
    recovery_turn=1;retry_job=None;retry_text=None
    if resume:
        # Only this script's explicitly fictional fixture is eligible. Never
        # restore the application data directory or its real health records.
        fixture=json.loads((ROOT/'tmp/guided-weight-live-0.4.28-fictional-state.json').read_text(encoding='utf-8'))
        assert set(fixture)==set(storage.NAMES)
        with storage.transaction(server.DATA):
            for name,value in fixture.items():storage.write(server.DATA,name,value)
        results=json.loads((ROOT/'tmp/guided-weight-live-0.4.28.json').read_text(encoding='utf-8'))
        recovery_turn=results[-1]['turn']
        job=next((j for j in reversed(product.workspace(server).get('evaluation_jobs',[]))
                  if j.get('kind')=='chat' and j.get('status')=='failed'),None)
        if job:retry_job=job['id'];retry_text=job['request']['text']
    try:
        for number,text in enumerate(turns,1):
            if resume and number<recovery_turn:continue
            started=time.monotonic()
            request={'text':text,'conversation_id':'guided-weight-live',
                     'client_message_id':f'guided-weight-live-{number}' if not resume else f'guided-weight-recovery-{number}-{time.time_ns()}'}
            if resume and retry_job and number==recovery_turn:request['retry_chat']=retry_job
            answer=product.chat(server,request)
            row={'turn':number,'user':text,'reply':answer['reply'],'error':answer.get('ai_error'),
                 'elapsed_ms':round((time.monotonic()-started)*1000),'has_plan':bool(answer.get('plan')),
                 'mode':product.workspace(server)['sessions']['guided-weight-live'].get('dialogue_mode')}
            results.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
            assert not answer.get('ai_error'),answer.get('ai_error')
            assert not answer.get('plan'),'Plan generated before fact confirmation'
            assert row['mode']=='assessment','Guidance unexpectedly stopped'
            assert intake.reply_question(answer['reply'],answer.get('decision')) or '请核对' in answer['reply'],'No next question or summary'
        profile=product.snapshot(server)['profile']
        assert profile.get('age')==38 and profile.get('height_cm')==175
        assert '78公斤' in profile.get('goals','')
        assert '七点起' in profile.get('sleep_schedule','')
        assert profile.get('occupation')=='办公室久坐'
        assert '20分钟' in profile.get('activity_baseline','')
        # The consultation must lead to an actual saved plan after the user
        # confirms the fact summary, not stop at another promise to help.
        started=time.monotonic()
        confirmation_request={'text':'确认','conversation_id':'guided-weight-live',
            'client_message_id':'guided-weight-live-confirm' if not resume else f'guided-weight-confirm-{time.time_ns()}'}
        if resume and recovery_turn>=6 and retry_job:
            confirmation_request.update(text=retry_text,retry_chat=retry_job)
        answer=product.chat(server,confirmation_request)
        row={'turn':6,'user':confirmation_request['text'],'reply':answer['reply'],'error':answer.get('ai_error'),
             'elapsed_ms':round((time.monotonic()-started)*1000),'has_plan':bool(answer.get('plan')),
             'plan':answer.get('plan'),'receipts':answer.get('receipts')}
        results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        assert not answer.get('ai_error'),answer.get('ai_error')
        # Older builds may have left a preference rewording pending. Resolve
        # that visibly through the same conversation, never by editing data.
        followup_number=6
        for _ in range(3):
            if answer.get('plan'):break
            if '用新记录' in answer['reply'] and '保留原记录' in answer['reply']:
                followup='保留原记录'
            elif '请核对我理解的情况' in answer['reply']:
                followup='确认'
            else:break
            followup_number+=1;started=time.monotonic()
            answer=product.chat(server,{'text':followup,'conversation_id':'guided-weight-live',
                'client_message_id':f'guided-weight-followup-{time.time_ns()}'})
            row={'turn':followup_number,'user':followup,'reply':answer['reply'],'error':answer.get('ai_error'),
                 'elapsed_ms':round((time.monotonic()-started)*1000),'has_plan':bool(answer.get('plan')),
                 'plan':answer.get('plan'),'receipts':answer.get('receipts')}
            results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
            assert not answer.get('ai_error'),answer.get('ai_error')
        if not answer.get('plan'):
            assert '今天已经吃过哪些餐' in answer['reply'],'No plan or concrete remaining-day question'
            assert product.workspace(server)['assessment_state']['summary_confirmation']['status']=='confirmed'
            started=time.monotonic()
            answer=product.chat(server,{'text':'今天早餐午餐晚餐都吃过了，今天没有安排机会，请明天开始。',
                'conversation_id':'guided-weight-live','client_message_id':'guided-weight-live-start'})
            row={'turn':followup_number+1,'user':'今天早餐午餐晚餐都吃过了，今天没有安排机会，请明天开始。',
                 'reply':answer['reply'],'error':answer.get('ai_error'),
                 'elapsed_ms':round((time.monotonic()-started)*1000),'has_plan':bool(answer.get('plan')),
                 'plan':answer.get('plan'),'receipts':answer.get('receipts')}
            results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
            assert not answer.get('ai_error'),answer.get('ai_error')
        assert answer.get('plan') and answer['plan'].get('items'),'No usable plan after summary confirmation'
        assert product.snapshot(server)['plans'],'Plan did not persist'
    finally:
        (ROOT/'tmp/guided-weight-live-0.4.28.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/'tmp/guided-weight-live-0.4.28-fictional-state.json').write_text(json.dumps(storage.snapshot(server.DATA),ensure_ascii=False,indent=2),encoding='utf-8')
