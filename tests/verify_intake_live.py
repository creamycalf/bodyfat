"""Real model interview in a fresh synthetic workspace, never formal health data."""
import json, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server, storage, product

out=Path('tmp')/('intake-live-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
server.DATA=out/'data';server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA)
server.CONFIG['ai']['base_url']='http://47.110.38.211:8080/v1'
answers={'age':'35','sex':'男','height_cm':'175','weight_kg':'80公斤',
 'goals':'希望三个月改善体重和体力，以前节食后反弹，不追求快速减重',
 'conditions':'没有确诊疾病，也没有身体不适','medications':'没有用药或保健品',
 'allergies':'对花生过敏','surgeries':'没有手术或伤病',
 'life_stage':'不适用','sleep_schedule':'凌晨2点睡，上午10点起床，休息日也这样',
 'work_schedule':'中午12点上班，晚上20点下班，单程通勤半小时',
 'meal_schedule':'起床吃早餐，16点午餐，21点晚餐，主要食堂和外卖',
 'food_habits':'早餐两个鸡蛋一杯牛奶，午餐一碗米饭配肉菜，晚餐面条，不喝甜饮，每天预算50元',
 'breakfast_habit':'早餐一般两个鸡蛋，一杯250毫升纯牛奶，一片全麦面包',
 'lunch_habit':'午餐食堂一碗米饭，一掌鸡肉，两拳蔬菜，喝水',
 'dinner_habit':'晚餐外卖一碗牛肉面，加一份青菜，不喝甜饮',
 'snacks_drinks':'每天下午一杯不加糖咖啡，偶尔一个苹果，不喝酒，没有夜宵',
 'eating_pattern':'午餐前会有点饿，饭后基本舒服，没有吃撑或刻意少吃下一餐',
 'weight_history':'近三个月体重稳定，以前节食很饿，停下来会反弹',
 'occupation':'办公室工作，主要久坐，目前很少运动',
 'activity_baseline':'白天主要久坐，目前没有固定运动，每周偶尔散步一次大约20分钟',
 'available_time':'下班到家后可以散步20分钟，没有场地限制',
 'preferences':'喜欢清淡家常菜，不喜欢跑步，最难的是下班后没力气做饭'}
results=[]
def chat(text):
    n=len(results)+1
    print('START round',n,flush=True)
    r=product.chat(server,{'text':text,'conversation_id':'intake-live-synthetic','client_message_id':f'intake-live-{n:03}'})
    results.append({'input':text,'result':r})
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    asked=product.workspace(server)['sessions']['intake-live-synthetic'].get('asked_field')
    print(json.dumps({'round':n,'status':r.get('ai_status'),'error':r.get('ai_error'),'next':asked,'plan':bool(r.get('plan'))}),flush=True)
    assert r.get('ai_status')=='connected' and not r.get('ai_error'),r.get('ai_error')
    return r,asked
r,asked=chat('我想减脂，请先了解我的情况，再帮我制定计划。')
assert r['plan'] is None
for _ in range(30):
    if r.get('plan'):break
    assert asked is None or asked in answers,asked
    r,asked=chat(answers[asked] if asked else '请根据刚才已完成的建档，生成明天开始的具体计划。')
else:raise AssertionError('Interview did not converge')
snap=product.snapshot(server)
assert snap['profile']['age']==35 and snap['profile']['sex']=='男'
assert snap['profile']['height_cm']==175
assert any(x['type']=='weight' and x['value']['kg']==80 for x in snap['records'])
assert '花生' in str(snap['profile']['allergies'])
assert r['plan']['start_date']>product.today()
assert not asked
assert all(field in snap['profile'] for field in ('breakfast_habit','lunch_habit','dinner_habit','snacks_drinks','eating_pattern','weight_history'))
assert r['plan']['start_guide']['steps']
(out/'state.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS live interview:',out,flush=True)
