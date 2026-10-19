"""Revisioned food-photo reports and explicit intake confirmation.

Only local arithmetic uses these inputs.  A user-entered label/reference is
kept distinct from a verified database match.  Report edits alone never mean
that anyone consumed the photographed food.
"""
import copy
import hashlib
import json
import math
from datetime import date, datetime

import nutrition_reports
import food_catalog
import workbench


class ReportEditError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _number(value, maximum):
    if value is None or value=='':return None
    if isinstance(value,bool):raise ReportEditError('营养数值或重量格式无效')
    try:number=float(value)
    except (TypeError,ValueError):raise ReportEditError('营养数值或重量格式无效')
    if not 0<=number<=maximum or not math.isfinite(number):
        raise ReportEditError('营养数值或重量超出可核对范围')
    return number


def _pair(value, maximum):
    if value is None or value=='':return None
    if not isinstance(value,list) or len(value)!=2:raise ReportEditError('区间应填写下限与上限')
    low,high=(_number(v,maximum) for v in value)
    if low is None or high is None or low>high:raise ReportEditError('区间上下限无效')
    return [low,high]


def _validated_food(raw):
    if not isinstance(raw,dict):raise ReportEditError('食物条目格式无效')
    name=str(raw.get('name') or '').strip()
    if not 1<=len(name)<=120:raise ReportEditError('请填写食物名称')
    source=raw.get('source_kind','model_estimate')
    if source not in ('model_estimate','user_label','user_reference','usda_fdc'):
        raise ReportEditError('数据来源不受支持；未查库不能标成数据库值')
    density_basis=raw.get('density_basis','per_100g')
    if density_basis not in ('per_100g','per_serving','visible_portion'):
        raise ReportEditError('请选择每100g、每份标签或照片整份的口径')
    direct=density_basis=='visible_portion'
    density=raw.get('nutrition') if direct else raw.get('per_100g')
    if not isinstance(density,dict):raise ReportEditError('请核对所选口径的营养值')
    if direct and source=='usda_fdc':raise ReportEditError('照片整份估计不能标成数据库每100g参考值')
    serving_grams=_number(raw.get('serving_grams'),5000) if density_basis=='per_serving' else None
    if density_basis=='per_serving' and (serving_grams is None or serving_grams<=0):
        raise ReportEditError('每份标签需要填写对应的可食重量')
    normalized={}
    for key in nutrition_reports.NUTRIENTS:
        portion_limit={'kcal':15000,'protein_g':1000,'carbs_g':2000,'fat_g':1500}[key]
        pair=_pair(density.get(key),portion_limit if direct else (1000 if key=='kcal' else 100))
        if pair and serving_grams:
            pair=[round(v*100/serving_grams,2) for v in pair]
            if pair[1]>(1000 if key=='kcal' else 100):
                raise ReportEditError('按每份换算后的每100g数值超出可核对范围')
        normalized[key]=pair
    reference=None
    if source=='usda_fdc':
        reference=food_catalog.verified(name,raw.get('source_id'),normalized)
        if density_basis!='per_100g' or not reference or str(raw.get('weight_basis') or '')!=reference['weight_basis']:
            raise ReportEditError('USDA参考值与食材或每100g数值不匹配；请改选模型估计或用户参考')
    return {'name':name,'grams':_pair(raw.get('grams'),5000),
            'per_100g':{key:None for key in nutrition_reports.NUTRIENTS} if direct else normalized,
            'nutrition':normalized if direct else {},
            'nutrition_basis':'portion_estimate' if direct else 'weight_density',
            'density_basis':'visible_portion' if direct else 'per_100g',
            'original_density_basis':density_basis,'serving_grams':serving_grams,
            'source_kind':source,'source_id':reference['id'] if reference else str(raw.get('source_id') or '').strip()[:120],
            'source_version':reference['version'] if reference else str(raw.get('source_version') or '').strip()[:80],
            'source_reviewed_at':date.today().isoformat(),
            'weight_basis':str(raw.get('weight_basis') or '生熟口径待核对').strip()[:150],
            'edible_basis':str(raw.get('edible_basis') or '可食部分待核对').strip()[:120],
            'portion_basis':str(raw.get('portion_basis') or '用户核对的估计重量').strip()[:500],
            'uncertainty':str(raw.get('uncertainty') or '食材、用油或份量仍可能有误差').strip()[:500],
            'included':raw.get('included') is not False}


def preview(s,p):
    media=next((m for m in s.load_json(s.MEDIA,[]) if m.get('id')==p.get('id')),None)
    if not media or media.get('review',{}).get('report',{}).get('kind')!='food':
        raise ReportEditError('餐食报告不存在，请刷新后重试')
    rows=p.get('foods')
    if not isinstance(rows,list) or not 1<=len(rows)<=30:
        raise ReportEditError('请保留至少一项、最多三十项食物')
    foods=[_validated_food(row) for row in rows]
    servings=_number(p.get('servings'),20)
    if servings is not None and servings<=0:raise ReportEditError('分食人数应大于零')
    report=nutrition_reports.food_report({'foods':foods,'servings':servings,
                                          'advice':media['review']['report'].get('advice',[]),
                                          'questions':media['review']['report'].get('questions',[])})
    if not any(row['included'] for row in report['foods']):raise ReportEditError('至少一项食物需要计入报告')
    eaten=p.get('eaten_servings')
    if eaten not in (None,''):
        if servings is None:raise ReportEditError('记录本人食用份数前，请先核对照片总共几人份')
        eaten=_number(eaten,20)
        if eaten>servings:raise ReportEditError('本人实际吃的份数不能超过照片可见总份数')
        fraction=round(eaten/servings,6)
        if not isinstance(p.get('confirm_consumption'),bool) or not p['confirm_consumption']:
            raise ReportEditError('确认实际食用前请明确勾选')
        try:day=date.fromisoformat(str(p.get('date','')))
        except (TypeError,ValueError):raise ReportEditError('请核对实际用餐日期')
        if day>date.today():raise ReportEditError('实际用餐日期不能是未来')
    else:fraction=None;day=None
    old=copy.deepcopy(media)
    record=next((r for r in s.records() if r.get('media_id')==media['id'] and r.get('type') in ('meal','beverage')),None)
    if record and fraction is None:
        raise ReportEditError('这张照片已有实际摄入记录；修改报告时请重新确认本人吃的份数，以同步修正同一条记录')
    nutrition={key:([round(v*fraction,1) for v in report['totals'][key]]
                    if fraction is not None and report['totals'][key] is not None and
                    report['coverage'][key]==report['counted_count'] else None)
               for key in nutrition_reports.NUTRIENTS}
    generation=[(x.get('token'),x.get('undone')) for x in media.get('report_history',[])]
    token=_digest([old,record,foods,fraction,day.isoformat() if day else None,generation,p.get('save_favorites') is True])
    return {'before':old['review']['report'],'after':report,'record_before':record,
            'consumed_fraction':fraction,'intake_nutrition':nutrition,
            'date':day.isoformat() if day else None,'token':token,'foods_input':foods,
            'candidates_before':copy.deepcopy(old['review'].get('record_candidates',[]))}


def act(s,p,w=None):
    media_list=s.load_json(s.MEDIA,[])
    media=next((m for m in media_list if m.get('id')==p.get('id')),None)
    if p['action']=='report_undo':
        if not media:raise ReportEditError('图片已不存在')
        entry=next((x for x in media.get('report_history',[]) if x['token']==p.get('token')),None)
        if not entry or entry.get('undone'):raise ReportEditError('修正不存在或已经撤销')
        records=s.records();current=next((r for r in records if r.get('media_id')==media['id'] and r.get('type') in ('meal','beverage')),None)
        if media['review']['report']!=entry['after'] or current!=entry['record_after']:
            raise ReportEditError('报告或摄入记录已有后续变化，请先刷新核对')
        media['review']['report']=copy.deepcopy(entry['before'])
        media['review']['record_candidates']=copy.deepcopy(entry['candidates_before'])
        if entry['food_decision_before'] is None:media.pop('food_decision',None)
        else:media['food_decision']=copy.deepcopy(entry['food_decision_before'])
        media['confirmed']=entry['confirmed_before']
        if current:records.remove(current)
        if entry['record_before']:
            records.insert(min(entry.get('record_position',len(records)),len(records)),copy.deepcopy(entry['record_before']))
        entry['undone']=True;entry['undone_at']=datetime.now().isoformat()
        s.save_json(s.MEDIA,media_list);s.save_json(s.RECORDS,records)
        return {'ok':True}
    if not media:raise ReportEditError('图片已不存在')
    old_entry=next((x for x in media.get('report_history',[]) if x['token']==p.get('token')),None)
    if p['action']=='report_commit' and old_entry and not old_entry.get('undone'):
        return {'ok':True,'token':old_entry['token'],'report':old_entry['after']}
    result=preview(s,p)
    if p['action']=='report_preview':
        return {key:value for key,value in result.items() if key!='foods_input'}
    if p.get('token')!=result['token']:raise ReportEditError('报告或摄入记录已变化，请重新预览')
    records=s.records();old_record=result['record_before'];fraction=result['consumed_fraction']
    record_position=records.index(old_record) if old_record else len(records)
    food_decision_before=copy.deepcopy(media.get('food_decision'))
    confirmed_before=media.get('confirmed',False)
    new_record=copy.deepcopy(old_record)
    if fraction is not None:
        if old_record:records.remove(old_record)
        if fraction>0:
            description='、'.join(row['name'] for row in result['after']['foods'] if row['included'])
            value={'description':f'{description}；本人确认吃了照片可见总量的 {fraction:g}',
                   'nutrition':result['intake_nutrition'],
                   'uncertainty':'按核对后的可见食物与明确食用比例计算；未知食物和营养项保持未知。',
                   'nutrition_context':{'method':'report_revision','basis':'用户核对食物、份量及实际食用比例',
                                        'reliability':'user_reviewed_estimate'}}
            new_record=s.prepare_record({'type':'meal','value':value})
            if not new_record:raise ReportEditError('摄入记录格式无法保存')
            if old_record:new_record['id']=old_record['id'];new_record['memory_enabled']=old_record.get('memory_enabled',True)
            new_record.update(media_id=media['id'],source='image_user_confirmed',status='confirmed',
                              confirmed=True,occurred_at=result['date'],recorded_at=datetime.now().isoformat())
            records.insert(min(record_position,len(records)),new_record)
        else:new_record=None
    media['review']['report']=result['after']
    media['review']['record_candidates']=[{'type':'meal','label':row['name'],
        'value':{'description':row['name'],'nutrition':row['nutrition'],'uncertainty':row['uncertainty']}}
        for row in result['after']['foods'] if row['included']]
    if fraction is not None:
        media['food_decision']={'status':'consumed' if fraction>0 else 'reference',
            'evidence':'用户在报告修正中明确确认实际食用比例',
            'date':result['date'],'fraction':fraction}
        media['confirmed']=fraction>0
    media.setdefault('report_history',[]).append({'token':result['token'],'before':result['before'],
        'after':result['after'],'record_before':old_record,'record_after':new_record,
        'record_position':record_position,'candidates_before':result['candidates_before'],
        'food_decision_before':food_decision_before,'confirmed_before':confirmed_before,
        'created_at':datetime.now().isoformat(),'consumed_fraction':fraction,'undone':False})
    if w is not None and p.get('save_favorites') is True:
        favorites=w.setdefault('saved_foods',[])
        for row in result['foods_input']:
            if row['source_kind']=='model_estimate' or row['density_basis']=='visible_portion':continue
            key=_digest([row['name'],row['source_kind'],row['source_id']])[:16]
            favorite={'id':key,'name':row['name'],'per_100g':row['per_100g'],
                      'source_kind':row['source_kind'],'source_id':row['source_id'],
                      'source_version':row['source_version'],'weight_basis':row['weight_basis'],
                      'edible_basis':row['edible_basis'],'saved_at':datetime.now().isoformat()}
            favorites[:]=[item for item in favorites if item.get('id')!=key]
            favorites.append(favorite)
        w['saved_foods']=favorites[-100:]
    s.save_json(s.MEDIA,media_list)
    if fraction is not None:s.save_json(s.RECORDS,records)
    return {'ok':True,'token':result['token'],'report':result['after'],'consumption_saved':fraction is not None}
