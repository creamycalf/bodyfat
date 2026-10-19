"""Evidence-limited execution review. No nutritional prescription or weight rule."""
from datetime import date, timedelta


def _recent_evidence(records, day):
    cutoff=(date.fromisoformat(day)-timedelta(days=7)).isoformat()
    recent=[r for r in records if r.get('confirmed') is not False and
            r.get('memory_enabled') is not False and r.get('status') not in ('pending','inferred','retracted') and
            cutoff<=str(r.get('occurred_at') or r.get('created_at') or '')[:10]<=day]
    recent.sort(key=lambda r:(str(r.get('occurred_at') or r.get('created_at') or ''),str(r.get('created_at') or '')))
    result={}
    for kind,label in (('hunger','饥饿感'),('sleep','睡眠'),('activity','活动')):
        items=[r for r in recent if r.get('type')==kind]
        result[kind]={'label':label,'count':len(items),'latest':str(items[-1].get('value',{}).get('description') or
            items[-1].get('value',{}).get('summary') or '')[:160] if items else '',
            'record_ids':[r.get('id') for r in items if r.get('id')]}
    weights=[r for r in recent if r.get('type')=='weight' and isinstance(r.get('value',{}).get('kg'),(int,float))]
    result['weight']={'label':'体重','count':len(weights),'record_ids':[r.get('id') for r in weights if r.get('id')],
        'first_kg':weights[0]['value']['kg'] if weights else None,
        'last_kg':weights[-1]['value']['kg'] if weights else None,
        'trend_note':'两次测量只能描述变化，不能单凭短期波动调整饮食强度。' if len(weights)>1 else '记录不足，不能判断趋势。'}
    return result


def summarize(plan, tasks_for, workspace, day, records=()):
    end=min(date.fromisoformat(day)-timedelta(days=1),date.fromisoformat(plan['end_date']))
    start=max(date.fromisoformat(plan['start_date']),end-timedelta(days=6))
    rows=[]
    while start<=end:
        rows.extend(t for t in tasks_for(workspace,start.isoformat())
                    if t['plan_id']==plan['id'] and t['version']==plan['version'])
        start+=timedelta(days=1)
    counts={key:sum(t['status']==key for t in rows) for key in ('done','partial','skipped','unreported','deferred')}
    observed=counts['done']+counts['partial']+counts['skipped']
    if not rows or observed<len(rows)/2:
        decision='assess';reason='已反馈的执行记录不足，先补充感受和阻碍；未记录不等于未执行。'
    elif counts['partial']+counts['skipped']>counts['done']:
        decision='simplify';reason='部分完成或未完成较多，可选择已有最低行动；先核对困难，不增加补偿任务。'
    else:
        decision='maintain';reason='多数已反馈事项完成，可保持当前难度并继续观察感受。'
    evidence=_recent_evidence(records,day)
    unknowns=[item['label'] for item in evidence.values() if item['count']==0]
    return {'plan_id':plan['id'],'version':plan['version'],'as_of':day,'counts':counts,
            'observed':observed,'expected':len(rows),'decision':decision,'reason':reason,
            'observations':evidence,'unknowns':unknowns,
            'observation_condition':'下一次复盘结合实际记录、饥饿感、执行困难与睡眠活动；缺记不等于未执行，单日体重波动不触发限制。',
            'feedback_task_ids':[t['task_id'] for t in rows if t['status']!='unreported'],
            'struggling_item_ids':sorted({t['id'] for t in rows if t['status'] in ('partial','skipped')}),
            'due':day>=plan['review_date']}
