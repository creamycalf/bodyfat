"""Conservative gates for new behavioral actions, not a nutrient calculator."""
import json
import re
import copy


def known_allergens(profile):
    """Normalize explicitly reported allergen names, without inferring diagnoses."""
    raw=profile.get('allergies') or []
    if isinstance(raw,str):raw=[raw]
    aliases={'花生':r'花生|落花生|peanut', '虾':r'虾|shrimp', '蟹':r'蟹|crab',
             '牛奶':r'牛奶|乳制品|milk', '鸡蛋':r'鸡蛋|蛋清|蛋白过敏|egg',
             '大豆':r'大豆|黄豆|soy', '小麦':r'小麦|wheat', '芝麻':r'芝麻|sesame',
             '鱼':r'鱼|fish', '坚果':r'坚果|tree nut'}
    found=[]
    for entry in raw if isinstance(raw,list) else []:
        for part in re.split('[，,；;、。]',str(entry)):
            if re.search(r'没有.{0,6}过敏|无过敏|不确定|怀疑|可能|未知|不清楚',part):continue
            for name,pattern in aliases.items():
                if not re.search(pattern,part,re.I):continue
                if re.search(r'(?:不对|没有对).{0,5}(?:'+pattern+r')|(?:'+pattern+r').{0,3}(?:不|没)过敏|无.{0,2}(?:'+pattern+r').{0,2}过敏',part,re.I):continue
                found.append(name)
            if not any(re.search(pattern,part,re.I) for pattern in aliases.values()):
                value=re.sub(r'^(?:我)?(?:还|也)?(?:对)?','',part.strip())
                value=re.sub(r'(?:食物)?过敏.*$|不耐受.*$','',value).strip()
                if re.fullmatch(r'[\u4e00-\u9fff]{2,12}',value) and not re.search('没有|未知|不清楚|暂时|食物',value):found.append(value)
    return list(dict.fromkeys(found))


def allergen_terms(name):
    # Named dishes here are possible ingredient risks, never proof of contents.
    return {'花生':r'花生|落花生|peanut|宫保鸡丁|宫爆鸡丁',
            '牛奶':r'牛奶|奶酪|乳酪|乳清|黄油|奶油|酸奶',
            '鸡蛋':r'鸡蛋|蛋清|蛋黄|蛋液|蛋粉',
            '大豆':r'大豆|黄豆|豆腐|豆浆|豆皮',
            '坚果':r'坚果|核桃|腰果|杏仁|榛子|开心果'}.get(name,re.escape(name))


def allergen_conflicts(profile, value):
    text=json.dumps(value,ensure_ascii=False)
    return [name for name in known_allergens(profile) if re.search(allergen_terms(name),text,re.I)]


def guard_allergen_reply(text, profile):
    """Remove a specific unsafe recommendation, preserving other explanations.

    This is a conservative lexical backstop for known ingredients. It is not a
    complete recipe database and cannot certify that unflagged food is safe.
    """
    allergens=known_allergens(profile)
    if not allergens:return text,[]
    removed=[];kept=[]
    for part in re.split(r'(?<=[。！？!?；;，,\n])',str(text)):
        conflicts=[name for name in allergens if re.search(allergen_terms(name),part,re.I)]
        unsafe=False
        for name in conflicts:
            pattern=allergen_terms(name)
            # "do not remove and eat" is a warning, not a recommendation.
            warns=bool(re.search(r'不要|不能|不建议|避免|避开|别吃|不选|不宜|无法确认|不能保证|不代表安全|不能排除',part))
            recommends=bool(re.search(r'(?:建议|优先|推荐|可以|可选|选择|搭配|吃点|吃少量|少量吃|取半份|选半份).{0,25}(?:'+pattern+r')|(?:'+pattern+r').{0,20}(?:可以吃|可吃|能吃|半份|少量|一份|配米饭|配主食)',part,re.I))
            meal_list=bool(re.search(r'(?:早餐|午餐|晚餐|加餐|菜谱|菜单|餐单|食谱)(?:安排|推荐|建议)?\s*[：:]',part))
            factual=bool(re.search(r'已吃|吃了|吃过|你说|实际吃|记录为|已记录',part))
            removal=bool(re.search(r'(?:去掉|挑掉|拿掉|去除|剔除).{0,8}(?:'+pattern+r')',part,re.I))
            if (recommends or removal or (meal_list and not factual)) and not warns:
                unsafe=True;removed.append(name)
        if not unsafe:kept.append(part)
    if not removed:return str(text),[]
    names='、'.join(dict.fromkeys(removed))
    caution=f'你已说明对{names}过敏，相关食物及配料无法核实时先避开。去掉可见过敏原不能排除交叉接触，需要向商家确认配料和制作过程；不能确认时换一道可核实的选择。'
    return '\n\n'.join(filter(None,[''.join(kept).strip(),caution])),list(dict.fromkeys(removed))


def guard_image_review(review, profile):
    """Apply the same recommendation guard to the report's detailed view."""
    if not isinstance(review,dict):return review
    safe=copy.deepcopy(review)
    safe['summary']=guard_allergen_reply(str(safe.get('summary') or ''),profile)[0]
    report=safe.get('report')
    if isinstance(report,dict) and isinstance(report.get('advice'),list):
        advice=[guard_allergen_reply(str(item),profile)[0] for item in report['advice']]
        report['advice']=list(dict.fromkeys(value for value in advice if value))
    return safe


def has_unverified_nutrients(value):
    """Until a sourced calculator exists, do not save numeric nutrient advice.

    Ingredient weights are recipe portions, not nutrient calculations. This gate
    deliberately also rejects quoted nutrient numbers in a new plan.
    """
    text=json.dumps(value,ensure_ascii=False)
    number=r'(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两]+)'
    return bool(re.search(number+r'\s*(?:千卡|大卡|卡路里|千焦|kcal|kj)\b',text,re.I)
                or re.search(number+r'\s*卡(?=[）)。，,；;\s"\\]|$)',text)
                or re.search(number+r'\s*(?:千卡|大卡|卡路里|千焦)',text)
                or re.search(r'(?:热量|能量|蛋白质|蛋白|碳水(?:化合物)?|脂肪|膳食纤维|钠|糖|protein|carbs?|fat|calories)[^。；;\n"，,]{0,20}'+number+r'\s*(?:克|毫克|g\b|mg\b|%|千卡|大卡|kcal)',text,re.I)
                or re.search(number+r'\s*(?:克|毫克|g\b|mg\b|%)\s*(?:蛋白质|蛋白|碳水|脂肪|糖|钠|膳食纤维|protein|carbs?|fat)',text,re.I))


def _verified_report_mask(text,tests):
    """Mask only exact saved numeric concentrations for the named report test."""
    spans=[];named=False
    number=r'(?:[<>≤≥]\s*)?\d+(?:\.\d+)?(?:\s*[-–—~～至]\s*\d+(?:\.\d+)?)?'
    concentration=number+r'\s*(?:[munpμµ]?g|克|毫克|微克)\s*/\s*(?:[dmuμµ]?l|升|毫升)\b'
    def numeric_pattern(value):
        value=str(value).strip()
        if not re.fullmatch(number,value):return None
        pieces=[]
        for token in re.findall(r'\d+(?:\.\d+)?|[-–—~～至]|[<>≤≥]',value):
            if re.fullmatch(r'\d+(?:\.\d+)?',token):
                normalized=token.rstrip('0').rstrip('.') if '.' in token else token
                pieces.append(re.escape(normalized)+(r'0*' if '.' in normalized else r'(?:\.0+)?'))
            elif token in '-–—~～至':pieces.append(r'[-–—~～至]')
            else:pieces.append(re.escape(token))
        return r'(?<![\d.])'+r'\s*'.join(pieces)
    for test in tests if isinstance(tests,list) else []:
        if not isinstance(test,dict):continue
        name=str(test.get('name') or '').strip();unit=re.sub(r'\s+','',str(test.get('unit') or ''))
        if (not name or not re.fullmatch(r'(?:[munpμµ]?g|克|毫克|微克)/(?:[dmuμµ]?l|升|毫升)',unit,re.I)
                or not re.search(r'\s*'.join(map(re.escape,name)),text,re.I)):continue
        named=True
        unit_pattern=r'\s*'.join(map(re.escape,unit))
        for key in ('value','reference'):
            value=str(test.get(key) if test.get(key) is not None else '').strip()
            value=re.sub(r'\s*'+unit_pattern+r'\s*$','',value,flags=re.I)
            pattern=numeric_pattern(value)
            if pattern:
                spans.extend(match.span() for match in re.finditer(pattern+r'\s*'+unit_pattern+r'(?![A-Za-zμµ/])',text,re.I))
    masked=list(text)
    for start,end in spans:masked[start:end]=' '*(end-start)
    return ''.join(masked),bool(spans),concentration if named else None


def _verified_food_mask(text,report):
    """Authorize exact photo estimates, never daily targets or intake advice."""
    if not isinstance(report,dict) or report.get('kind')!='food':return text,False
    if not re.search(r'照片|图中|这张图|这(?:一)?(?:份|盘|餐)|整(?:份|盘|餐)',text):return text,False
    import nutrition_reports
    # Parenthesized partial-total limitations belong to their nutrient clause.
    cuts=[0];depth=0
    for index,char in enumerate(text):
        if char in '（(':depth+=1
        elif char in '）)':depth=max(0,depth-1)
        elif char in '，,' and not depth:cuts.append(index+1)
    cuts.extend(match.start() for match in re.finditer(
        r'(?:并且|而且|同时|且)?(?:建议|每天|每日|每餐|每顿|目标|需要)',text))
    cuts=sorted(set([*cuts,len(text)]));masked=list(text);verified=False
    def number_pattern(value):
        value=f'{value:.2f}'.rstrip('0').rstrip('.')
        return re.escape(value)+(r'0*' if '.' in value else r'(?:\.0+)?')
    for start,end in zip(cuts,cuts[1:]):
        clause=text[start:end]
        if re.search(r'每天|每日|每餐|每顿|一天|一日|日需|每公斤|目标|处方|建议|推荐|至少|至多|应当|应该|需要|摄入|正常人|成年人|人体|标准|(?:吃|喝|补充)\s*\d',clause):continue
        for key,label,unit in [('kcal',r'热量|能量',r'千卡|大卡|kcal'),
                               ('protein_g',r'(?<!优质)蛋白质|protein',r'克|g'),
                               ('carbs_g',r'(?<!净)碳水(?:化合物)?|carbs?',r'克|g'),
                               ('fat_g',r'(?<!饱和)(?<!反式)脂肪(?!酸)|fat',r'克|g')]:
            totals=report.get('totals') if isinstance(report.get('totals'),dict) else {}
            pair=nutrition_reports.interval(totals.get(key),nutrition_reports.PORTION_LIMITS[key]*30)
            if pair is None:
                partial=report.get('partial_totals') if isinstance(report.get('partial_totals'),dict) else {}
                pair=nutrition_reports.interval(partial.get(key),nutrition_reports.PORTION_LIMITS[key]*30)
                if (pair is None or not re.search(r'仅(?:已)?估算(?:的)?部分',clause) or
                        not re.search(r'(?:不是|不代表)整(?:餐|盘|份)(?:的)?总量',clause)):continue
            low,high=map(number_pattern,pair)
            amount=(low+r'(?:\s*[-–—~～至到]\s*'+high+r')?' if pair[0]==pair[1] else low+r'\s*[-–—~～至到]\s*'+high)
            quantity=r'(?<![\d.])'+amount+r'\s*(?:'+unit+r')(?![A-Za-z]|\s*/)'
            pattern=(r'(?:'+label+r')[^\d，,。；;!?！？]{0,16}(?P<forward>'+quantity+r')|'
                     r'(?P<reverse>'+quantity+r')\s*(?:的)?(?:'+label+r')')
            for match in re.finditer(pattern,clause,re.I):
                first,last=match.span('forward' if match.group('forward') is not None else 'reverse')
                masked[start+first:start+last]=' '*(last-first);verified=True
    return ''.join(masked),verified


def redact_unverified_nutrients(text,verified_report_tests=None,verified_food_report=None):
    """Remove only unsafe numeric sentences; keep the conversation alive."""
    parts=re.split(r'(?<=[。！？!?；;\n])',str(text or ''))
    kept=[];removed=False
    for part in parts:
        masked,verified,concentration=_verified_report_mask(part,verified_report_tests)
        food_mask,food_verified=_verified_food_mask(part,verified_food_report)
        masked=''.join(' ' if a==' ' or b==' ' else original for original,a,b in zip(part,masked,food_mask))
        verified=verified or food_verified
        unsafe=lambda value:has_unverified_nutrients(value) or bool(concentration and re.search(concentration,value,re.I))
        if verified and unsafe(masked):
            # A verified lab number does not authorize adjacent intake advice.
            # Keep the source-backed clauses and reject the numeric advice.
            boundaries=list(re.finditer(r'[^，,]+[，,]?|[，,]',part))
            safe=[]
            for match in boundaries:
                cuts=[match.start()]+[match.start()+cue.start() for cue in
                      re.finditer(r'(?:并且|而且|同时|且)?(?:建议|每天|每日|每餐|每顿|目标|需要)',match[0]) if cue.start()>0]+[match.end()]
                for start,end in zip(cuts,cuts[1:]):
                    if unsafe(masked[start:end]):removed=True
                    else:safe.append(part[start:end])
            clean=''.join(safe).rstrip('，, ')
            if clean and part.rstrip().endswith('。') and not clean.endswith('。'):clean+='。'
            kept.append(clean)
        elif part.strip() and unsafe(masked):
            removed=True
        else:
            kept.append(part)
    return ''.join(kept).strip(),removed


def exercise_session_reply(session):
    """Render a timed session only after calculating its seconds in Python."""
    if not isinstance(session,dict):return ''
    warm=session.get('warmup');cool=session.get('cooldown');circuit=session.get('circuit')
    if not isinstance(warm,dict) or not isinstance(cool,dict) or not isinstance(circuit,dict):return ''
    timing=r'(?:\d+(?:\.\d+)?|[一二三四五六七八九十两]+)\s*(?:分钟|秒|轮|组|次/组)'
    if any(re.search(timing,str(block.get('name') or '')) for block in (warm,cool)):return ''
    def duration(value,maximum):
        return isinstance(value,int) and not isinstance(value,bool) and 0<=value<=maximum
    if not duration(warm.get('seconds'),1800) or not duration(cool.get('seconds'),1800):return ''
    rounds=circuit.get('rounds');items=circuit.get('items')
    if not isinstance(rounds,int) or isinstance(rounds,bool) or not 1<=rounds<=10:return ''
    if not isinstance(items,list) or not 1<=len(items)<=12:return ''
    names=[];per_round=0
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip():return ''
        if re.search(timing,item['name']):return ''
        if not duration(item.get('work_seconds'),600) or not 1<=item['work_seconds']:return ''
        if not duration(item.get('rest_seconds'),600):return ''
        per_round+=item['work_seconds']+item['rest_seconds']
        names.append(f"{item['name'][:100]}：活动{item['work_seconds']}秒，休息{item['rest_seconds']}秒")
    total=warm['seconds']+per_round*rounds+cool['seconds']
    if not 60<=total<=7200:return ''
    def shown(seconds):
        minutes,seconds=divmod(seconds,60)
        return (f'{minutes}分钟' if minutes else '')+(f'{seconds}秒' if seconds else '') or '0分钟'
    return (f'本次安排合计{shown(total)}（包含下列休息时间；动作转换或额外休息另计）：\n'
            f"热身：{str(warm.get('name') or '舒适范围内热身')[:150]}，{shown(warm['seconds'])}。\n"
            +'\n'.join(names)+f'。\n上述动作共{rounds}轮，每轮{shown(per_round)}，练习段共{shown(per_round*rounds)}。\n'
            f"收尾：{str(cool.get('name') or '舒缓活动')[:150]}，{shown(cool['seconds'])}。")


def remove_unchecked_exercise_times(text):
    """Keep nonnumeric explanations; discard timings not backed by the calculator."""
    parts=re.split(r'(?<=[。！？!?；;，,\n])',str(text))
    return ''.join(part for part in parts if not re.search(
        r'(?:\d+(?:\.\d+)?|[一二三四五六七八九十两]+)\s*(?:分钟|秒|轮|组|次/组)',part)).strip()
