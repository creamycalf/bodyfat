"""Behavioral audit with fictional facts, raw/final comparisons and isolated storage."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
label=sys.argv[1] if len(sys.argv)>1 else 'before'
if label not in ('before','after','final'):raise SystemExit('Expected before, after or final')
output=ROOT/f'tmp/agent-audit-{"0.4.40" if label=="final" else "0.4.39"}-{label}.json'
rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-agent-audit-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    actual=server.call_ai
    captured=[]
    def model(*args,**kwargs):
        raw=actual(*args,**kwargs)
        captured.append(server.parse_json(raw) or raw)
        return raw
    server.call_ai=model
    def reset():
        for path,value in [(server.PROFILE,{}),(server.RECORDS,[]),(server.CONVERSATIONS,[]),
                           (server.MEDIA,[]),(server.DATA/'workspace.json',{})]:server.save_json(path,value)
    def turn(name,text,cid='audit-dialogue',**extra):
        captured.clear();start=time.monotonic()
        result=product.chat(server,{'text':text,'conversation_id':cid,
            'client_message_id':'audit-'+name,**extra})
        state=product.snapshot(server)
        row={'name':name,'user':text,'reply':result['reply'],'error':result.get('ai_error'),
            'seconds':round(time.monotonic()-start,2),'raw':captured.copy(),'profile':state['profile'],
            'records':state['records'],'pending':state['pending'],'plan':result.get('plan'),
            'receipts':result.get('receipts')}
        rows.append(row);output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({key:row[key] for key in ('name','reply','error','seconds','profile','receipts')},ensure_ascii=False),flush=True)
    reset()
    turn('mixed_self_friend','我男，38岁，身高175厘米，体重85公斤，想减到75公斤。我朋友推荐跑步，但我膝盖有旧伤，跑步会疼。平日只能外卖，不吃鱼，对花生过敏。先帮我判断从哪里开始。')
    turn('new_chat_memory','根据你已经记住的我的情况，给我一个外卖和运动的起步建议。',cid='audit-new-chat')
    reset()
    turn('compact_profile','女，32岁，165cm，65kg，想减到58kg，未怀孕未哺乳。没有确诊疾病，没有手术史，没有用药，对花生过敏。午餐只能食堂，晚餐自己做。先聊聊如何吃得合理。')
    turn('meal_question','今天中午食堂有宫保鸡丁、清炒豆腐和炒面，你建议怎么选？')
    turn('profile_correction','更正一下，身高是168厘米，之前165记错了。最近换成下午三点到晚上十一点上班，原来的晚餐时间不适用了。')
    turn('correction_new_chat','你记住我的身高、上班时间和过敏是什么？',cid='audit-correction-chat')
    reset()
    review=server.normalize_image_analysis({'category':'food','summary':'用于隔离测试的餐盘估计。',
        'foods':[{'name':'米饭与配菜','nutrition_basis':'portion_estimate',
            'nutrition':{'kcal':[500,700],'protein_g':[20,30],'carbs_g':[60,80],'fat_g':[15,25]},
            'uncertainty':'合成测试估计，非真实测量'}]},'food')
    server.save_json(server.MEDIA,[{'id':'audit-food','type':'food','review':review,'confirmed':False}])
    turn('photo_half_hypothetical','如果这份只吃一半，热量和蛋白质范围大概是多少？只是分析，不要记录摄入。',media_id='audit-food')
    turn('photo_half_consumed','这份我吃了一半，请记录。',media_id='audit-food')
    reset()
    turn('injury_exercise','我38岁，男，175厘米，85公斤。想开始健身，每天20分钟，家里没有器械，膝盖旧伤下蹲会痛。请给一个适合的起步方向，不要先让我填减肥问卷。')
    turn('hypothetical_not_fact','如果我能每天跑五公里，会不会瘦得快一点？这只是问问，我并没有开始跑步。')
