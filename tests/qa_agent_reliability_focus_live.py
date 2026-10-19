"""Final route check after the 19-scene run, using isolated fictional facts."""
import json,os,sys,tempfile,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));rows=[]
with tempfile.TemporaryDirectory(prefix='zhiheng-reliability-focus-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,product,storage
    storage.initialize(server.DATA)
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    actual=server.call_ai;raws=[]
    def model(*args,**kwargs):
        raw=actual(*args,**kwargs);raws.append(server.parse_json(raw) or raw);return raw
    server.call_ai=model
    cases=[('starting_choice','我男，38岁，身高175厘米，体重85公斤，对花生过敏。如果我想减脂，先从饮食还是运动开始更合适？','focus-main'),
           ('correction','更正一下，身高是168厘米，之前175记错了。现在下午三点到晚上十一点上班。','focus-main'),
           ('new_chat','你记住我的年龄、身高、体重、上班时间和过敏吗？','focus-new-chat')]
    for name,text,cid in cases:
        raws.clear();start=time.monotonic()
        result=product.chat(server,{'text':text,'conversation_id':cid,'client_message_id':'focus-'+name})
        state=product.snapshot(server)
        checks={'model_completed':not bool(result.get('ai_error'))}
        if name=='starting_choice':
            checks.update(question_answered=all(x in result['reply'] for x in ('饮食','运动')),
                no_questionnaire=not any(x in result['reply'] for x in ('还要先了解','一起说下确诊','为了让建议适合你')),
                facts_kept=state['profile'].get('age')==38 and '花生' in str(state['profile'].get('allergies')))
        elif name=='correction':
            checks.update(height_corrected=state['profile'].get('height_cm')==168,
                no_questionnaire=not any(x in result['reply'] for x in ('还要先了解','一起说下确诊','为了让建议适合你')))
        else:
            checks.update(recalls_current_facts=all(x in result['reply'] for x in ('38','168','85','花生')),
                          no_superseded_conflict='175' not in result['reply'])
        row={'name':name,'user':text,'reply':result['reply'],'raw':raws.copy(),
             'error':result.get('ai_error'),'seconds':round(time.monotonic()-start,2),'checks':checks,
             'profile':state['profile'],'records':state['records'],'receipts':result['receipts']}
        rows.append(row)
        (ROOT/'tmp/agent-reliability-focus-0.4.41-final.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:row[k] for k in ('name','reply','error','seconds','checks')},ensure_ascii=False),flush=True)
    if not all(all(row['checks'].values()) for row in rows):raise SystemExit(1)
