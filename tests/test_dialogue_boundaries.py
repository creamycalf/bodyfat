"""Conversational boundaries use fictional data and an isolated workbench."""
import json
import unittest

import consultation
import product
import server
import test_workbench


class DialogueBoundaryTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchTests.setUp
    tearDown = test_workbench.WorkbenchTests.tearDown
    chat = test_workbench.WorkbenchTests.chat

    def fresh(self):
        server.save_json(server.DATA / 'workspace.json', {})
        server.save_json(server.PROFILE, {})
        server.save_json(server.RECORDS, [])
        server.save_json(server.CONVERSATIONS, [])

    def say(self, reply):
        self.output = {'reply': reply, 'decision': {'action': 'none'}, 'plan': None}

    def test_two_gentle_takeout_choices_survive_missing_profile(self):
        self.fresh()
        reply = ('你只能点外卖，就先在眼前的两种选择里挑，不必改成每天做饭。\n'
                 '1. 盖饭可以看有没有蔬菜和你愿意吃的蛋、肉或豆制品。\n'
                 '2. 面条也可以看实际配菜，吃到舒服时不必勉强清盘。\n'
                 '你更愿意先试哪一种？')
        self.say(reply)
        result = self.chat('我想减肥，最近加班只能点外卖，附近就盖饭和面条，想先把这顿吃舒服。')
        self.assertEqual(result['reply'], reply)
        self.assertIsNone(result['plan'])
        self.assertFalse(product.snapshot(server)['plans'])
        self.assertNotIn('多大', result['reply'])

    def test_compound_symptom_denials_do_not_invent_exertional_discomfort(self):
        denials = (
            '运动时头晕没有，气短也没有。',
            '我没有在运动时头晕，也没有气短。',
            '没有做手术，也没有用药，运动时不会头晕或气短。',
        )
        for denial in denials:
            with self.subTest(denial=denial):
                self.fresh()
                reply = '这些不适你已明确说没有。平时晚餐通常吃什么？'
                self.say(reply)
                result = self.chat('我想减肥，' + denial)
                self.assertEqual(result['reply'], reply)
                self.assertFalse(consultation.exertion_symptom_reported(denial, {}))
                self.assertIsNone(result['plan'])

    def test_mixed_negative_and_positive_symptoms_keep_the_positive_concern(self):
        self.assertTrue(consultation.exertion_symptom_reported(
            '运动时没有胸痛，但快走时会头晕。', {}))
        self.assertFalse(consultation.exertion_symptom_reported(
            '运动时没有头晕，也没有气短。', {}))

    def test_compound_chest_and_breathing_denial_does_not_trigger_emergency(self):
        self.fresh()
        text = '我想减肥，运动时没有胸痛或呼吸困难。'
        reply = '这些症状你已明确说没有。平时晚餐通常吃什么？'
        self.say(reply)
        result = self.chat(text)
        self.assertEqual(consultation.decision_kind(text), 'personal_weight_plan')
        self.assertFalse(server.active_safety_findings(text))
        self.assertNotEqual(result['ai_status'], 'safety_rule')
        self.assertEqual(result['reply'], reply)
        self.assertIsNone(result['plan'])

    def test_separate_chest_or_breathing_denial_remains_a_normal_consultation(self):
        for denial in ('没有胸痛。', '没有呼吸困难。'):
            with self.subTest(denial=denial):
                self.fresh()
                text = '我想减肥，' + denial
                reply = '这一项没有相关症状。平时晚餐通常吃什么？'
                self.say(reply)
                result = self.chat(text)
                self.assertEqual(consultation.decision_kind(text), 'personal_weight_plan')
                self.assertFalse(server.active_safety_findings(text))
                self.assertNotEqual(result['ai_status'], 'safety_rule')
                self.assertEqual(result['reply'], reply)
                self.assertIsNone(result['plan'])

    def test_denied_chest_pain_does_not_hide_current_breathing_difficulty(self):
        self.fresh()
        text = '没有胸痛，但目前呼吸困难。'
        self.say('这段模型文字不应该覆盖紧急症状提示。')
        result = self.chat(text)
        self.assertEqual(consultation.decision_kind(text), 'high_risk')
        self.assertTrue(server.active_safety_findings(text))
        self.assertEqual(result['ai_status'], 'safety_rule')
        self.assertIn('急诊', result['reply'])
        self.assertEqual(self.prompt, [])
        self.assertIsNone(result['plan'])
        self.assertFalse(product.snapshot(server)['plans'])

    def test_refusing_numeric_interview_remains_in_effect_on_continue(self):
        self.fresh()
        self.say('你今年多大？')
        self.chat('我想减肥，你带着我聊。')
        self.say('先聊晚上吃多这件事，白天通常怎样吃？')
        result = self.chat('别连续问我年龄身高体重，像填表一样，先聊我晚上吃多这件事。')
        self.assertEqual(result['reply'], self.output['reply'])
        self.assertEqual(product.workspace(server)['sessions']['test-conversation']['dialogue_mode'], 'chat')

        reply = '我们就沿晚上吃多往下看：白天吃得少、晚饭又拖后，可能让晚上更难掌握进食，还需要结合实际餐次判断。'
        self.say(reply)
        continued = self.chat('继续')
        self.assertEqual(continued['reply'], reply)
        self.assertNotIn('plan_readiness', json.loads(self.prompt[1]['content']))
        self.assertEqual(product.workspace(server)['sessions']['test-conversation']['dialogue_mode'], 'chat')
        self.assertIsNone(continued['plan'])

    def test_symptom_has_not_improved_is_not_an_absence_of_symptoms(self):
        for text in ('胸痛没有缓解。', '呼吸困难也没有好转。'):
            with self.subTest(text=text):
                self.fresh()
                self.say('本轮应使用症状安全提示。')
                result = self.chat(text)
                self.assertTrue(server.active_safety_findings(text))
                self.assertEqual(result['ai_status'], 'safety_rule')
                self.assertEqual(self.prompt, [])

    def test_health_answer_after_food_question_is_not_a_food_habit(self):
        self.fresh()
        self.say('最难控制的那顿通常吃什么，开始吃之前是饿得很厉害，还是想放松一下？')
        self.chat('我想减肥，下班后控制不住吃。')
        self.say('这些健康情况你已说明。晚餐通常吃什么？')
        result = self.chat('我没有确诊疾病，没有用药，没有做过手术，没有食物过敏。')
        saved = product.snapshot(server)['profile']
        for field in ('conditions', 'medications', 'surgeries', 'allergies'):
            self.assertIn(field, saved)
        for field in ('food_habits', 'breakfast_habit', 'lunch_habit', 'dinner_habit', 'snacks_drinks'):
            self.assertNotIn(field, saved)
        self.assertIsNone(result['plan'])


if __name__ == '__main__':
    unittest.main()
