"""Real model recipe checks with synthetic data; preserve each run for review."""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import product
import server
import storage

sys.stdout.reconfigure(errors='backslashreplace')

out = Path('tmp') / ('recipe-live-' + time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True, exist_ok=False)
server.DATA = out / 'data'
server.MEDIA_DIR = server.DATA / 'media'
for key in ('PROFILE', 'RECORDS', 'CONVERSATIONS', 'MEDIA', 'METADATA'):
    setattr(server, key, server.DATA / (key.lower() + '.json'))
storage.initialize(server.DATA)
server.save_json(server.PROFILE, {'nickname': '虚构食谱测试用户', 'allergies': ['花生', '虾'], 'preferences': '家常菜'})
w = product.workspace(server)
plan = product.normalize_plan({'title': '虚构午餐计划', 'goal': '规律饮食', 'items': [{'title': '午餐', 'when': '每天'}]}, '今天', w, None)
plan['status'] = 'active'
w['plans'] = [plan]
server.save_json(server.DATA / 'workspace.json', w)
checks = []
results = []

def dump(name, value):
    (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def check(name, passed):
    checks.append({'name': name, 'passed': bool(passed)})
    dump('checks.json', checks)

real_call = server.call_ai
def capture(*args, **kwargs):
    raw = real_call(*args, **kwargs)
    dump(f'raw-{len(results)+1}.json', {'raw': raw, 'meta': server.ai_meta()})
    return raw
server.call_ai = capture

def chat(label, text, mode):
    before = product.snapshot(server)
    start = time.monotonic()
    print('START ' + label, flush=True)
    r = product.chat(server, {'text': text, 'conversation_id': 'synthetic-recipe', 'client_message_id': 'recipe-' + label,
        'plan_help': {'id': plan['id'], 'version': plan['version'], 'item_id': plan['items'][0]['id'], 'mode': mode}})
    after = product.snapshot(server)
    results.append({'label': label, 'seconds': round(time.monotonic()-start, 1), 'input': text, 'result': r})
    dump('results.json', results)
    check(label + ': connected', r.get('ai_status') == 'connected')
    check(label + ': complete draft', bool(r.get('recipe_draft')))
    option=r.get('recipe_draft',{}).get('option',{})
    check(label + ': portion explained', bool(option.get('servings')))
    if mode=='cook':check(label + ': raw or cooked weight explained', bool(option.get('weight_basis')))
    check(label + ': read only', all(before[k] == after[k] for k in ('profile', 'plans', 'records', 'feedback')))
    print(json.dumps({'label': label, 'status': r.get('ai_status'), 'draft': r.get('recipe_draft', {}).get('option'), 'error': r.get('ai_error')}, ensure_ascii=False), flush=True)
    return r

def save(r):
    before = product.snapshot(server)
    product.action(server, {'action': 'recipe_save', 'id': r['client_message_id']})
    after = product.snapshot(server)
    check(r['client_message_id'] + ': save preserves health and task identity',
          all(before[k] == after[k] for k in ('profile', 'records', 'feedback')) and
          [(t['task_id'],t['status']) for t in before['tasks']] == [(t['task_id'],t['status']) for t in after['tasks']])
    draft = r['recipe_draft']
    check(r['client_message_id'] + ': saved option matches draft', after['plans'][0]['items'][0]['meal_options'][draft['mode']] == draft['option'])
    product.action(server, {'action': 'recipe_save', 'id': r['client_message_id']})
    check(r['client_message_id'] + ': duplicate save', after == product.snapshot(server))

first = chat('cook-original', '以下为虚构软件测试。请给这项午餐鸡肉配米饭蔬菜的详细做法，写清食材用量和步骤，遵守档案过敏限制，仅查看不要保存。', 'cook')
second = chat('cook-replacement', '这次只替换做法中的鸡肉，改用豆腐，不要鸡肉；请给完整食材用量和步骤，继续遵守过敏限制，不修改档案或计划。', 'cook')
if first.get('recipe_draft') and second.get('recipe_draft'):
    save(second)
    try:
        product.action(server, {'action': 'recipe_save', 'id': first['client_message_id']})
        rejected = False
    except product.ProductError:
        rejected = True
    check('older draft conflict rejected', rejected)
third = chat('takeout', '今天想点外卖。请给符合档案过敏限制的具体搭配、可复制搜索词和点单备注，提醒向商家核实过敏原与交叉接触；不要编造商家。', 'takeout')
if third.get('recipe_draft'):
    original_profile = server.load_json(server.PROFILE, {})
    server.save_json(server.PROFILE, {**original_profile, 'allergies': ['花生', '虾', '大豆']})
    try:
        product.action(server, {'action': 'recipe_save', 'id': third['client_message_id']})
        rejected = False
    except product.ProductError:
        rejected = True
    check('profile change rejects draft', rejected)
    server.save_json(server.PROFILE, original_profile)
    cook_before = copy.deepcopy(product.snapshot(server)['plans'][0]['items'][0]['meal_options'].get('cook'))
    save(third)
    check('takeout preserves cook', product.snapshot(server)['plans'][0]['items'][0]['meal_options'].get('cook') == cook_before)
dump('final-state.json', product.snapshot(server))
print('OUTPUT ' + str(out.resolve()), flush=True)
print(json.dumps(checks, ensure_ascii=False), flush=True)
sys.exit(0 if all(x['passed'] for x in checks) else 1)
