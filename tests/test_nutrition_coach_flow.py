"""Regression coverage for the purpose-driven nutrition coach flow."""
import json
import unittest
from unittest.mock import patch

import product
import server
import test_workbench


class NutritionCoachFlowTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchTests.setUp
    tearDown = test_workbench.WorkbenchTests.tearDown
    chat = test_workbench.WorkbenchTests.chat

    def test_cross_conversation_resume_retains_unanswered_topic(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output.update(reply='晚餐后具体是什么不舒服？',decision={'action':'clarify','question_topic':'meal_symptom'})
        self.chat('最近晚餐后不舒服，想减肥')
        self.output.update(reply='收到本次体重。',decision={'action':'none'})
        self.chat('今天体重80公斤，请只记录，不用制定计划')
        self.output.update(reply='继续刚才的问题：晚餐后具体是什么不舒服？',decision={'action':'clarify','question_topic':'meal_symptom'})
        with patch.object(server,'call_ai',return_value=json.dumps(self.output)):
            result=product.chat(server,{'text':'继续评估','conversation_id':'another-conversation','client_message_id':'resume-assessment'})
        self.assertEqual(result['decision']['question_topic'],'meal_symptom')

    def test_invalid_action_reference_is_rejected(self):
        self.output.update(decision={'action':'update','reason':'初步行动'},plan={
            'title':'记录','goal':'记录感受','items':[{'title':'记录感受','basis_record_ids':['invented-record']}]})
        result=self.chat('请先给初步计划')
        self.assertEqual(result['ai_error'],'AI_INVALID_PLAN')
        self.assertEqual(product.workspace(server)['plans'],[])

    def test_context_is_not_automatically_action_evidence(self):
        self.output.update(decision={'action':'update','reason':'初步行动'},plan={
            'title':'记录','goal':'记录感受','items':[{'title':'记录感受'}]})
        result=self.chat('今天体重80公斤，请先给初步计划')
        self.assertEqual(result['plan']['items'][0]['basis_record_ids'],[])
        self.assertEqual(result['plan']['items'][0]['basis_status'],'unlinked')
        self.assertTrue(result['plan']['context_record_ids'])

    def test_generic_goal_asks_problem_and_does_not_infer_bare_age(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output.update(reply='减重时你遇到过哪些困难？',decision={'action':'clarify','question_topic':'goal_barrier'})
        result=self.chat('想减肥，请给我计划')
        self.assertEqual(result['decision']['question_topic'],'goal_barrier')
        self.output['profile_changes']=[{'field':'age','value':80,'evidence':'35'}]
        self.chat('35')
        self.assertNotIn('age',server.load_json(server.PROFILE,{}))

    def test_concrete_goal_keeps_model_reply_instead_of_overwriting_with_script(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output.update(reply='收到你的目标。你更想先从饮食、活动还是作息开始？',decision={'action':'clarify','reason':'需要一个执行入口'})
        result=self.chat('我现在体重200斤，我想减肥，减到150斤')
        self.assertEqual(result['reply'],'收到你的目标。你更想先从饮食、活动还是作息开始？')
        self.assertNotIn('先确认你要解决的问题和最常见的阻碍',result['reply'])

    def test_snapshot_recovery_restores_original_request(self):
        payload={'text':'我今年38岁，今天体重80公斤','conversation_id':'test-conversation','client_message_id':'snapshot-recovery'}
        with patch.object(server,'call_ai',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):product.chat(server,payload)
        turns=product.snapshot(server)['interrupted_turns']
        self.assertEqual(len(turns),1)
        self.assertTrue(turns[0]['resumable'])
        with patch.object(server,'call_ai',return_value=json.dumps(self.output)):
            result=product.chat(server,{'resume_turn':turns[0]['id']})
        self.assertEqual(result['client_message_id'],payload['client_message_id'])
        self.assertEqual(len(server.records()),1)
        self.assertEqual(product.snapshot(server)['interrupted_turns'],[])

    def test_process_interrupt_keeps_facts_and_replay_is_idempotent(self):
        payload={'text':'我今年38岁，今天体重80公斤','conversation_id':'test-conversation','client_message_id':'interrupted-message'}
        def interrupted(*args):
            self.assertEqual(server.load_json(server.PROFILE,{})['age'],38)
            self.assertEqual(len(server.records()),1)
            raise KeyboardInterrupt()
        with patch.object(server,'call_ai',side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):product.chat(server,payload)
        with patch.object(server,'call_ai',return_value=json.dumps(self.output)):
            result=product.chat(server,payload)
            self.assertEqual(product.chat(server,payload),result)
        self.assertEqual(len(server.records()),1)
        self.assertNotIn(payload['client_message_id'],product.workspace(server)['pending_turns'])
        product.action(server,{'action':'undo','id':payload['client_message_id']})
        self.assertEqual(server.records(),[])
        self.assertEqual(server.load_json(server.PROFILE,{}),{})

    def test_final_write_failure_rolls_back_plan_but_keeps_checkpoint(self):
        payload={'text':'我今年38岁，今天体重80公斤，请先给初步计划','conversation_id':'test-conversation','client_message_id':'failed-save-message'}
        output={'reply':'建议','decision':{'action':'update','reason':'初步行动'},'plan':{'title':'观察','goal':'记录感受','items':[{'title':'记录感受'}]}}
        original=server.save_json
        def fail(path,value):
            if path==server.CONVERSATIONS:raise OSError('injected write failure')
            return original(path,value)
        with patch.object(server,'call_ai',return_value=json.dumps(output)),patch.object(server,'save_json',side_effect=fail):
            with self.assertRaises(OSError):product.chat(server,payload)
        self.assertEqual(len(server.records()),1)
        self.assertEqual(product.workspace(server)['plans'],[])
        self.assertNotIn(payload['client_message_id'],product.workspace(server)['receipts'])
        with patch.object(server,'call_ai',return_value=json.dumps(output)):product.chat(server,payload)
        self.assertEqual(len(product.workspace(server)['plans']),1)
        self.assertEqual(len(server.records()),1)

    def test_interrupted_replay_cannot_overwrite_later_edit(self):
        payload={'text':'我今年38岁','conversation_id':'test-conversation','client_message_id':'interrupted-edit-message'}
        with patch.object(server,'call_ai',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):product.chat(server,payload)
        product.action(server,{'action':'profile','fields':{'age':39}})
        with self.assertRaises(product.ProductError):product.chat(server,payload)
        self.assertEqual(server.load_json(server.PROFILE,{})['age'],39)

    def test_answer_closes_topic_without_filling_unknown_health_fields(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output.update(reply='晚餐后是什么不舒服？',decision={'action':'clarify','question_topic':'meal_symptom'})
        first=self.chat('最近晚餐后不舒服，想减肥')
        self.output.update(reply='收到，你近期有没有医生给过饮食限制？',decision={'action':'clarify','question_topic':'meal_symptom'})
        second=self.chat('晚饭后一小时胃胀，持续半小时')
        self.assertNotEqual(first['reply'],second['reply'])
        self.assertNotIn('年龄',second['reply'].split('尚未确认')[0])
        state=product.workspace(server)['assessment_state']
        self.assertIn('meal_symptom',state['answered_topics'])
        self.assertNotIn('surgeries',product.snapshot(server)['profile'])
        self.assertEqual(second['reply'],self.output['reply'])
        self.assertEqual(state['next_question']['text'],'收到，你近期有没有医生给过饮食限制？')

    def test_specific_topic_does_not_start_with_age(self):
        workspace = product.workspace(server)
        workspace['interview'] = {'skipped': []}
        workspace['assessment_state']['skipped_topics'] = []
        server.save_json(server.DATA / 'workspace.json', workspace)
        self.output.update(
            reply='我先问一个与晚餐症状有关的问题。',
            decision={'action': 'clarify', 'reason': '需要把症状和餐次对应起来'},
            plan=None,
        )
        result = self.chat('最近晚餐后不舒服，想减肥')
        self.assertIsNone(result['plan'])
        self.assertEqual(result['decision']['question_topic'], 'meal_symptom')
        self.assertNotIn('asked_field', product.workspace(server)['sessions']['test-conversation'])
        self.assertEqual(product.workspace(server)['sessions']['test-conversation']['asked_topic'], 'meal_symptom')
        assessment = product.snapshot(server)['assessment']
        self.assertEqual(assessment['stage_code'], 'assessment')
        self.assertEqual(assessment['next_question_detail']['topic'], 'meal_symptom')

    def test_fact_receipt_survives_invalid_plan(self):
        malformed = json.dumps({
            'reply': '已经安排好了',
            'decision': {'action': 'update', 'reason': '模型尝试出方案'},
            'plan': {'title': '缺少事项', 'goal': '减脂', 'items': []},
        }, ensure_ascii=False)
        with patch.object(server, 'call_ai', return_value=malformed):
            result = product.chat(server,{'text':'我今年38岁，今天体重80公斤，请生成计划',
                'conversation_id':'test-conversation','client_message_id':'invalid-plan-facts'})
        self.assertEqual(result['ai_error'],'AI_INVALID_PLAN')
        state = product.snapshot(server)
        self.assertEqual(state['profile']['age'], 38)
        self.assertEqual(state['records'][0]['value']['kg'], 80)
        self.assertIsNone(result['plan'])
        self.assertIn('档案已保存', result['receipts'])
        self.assertIn('记录已保存', result['receipts'])
        self.assertIn('评估已更新', result['receipts'])
        self.assertTrue(state['assessment']['assessment_history'])

    def test_action_keeps_problem_basis_alternatives_and_feedback(self):
        self.output.update(
            reply='先试一周再复盘。',
            decision={'action': 'update', 'reason': '已具备阶段行动所需依据'},
            plan={'title': '阶段行动', 'goal': '减少晚餐后不适', 'duration_days': 7,
                  'basis': '晚餐后不适的用户原话', 'unknowns': '手术与医嘱待核实',
                  'items': [{'title': '晚餐后记录感受', 'detail': '记录出现时间和感觉',
                             'when': '每天·晚餐后', 'minimum': '只记一句话',
                             'problem': '晚餐后不适', 'basis_record_ids': [],
                             'alternatives': '加班时用手机简记', 'feedback': '反馈是否仍不舒服',
                             'review_at': '一周后'}]},
        )
        result = self.chat('资料还没齐，请先给初步计划')
        self.assertIsNotNone(result['plan'])
        action = result['plan']['items'][0]
        for key in ('problem', 'basis_record_ids', 'alternatives', 'feedback', 'review_at'):
            self.assertIn(key, action)
        self.assertEqual(product.snapshot(server)['assessment']['stage_code'], 'trial')


if __name__ == '__main__':
    unittest.main()
