import json
import unittest
from unittest.mock import patch
import product
import server
import test_workbench


class ModelJsonRepairTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def test_malformed_outer_object_never_becomes_nested_decision(self):
        raw='{"reply":"也可以回复"跳过"。","decision":{"action":"clarify"}}'
        self.assertIsNone(server.parse_json(raw))
        self.assertIsNone(server.parse_json('下面是JSON： '+raw))
        self.assertIsNone(server.parse_json('说明：```json\n'+raw+'\n```'))

    def test_invalid_reply_cannot_apply_plan_or_model_profile_changes(self):
        raw=json.dumps({'reply':'','decision':{'action':'update','reason':'方案'},
            'profile_changes':[{'field':'preferences','value':'喜欢散步','evidence':'想减肥'}],
            'plan':{'title':'观察','goal':'记录','items':[{'title':'记录感受'}]}})
        with patch.object(server,'call_ai',return_value=raw),patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            r=product.chat(server,{'text':'我体重100公斤，想减肥，请先给初步计划','conversation_id':'invalid-model','client_message_id':'invalid-model-001'})
        self.assertEqual(r['ai_error'],'AI_INVALID_STRUCTURED_RESPONSE')
        self.assertEqual(product.workspace(server)['plans'],[])
        self.assertNotIn('preferences',product.snapshot(server)['profile'])
        self.assertNotIn('已生成',r['reply'])
        self.assertEqual(len(server.records()),1)

    def test_one_format_retry_preserves_one_weight_and_natural_reply(self):
        server.save_json(server.DATA/'workspace.json',{})
        raw='{"reply":"也可以回复"跳过"。","decision":{"action":"clarify"}}'
        valid=json.dumps({'reply':'你平时早餐吃什么？','decision':{'action':'clarify'},'plan':None},ensure_ascii=False)
        with patch.object(server,'call_ai',side_effect=[raw,valid]) as model,patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            result=product.chat(server,{'text':'你好，我体重200斤，想减肥怎么办','conversation_id':'repair-test','client_message_id':'repair-test-001'})
        self.assertEqual(model.call_count,2)
        self.assertLessEqual(model.call_args.kwargs['total_timeout'],85)
        self.assertEqual(result['reply'],'你平时早餐吃什么？')
        self.assertFalse(result.get('ai_error'))
        self.assertEqual(len(server.records()),1)
        self.assertEqual(server.records()[0]['value']['kg'],100)
        prompt=str(model.call_args_list[0].args)
        self.assertNotIn('allowed_assessment_questions',prompt)
        self.assertNotIn('最容易在哪个时段或情境卡住',prompt)

    def test_second_malformed_reply_stops_and_preserves_fact(self):
        raw='{"reply":"broken "quote"","decision":{"action":"none"}}'
        with patch.object(server,'call_ai',return_value=raw) as model,patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            result=product.chat(server,{'text':'今天体重100公斤','conversation_id':'repair-fail','client_message_id':'repair-fail-001'})
        self.assertEqual(model.call_count,2)
        self.assertEqual(result['ai_error'],'AI_INVALID_STRUCTURED_RESPONSE')
        self.assertEqual(len(server.records()),1)
