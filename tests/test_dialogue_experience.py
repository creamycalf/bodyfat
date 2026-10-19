"""Protect useful conversation from over-broad deterministic reply rewrites."""
import unittest
from unittest.mock import patch

import consultation
import intake
import product
import server
import test_workbench


class DialogueExperienceTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchTests.setUp
    tearDown = test_workbench.WorkbenchTests.tearDown
    chat = test_workbench.WorkbenchTests.chat

    def fresh(self, profile=None, weight=None):
        server.save_json(server.DATA/'workspace.json', {})
        server.save_json(server.PROFILE, profile or {})
        if weight is not None:
            server.save_json(server.RECORDS, [{
                'id':'experience-weight', 'type':'weight', 'value':{'kg':weight},
                'status':'confirmed', 'memory_enabled':True,
                'observed_at':'2026-10-09T08:00:00',
            }])

    def model(self, reply, action='clarify', *, include_plan=True):
        self.output = {'reply':reply, 'profile_changes':[], 'record_events':[],
                       'decision':{'action':action, 'reason':'承接用户当前困难'}}
        if include_plan:
            self.output['plan'] = None

    def session(self):
        return product.workspace(server)['sessions']['test-conversation']

    def test_missing_weight_can_be_asked_before_missing_age(self):
        self.fresh()
        reply = '我们先看你现在的起点，再找适合你生活的办法。最近测到的体重是多少公斤？'
        self.model(reply)
        answer = self.chat('我想减肥')
        self.assertEqual(answer['reply'], reply)
        self.assertIsNone(answer['plan'])
        self.assertEqual(self.session().get('asked_field'), 'weight_kg')

    def test_missing_height_can_be_asked_before_missing_age(self):
        self.fresh()
        reply = '先找一个能持续的起点，不急着大改饮食。你的身高是多少厘米？'
        self.model(reply)
        answer = self.chat('我想减肥')
        self.assertEqual(answer['reply'], reply)
        self.assertEqual(self.session().get('asked_field'), 'height_cm')

    def test_known_age_in_reflection_does_not_turn_height_question_into_form(self):
        self.fresh({'age':38})
        reply = '你今年38岁这点已经清楚了，我们再结合实际体型看。你的身高是多少厘米？'
        self.model(reply)
        answer = self.chat('我想减肥，请先了解我')
        self.assertEqual(answer['reply'], reply)
        self.assertEqual(self.session().get('asked_field'), 'height_cm')

    def test_useful_reply_without_question_is_preserved(self):
        self.fresh({'age':38, 'sex':'男', 'height_cm':175}, 85)
        reply = '加班后太饿时临时决定晚饭，确实容易吃得急。可以先在下班前看看实际可选的晚饭，保留正常进食。'
        self.model(reply, action='none')
        answer = self.chat('我想减肥，晚上八点下班，晚餐总是到家很饿才点外卖。')
        self.assertTrue(answer['reply'].startswith(reply), answer['reply'])
        self.assertEqual(answer['reply'], reply)
        self.assertIsNone(answer['plan'])

    def test_clarify_metadata_does_not_force_a_question(self):
        self.fresh({'age':38, 'sex':'男', 'height_cm':175}, 85)
        reply = '先不用把午餐吃得更少，加班后的饥饿程度和晚餐条件都值得一起看。'
        self.model(reply, action='clarify')
        answer = self.chat('我想减肥，晚上八点下班，经常饿得吃很多外卖。')
        self.assertTrue(answer['reply'].startswith(reply), answer['reply'])
        self.assertEqual(answer['reply'], reply)

    def test_missing_plan_field_does_not_discard_safe_connected_reply(self):
        self.fresh()
        reply = '总在加班后才决定吃什么，安排可能比意志力更值得先看。你晚餐通常几点能真正吃上？'
        self.model(reply, include_plan=False)
        answer = self.chat('我想减肥，下班太晚，经常点外卖。')
        self.assertEqual(answer['reply'], reply)
        self.assertIsNone(answer['plan'])
        self.assertIsNone(answer['ai_error'])

    def test_fallback_question_does_not_keep_unrelated_health_field(self):
        self.fresh({'age':38, 'sex':'男', 'height_cm':175}, 85)
        self.model('这是完整方案，你照着做就行。', action='none')
        answer = self.chat('我想减肥，晚上八点下班，晚餐基本靠外卖。')
        question = intake.reply_question(answer['reply'])
        self.assertIsNotNone(question)
        self.assertRegex(question['text'], '晚餐|晚饭|那顿')
        self.assertNotIn(self.session().get('asked_field'), ('age', 'conditions'))
        self.assertIsNone(answer['plan'])

    def test_denied_exertional_symptoms_do_not_insert_symptom_warning(self):
        self.fresh({'age':38, 'sex':'男', 'height_cm':175}, 85)
        reply = '你说活动时没有不适，这点已经了解。你平常午餐吃些什么、大约多少？'
        self.model(reply)
        answer = self.chat('我想减肥，运动时没有头晕，也不会喘；没有用药，也没有手术史。')
        self.assertEqual(answer['reply'], reply)
        self.assertNotIn('停下', answer['reply'])
        self.assertNotIn('线下评估', answer['reply'])

    def test_explicit_negative_symptoms_are_not_positive_exertional_findings(self):
        for negative in ('运动时没有头晕，也不会喘。', '运动时从来没出现过头晕或气短。'):
            with self.subTest(negative=negative):
                self.assertFalse(consultation.exertion_symptom_reported(negative, {}))
                self.assertIsNone(consultation.exertion_followup_question(negative))
        self.assertTrue(consultation.exertion_symptom_reported('跑步时会头晕，停下来才好。', {}))

    def test_preserving_conversation_never_saves_unsupported_prescription(self):
        self.fresh()
        self.model('每天只吃500千卡，同时跑步60分钟。你的身高是多少？', action='update')
        self.output['plan'] = {
            'title':'极端减重', 'goal':'快速变瘦', 'duration_days':7,
            'items':[{'title':'少吃多跑', 'detail':'每天只吃500千卡并跑步60分钟',
                      'when':'每天', 'minimum':'同样执行'}],
        }
        answer = self.chat('我想减肥，请带我开始。')
        self.assertIsNone(answer['plan'])
        self.assertFalse(product.snapshot(server)['plans'])
        self.assertNotIn('500千卡', answer['reply'])
        self.assertNotIn('跑步60分钟', answer['reply'])

    def test_timeout_recovery_follows_takeout_constraint_without_asking_age(self):
        self.fresh()
        self.model('白天吃得少和晚餐拖后可能有关。午餐到晚餐通常隔多久？')
        self.chat('我想减肥，但下班就控制不住吃。')
        with patch.object(server,'call_ai',return_value=None), patch.object(server,'ai_meta',return_value={
                'ai_status':'fallback','ai_error':'AI_TIMEOUT'}):
            answer=product.chat(server,{'text':'还是得点外卖，没时间做饭。',
                'conversation_id':'test-conversation','client_message_id':'experience-timeout-takeout'})
        self.assertEqual(answer['ai_error'],'AI_TIMEOUT')
        self.assertIn('超时',answer['reply'])
        self.assertIn('配菜',answer['reply'])
        self.assertNotRegex(consultation.displayed_question_text(answer['reply']),'年龄|多大|身高|体重')
        self.assertIsNone(answer['plan'])
        self.assertTrue(answer.get('retry_chat'))


if __name__ == '__main__':
    unittest.main()
