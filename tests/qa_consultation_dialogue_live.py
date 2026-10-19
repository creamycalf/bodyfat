"""Fictional multi-turn consultation, isolated from the project's .data."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import product
import server
import storage

TURNS = [
    '我现在88公斤，想减重，能先聊聊怎么开始吗？',
    '我43岁，身高164厘米，目标73公斤；体重去年开始涨。',
    '以前做过阑尾切除，有高血压，目前吃降压药，没有食物过敏。',
    '快走一小段会头晕，停下休息一会儿就好。',
    '没有胸痛，也没晕倒，偶尔心跳快。',
    '工作日早餐买鸡蛋饼和咖啡，午餐外卖一碗米饭配炒菜，晚餐有时吃一碗面。',
    '我晚上九点才到家，工作日久坐，平时几乎不运动，睡觉通常十二点左右。',
]

with tempfile.TemporaryDirectory(prefix='zhiheng-dialogue-qa-') as folder:
    data=Path(folder)/'data'
    paths={'DATA':data,'MEDIA_DIR':data/'media'}
    paths.update({key:data/name for key,name in {
        'PROFILE':'profile.json','RECORDS':'records.json','CONVERSATIONS':'conversations.json',
        'MEDIA':'media.json','METADATA':'metadata.json'}.items()})
    with patch.multiple(server,**paths):
        storage.initialize(data)
        for index,utterance in enumerate(TURNS,1):
            result=product.chat(server,{'conversation_id':'fictional-dialogue',
                'client_message_id':f'fictional-dialogue-{index}','text':utterance})
            print(json.dumps({'turn':index,'status':result.get('ai_status'),'error':result.get('ai_error'),
                'plan_saved':bool(result.get('plan')),'reply':result.get('reply'),
                'profile_fields':sorted(server.load_json(server.PROFILE,{}))},ensure_ascii=False),flush=True)
            assert result.get('ai_status')=='connected' or (
                result.get('ai_error') in ('AI_INVALID_STRUCTURED_RESPONSE','AI_TIMEOUT') and
                result.get('safe_local_reply') and '错误码' not in result['reply'])
            assert not result.get('plan')
            assert '合理的目标' not in result['reply']
            if index==7:
                assert '回到刚才的问题' not in result['reply']
                assert '晚餐' in result['reply']
                assert '体重上涨的重要原因' not in result['reply']
        profile=server.load_json(server.PROFILE,{})
        assert profile.get('age')==43 and profile.get('height_cm')==164
        assert 'sex' not in profile
        assert 'surgeries' in profile and 'medications' in profile and 'conditions' in profile
        assert 'allergies' in profile
