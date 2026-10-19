"""Grounded interview state: short answers belong only to the last asked field."""
import re
from datetime import datetime, timedelta

QUESTIONS = {
    'age': '你今年多大？可以直接回复年龄数字。',
    'sex': '你的生理性别是什么？这会影响营养评估；不方便可以回复“跳过”。',
    'height_cm': '你的身高是多少厘米？',
    'weight_kg': '最近测到的体重是多少公斤或斤？请带单位。',
    'goals': '你希望改善什么、期望多久？也请说说过去减重的经历。',
    'conditions': '有没有确诊疾病、身体不适或医生要求限制的活动？没有请回复“没有”。',
    'medications': '目前有没有在用药物或保健品？没有请回复“没有”。',
    'allergies': '有哪些食物过敏或必须避开的食物？没有请回复“没有”。',
    'surgeries': '是否有手术史或尚在恢复的伤病？没有请回复“没有”。',
    'life_stage': '目前是否处于孕期、备孕或哺乳期？可回复具体情况、不适用或跳过。',
    'sleep_schedule': '平常几点起床、几点睡觉？工作日和休息日不同的话请分别说。',
    'work_schedule': '每天几点上班或上学、几点结束、通勤多久？轮班或没有固定安排也请说明。',
    'meal_schedule': '通常什么时候吃各餐？能做饭还是主要食堂、外卖？时间不固定也可以。',
    'breakfast_habit': '先了解早餐：平常吃什么、喝什么，各有多少？通常不吃或不同日子不同，也请照实说。可以用碗、个、杯描述份量。',
    'lunch_habit': '午餐通常吃什么、喝什么，各有多少？是在食堂、点外卖还是自己做？不用按建议回答，描述平常真实的一餐就好。',
    'dinner_habit': '晚餐通常吃什么、喝什么，各有多少？会不会不吃、很晚吃或之后加餐？',
    'snacks_drinks': '三餐以外会吃什么零食、水果、夜宵，喝什么饮料、咖啡或酒？大概多少、多久一次？没有也可以直接说。',
    'food_habits': '吃饭条件怎样：通常自己做、食堂还是外卖？每天预算大约多少，有哪些买菜、做饭或聚餐限制？',
    'eating_pattern': '平时饥饿和饱腹感怎么样？有没有经常饿得难受、吃到撑、情绪性进食，或吃完后刻意少吃下一餐的情况？',
    'weight_history': '最近几个月体重大致怎样变化？以前试过哪些减重方法，有没有难坚持、反弹或不舒服的经历？',
    'occupation': '平常工作或学习主要久坐、站立还是体力活动？目前有什么运动习惯？',
    'activity_baseline': '目前一天主要久坐、站立还是走动？每周实际运动几次、每次多久？没运动也可以直接说。',
    'available_time': '你愿意在什么时间活动、每次多久？有哪些身体或场地限制？',
    'preferences': '有哪些喜欢或不喜欢的食物、活动？计划最需要照顾哪种现实困难？',
}

MEALS=('breakfast_habit','lunch_habit','dinner_habit')


def declined_fields(text, asked=None):
    """Explicit refusal is a preference, never a negative health fact."""
    value=str(text or '')
    refusal=r'(?:暂时|暂且|现在|先)?(?:不想|不愿|不方便|暂不|不)(?:再)?(?:说|回答|提供|透露|聊)|跳过'
    if re.fullmatch(r'\s*(?:'+refusal+r')[了吧。！!\s]*',value):
        return [asked] if asked in QUESTIONS else []
    aliases={'sex':'性别','age':'年龄','height_cm':'身高','weight_kg':'体重',
             'conditions':'病史|疾病','medications':'用药|药物','allergies':'过敏',
             'surgeries':'手术','life_stage':'孕期|哺乳|孕哺'}
    fields=[]
    for field, words in aliases.items():
        if re.search(r'(?:'+words+r')[^，,。；;？?]{0,10}(?:'+refusal+r')|(?:'+refusal+r')[^，,。；;？?]{0,10}(?:'+words+r')',value):
            fields.append(field)
    return fields

# The legacy QUESTIONS map is intentionally kept for profile completeness and
# old conversations.  Assessment is a separate, purpose-driven layer: a
# question is selected because it can change the next action, not because it
# happens to be the next empty profile field.
ASSESSMENT_QUESTIONS = {
    'goal_barrier': {
        'label': '目标与阻碍',
        'fields': ('goals', 'preferences'),
        'question': '这次最想先改善什么？最容易在哪个时段或情境卡住？\n可以直接这样回：晚餐容易吃多；加班没时间；下午容易饿；暂时说不清。也可以只选一个，或回复“跳过”。',
        'reason': '先确认你要解决的问题和最常见的阻碍，避免给一套与你生活无关的安排。',
    },
    'meal_pattern': {
        'label': '代表性饮食',
        'fields': ('breakfast_habit', 'lunch_habit', 'dinner_habit', 'snacks_drinks'),
        'question': '请描述一个平常工作日：从第一餐到最后一餐吃了什么、喝了什么？\n可以按“早餐/午餐/晚餐/加餐”简单列出，份量用碗、个、杯即可；不知道或不想答的部分可说“跳过”。',
        'reason': '需要先看到真实的进食模式，才能选择一个值得试行的小改变。',
    },
    'meal_symptom': {
        'label': '餐后症状',
        'fields': ('dinner_habit', 'conditions', 'surgeries', 'medications'),
        'question': '不舒服通常发生在哪一餐、吃完多久出现？具体是什么感觉、持续多久？\n可以直接回：晚餐后约1小时胀；没有医生限制；不确定的部分可说“不清楚”，如有明显危险症状请先就医。',
        'reason': '先把症状、餐次和健康限制对应起来，才能判断哪些建议需要先暂停或请专业人员评估。',
    },
    'schedule_barrier': {
        'label': '生活条件',
        'fields': ('work_schedule', 'meal_schedule', 'available_time', 'food_habits'),
        'question': '最难执行的是哪个生活节点？\n可以直接回：工作日午餐只能外卖；晚餐常加班；每天只有10分钟；暂时没有固定困难。',
        'reason': '行动必须适合你的作息、通勤和可用条件，先找出最容易失败的节点。',
    },
    'hunger_pattern': {
        'label': '饥饿与进食感受',
        'fields': ('eating_pattern', 'snacks_drinks', 'weight_history'),
        'question': '你通常在哪个时段最容易饿、吃撑或想吃零食？过去试过什么，哪里最难坚持？\n可以直接回：下午最饿；晚饭后想吃零食；试过节食但坚持不了；不清楚也可以说“不知道”。',
        'reason': '饥饿感和过去的阻碍会决定行动难度，先从能坚持的版本开始。',
    },
    'sleep_activity': {
        'label': '睡眠与活动',
        'fields': ('sleep_schedule', 'activity_baseline', 'occupation'),
        'question': '平常什么时候睡醒、白天主要坐着还是走动？最近实际能安排多少活动？\n可以直接回：23点睡7点起；白天久坐；每天只能散步10分钟；不知道的部分可以跳过。',
        'reason': '睡眠和日常活动会影响饥饿、精力及行动时机，先确认现实基线。',
    },
    'profile_basics': {
        'label':'基础资料','fields':('age','height_cm','sex'),
        'question':'请补充尚未说明的年龄、身高或性别。',
        'reason':'只补充尚未明确的基础信息。',
    },
}

def assessment_topic(text='', profile=None, state=None):
    """Choose a purpose-driven assessment topic from the current conversation.

    This is deliberately deterministic and conservative.  The model may
    phrase the question, but the application supplies the allowed topic and
    reason so a missing age field cannot hijack a symptom or meal discussion.
    """
    text = str(text or '')
    state = state or {}
    if re.search(r'(?:晚餐|晚饭|吃完|餐后).{0,12}(?:不舒服|难受|反酸|胀|痛|恶心|症状)', text):
        return 'meal_symptom'
    if re.search(r'做不到|难坚持|没时间|加班|通勤|上班很忙|聚餐|外卖条件|预算', text):
        return 'schedule_barrier'
    if re.search(r'饿|饱|吃撑|零食|嘴馋|暴食|反弹|坚持不住', text):
        return 'hunger_pattern'
    if re.search(r'睡眠|睡觉|作息|失眠|运动|活动|久坐|散步', text):
        return 'sleep_activity'
    if re.search(r'早餐|午餐|午饭|晚餐|晚饭|吃了|饮料|加餐|零食|一碗|一杯|外卖', text):
        return 'meal_pattern'
    if re.search(r'减肥|减脂|减重|瘦|改善|目标|想要|希望', text):
        return 'goal_barrier'
    return state.get('topic') if state.get('topic') in ASSESSMENT_QUESTIONS else 'goal_barrier'

def assessment_candidates(text='', profile=None, records=None, state=None, skipped=()):
    """Return at most one allowed next topic, ordered by decision value.

    Confirmed fields are not automatically treated as a reason to ask for
    another field; they are only used to avoid repeating a completed topic.
    A skipped topic remains skipped until the user explicitly changes topic.
    """
    profile = profile or {}; state = state or {}; skipped=set(skipped or ()) | set(state.get('skipped_topics', []))
    completed=set(state.get('answered_topics',{}))
    topic = assessment_topic(text, profile, state)
    candidates=[]
    preferred=[topic] + [key for key in ASSESSMENT_QUESTIONS if key != topic]
    for key in preferred:
        if key in skipped or key in completed: continue
        spec=ASSESSMENT_QUESTIONS[key]
        missing=[field for field in spec['fields'] if not known(profile, field)]
        if missing:
            question, reason = contextual_assessment_question(key, text, spec)
            candidates.append({'topic':key,'label':spec['label'],'missing':missing,
                               'question':question,'reason':reason})
        if candidates: break
    return candidates


def contextual_assessment_question(topic, text='', spec=None):
    """Do not expose a generic intake script after a concrete user goal."""
    spec=spec or ASSESSMENT_QUESTIONS.get(topic,{})
    text=str(text or '')
    return str(spec.get('question','')),str(spec.get('reason',''))


def reply_question(reply, decision=None):
    """Track the displayed question, never the user's original request.

    Unknown topics remain unclassified rather than becoming a fake goal
    question. This metadata is not permission to infer health facts.
    """
    decision=decision if isinstance(decision,dict) else {}
    clauses=re.findall(r'[^。！？!?\n]*[？?]',str(reply or ''))
    question=' '.join(x.strip() for x in clauses).strip()
    if not question and decision.get('action')=='clarify':question=str(reply or '').strip()
    if not question:return None
    patterns={'profile_basics':'年龄|多大|身高|男生|女生|男性|女性|性别',
              'meal_symptom':'症状|不舒服|反酸|胀|疼|医生|医嘱|手术|用药|饮食限制',
              'sleep_activity':'睡|起床|活动|运动|久坐',
              'schedule_barrier':'加班|通勤|上班|下班|预算',
              'hunger_pattern':'饿|饱|撑|零食|反弹',
              'meal_pattern':'餐|饭|吃|喝|饮食',
              'goal_barrier':'目标|改善|困难|阻碍|减重|减肥'}
    parts=[]
    for clause in clauses or [question]:
        topics=[key for key,pattern in patterns.items() if re.search(pattern,clause)]
        if 'meal_symptom' in topics and re.search('饮食限制|餐后|饭后|吃完|(?:餐|饭).{0,6}(?:症状|不舒服|胀|疼)',clause):
            topics=[key for key in topics if key!='meal_pattern']
        parts.append({'text':clause.strip(),'topics':topics})
    topics=list(dict.fromkeys(key for part in parts for key in part['topics']))
    return {'topic':topics[0] if len(topics)==1 else '', 'topics':topics,'questions':parts,
            'text':question,'reason':str(decision.get('question_reason') or decision.get('reason') or '')[:500]}

def topic_answered(topic,text):
    """A grounded answer closes a question, not a clinical uncertainty."""
    if re.search(r'如果|假如|朋友|不知道|不清楚|跳过|[？?]|请生成|先给',text) or discussion_request(text):return False
    patterns={
        'profile_basics':r'岁|厘米|身高|男|女',
        'meal_symptom':r'胀|疼|反酸|恶心|腹泻|不舒服|分钟|小时',
        'schedule_barrier':r'加班|上班|下班|食堂|外卖|分钟|做饭|买',
        'hunger_pattern':r'饿|撑|饱|零食|反弹',
        'sleep_activity':r'睡|起床|散步|久坐|运动',
        'meal_pattern':r'吃|喝|碗|杯|鸡蛋|米饭|面条',
        'goal_barrier':r'改善|减重|减肥|减脂|希望|想|困难|忙|饿|晚餐|加班|零食'}
    return len(text.strip())>=2 and bool(re.search(patterns.get(topic,r'(?!)'),text))

def assessment_question(topic, profile=None):
    spec=ASSESSMENT_QUESTIONS.get(topic)
    if not spec:return None
    return spec['question']

def has_portion(value):
    return bool(re.search(r'(?:\d+(?:\.\d+)?|[一二三四五六七八九十两半几]+)\s*(?:小|大|中|满|平)?\s*(?:碗|个|杯|瓶|盒|份|片|块|勺|把|克|斤|两|毫升|ml|g)|手掌|拳头',str(value),re.I))

def known(profile, field):
    if field not in profile or profile[field] is None or profile[field]=='':return False
    values=profile[field] if isinstance(profile[field],list) else [profile[field]]
    if not values or all(re.fullmatch(r'不知道|不清楚|待了解|未提供|未知|待补充|已说明|跳过|暂不回答|不方便回答',str(v).strip()) for v in values):return False
    value=str(profile[field])
    if re.fullmatch(r'不知道|不清楚|待了解|未提供|未知|待补充|已说明',value):return False
    if field in MEALS:
        if re.search('不吃|没吃|无固定|不固定|跳过',value):return True
        # "面条、米饭" is a food example, not a complete meal pattern.
        return has_portion(value) and not re.fullmatch(r'随便|正常吃|都吃|举例.*',value)
    if field=='surgeries' and re.search('切除|手术',value) and not re.search('没有|无手术|没做|未做|未手术',value):
        if '切除' in value and not re.search('胆囊|阑尾|胃|肠|肝|胰|脾|肾|肺|子宫|卵巢|甲状腺|乳腺|扁桃体|肿瘤|囊肿|息肉',value):return False
        return not re.fullmatch(r'[\d\s年做过是在我，,。]*?(?:切除[了的]?|手术[了的]?)[，,。\s]*',value)
    return True

def question(field,profile):
    if field in MEALS and profile.get(field):
        return '你提到“'+str(profile[field])[:180]+'”。这餐通常每样吃多少、有没有其他食物或饮品？用碗、个、杯估计即可，不知道的部分可以明确说不知道或跳过。'
    if field=='surgeries' and profile.get(field) and not known(profile,field):
        return '你提到做过手术，具体是什么手术、哪个部位？目前还有什么不适或医嘱？我不能根据“切除了”猜测器官。'
    return QUESTIONS[field]

# Used only for a preceding assistant question, never to infer an answer's meaning.
QUESTION_TERMS={
 'conditions':r'疾病|确诊|病史|健康状况',
 'age':r'年龄|多大|几岁','sex':r'性别|男生|女生|男性|女性','height_cm':r'身高','weight_kg':r'体重',
 'surgeries':r'手术|切除','breakfast_habit':r'早餐|早饭|早晨.*吃',
 'lunch_habit':r'午餐|午饭|中餐','dinner_habit':r'晚餐|晚饭',
 'snacks_drinks':r'饮料|咖啡|零食','allergies':r'过敏|忌口','medications':r'用药|药物|保健品',
 'sleep_schedule':r'几点.*睡|几点.*起|起床|睡觉','food_habits':r'平时.*吃什么|(?<!通)常吃.*什么|预算|吃饭条件',
}

def previous_questions(reply):
    # Only map single-field questions. Multi-field bullets remain ambiguous.
    parts=re.split(r'(?:^|\n)\s*(\d{1,2})[.、)）\s]+',reply)
    mapped={}
    if len(parts)>1:
        for i in range(1,len(parts)-1,2):
            hits=[f for f,pattern in QUESTION_TERMS.items() if re.search(pattern,parts[i+1])]
            if len(hits)==1:mapped[parts[i]]=hits[0]
    elif re.search('[？?]|请.*(?:告诉|提供|回复|说)|你.*(?:多少|多大|几岁)',reply):
        hits=[f for f,pattern in QUESTION_TERMS.items() if re.search(pattern,reply)]
        if len(hits)==1:mapped['1']=hits[0]
    return mapped

def contextual_answers(reply,text):
    mapping=previous_questions(reply)
    if not mapping:return {}
    parts=re.split(r'(?:^|\n|(?<=\s))\s*('+ '|'.join(map(re.escape,mapping))+r')[.、)）\s]+',text)
    if len(parts)>1:
        out={}
        for i in range(1,len(parts)-1,2):
            out.update(short_answer(mapping.get(parts[i]),parts[i+1].strip()))
        return out
    return short_answer(next(iter(mapping.values())),text) if len(mapping)==1 else {}

def current_weight_records(records,reference=None):
    """Recent measured weights ordered by observation, not insertion order.

    Imprecise historical dates never stand in for current weight. Older
    records without any date retain their legacy eligibility.
    """
    reference=reference or datetime.now()
    rows=[]
    for index,record in enumerate(records):
        value=record.get('value',{})
        kg=value.get('kg') if isinstance(value,dict) else None
        if (record.get('type')!='weight' or record.get('memory_enabled') is False or
                record.get('confirmed') is False or record.get('status') in ('pending','inferred','retracted') or
                not isinstance(kg,(int,float)) or isinstance(kg,bool) or not 20<=kg<=400 or
                record.get('date_precision','day')!='day'):continue
        stamp=record.get('observed_at') or record.get('occurred_at') or record.get('created_at')
        observed=None
        if stamp:
            try:observed=datetime.fromisoformat(str(stamp).replace('Z','+00:00')).replace(tzinfo=None)
            except (ValueError,TypeError):continue
            if not reference.date()-timedelta(days=30)<=observed.date()<=reference.date():continue
        rows.append((observed or datetime.min,index,record))
    return [row[2] for row in sorted(rows,key=lambda row:(row[0],row[1]))]


def missing(profile, records, skipped=()):
    return [f for f in QUESTIONS if f not in skipped
            and not (f == 'life_stage' and profile.get('sex') in ('男', '男性'))
            and not (bool(current_weight_records(records))
                     if f == 'weight_kg' else known(profile, f))]

def discussion_request(text):
    """A request to explain or pause is not an answer to a profile field."""
    return bool(re.search(r'为什么|怎么回事|什么意思|请解释|想知道|先解释|别急着安排|先别安排|先不安排',str(text)))


def short_answer(field, text):
    text=text.strip().rstrip('。！!')
    if not field or len(text)>500 or re.search(r'如果|假如|不确定|不知道|[？?]|跳过|不要记录|别记|朋友|我爸|我妈',text):return {}
    if discussion_request(text):return {}
    if declined_fields(text,field) or re.search(r'^(?:好[的吧]?|明白了|那|嗯|行|可以)[，,\s]*(?:那)?(?:我们)?继续|别再问|不要再问|先别问|不想说',text):return {}
    if field in ('age','height_cm','weight_kg'):
        patterns={'age':r'(?:我?今年|年龄是?)?\s*(\d{1,3})\s*岁?',
                  'height_cm':r'(?:身高是?)?\s*(\d{2,3}(?:\.\d+)?)\s*(?:厘米|cm)?',
                  'weight_kg':r'(?:体重是?)?\s*(\d+(?:\.\d+)?)\s*(公斤|千克|kg|斤)'}
        m=re.fullmatch(patterns[field],text,re.I)
        if not m:return {}
        value=float(m[1])
        if field=='weight_kg' and m[2]=='斤':value/=2
        return {field:value}
    if field=='sex':
        m=re.fullmatch(r'(?:我是)?(男|女|男性|女性|其他)',text)
        return {field:m[1]} if m else {}
    # A standalone acknowledgment or a new command must never become a profile fact.
    if re.fullmatch(r'好[的吧]?|嗯+|是的?|继续|谢谢|收到|可以|确认|没问题|正确|用新记录|保留原记录',text) or re.search(r'请|帮我|生成|方案|计划|今天.*(?:吃|喝)|昨天',text):return {}
    return {field:text}

def explicit_basics(text):
    out={}
    age=re.search(r'(?:^|[，,；;。\s])(?:我今年|今年|我)?\s*(\d{1,3})\s*岁(?:$|[，,；;。\s])',text)
    sex=re.search(r'(?:^|[，,；;。\s])(?:我是|我|性别(?:是|为)?)?\s*(男性|女性|男|女)(?:$|[，,；;。\s])',text)
    if age:out['age']=int(age[1])
    if sex:out['sex']=sex[1][0]
    height=re.search(r'身高\s*(?:是|为)?\s*(1[.,]\d{1,2})\s*(?:米|m\b)',text,re.I)
    if height:out['height_cm']=round(float(height[1].replace(',','.'))*100,1)
    # A unit-bearing standalone clause in a self-description is unambiguous;
    # a bare number after a bundled question is deliberately not assigned.
    weight=re.search(r'(?:^|[，,；;。\s])(?:我)?\s*(\d+(?:\.\d+)?)\s*(公斤|千克|kg|斤)(?=$|[，,；;。\s])',text,re.I)
    if weight:out['weight_kg']=float(weight[1])/(2 if weight[2]=='斤' else 1)
    return out

def explicit_medication(text):
    """Extract only a clearly self-reported current medication name."""
    text=str(text or '')
    if re.search(r'如果|假设|假如|朋友|我爸|我妈|他吃|她吃|[？?]|不确定|不知道',text):return {}
    names=[]
    for match in re.finditer(r'(?:服用|吃|用)\s*(?:着|的|了)?\s*([^\s，,。；;、]{1,25})',text):
        before=text[max(0,match.start()-3):match.start()]
        if re.search(r'没有|没|不|未|停',before):continue
        name=match[1].strip('的了着')
        if not re.search(r'优甲乐|甲状腺素|胰岛素|二甲双胍|[^什哪何这那]药|胶囊',name):continue
        if re.search(r'什么药|哪些药|怎么用药|该不该|能不能',name):continue
        names.append(name[:80])
    return {'medications':names} if names else {}

def explicit_health_facts(text):
    """Keep explicitly named health facts separate in a mixed interview answer.

    This deliberately recognises only clear self-reports; silence about a
    category never becomes a negative history.
    """
    value=str(text or '')
    if re.search(r'如果|假如|朋友|我爸|我妈|他有|她有|[？?]|不确定|不知道',value):return {}
    parts=[part.strip() for part in re.split(r'[，,。；;、\n]',value) if part.strip()]
    result={}
    surgeries=[part for part in parts if re.search(r'切除|做过.{0,8}手术|手术史|术后|没有.{0,8}手术|没做过手术',part)]
    conditions=[part for part in parts if re.search(
        r'确诊.{0,12}(?:病|疾病)|没有.{0,12}(?:确诊|疾病|慢性病)|'
        r'哮喘|鼻炎|糖尿病|高血压|脂肪肝|痛风|胃炎|肾病|心脏病|'
        r'运动.{0,12}(?:头晕|晕|喘)|(?:头晕|晕|喘).{0,12}运动|'
        r'(?:膝盖?|肩|腰|脚踝|关节|手腕).{0,12}(?:旧伤|疼|痛|受伤)',part)
        and not re.search(r'切除|手术',part)]
    allergies=[part for part in parts if re.search(r'食物过敏|对[^，,。；;]{1,20}过敏|没有.{0,6}过敏|无.{0,3}过敏',part)
               and not re.search(r'过敏性(?:鼻炎|哮喘)',part)]
    medications=[part for part in parts if re.search(
        r'(?:没有|未|无|不).{0,6}(?:用药|吃药|服药|(?:服用|使用).{0,5}(?:药物|药|保健品)|药物|保健品)$',part)]
    if surgeries:result['surgeries']=surgeries
    if conditions:result['conditions']=conditions
    if allergies:result['allergies']=allergies
    if medications:result['medications']=medications
    return result

def timing_contract(profile):
    return ('普通咨询和单餐问题立即回答，不以确定计划开始日期为前提。用户未指定日期时，'
            '从今天剩余的可执行时段考虑下一步；只有今天确实没有合适机会时，才解释首个定时行动可放到明天。'
            '用户明确指定日期或轮班生活节点时尊重原意。结合今天实际吃过什么及接下来还有哪些餐；'
            '不得要求补吃已过去的餐或用节食补偿。'
            '作息、上下班和餐时以档案原话为准，轮班按其起床/上班/下班作为锚点。'
            'when使用“每天·起床后”“每天·午餐时”“每天·下班后”等相对生活节点，'
            '不要自编几点几分。没有完成建档时先回应本轮困扰，可给一项低风险的起步选择并追问最相关的未知项；不输出个性化热量处方或声称已出方案。'
            '缺项清单为空且用户已请求计划时，直接返回可保存的plan，不再重复询问是否要生成计划。'
            '不能仅因凌晨入睡就判定作息不健康，应结合睡眠时长、规律和白天状态；尊重轮班。'
            '不能保证减重几公斤或不反弹。热量目标若缺乏可靠计算依据只给食物搭配和参考份量，不编造精准处方。'
            '运动中身体不适应停止相关活动并评估，不能要求减量但不停止或继续坚持。'
            '跳过的项目写进unknowns；未成年人、孕哺期、进食障碍或疾病用药限制时优先专业评估，'
            '不给激进减重和药物调整建议。')

def relative_when(when, title):
    """Remove guessed clock times without producing broken ranges or losing frequency."""
    clock=r'\d{1,2}\s*[:：点时]\s*\d{0,2}(?:分)?'
    if not re.search(clock,when):return when
    clean=re.sub(r'\d{1,2}\s*[-—~至到]\s*'+clock+r'(?:之间|左右)?','',when)
    clean=re.sub(clock+r'(?:\s*[-—~至到]\s*'+clock+r')?(?:之间|左右)?','',clean)
    clean=re.sub(r'[（(]\s*[)）]','',clean).strip(' ·，,：:')
    if re.search('起床|下班|午休|睡前|餐前|餐后|用餐|晚饭后',clean):return clean
    meal=next((m for m in ('早餐','午餐','晚餐') if m in title),None)
    return clean+'·'+(meal+'时' if meal else '按已确认的作息，在方便的时段执行')

def already_passed_today(item, text, hour):
    combined=item['title']+' '+item['when']
    for index,(meal,alias) in enumerate((('早餐','早饭'),('午餐','午饭'),('晚餐','晚饭'))):
        if meal in combined:
            named='(?:'+meal+'|'+alias+')'
            if re.search(named+r'.{0,12}(?:吃了|吃过|吃完|已吃)',text):return True
            if re.search(r'(?:吃了|吃过|吃完|已吃).{0,12}'+named,text):return True
            next_meal=re.search(r'下一餐(?:是|为|还有|想吃|要吃)?\s*(早餐|午餐|晚餐)',text)
            if next_meal and index<('早餐','午餐','晚餐').index(next_meal[1]):return True
    if hour>=12 and re.search('早上|上午|晨起',combined):return True
    if hour>=18 and re.search('下午',combined):return True
    if re.search('起床后',combined) and re.search('早餐|早饭',text):return True
    # A whole-day target must never become a catch-up target on the partial first day.
    if re.search('全天|每日饮水|每天饮水',combined):return True
    return False
