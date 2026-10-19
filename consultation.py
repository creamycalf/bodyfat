"""Decision-scoped consultation readiness and summary confirmation.

The model may phrase a response, but the application owns the boundary between
an immediately useful answer and a saved, personalized plan.  Readiness is
therefore based on the decision being made, not on completion of every profile
field in the product.
"""
import hashlib
import json
import re
import intake

class IncompleteAssessment(Exception):
    pass

GROUPS={
    '基础与目标':('age','sex','height_cm','goals'),
    '健康限制':('conditions','medications','allergies','surgeries','life_stage'),
    '典型饮食':('breakfast_habit','lunch_habit','dinner_habit','snacks_drinks'),
    '作息和活动':('sleep_schedule','work_schedule','activity_baseline'),
    '体重与执行经历':('weight_history','eating_pattern','preferences','food_habits'),
}

# A formal weight-management plan needs enough information to choose safe,
# realistic actions.  Each tuple is an "any of" group; the entire legacy form
# is deliberately not required.  Explicitly unknown/skipped values do not
# become reassuring facts.
DECISION_REQUIREMENTS = {
    'personal_weight_plan': {
        '基础资料': (('age',), ('sex',), ('height_cm',), ('weight_kg',)),
        '安全边界': (('conditions',), ('medications',), ('allergies',), ('surgeries',)),
        '目标与困难': (('goals',), ('preferences', 'food_habits')),
        '代表性饮食': (('breakfast_habit',), ('lunch_habit',), ('dinner_habit',), ('snacks_drinks',)),
        '睡眠与作息': (('sleep_schedule',),),
        '活动与执行条件': (('activity_baseline', 'occupation'), ('available_time', 'work_schedule', 'food_habits')),
        '变化或执行经历': (('weight_history', 'eating_pattern'),),
    },
}

UNKNOWN_VALUES = {'跳过', '暂不回答', '不方便回答', '不知道', '不清楚', '未知', '待了解', '待补充'}


def conversation_preference(text):
    """Explicit pacing wins over goal keywords and old interview state."""
    if re.search(r'先聊|聊聊|只想聊|随便聊|不做计划|不要计划|先不.{0,6}(?:计划|方案)|'
                 r'(?:别|不要|不用|不急|别急).{0,6}(?:安排|计划|方案|建档)|暂停建档|停止建档|'
                 r'先解释|只.{0,6}(?:知道|明白|理解|解释)|换个话题|像填表|像问卷|不要盘问|别盘问|'
                 r'查户口|已经说过|说过好几遍|(?:别|不要|不用).{0,8}(?:连续问|一直问|挨个问|重复问|问数字|问年龄|问身高|问体重)', text):
        return 'chat'
    return None


def explicit_assessment_request(text):
    return bool(re.search(r'完善档案|继续建档|先了解我|先了解情况|了解我的|继续评估|'
                         r'(?:制定|生成|做个|给我|帮我|安排|规划).{0,10}(?:计划|方案)|怎么吃怎么练', text))


def reply_focus(text, previous='discuss'):
    if re.search(r'换个话题|换一个话题|说点别的', text):
        return 'discuss'
    if re.search(r'为什么|(?:先|只|就).{0,10}(?:解释|知道|了解原因|明白原因)|别急着安排|'
                 r'(?:别|不要|不用).{0,5}(?:给|说).{0,5}(?:办法|建议|安排)', text):
        return 'explain'
    if re.search(r'(?:给|想听|说说).{0,8}(?:建议|办法)|怎么办|怎么做|怎么选|可以怎么', text):
        return 'discuss'
    return previous


CONVERSATION_INSTRUCTION='''你是知衡营养管理助手，正在与用户自然交谈。
先弄清本轮是在表达困难、问原因、纠正事实还是要建议，再直接回应。不要把表达减重愿望当作要求制定方案。
聊天与资料整理独立：缺少档案字段不构成追问理由；不要为了补档案问年龄、性别、身高、体重。只在回答当前问题确实需要时补问，相关条件可以合并，也可以不问。
话长短取决于问题：简短回答用几句；用户问原因、比较或抱怨没帮助时，把关键判断说清楚，可以用两三个短段落，不为凑短句省掉解释。不要复述整份档案，不反复说“我理解你”“情况已记录”，不套用安慰话术。承接本轮具体食物、时段、困难和上轮问题，区别“还不知道”和“已经说过”。
用户说像填表、不想被盘问时，当场调整节奏：先认真回答正在困扰他的那件事，解释你的判断和未知，能提供一个贴近条件的起步选择；不要把这种反馈也变成补档案问题。
reply_focus=explain时仅解释原因和不确定性，不给行动安排、饮食建议，不问执行条件；用户明确转而要建议才推进。
本轮更正先承认并按新事实理解；只要求更正时说清改正了什么即可。不要借更正继续分析食物好坏或追问。
不把餐次间隔、饥饿或食物名称推断成个人血糖、激素、代谢变化，不能编造消化所需小时数。用已知生活事实解释可能性，缺乏依据时直说不能确定。
用户说继续是沿当前话题继续，不是恢复问卷或授权方案。用户明确换话题就回应新话题，不把用户拉回上个问题。
reply里只写给用户的自然回应，不展示内部字段，不声称已经保存或已经生成方案。
在同一个JSON回复中整理本轮原话明确提供的本人事实；每条事实带本轮连续原文evidence，不把自己的回复、推断、假设、他人情况或目标数值当成当前事实，不把单次餐食写成长久习惯。没有新事实时留空数组，程序会核验并保存。
不诊断疾病、不改变处方，不编造营养数字或附近商家信息。只返回输出约定中的JSON，不返回代码块。'''


def decision_kind(text, *, has_plan=False):
    """Classify the current request without treating every health chat as intake."""
    value=str(text or '')
    if re.search(r'胸痛|呼吸困难|喘不过气|晕厥|昏厥|呕血|黑便|意识不清|剧烈疼痛',affirmative_health_text(value)):
        return 'high_risk'
    if has_plan and re.search(r'复盘|回顾|这几天|执行情况|没做到|没完成|很难坚持|调整计划|计划.{0,12}第[一二三四五六七八九十\d]+天|执行到第[一二三四五六七八九十\d]+天',value):
        return 'review'
    meal=bool(re.search(r'早餐|午餐|午饭|晚餐|晚饭|一餐|这餐|吃了|喝了',value)
              and not re.search(r'制定|生成|安排|规划|完整.*(?:计划|方案)',value))
    # A refusal of a questionnaire is not a request to start that questionnaire.
    goal_text=re.sub(r'(?:不要|别|不想|不用|不需要)[^，,。；;！？?\n]*(?:减肥|减脂|减重)[^，,。；;！？?\n]*','',value)
    weight=bool(re.search(r'减肥|减脂|减重|减肚|瘦肚|体重管理|减腹|瘦下来|瘦身|控制体重|瘦(?:一点|点|一些)',goal_text))
    information_question=bool(re.search(r'能不能|可以吗|是否|为什么|是什么|有影响吗|会不会|怎么选|区别|更合适|先从.{0,20}还是|先.{0,12}还是',value))
    plan_request=bool(re.search(r'制定|生成|安排|规划|一周|长期|完整|计划|方案|怎么吃怎么练|怎么开始|怎么办|怎么减|如何减|怎样减|咋减|指导|引导',value))
    personal_goal=bool(re.search(r'(?:我|想|希望|帮我).{0,20}(?:减肥|减脂|减重|瘦身|瘦一点|瘦点|瘦一些)|减到\s*\d+',goal_text))
    if (weight and plan_request or personal_goal) and not (information_question and not re.search(r'计划|方案|安排|规划',value)):
        return 'personal_weight_plan'
    if meal:return 'meal'
    return 'general'


def _known_any(profile, records, fields):
    for field in fields:
        if field == 'weight_kg':
            if intake.current_weight_records(records):
                return True
        elif intake.known(profile,field) and str(profile.get(field,'')).strip() not in UNKNOWN_VALUES:
            return True
    return False


def required_information(kind, profile, records, *, text=''):
    """Return only gaps that can change the current product decision."""
    if kind != 'personal_weight_plan':
        return {}
    requirements={label:list(groups) for label,groups in DECISION_REQUIREMENTS[kind].items()}
    # Surgery history is part of the baseline; silence never means "none".
    sex=str(profile.get('sex',''))
    if sex in ('女','女性') or re.search(r'孕|备孕|哺乳|产后',str(text)):
        requirements['安全边界'].append(('life_stage',))
    missing={}
    for label, groups in requirements.items():
        gaps=[list(group) for group in groups if not _known_any(profile,records,group)]
        if gaps:missing[label]=gaps
    return missing


def facts_digest(profile, records):
    """Stable digest of facts that affect a personalized weight plan."""
    relevant=set(field for groups in DECISION_REQUIREMENTS['personal_weight_plan'].values()
                 for group in groups for field in group) | {'life_stage','surgeries'}
    weights=[{'id':r.get('id'),'kg':r.get('value',{}).get('kg'),'observed_at':r.get('observed_at')}
             for r in records if r.get('type')=='weight' and r.get('memory_enabled') is not False and
             r.get('status') not in ('pending','inferred','retracted')]
    payload={'profile':{k:profile[k] for k in sorted(relevant) if k in profile},'weights':weights[-3:]}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def summary_text(profile, records, fields):
    """Build a concise, deterministic fact summary; never summarize guesses."""
    labels={'age':'年龄','sex':'生理性别','height_cm':'身高','goals':'目标','conditions':'健康状况',
            'medications':'用药','allergies':'过敏/忌口','surgeries':'手术/恢复','life_stage':'特殊阶段',
            'breakfast_habit':'早餐','lunch_habit':'午餐','dinner_habit':'晚餐','snacks_drinks':'加餐饮料',
            'activity_baseline':'活动','occupation':'日常活动','available_time':'可用时间','work_schedule':'作息条件','sleep_schedule':'睡眠作息',
            'food_habits':'饮食条件','preferences':'偏好/困难','weight_history':'体重经历','eating_pattern':'饥饱/进食感受'}
    parts=[]
    weights=intake.current_weight_records(records)
    if weights and isinstance(weights[-1]['value'].get('kg'),(int,float)):
        parts.append('最近体重：'+str(weights[-1]['value']['kg'])+'公斤')
    for field in fields:
        if intake.known(profile,field):
            value=profile[field]
            if isinstance(value,list):value='、'.join(map(str,value))
            parts.append(labels.get(field,field)+'：'+str(value))
    return '；'.join(parts)[:1400]


def confirmation_state(state, profile, records):
    item=(state or {}).get('summary_confirmation',{})
    digest=facts_digest(profile,records)
    status=item.get('status','not_requested')
    if item.get('digest') and item.get('digest') != digest:
        status='stale'
    return {**item,'status':status,'current_digest':digest,
            'confirmed':status=='confirmed' and item.get('digest')==digest}


def is_summary_confirmation(text):
    value=str(text or '').strip()
    if re.search(r'不对|有误|错了|更正|改成|不是|撤回',value):return False
    return bool(re.fullmatch(r'(?:确认|没问题|正确|对|是的|可以|就按这些|以上无误|情况属实)[。！!\s]*',value))


def next_question(missing):
    """Bundle related unknowns; never turn baseline discovery into a quiz."""
    if not missing:return None
    label=next(iter(missing))
    fields=missing[label][0]
    bundles={
        '基础资料':{'age':'年龄','sex':'性别','height_cm':'身高','weight_kg':'目前体重'},
        '安全边界':{'conditions':'确诊疾病或近期不适、医生限制','medications':'用药','allergies':'食物过敏','surgeries':'手术或伤病恢复','life_stage':'孕产或哺乳情况'},
    }
    if label in bundles:
        names=[bundles[label][key] for group in missing[label] for key in group if key in bundles[label]]
        if len(names)>1:
            return ('为了让建议适合你，可以一起说下'+ '、'.join(names)+
                    ('，以及希望减多少或最想改善什么' if label=='基础资料' and any('goals' in group for group in missing.get('目标与困难',[])) else '')+
                    '吗？用一段话回答就行，已经说过的不用重复，不方便的可以跳过。')
    questions={
        'age':'你今年多大？', 'sex':'你的生理性别是什么？不方便可以跳过。',
        'height_cm':'你的身高是多少厘米？', 'weight_kg':'最近一次体重是多少？请带公斤或斤。',
        'goals':'除了体重变化，你这次最想先改善什么、希望先解决哪个困难？',
        'conditions':'以前或目前有没有确诊疾病、近期不适，或医生给过的饮食/活动限制？没有也请明确说没有。',
        'medications':'目前有没有在用药物或保健品？没有也请明确说没有。',
        'allergies':'有没有食物过敏或必须避开的食物？没有也请明确说没有。',
        'life_stage':'目前是否处于备孕、孕期、产后或哺乳期？不适用可以直接说明。',
        'surgeries':'以前有没有做过手术或尚在恢复的伤病？如有，请说具体部位、目前的不适或医嘱；没有也请明确说没有。',
        **{field:intake.QUESTIONS[field] for field in (*intake.MEALS,'snacks_drinks','sleep_schedule')},
    }
    if len(fields)==1 and fields[0] in questions:return questions[fields[0]]
    if label=='目标与困难':return '为了让建议能执行，你最需要照顾的现实困难是什么，例如加班、外卖、预算或不喜欢的食物？'
    if label=='代表性饮食':return '先说一个最典型或最难处理的餐次：通常吃喝什么、份量大约多少？'
    if label=='活动与执行条件':return '平时主要久坐、走动还是体力活动？一天实际能留出多少时间调整饮食或活动？'
    if label=='变化或执行经历':return '最近几个月体重和饥饿感大致怎样变化？以前试过什么，哪里最难坚持？'
    return '还需要补充一项会影响方案的信息：'+label+'。'


def readiness(profile,records, *, text='', state=None, kind='personal_weight_plan', require_summary=False):
    missing=required_information(kind,profile,records,text=text)
    confirmation=confirmation_state(state,profile,records)
    information_ready=not missing
    ready=information_ready and (confirmation['confirmed'] if require_summary else True)
    return {'ready':ready,'information_ready':information_ready,'missing':missing,
            'summary_confirmation':confirmation,
            'stage':'可讨论个体方案' if ready else '摘要核对' if information_ready else '了解与评估',
            'metabolism':'不能根据体型、照片或一句话判断代谢快慢。结合体重变化、作息、饮食、活动、既往诊断及已有检查了解；不要强迫用户为建档额外检查。'}


def is_weight_plan(text,plan):
    return bool(re.search('减肥|减脂|减重|减肚|瘦肚|体重管理|减腹|瘦下来|瘦身|控制体重',str(text)+' '+str(plan.get('goal',''))+' '+str(plan.get('title',''))))


def exertion_symptom_reported(text, profile):
    """Detect the user's own reported activity-triggered dizziness or breathing trouble."""
    fields=('conditions','activity_baseline','work_schedule','dinner_habit','breakfast_habit','snacks_drinks')
    known='；'.join('；'.join(map(str,profile[key])) if isinstance(profile.get(key),list)
                   else str(profile.get(key,'')) for key in fields)
    context=affirmative_health_text(str(text)+'；'+known)
    return bool(re.search(r'(?:跑|运动|快走|爬楼|冲刺).{0,20}(?:头晕|晕|喘|气短)|(?:头晕|晕|喘|气短).{0,20}(?:跑|运动|快走|爬楼|冲刺)',context))


def affirmative_health_text(text):
    """Remove explicit denials before detecting a newly reported concern."""
    terms='喘不过气|呼吸困难|无法呼吸|喘得厉害|头晕|晕倒|晕厥|昏厥|气短|心跳快|心悸|胸痛|哮喘|高血压|糖尿病|鼻炎|喘|晕|手术史|手术|切除|术后|确诊疾病|确诊|用药|服药|吃药'
    term='(?:'+terms+r')'
    value=re.sub(term+r'\s*(?:也|都)?(?:没有(?:出现|发生)?|从未出现|未出现|没发生)(?:过)?'
                 r'(?=$|[，,。；;、\n]|但|不过|只是)', '',str(text or ''))
    return re.sub(r'(?:从来(?:没有|没)|没有|从未|不曾|不会|没|无|未|不)'
                  r'(?:(?:出现|发生|做过|做|明显|过|再|在|运动时|活动时|跑步时|快走时|爬楼时))*'
                  +term+r'(?:(?:或|和|、|及|以及)'+term+r')*','',value)


def displayed_question_text(reply, decision=None):
    """A clarify label is not itself a question to the user."""
    questions=re.findall(r'[^。！？!?\n]*[？?]',str(reply or ''))
    if questions:return '\n'.join(question.strip() for question in questions)
    requests=[part.strip() for part in re.split(r'[。！!\n]',str(reply or ''))
              if re.search(r'请.{0,12}(?:告诉|说说|描述|提供|回复)|(?:能否|方便|可以).{0,8}(?:说说|告诉|描述)|'
                           r'说说.{0,15}(?:情况|困难|什么|怎样)|你.{0,20}(?:多少|多大|几岁)|请核对|请回复|请说',part)]
    return ' '.join(requests)


def followup_question(text, profile, missing):
    """A current difficulty can be understood before demographic collection."""
    value=str(text or '')
    health=affirmative_health_text(value)
    if re.search('头晕|晕倒|气短|喘|心跳快|胸痛|心悸|手术|切除|用药|服药|吃药',health):
        return exertion_followup_question(value) or pivot_question(value,profile,missing)
    if re.search(r'(?:餐|饭|吃).{0,8}(?:不舒服|反酸|胀|疼|恶心|腹泻)',value):
        return '餐后具体是哪里不舒服、什么感觉，通常吃完多久出现？'
    if re.search(r'(?:午餐|午饭|晚餐|晚饭).{0,10}(?:点|[一二三四五六七八九十\d])',value):
        return '按这个进食间隔，你到晚饭前通常有多饿，中间有没有吃喝其他东西？'
    if re.search('饿|吃多|吃撑|控制不住|节食|反弹',value):
        if not intake.known(profile,'dinner_habit'):
            return '最难控制的那顿通常吃什么，开始吃之前是饿得很厉害，还是想放松一下？'
        if not intake.known(profile,'meal_schedule'):
            return '容易吃多的那顿，距离上一餐通常隔多久，中间有没有吃喝一点东西？'
    if re.search('下班|晚班|通勤|到家',value):
        if not intake.known(profile,'dinner_habit'):
            return '下班后的晚餐一般怎么解决，是到家再点外卖，还是路上就能吃上？'
    if re.search(r'外卖|食堂|没时间做饭|不能做饭',value):
        return '你平常最常点哪两样，菜单里还有哪些你愿意吃的配菜？'
    if re.search('早餐|午餐|晚餐|外卖|咖啡|奶茶|饮料',value) and not ('安全边界' in missing):
        if '睡眠与作息' in missing:return '你通常几点睡、几点起，白天精神怎么样？'
        if '活动与执行条件' in missing:return next_question({'活动与执行条件':missing['活动与执行条件']})
    return next_question(missing)


def add_followup(reply, text, profile, missing, *, replace_question=False):
    """Repair the conversational step without erasing a safe model response."""
    question=followup_question(text,profile,missing)
    if not question:return str(reply or '')
    response=str(reply or '').strip()
    if replace_question:
        response=''.join(part for part in re.split(r'(?<=[。！？!?])|\n+',response)
                         if part.strip() and not re.search(r'[？?]|回到(?:刚才|之前)的问题',part)).strip()
    if not response or re.fullmatch(r'(?:收到|好的|明白|可以|我们继续|请先回答)[。！!：:\s]*',response):
        return assessment_reply(text,profile,missing)
    return response+'\n\n'+question


def exertion_followup_question(text):
    """Prioritize the user's new exertional symptoms over routine intake gaps."""
    if not exertion_symptom_reported(text,{}):return None
    if re.search(r'胸痛|心悸|晕倒|昏厥|喘不过气',affirmative_health_text(text)):
        return '这种不适是在什么活动后出现、停下后多久缓解？'
    return '当时有没有胸痛、心悸、几乎晕倒或明显喘不过气？'


def pivot_question(text, profile, missing):
    """Follow a newly volunteered concern instead of repeating an old question."""
    value=affirmative_health_text(text)
    if re.search(r'胸痛|心悸|心跳快|晕倒|头晕|气短|喘',value):
        if re.search(r'心悸|心跳快',value):
            return '心跳快是和头晕一起出现，还是休息时也会有？'
        return '这种不适是在活动时还是休息时出现，停下来通常多久能缓解？'
    if re.search(r'手术|切除|确诊|高血压|糖尿病|哮喘|鼻炎|用药|服药|吃药',value):
        if not re.search(r'稳定|医嘱|医生.{0,8}限制',value):
            return '这些情况目前稳定吗？医生有没有给过饮食或活动方面的限制？'
    if re.search(r'下班|晚班|通勤|到家',value):
        return '按你的下班时间，晚餐通常是在回家路上解决，还是到家后才吃？平常能买到什么？'
    if re.search(r'咖啡|奶茶|饮料',value) and not intake.known(profile,'snacks_drinks'):
        return '平常这类饮料一天大概喝多少，包装上的糖和能量信息你方便看一下吗？'
    if re.search(r'早餐|午餐|晚餐|外卖',value):
        return '这几餐里，哪一餐最受时间或外卖选择限制，通常会吃到多饱？'
    if re.search(r'睡觉|睡眠|久坐|运动',value) and not intake.known(profile,'activity_baseline'):
        return '你平常一天主要是坐着还是走动，活动时有没有让你不舒服的情况？'
    return next_question(missing)


def pivot_reflection(text, profile):
    value=affirmative_health_text(text)
    if re.search(r'胸痛|心悸|心跳快|晕倒|头晕|气短|喘',value):
        return assessment_starter(value,profile) if exertion_symptom_reported(value,{}) else '你补充了活动时不适的表现；不把运动当成当前减重任务，相关症状仍需要线下评估。'
    if re.search(r'手术|切除|确诊|高血压|糖尿病|哮喘|鼻炎|用药|服药|吃药',value):
        return '你提到的健康经历和用药需要分开考虑，不能只凭身高体重套一套减重方法。'
    if re.search(r'下班|晚班|通勤|到家',value):
        return '你说下班晚、到家时饿，先把下班和实际吃上晚餐的时间分开看，不能把建议建立在标准作息上。'
    if exertion_symptom_reported(value,{}):return assessment_starter(value,profile)
    if re.search(r'早餐|午餐|晚餐|外卖|咖啡|饮料',value):
        return '这些是你平常真实的吃喝方式，接下来可以按份量和可选食物讨论，不急着套标准食谱。'
    return '你补充的新情况我会放进后续判断，先接着你刚说的这一点聊。'


def assessment_starter(text, profile):
    """One bounded, reversible observation when model prose fails readiness QA."""
    fields=('conditions','activity_baseline','work_schedule','dinner_habit','breakfast_habit','snacks_drinks')
    known=' '.join(str(profile.get(key,'')) for key in fields)
    context=str(text)+' '+known
    if exertion_symptom_reported(text,{}) or (re.search(r'跑|运动|爬楼|活动',str(text)) and exertion_symptom_reported('',profile)):
        return '你提到活动时会晕或喘，先停下会诱发不适的动作，暂时不把跑步当减重任务；若反复出现，请线下评估。'
    if re.search(r'下班晚|晚班|加班|通勤|九点到家|8点到家|9点到家',context) and re.search(r'外卖|现成|晚餐|晚饭|盖饭|卷饼',context):
        return '你下班晚、晚饭常靠现成食物，可以先比较两种容易买到的晚饭，留意哪种吃后更舒服、也更容易坚持。'
    if re.search(r'咖啡|奶茶|饮料',context):
        return '先留意平常饮料喝几瓶，以及包装背面的能量、糖和咖啡因信息；只看正面的“0脂”还不能估算整瓶热量。'
    return '可以先留意平时最常吃的一餐及大致份量，找出真正可调整的一处，不必立刻改变整天饮食。'


def assessment_reply(text, profile, missing):
    """Short, contextual recovery when the model returns an unsafe questionnaire."""
    question=followup_question(text,profile,missing)
    if not question:return '这部分情况我记下了。我们可以继续从你最想解决的困难谈起。'
    if exertion_followup_question(text):
        return assessment_starter(text,profile)+'\n\n'+question
    first=next(iter(missing),'')
    value=str(text or '')
    if re.search(r'外卖|没时间做饭|不能做饭',value):
        lead='按你现在的条件，可以先在常点的饭或面里比较实际配菜，看看有没有你愿意吃的蛋、肉或豆制品和蔬菜，不必要求自己改成做饭。'
        return lead+'\n\n'+question
    if re.search(r'早餐|午餐|晚餐|外卖|咖啡|饮料|下班|晚班|通勤|到家',value):
        return pivot_reflection(value,profile)+'\n\n'+question
    if first=='基础资料':
        weights=re.findall(r'(?<!\d)(\d+(?:\.\d+)?)\s*斤',value)
        lead=('你希望从'+weights[0]+'斤逐步到'+weights[1]+'斤，这是一个需要按实际情况评估的长期目标。'
              if len(weights)>=2 else '你的目标我记下了，先把几个基础信息弄清楚，再看哪些调整真正适合你。')
    elif first=='安全边界':
        if re.search(r'手术|切除|用药|药|哮喘|鼻炎|高血压|糖尿病',affirmative_health_text(value)):
            lead='你提到的健康经历会影响饮食和活动的选择，我会把它们分开考虑。'
        else:lead='年龄、身高和体重已记下；在给个人安排前，还要先了解会影响安全的健康情况。'
    elif first=='代表性饮食':
        lead='接下来按你平常真正吃得到的食物讨论，先了解一个典型工作日就够。'
    elif first=='活动与执行条件' and re.search(r'下班|通勤|加班|晚班',value):
        lead='你的时间安排决定什么建议能坚持，暂时不按标准作息假设。'
    else:lead='这部分信息已记下，我再了解一个会改变下一步建议的情况。'
    return lead+'\n\n'+question


def question_fields(text):
    """Semantic field inventory, separate from attribution of bare short answers."""
    return {key for key,pattern in intake.QUESTION_TERMS.items() if re.search(pattern,str(text))}


def remove_answered_questions(reply, profile, records, declined=()):
    """Drop fully answered questions after this turn's facts have been extracted.

    Keep mixed known/unknown questions: removing them could erase a necessary
    clarification. Do not use this inventory to assign a bare number to a field.
    """
    parts=re.split(r'(?<=[。！？?])|(?<=\n)',str(reply))
    kept=[]
    dropped_weight_question=False
    for part in parts:
        if dropped_weight_question and re.fullmatch(r'\s*请带(?:上)?(?:公斤或斤|单位)[。！!\s]*',part):
            dropped_weight_question=False
            continue
        dropped_weight_question=False
        fields=question_fields(part)
        # Rechecks and genuine conflict resolution must remain visible.
        recheck=re.search(r'更正|冲突|变化|仍然|还是|最近.*(?:变|测)|现在.*(?:变|测)',part)
        if (not recheck and fields and displayed_question_text(part) and
                all(key in declined or _known_any(profile,records,[key]) for key in fields)):
            dropped_weight_question='weight_kg' in fields
            continue
        basics={'age','sex','height_cm','weight_kg'}
        if not recheck and fields and fields<=basics and displayed_question_text(part):
            unknown=[key for key in ('age','sex','height_cm','weight_kg') if key in fields and
                     key not in declined and not _known_any(profile,records,[key])]
            if unknown and len(unknown)<len(fields):
                kept.append(next_question({'基础资料':[[key] for key in unknown]}))
                continue
        kept.append(part)
    return ''.join(kept).strip()


AGENT_INSTRUCTION='''你是知衡，持续了解用户的个人健康助手，结合营养咨询、运动指导和基础健康信息解读帮助用户做决定。
先解决用户当前请求，再决定是否需要提问。能回答就直接回答，不必以问题结尾；绝不为补档案强行推进访谈。
初次只说“我要减肥”时，说明先了解基础，一次合并询问尚未知的年龄、性别、身高、目前体重、目标；允许整段自由回答。下一轮只补会影响建议的空缺，健康限制可合并询问，不能年龄一轮、性别一轮地盘问。用户已经描述具体困难时先回应困难。
用户一次给了多项资料，要全部识别，结合profile、recent_records、本轮原话和历史回答使用；不要因为上次只问了年龄就忽略其他答案。不重复索要已知或拒绝的信息；确有矛盾才明确指出两种说法，让用户更正。
缺少正式方案资料不妨碍给有条件的饮食选择、份量建议、运动起步方向和理由；只让缺失资料限制依赖它的精确目标或强度处方，不要把整个聊天变成等资料齐全。
食物照片默认是请你分析和帮助决定怎么吃：先解释可见食物的营养特点、建议吃的份量/搭配、若吃完整份需要考虑什么及估计不确定性。不要默认追问“吃了吗、吃了多少”；只有用户主动要求记录实际摄入时才核实记录所需信息。未记账不妨碍分析，已吃也仍可分析；不责备，不建议补偿性节食。
用户要运动方案时围绕目标、当前能力、伤病/活动不适、器械场地和时间了解，不套用减重饮食问卷。报告解读要区分可读指标、可能意义、不能确定的原因、合理下一步；如考虑检查，说清为什么、解决什么疑问、是否需要就医决定，不开无差别检查清单。不冒充医生，不诊断或调整处方，紧急症状优先就医。
回复详略由问题决定，不设180字上限；需要比较、份量选择或解释时可以分段和列简短要点，不能只复述用户加一个问题。资料和计划以程序实际保存结果为准。'''


INSTRUCTION='''你是知衡健康管理助手，不冒充任何真人营养师或医疗机构。一般科普或一餐分析可直接回答，不要求先建档。
对个人减重/减肚子方案，先解释不能承诺局部减脂，再逐步了解基础、目标、健康与用药限制、典型三餐和饮料、睡眠工作活动、体重变化及执行条件。参考plan_readiness，合并询问同一主题下尚未了解且影响下一步的条件，避免逐个字段盘问。不重复用户已给目标。未知可跳过，但未知不能算已完成评估。
在plan_readiness.ready为false时，plan必须null；但要像真正的咨询一样先回应本轮困扰，基于已确认的生活条件给一项可逆、低风险、不带热量或强度处方的起步选择，必要时合并补问相关的缺失条件。不要连续几轮只复读建档问卷，也不要把“先记录”当成唯一帮助。不生成减重时间表、食谱或强度任务，不因用户催促直接跳过安全评估。资料充分后先用简短摘要请用户纠正，再讨论可执行方案。不要把“代谢慢”当诊断，也不要建议无必要的检查。运动时曾出现喘、晕等不适，应先提醒停止诱发动作并评估，不布置跑步、爬楼或冲刺任务；疾病、用药或高风险情况提醒合适的线下专业评估，不自行调整药物。图片若是以前吃的或多人分食，不能记成今天本人完整摄入。'''

PLAN_INSTRUCTION='''你是知衡减重咨询助手。用户已请求个人减重方案，必要资料和事实摘要已确认，本轮必须推进到可保存的一周行动方案。用户回复“确认”是在确认资料并让你继续制定方案，不能只回复确认或泛泛建议，不能再问是否需要计划。profile和recent_records是已核实事实，不能再反复索要已有资料。
结合目标、健康限制、平常三餐和饮料、睡眠工作安排、活动与执行困难，优先选1至3个最容易实行的改变，解释为什么先改它们，明确怎么做、最低版本、做不到时的一种替代和一周复盘反馈。不要一次列十条规定，不把目标体重当成当前体重，不承诺多久减几公斤。已有计划确需调整时结合current_plan，不声称安排已经保存，程序负责校验和保存。
不诊断、不改变用药。疾病、手术恢复、运动中不适等限制须遵守；运动中晕或喘应停止诱发动作并寻求线下评估，不安排跑步或冲刺。只能给温和的行为建议，不提供未经来源和计算核实的热量、蛋白质、碳水、脂肪数字，不从照片或碗数推算实际摄入克数，不强制每餐减半，不建议节食补偿。按用户原有生活节点安排，不自编钟点。具体菜单、外卖店铺与可得性未知时请用户在自己的平台核对，不编造店铺、价格或库存。没有发生的行动不提取成记录。
用户指定明天开始时按明天制定；默认考虑今天剩余机会，今天已吃过的餐不重复安排。必要时只核对今天已吃哪些餐和下一餐实际可选，然后继续制定，不另开问卷。完整JSON含reply,profile_changes,record_events,feedback,plan,decision,page_changes,food_decisions；plan非空时含完整items对象数组，decision.action=update。只返回合法JSON。'''

INTERVIEW_INSTRUCTION='''你是知衡的减重咨询助手，像一个有判断力的对话伙伴带着用户想清楚问题。用户表达“我想减肥”就是开始了解的请求。当前不是生成计划的轮次：正式方案还缺资料，plan必须为null；这不妨碍直接解释当前困难、比较真实选择、给一个温和可撤回的小尝试。不要写整套方案、日程表、热量目标、运动次数或饮水升数。
每轮先判断用户是回答上轮、补充困难、问原因、纠正、想要办法还是质疑你的帮助；正文先处理这个意图，把本轮最关键的具体信息用到判断里，再自然推进。不要只把事实重复一遍就问下一项字段：若用户已有具体困难，说清一种有依据的可能性或能先尝试的改变，说明尚不知道什么，必要时补问会改变判断的条件；不强求每轮追问。用户专门问解释或更正时可先完整回答，不必每轮硬塞问题。通常两三个短段落即可，不为限制成2句省掉关键解释，不写机械标题。
已保存的profile和recent_records是已知事实，不能重复询问；missing只限制正式方案，不是提问顺序。起步只有“我想减肥”时先说明用途，把尚未知的年龄、性别、身高、体重和目标合在一次自然邀请中，允许整段回答；不能逐项盘问。用户一上来讲下班饿、外卖或反弹，就沿具体困难追问白天进食、晚餐时机与现实选择，基础数字可稍后解释用途再了解。出现真实疾病、手术、用药或活动不适时优先核对安全；明确“没有”的项不要当作有症状。一次回答可覆盖多个字段。不要强迫用户逐格回答，不用“回到刚才的问题”拉回问卷。不要凭久坐断言变胖原因，不凭入睡钟点判断睡眠不足，没了解份量不能断言主食过多或蛋白质不足。用户问原因先解释，能帮着做选择时要明确比较理由，不只说“先记录、以后再看”。
例：用户说“白天忍着，下班后控制不住吃”，可以解释白天吃得少、晚餐拖后可能让晚上更难掌握进食，需了解实际餐次后再判断；不要诊断低血糖或指责意志力。可以先选择不跳餐、不靠第二天少吃补偿这一类温和起点，问白天通常吃多少、到晚餐隔多久。用户说“还是得点外卖”，就把建议改成实际外卖选择，不能继续推荐做饭。用户说“继续”时沿当前困难接着帮他判断，避免连续几轮只有“记下了+下一问”。
运动中出现头晕、明显气短等不适，应提醒停止诱发动作并寻求线下评估，不布置跑步或冲刺；不诊断病因，不调整药物。不要把腹部感觉或体型直接诊断为“代谢慢”。照片、多人分食或历史餐食不能当成今天本人完整摄入。口语自然，不用固定开场或程序内部术语，不声称尚未保存的事实已经保存。
只提取用户本次明确说出的事实。profile_changes中每项必须有field、value及evidence，evidence必须是本次用户原话中的连续片段；疾病、手术、药物、饮食和作息分字段，不把整段话都塞进一个字段。没有明确证据就留空，不推断“没有病史/过敏”。只返回合法JSON。'''
