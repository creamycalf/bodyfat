"""Compare available models on the same fictional first-use conversation.

No actual user profile, photos, or local .data records enter this test.
"""
import copy
import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch

import product
import server
import storage


TURNS = [
    '我想减重，先帮我弄清楚怎么开始。',
    '女，42岁，身高165厘米，体重84公斤，目标是72公斤，工作日经常坐着。',
    '有膝盖旧伤，最近快走时会头晕，休息后缓解；晚班到家九点，只能买现成晚饭。过去没有其他确诊病，正在服用降压药。',
]
MODELS = ('claude-opus-4-8', 'claude-opus-5')


for model in (tuple(sys.argv[1:]) or MODELS):
    with tempfile.TemporaryDirectory(prefix='zhiheng-model-qa-') as folder:
        data = Path(folder) / 'data'
        paths = {'DATA': data, 'MEDIA_DIR': data / 'media'}
        paths.update({key: data / filename for key, filename in {
            'PROFILE': 'profile.json', 'RECORDS': 'records.json',
            'CONVERSATIONS': 'conversations.json', 'MEDIA': 'media.json',
            'METADATA': 'metadata.json',
        }.items()})
        config=copy.deepcopy(server.CONFIG)
        config['ai']['model']=model
        actual_call=server.call_ai
        def inspect_call(*args,**kwargs):
            raw=actual_call(*args,**kwargs)
            try:parsed=server.parse_json(raw)
            except Exception:parsed=None
            if isinstance(parsed,dict):
                print(json.dumps({'model':model,'raw_reply':parsed.get('reply'),
                                  'raw_profile_changes':parsed.get('profile_changes')},ensure_ascii=False),flush=True)
            return raw
        with patch.multiple(server, **paths), patch.object(server,'CONFIG',config), patch.object(server,'call_ai',inspect_call):
            storage.initialize(data)
            for index, utterance in enumerate(TURNS, 1):
                result=product.chat(server, {
                    'conversation_id': 'fictional-first-use',
                    'client_message_id': f'{model}-{index}',
                    'text': utterance,
                })
                print(json.dumps({
                    'model': model, 'turn': index,
                    'status': result.get('ai_status'),
                    'error': result.get('ai_error'),
                    'plan_saved': bool(result.get('plan')),
                    'reply': result.get('reply'),
                    'saved_profile_fields': sorted(server.load_json(server.PROFILE,{})),
                }, ensure_ascii=False), flush=True)
