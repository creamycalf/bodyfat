"""Small synthetic P0 conversation set against the configured real model."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import product
import server
import storage


SCENARIOS = [
    ('health_history', [
        '我想减肥，请先了解我的整体情况。',
        '男，28岁，身高172厘米，现在200斤，想减到150斤，平常久坐，不吃辣。',
        '以前和目前没有确诊疾病，也没有近期不适或医生限制。',
        '目前没有用药，也不吃保健品。',
        '没有食物过敏。',
        '没有做过手术，也没有恢复中的伤病。',
    ], False),
    ('weight_goal', [
        '我目前体重200斤，想减肥减到150斤。你先告诉我现在应该怎么开始。',
        '172厘米。',
    ], False),
    ('late_meal', [
        '现在是晚上九点，我已经吃了早餐和午餐，想点外卖晚餐。手头没有菜单，怎么选比较实际？',
    ], False),
    ('known_breakfast', [
        '我今天早上吃了两个鸡蛋和一杯牛奶。',
        '我在减脂，现在午餐怎么选？',
    ], False),
    ('shift_and_dislike', [
        '我上夜班，凌晨一点下班，现在想吃点东西，不想做鱼。没有店铺菜单，给我可搜索的方向。',
    ], False),
    ('plan_day_three', [
        '计划已经到第三天了。昨晚加班没散步，今天晚餐只能点外卖，我不想做鱼。先说今天怎么办，别从明天重开。',
    ], True),
]


for name, turns, seed_plan in SCENARIOS:
    if len(sys.argv)>1 and name not in sys.argv[1:]:
        continue
    with tempfile.TemporaryDirectory(prefix='zhiheng-p0-live-') as folder:
        data = Path(folder) / 'data'
        paths = {'DATA': data, 'MEDIA_DIR': data / 'media'}
        paths.update({key: data / filename for key, filename in {
            'PROFILE': 'profile.json', 'RECORDS': 'records.json',
            'CONVERSATIONS': 'conversations.json', 'MEDIA': 'media.json',
            'METADATA': 'metadata.json',
        }.items()})
        with patch.multiple(server, **paths):
            storage.initialize(data)
            if seed_plan:
                workspace = product.workspace(server)
                plan = product.normalize_plan({
                    'title': '生活节奏试行', 'goal': '试行可持续的小行动',
                    'items': [{'title': '晚饭后舒适散步', 'when': '每天下班后',
                               'detail': '身体舒适时散步，遇到加班可跳过并反馈。',
                               'minimum': '有空时短暂走动',
                               'feedback': '记录是否可行与困难'}],
                }, '今天', workspace, None)
                plan['status'] = 'active'
                plan['start_date'] = (product.datetime.now().date() - product.timedelta(days=2)).isoformat()
                workspace['plans'].append(plan)
                server.save_json(data / 'workspace.json', workspace)
            for index, utterance in enumerate(turns, 1):
                result = product.chat(server, {
                    'conversation_id': name,
                    'client_message_id': f'{name}-{index}',
                    'text': utterance,
                })
                print(json.dumps({
                    'scenario': name, 'turn': index,
                    'status': result.get('ai_status'),
                    'error': result.get('ai_error'),
                    'plan_saved': bool(result.get('plan')),
                    'reply': result.get('reply'),
                }, ensure_ascii=False), flush=True)
