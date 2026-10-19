"""Validated page changes and contextual food records. No model-generated markup."""
import copy
import math
import re
import intake
from datetime import datetime

TOPICS = {
    '身体基础': ['age', 'sex', 'height_cm'], '健康背景': ['conditions', 'surgeries', 'medications', 'allergies'],
    '三餐与加餐': ['breakfast_habit','lunch_habit','dinner_habit','snacks_drinks'],
    '饮食习惯': ['food_habits','eating_pattern','weight_history'], '日常活动': ['occupation', 'activity_baseline', 'available_time'],
    '睡眠作息': ['sleep_schedule','work_schedule','meal_schedule'], '目标偏好': ['goals', 'preferences'],
}
CONTRACT = '''
【持续工作台协议】每轮都根据新信息评估页面是否需要变化，不要求出现“修改”关键词。
增加 decision:{action:"none/update/clarify",reason:"本轮判断依据"}。
仅实际行动/日期改变才返回plan；普通解释、图片、图表用page_changes，不重建计划。
page_changes最多8项，每项 {id:"稳定英文模块ID",page:"plan/dashboard/archive",type:"text/checklist/image/trend",title:"标题",body:"正文",items:["条目"],media_id:"已提供图片ID或空",reason:"更新原因",date:"仅今日模块填YYYY-MM-DD，否则空"}。
同一主题更新原ID，不重复创建。只更新受影响的模块，不删除未提到的内容。
trend仅可使用真实体重记录，不能提供虚构数据点。image只能引用给定media_id。
创建首次方案时同时给出个人情况摘要、饮食策略、活动建议和复盘等适合当前资料的独立模块。
首次了解时一次问一个最有价值的问题，读取assessment中的缺口；不要因知道体重就认定整体了解完成。
用户可跳过或先要初步方案，标出未知项；普通记录或知识问答不强制访谈。新会话继承用户级了解状态。
food_decisions最多4项，格式 {media_id:"给定ID",status:"consumed/planned/reference/unknown",evidence:"本轮原文连续片段",description:"食物与实际食用量",date:"实际进餐YYYY-MM-DD",nutrition:{kcal:[下限,上限],protein_g:[下限,上限],carbs_g:[下限,上限],fat_g:[下限,上限]},uncertainty:"份量/用油等不确定性"}。
仅照片不能证明本人吃过；明确本人已吃才consumed。准备吃是planned，菜单/别人食物/没吃是reference，不明确是unknown。
后续“刚才那个吃了一半”应关联同一图片，nutrition是实际吃的部分的估算；不得再在record_events重复写该餐。
照片是否入档与方案是否调整分别判断。未知营养用null，不填零。参考标签及用户重量优先，估算必须给范围。
文字餐食 record_events 的 value 也应包含 description、nutrition:{kcal:[下限,上限],protein_g:[下限,上限],carbs_g:[下限,上限],fat_g:[下限,上限]}、uncertainty。仅对本人明确已吃的部分估算；根据提供的食物和份量能粗估时给范围并在uncertainty说明份量、品牌、用油等假设；信息不足用null并说明缺什么。不得编造查表、检测或数据库来源，不输出未经校准的置信百分比。用户给了标签和食用重量时说明换算依据；生重熟重不明时不要默认为已知。
对话中用户明确说没吃/吃过/更正时更新同一餐。不能从图片推断服药、疾病或已完成行为。
'''


def assessment(profile, records, plans, state=None, *, for_model=False):
    if for_model:
        # Old summaries/questions are local audit material, not a second
        # authoritative source of health facts after their evidence is disabled.
        records=[r for r in records if r.get('memory_enabled') is not False
                 and r.get('confirmed') is not False
                 and r.get('status') not in ('pending','inferred','retracted','corrected','deleted','dismissed')]
        original=state or {}
        state={key:original[key] for key in ('stage','topic') if original.get(key) in (
            {'understanding','assessment','trial','review','follow_up'} if key=='stage' else
            set(TOPICS)|set(intake.ASSESSMENT_QUESTIONS))}
        state['skipped_topics']=[topic for topic in original.get('skipped_topics',[])
                                 if isinstance(topic,str) and topic in set(TOPICS)|set(intake.ASSESSMENT_QUESTIONS)]
    state = state or {}
    skipped = set(state.get('skipped_topics', []))
    topics = [{'title': title, 'known': [k for k in fields if intake.known(profile,k)],
               'missing': [k for k in fields if not intake.known(profile,k)],
               'status': 'skipped' if title in skipped else ('known' if all(intake.known(profile,k) for k in fields) else 'open')}
              for title, fields in TOPICS.items()]
    known_count = sum(bool(profile.get(k)) for fields in TOPICS.values() for k in fields)
    # ``stage`` remains the legacy Chinese label used by the existing UI.  The
    # machine-readable code is persisted separately so API consumers can make
    # decisions without parsing presentation text.
    if (state.get('stage') == 'understanding' and known_count and not state.get('updated_at')
            and not state.get('history')):
        # Legacy workspace documents had no assessment state.  Infer only the
        # coarse phase from confirmed facts; do not invent a topic or judgment.
        stage_code = 'assessment'
    elif state.get('stage') in {'understanding','assessment','trial','review','follow_up'}:
        stage_code = state['stage']
    elif plans:
        stage_code = 'follow_up' if all(t['status']=='known' for t in topics) else 'trial'
    elif not known_count and not skipped:
        stage_code = 'understanding'
    else:
        stage_code = 'assessment'
    labels={'understanding':'尚未开始','assessment':'逐步了解','trial':'阶段行动','review':'复盘调整','follow_up':'持续跟进'}
    stage = labels[stage_code]
    next_question=state.get('next_question') or {}
    # Old clients expect a string; new clients get the structured form too.
    next_text=next_question.get('text','') if isinstance(next_question,dict) else str(next_question)
    result={'stage': stage, 'stage_code': stage_code, 'topics': topics,
            'has_weight': any(r.get('type') == 'weight' for r in records),
            'skipped_topics': sorted(skipped), 'next_question': next_text,
            'next_question_detail': copy.deepcopy(next_question) if isinstance(next_question,dict) else {},
            'topic': state.get('topic',''), 'primary_problem': state.get('primary_problem',''),
            'evidence_record_ids': list(state.get('evidence_record_ids', [])),
            'unknowns': list(state.get('unknowns', [])), 'priority': state.get('priority','medium'),
            'user_summary': state.get('user_summary',''), 'assessment_history': copy.deepcopy(state.get('history', [])),
            'updated_at': state.get('updated_at'), 'known_count': known_count}
    if for_model:
        result['evidence_record_ids']=[r['id'] for r in records[-20:] if r.get('id')]
        result['unknowns']=[key for item in topics for key in item['missing']]
    return result


def visible_modules(w, records):
    eligible = {r['id'] for r in records if r.get('memory_enabled') is not False}
    return [m for m in w.get('modules', []) if set(m.get('basis_record_ids', [])) <= eligible]


def apply_modules(w, changes, source, records, media, safety):
    if not isinstance(changes, list):
        raise ValueError('页面变更必须为列表')
    modules = copy.deepcopy(w.get('modules', [])); applied = []
    for raw in changes[:8]:
        if not isinstance(raw, dict): raise ValueError('页面模块格式错误')
        raw=copy.deepcopy(raw)
        raw['page']={'方案':'plan','计划':'plan','plans':'plan','today':'dashboard','今日':'dashboard','看板':'dashboard','overview':'dashboard','profile':'archive','档案':'archive','health_profile':'archive'}.get(raw.get('page'),raw.get('page'))
        raw['type']={'markdown':'text','rich_text':'text','paragraph':'text','list':'checklist','image_text':'image'}.get(raw.get('type'),raw.get('type'))
        key = re.sub(r'-v\d+$', '', str(raw.get('id', '')))
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', key): raise ValueError('页面模块标识无效')
        if raw.get('page') not in ('plan', 'dashboard', 'archive'): raise ValueError('页面无效')
        kind = {'module':'text','section':'text','paragraph':'text','card':'text','items':'checklist','list':'checklist','chart':'trend','photo':'image'}.get(raw.get('type'),raw.get('type'))
        if kind not in ('text', 'checklist', 'image', 'trend'):
            # Unknown presentation names may still contain ordinary prose. Render only
            # that prose, never model markup/code, computed metrics or chart points.
            if (isinstance(raw.get('body'),str) and raw['body'].strip()
                    and not any(raw.get(k) for k in ('html','script','code','data','series','metrics','media_id'))
                    and str(kind).lower() not in ('script','html','javascript','chart','metric')):
                kind='checklist' if raw.get('items') else 'text'
            else:raise ValueError('模块类型无效')
        title = str(raw.get('title', '')).strip()[:120]; body = str(raw.get('body', ''))[:6000]
        if not title or not str(raw.get('reason', '')).strip(): raise ValueError('模块缺少标题或更新依据')
        items = raw.get('items', [])
        if items is None:items=[]
        if not isinstance(items, list): raise ValueError('模块条目无效')
        normalized=[]
        for x in items:
            if isinstance(x,str):normalized.append(x)
            elif isinstance(x,dict) and any(isinstance(x.get(k),str) for k in ('title','detail','text','description')):
                normalized.append('：'.join(x[k] for k in ('title','detail','text','description') if isinstance(x.get(k),str) and x[k]))
            else:raise ValueError('模块条目无效')
        items=normalized
        items = [x[:1000] for x in items[:12]]
        if safety({'title': title, 'goal': body, 'items': [{'detail': x} for x in [body, *items]]}):
            raise ValueError('页面内容未通过健康规则校验')
        mid = raw.get('media_id') or ''
        if kind == 'image' and not any(m['id'] == mid for m in media): raise ValueError('图片来源不存在')
        date = str(raw.get('date') or '')
        if date:
            datetime.strptime(date, '%Y-%m-%d')
        content = dict(id=key, page=raw['page'], type=kind, title=title, body=body,
                       items=items, media_id=mid, date=date)
        previous = next((m for m in modules if m['id'] == key), None)
        if previous and all(previous.get(k) == v for k, v in content.items()): continue
        content.update(version=(previous or {}).get('version', 0) + 1, source=source,
                       reason=str(raw['reason'])[:800], updated_at=source['at'],
                       basis_record_ids=[r['id'] for r in records[-15:] if r.get('memory_enabled') is not False])
        if previous: modules.remove(previous)
        modules.append(content); applied.append({'id': key, 'title': title, 'page': raw['page'],
                                                 'before': previous, 'after': copy.deepcopy(content)})
    if len(modules) > 60: raise ValueError('页面模块过多，请合并已有主题')
    if applied:
        w['modules'] = modules
        w.setdefault('page_history', []).append({'source': source, 'changes': applied})
    return applied


def saved_page_changes(profile, plan, fields):
    """Rebuild readable summaries strictly from saved objects; no new health advice."""
    changes=[]
    if profile:
        body='\n'.join(f"{fields.get(k,k)}："+('、'.join(map(str,v)) if isinstance(v,list) else str(v))
                       for k,v in profile.items() if v not in (None,''))
        changes.append(dict(id='saved-profile-summary',page='archive',type='text',title='已保存的个人情况',
                            body=body,items=[],reason='从当前已保存档案恢复可读说明；自述不等于医学结论'))
    if plan:
        body=str(plan.get('goal',''))+'\n'+str(plan.get('basis',''))
        if plan.get('unknowns'):body+='\n待了解：'+str(plan['unknowns'])
        changes.append(dict(id='saved-plan-summary',page='plan',type='checklist',title='当前计划说明',body=body,
                            items=['：'.join(str(i.get(k,'')) for k in ('title','when','detail') if i.get(k)) for i in plan.get('items',[])],
                            reason='从已保存的当前计划恢复说明，执行安排及历史记录保持原样'))
    return changes


def nutrition_ranges(raw):
    out = {}
    for key, maximum in [('kcal', 15000), ('protein_g', 1000), ('carbs_g', 2000), ('fat_g', 1500)]:
        pair = (raw or {}).get(key) if isinstance(raw, dict) else None
        if pair is None: out[key] = None; continue
        if isinstance(pair,(int,float)) and not isinstance(pair,bool):pair=[pair,pair]
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in pair) or
                not 0 <= pair[0] <= pair[1] <= maximum):
            raise ValueError('营养范围无效')
        out[key] = [round(x, 1) for x in pair]
    return out


def nutrition_context(value, method, evidence=''):
    """Record provenance controlled by the application, never model authority claims."""
    known=any(v is not None for v in nutrition_ranges(value.get('nutrition')).values())
    return {'method':method if known else 'unknown', 'basis':str(evidence)[:1000],
            'reliability':'uncalibrated' if known else 'unknown'}


def consumption_blocked(text):
    """Check the whole utterance, not a model-selected positive substring."""
    return bool(re.search(r'没吃(?!多少)|没有吃(?!多少)|未吃|还没|尚未|准备|打算|想吃|别人|朋友|同事|我爸|我妈|如果|(?<!估算)(?<!计算)假设|假如|不是|不要记录|别记|[？?]|能吃吗|可以吃吗', text))


def food_scope_ambiguous(text):
    """Mixed assertions cannot be assigned to one photo by keyword priority.

    Quoted/retracted assertions remain ambiguous too: preserving data and asking
    is safer than guessing which clause, person, or time the photo represents.
    """
    negative=bool(re.search(r'没吃(?!多少)|没有吃(?!多少)|未吃|尚未食用|仅供参考',text))
    planned=bool(re.search(r'准备吃|打算吃|想吃',text))
    positive=bool(re.search(r'吃了一半|吃了半份|吃了一点|吃了少量|没吃多少|吃完了|吃过了|刚吃完|已经吃|已吃|喝完了|喝了',text))
    # A narrowly explicit correction of a quoted claim is supported. Multiple
    # meal/time anchors below still prevent applying it to an unrelated meal.
    correction=bool(re.search(r'我(?:自己)?(?:没吃|没有吃)',text) and
                    re.search(r'(?:之前|刚才)说.{0,12}(?:说错|不对)',text))
    meals=set(re.findall(r'早餐|早饭|午餐|午饭|晚餐|晚饭|夜宵',text))
    meals={ {'早饭':'早餐','午饭':'午餐','晚饭':'晚餐'}.get(x,x) for x in meals }
    times=set(re.findall(r'昨天|今天|明天|后天|昨晚|今晚|明晚',text))
    if len(meals)>1 or len(times)>1:return True
    if re.search(r'明天|后天|明晚|下次',text) and (negative or planned):return True
    return positive and (negative or planned) and not correction


def grounded_nonconsumption(text, explicitly_attached=False):
    """Require an unambiguous current-photo statement for destructive changes."""
    if food_scope_ambiguous(text):return None
    if re.search(r'如果|假设|假如|不要记录|别记|[？?]|(?:没|没有|未)吃完|不是.{0,3}(?:没吃|没有吃)',text):return None
    linked=bool(re.search('刚才那个|刚才那份|这份|那份|这餐|这张',text))
    # A named meal/day alone does not identify the session's previous photo.
    if not linked and re.search('早餐|早饭|午餐|午饭|晚餐|晚饭|夜宵|昨天|今天|昨晚|今晚',text):
        if not explicitly_attached:return None
    if re.search('我爸|我妈|朋友|别人|同事',text) and not re.search(r'我(?:自己)?(?:还没吃|没有吃|没吃|尚未食用)',text):
        if not re.search(r'^(?:更正[，,：:]?)?没吃[，,]是给别人拍的',text):return None
    negative=re.search(r'还没吃|没有吃(?!多少)|没吃(?!多少)|尚未食用|仅供参考',text)
    planned=re.search('准备吃|打算吃|想吃',text)
    if negative:return 'reference',negative.group(0)
    if planned:return 'planned',planned.group(0)
    return None


def grounded_food_decision(text, image, explicitly_attached=False):
    """Ground obvious statements when the model omits its action, without inventing food or intake."""
    if re.search('如果|假设|假如|不要记录|别记|[？?]',text):return None
    if not explicitly_attached and not re.search('刚才那个|刚才那份|这份|那份|这餐|这张',text):return None
    if food_scope_ambiguous(text):return None
    if re.search(r'(?:没|没有|未)吃完|不是.{0,3}(?:没吃|没有吃)|没吃.{0,12}(?:后来|现在|刚刚).{0,5}吃',text):return None
    # Third-party language may correct ownership, but is never positive evidence
    # of the user's intake. Require an explicit self-negation to remove a record.
    if re.search('我爸|我妈|朋友|别人|同事',text) and not re.search(r'我(?:自己)?(?:还没吃|没有吃|没吃|尚未食用)',text):return None
    not_eaten=re.search(r'还没吃|没有吃(?!多少)|没吃(?!多少)|尚未食用|仅供参考',text)
    planned=re.search('准备吃|打算吃|想吃',text)
    actual=re.search(r'(?:刚才(?:那个|这份|那份)?|这份|这餐|我|午饭|午餐|晚饭|晚餐|早餐).{0,12}(?:吃了一半|吃了半份|吃了一点|吃了少量|没吃多少|吃完了|吃过了|刚吃完|吃的)|刚吃完(?:这份|那份|早餐|午餐|晚餐|饭)',text)
    if not_eaten or planned:
        grounded=grounded_nonconsumption(text,explicitly_attached)
        if not grounded:return None
        status,evidence=grounded
    elif actual and not consumption_blocked(text):status='consumed';evidence=actual.group(0)
    else:return None
    candidates=[c for c in image.get('review',{}).get('record_candidates',[]) if c.get('type') in ('meal','beverage')]
    # Only explicit whole-portion fractions scale the visible portion; otherwise quantities stay unknown.
    fraction=.5 if re.search(r'(?:那个|那份|这份|这餐)(?:我)?吃了一半|吃了半份',text) else 1 if re.search(r'吃完了|刚吃完(?:这份|那份|早餐|午餐|晚餐|饭)',evidence) else None
    nutrition={}
    for key in ('kcal','protein_g','carbs_g','fat_g'):
        pairs=[]
        for candidate in candidates:
            try:pairs.append(nutrition_ranges(candidate.get('value',{}).get('nutrition'))[key])
            except ValueError:pairs.append(None)
        nutrition[key]=[round(sum(p[i] for p in pairs)*fraction,1) for i in (0,1)] if fraction is not None and pairs and all(p is not None for p in pairs) else None
    descriptions=[c.get('value',{}).get('description') or c.get('label','') for c in candidates]
    return {'media_id':image['id'],'status':status,'evidence':evidence,
            'description':('；'.join(descriptions) or '已关联照片的饮食，食物详情待补充')+'；实际陈述：'+evidence,
            'nutrition':nutrition,'uncertainty':'按图片参考份量及明确食用比例换算；图片识别和份量仍存在误差。' if fraction else '食用事实已明确，实际份量与营养待补充。'}


def apply_food(s, w, decisions, source, records, media, explicitly_attached=False):
    if not isinstance(decisions, list): raise ValueError('饮食判断格式错误')
    receipts = []; results = []
    for raw in decisions[:4]:
        if not isinstance(raw, dict): raise ValueError('饮食判断无效')
        item = next((m for m in media if m['id'] == raw.get('media_id') and m.get('type') == 'food'), None)
        if not item: raise ValueError('饮食图片不存在')
        status = raw.get('status'); evidence = str(raw.get('evidence') or '')
        status={'eaten':'consumed','not_eaten':'reference','not_consumed':'reference','reference_only':'reference','not_eaten_yet':'planned','planning':'planned'}.get(status,status)
        if status!='unknown' and food_scope_ambiguous(source['text']):
            raise ValueError('涉及不同餐次或时间，请明确这张照片对应哪一餐及实际食用情况')
        if status == 'consumed' and consumption_blocked(source['text']):
            raise ValueError('本轮包含否定、纠正或非本人食用信息，请核对实际食用情况')
        if status in ('reference','planned') and re.search(r'(?:没|没有|未)吃完',source['text']):
            raise ValueError('没吃完不等于没有吃，请补充实际食用份量')
        if status not in ('consumed', 'planned', 'reference', 'unknown'):
            grounded=grounded_food_decision(source['text'],item,True)
            if grounded:
                raw=grounded;status=raw['status'];evidence=raw['evidence']
            else:raise ValueError('食用状态无效')
        if status in ('reference','planned'):
            grounded=grounded_nonconsumption(source['text'],explicitly_attached)
            if not grounded:raise ValueError('无法确认未食用信息对应这张照片，原记录保留，请明确餐次')
            status,evidence=grounded
        if status != 'unknown' and (not evidence or evidence not in source['text']):
            # Ground an explicit current-turn statement, never model paraphrases or prior meals.
            actual=re.search(r'(?:刚才(?:那个|这份|那份)?|这份|这餐|我|午饭|午餐|晚饭|晚餐|早餐).{0,12}(?:吃了一半|吃完了|吃过了|吃了半份|吃了一点|吃了少量|没吃多少)',source['text'])
            negated=re.search(r'没吃(?!多少)|没有吃(?!多少)|还没|准备|打算|别人|如果|假设',source['text'])
            if status=='consumed' and actual and not negated:evidence=actual.group(0)
            else:raise ValueError('饮食判断缺少本轮原话依据')
        # Explicit non-consumption takes precedence even if the model contradicts it.
        if status == 'consumed' and re.search(r'没吃(?!多少)|没有吃(?!多少)|还没吃|准备吃|打算吃|别人|菜单|能吃吗|可以吃吗', evidence):
            raise ValueError('尚未吃过的照片不能计为摄入')
        if status == 'consumed' and not re.search('吃了|没吃多少|吃完|吃过|吃的|已吃|喝了|喝完|喝过|喝的|已喝|用过餐|进食了', evidence):
            raise ValueError('还不能确认是否实际吃过，请补充说明')
        date = str(raw.get('date') or source['at'][:10]); datetime.strptime(date, '%Y-%m-%d')
        if status == 'consumed' and date > source['at'][:10]: raise ValueError('未来饮食不能计为实际摄入')
        if status=='consumed':
            # A model cannot choose the eaten fraction from a shared photo. Its
            # supplied nutrition may be a whole-plate estimate, so validate its
            # shape but derive intake numbers only from explicit user wording.
            nutrition_ranges(raw.get('nutrition'))
            grounded=grounded_food_decision(source['text'],item,True)
            verified=grounded['nutrition'] if grounded and grounded['status']=='consumed' else {}
            raw={**raw,'nutrition':{key:verified.get(key) for key in ('kcal','protein_g','carbs_g','fat_g')},
                 'uncertainty':'实际食用事实已确认；食用份量未明确，营养数值保持未知。' if not any(verified.values()) else
                               '仅按用户明确食用比例与图片粗估换算；未识别食物仍可能遗漏。'}
        value = {'description': str(raw.get('description') or item.get('review', {}).get('summary', ''))[:2000],
                 'nutrition': nutrition_ranges(raw.get('nutrition')),
                 'uncertainty': str(raw.get('uncertainty') or '照片估算，份量与烹调用油存在不确定性')[:1000]}
        decision = {'status': status, 'evidence': evidence, 'value': value, 'date': date, 'source': source}
        value['nutrition_context']=nutrition_context(value,'image_estimate',evidence)
        old = next((r for r in records if r.get('media_id') == item['id']), None)
        if old and status == 'unknown':
            receipts.append('本轮食用情况不明确，保留已有饮食记录');continue
        if status == 'consumed' and w['settings']['confirm_each']:
            item['food_pending'] = decision; receipts.append('饮食记录待确认')
        else:
            item.pop('food_pending', None)
            if status == 'consumed':
                record = s.prepare_record({'type': 'meal', 'value': value})
                record.update(media_id=item['id'], source='image', source_message=source,
                              occurred_at=date, recorded_at=source['at'])
                if old:
                    record['id'] = old['id']; record['memory_enabled'] = old.get('memory_enabled', True)
                    records[records.index(old)] = record
                else: records.append(record)
                item['confirmed'] = True; item['review_status'] = 'confirmed'
                receipts.append('饮食已按实际食用情况更新')
            elif old and status in ('reference', 'planned'):
                records.remove(old); receipts.append('已纠正：该照片不计入实际摄入')
            item['food_decision'] = decision
        item.setdefault('food_history', []).append(decision)
        results.append(decision)
    return receipts, results


def food_summary(records, date):
    meals = [r for r in records if r.get('type') in ('meal', 'beverage') and
             str(r.get('occurred_at') or r.get('created_at', ''))[:10] == date]
    totals = {}
    for key in ('kcal', 'protein_g', 'carbs_g', 'fat_g'):
        pairs = []
        for record in meals:
            try: pair = nutrition_ranges(record.get('value', {}).get('nutrition')).get(key)
            except ValueError: pair = None
            if pair is not None: pairs.append(pair)
        totals[key] = {'range': [round(sum(p[i] for p in pairs), 1) for i in (0, 1)] if pairs else None,
                       'estimated_count': len(pairs), 'unknown_count': len(meals) - len(pairs)}
    return {'date': date, 'record_count': len(meals), 'totals': totals, 'records': meals}
