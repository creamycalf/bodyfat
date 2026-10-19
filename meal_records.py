"""Explicit meal corrections with read-only previews and per-record undo."""
import copy
import hashlib
import json
from datetime import date, datetime
import workbench


class CorrectionError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def preview(s, w, p):
    records=s.records()
    old=next((r for r in records if r['id']==p.get('id') and r['type'] in ('meal','beverage')),None)
    if not old:raise CorrectionError('餐食记录已不存在，请刷新后重新选择')
    media=next((m for m in s.load_json(s.MEDIA,[]) if m['id']==old.get('media_id')),None)
    if p.get('operation') not in ('edit','remove'):raise CorrectionError('请选择修正或撤回这餐摄入')
    new=None
    if p['operation']=='edit':
        description=p.get('description')
        if not isinstance(description,str) or not description.strip() or len(description)>2000:
            raise CorrectionError('请填写 1–2000 字的实际餐食说明')
        try:day=date.fromisoformat(str(p.get('date','')))
        except ValueError:raise CorrectionError('请选择有效的用餐日期')
        if day>date.today():raise CorrectionError('实际用餐日期不能是未来')
        mode=p.get('nutrition_mode')
        if mode not in ('keep','scale','unknown'):raise CorrectionError('请选择营养估算处理方式')
        new=copy.deepcopy(old);new['occurred_at']=day.isoformat()
        new['value']['description']=description.strip()
        nutrition=workbench.nutrition_ranges(old['value'].get('nutrition'))
        if mode=='scale':
            factor=p.get('factor')
            if isinstance(factor,bool) or not isinstance(factor,(int,float)) or not 0<factor<=4:
                raise CorrectionError('份量倍数应大于 0 且不超过 4')
            nutrition={k:[round(x*factor,1) for x in v] if v else None for k,v in nutrition.items()}
            nutrition=workbench.nutrition_ranges(nutrition)
            new['value']['uncertainty']='按修正前记录的估算等比例换算，原有估算误差仍存在。'
            new['value']['nutrition_context']={'method':'scaled','basis':f'原记录 {old["id"]} 的 {factor} 倍；不是重新识别或计算食材。','reliability':'uncalibrated'}
        elif mode=='unknown':
            nutrition={k:None for k in nutrition}
            new['value']['uncertainty']='餐食已手动修正，营养数值待重新核实。'
            new['value']['nutrition_context']={'method':'unknown','basis':'用户修改了餐食或份量，原估算已清除。','reliability':'unknown'}
        new['value']['nutrition']=nutrition
    generation=[(x['id'],x.get('undone')) for x in w.get('meal_corrections',[]) if x['before']['id']==old['id']]
    return {'before':old,'after':new,'media_before':media,
            'token':digest([old,media,new,p['operation'],generation])}


def act(s,w,p):
    history=w.setdefault('meal_corrections',[])
    if p['action']=='meal_undo':
        entry=next((x for x in history if x['id']==p.get('correction_id')),None)
        if not entry or entry.get('undone'):raise CorrectionError('该修正不存在或已经撤销')
        records=s.records();media=s.load_json(s.MEDIA,[])
        current=next((r for r in records if r['id']==entry['before']['id']),None)
        current_media=next((m for m in media if m['id']==entry['before'].get('media_id')),None)
        if current!=entry['after'] or current_media!=entry['media_after']:
            raise CorrectionError('这餐或关联照片已有后续更新，请刷新核对，不能覆盖后续修改')
        if current:records[records.index(current)]=copy.deepcopy(entry['before'])
        else:records.insert(min(entry['position'],len(records)),copy.deepcopy(entry['before']))
        if current_media:media[media.index(current_media)]=copy.deepcopy(entry['media_before'])
        entry['undone']=True;entry['undone_at']=datetime.now().isoformat()
        s.save_json(s.RECORDS,records);s.save_json(s.MEDIA,media)
        return {'ok':True}
    if p['action']=='meal_commit':
        previous=next((x for x in history if x['id']==p.get('token')),None)
        if previous:
            if previous.get('undone'):raise CorrectionError('该修正已撤销，请重新预览')
            return {'ok':True,'correction_id':previous['id']}
    result=preview(s,w,p)
    if p['action']=='meal_preview':return {k:v for k,v in result.items() if k!='media_before'}
    if p.get('token')!=result['token']:raise CorrectionError('餐食或照片已变化，请重新预览再确认')
    records=s.records();media=s.load_json(s.MEDIA,[])
    old=result['before'];position=next(i for i,r in enumerate(records) if r['id']==old['id'])
    if result['after'] is None:records.pop(position)
    else:records[position]=result['after']
    media_after=copy.deepcopy(result['media_before'])
    if media_after is not None:
        media_after.pop('food_pending',None)
        media_after['food_decision']={'status':'consumed' if result['after'] else 'reference',
            'evidence':'用户核对餐食后手动修正','date':result['after']['occurred_at'] if result['after'] else old.get('occurred_at'),
            'value':result['after']['value'] if result['after'] else old['value']}
        media[media.index(result['media_before'])]=media_after
    history.append({'id':result['token'],'before':old,'after':result['after'],
                    'media_before':result['media_before'],'media_after':media_after,
                    'position':position,'created_at':datetime.now().isoformat(),'undone':False})
    s.save_json(s.RECORDS,records);s.save_json(s.MEDIA,media)
    return {'ok':True,'correction_id':result['token']}
