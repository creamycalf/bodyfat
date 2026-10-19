"""Synthetic failures found by paired raw/final dialogue inspection."""
import unittest
import consultation
import intake
import coach_actions
import product
import server
import test_workbench


class DialogueAttributionTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchTests.setUp
    tearDown = test_workbench.WorkbenchTests.tearDown
    chat = test_workbench.WorkbenchTests.chat

    def fresh(self):
        server.save_json(server.DATA/'workspace.json', {})

    def reply(self, text):
        self.output = {'reply': text, 'decision': {'action': 'clarify'}, 'plan': None}

    def test_colloquial_weight_goal_does_not_start_assessment(self):
        self.fresh();self.reply('以前最难坚持的是哪一部分？')
        result = self.chat('我现在88公斤，想瘦一点，但以前一做计划就坚持不下来，先聊聊行吗？')
        self.assertEqual(result['request_kind'], 'personal_weight_plan')
        self.assertIn('正在与用户自然交谈', self.prompt[0]['content'])
        self.assertNotIn('plan_readiness', self.prompt[1]['content'])
        self.assertIsNone(result['plan'])
        self.assertEqual(consultation.decision_kind('减肥期间可以喝牛奶吗？'), 'general')

    def test_takeout_context_does_not_replace_relevant_reply_with_menu_template(self):
        self.fresh()
        text='晚下班又饿着到家，确实很难有精力做饭。你通常几点吃午餐，到晚饭之间有吃东西吗？'
        self.reply(text)
        result=self.chat('我38岁，172厘米。最烦的是九点下班，到家很饿，只能叫外卖。')
        self.assertEqual(result['reply'],text)

    def test_safe_takeout_answer_survives_without_menu(self):
        self.fresh()
        text='可以先在你常用的平台看家常饭或面食，具体还要核对店里的菜单。你现在看到了哪些选项？'
        self.reply(text)
        self.assertEqual(self.chat('晚餐外卖怎么选，没有菜单')['reply'],text)

    def test_invented_takeout_availability_still_replaced(self):
        self.fresh();self.reply('附近这家店有货，15分钟能送到，评分4.9。')
        result=self.chat('晚餐外卖怎么选？')
        self.assertNotIn('15分钟',result['reply'])
        self.assertIn('核对',result['reply'])

    def test_explanation_of_meal_interval_is_not_exercise_prescription(self):
        self.fresh();self.reply('你通常几点吃午餐？')
        self.chat('我38岁，172厘米，88公斤，想减重，晚上下班很晚')
        text='中午12点到晚上10点相隔10小时，中间没吃东西可能让饥饿感更明显。下午在公司方便吃东西吗？'
        self.reply(text)
        self.assertEqual(self.chat('午餐十二点吃，十点才到家，下午没吃东西')['reply'],text)

    def test_refused_gender_is_remembered_but_not_treated_as_known(self):
        self.fresh();self.reply('你的生理性别是什么？')
        self.chat('我38岁，172厘米，88公斤，想减重')
        self.reply('你的生理性别是什么？')
        result=self.chat('性别暂时不想说，能先聊聊晚上饿这件事吗？')
        self.assertNotIn('生理性别是什么',result['reply'])
        self.assertIn('sex',product.workspace(server)['interview']['skipped'])
        self.assertNotIn('sex',product.snapshot(server)['profile'])
        missing=consultation.required_information('personal_weight_plan',product.snapshot(server)['profile'],server.records())
        self.assertIn(['sex'],missing['基础资料'])
        self.reply('你的生理性别是什么？')
        result=self.chat('好，那继续吧')
        self.assertNotIn('生理性别是什么',result['reply'])
        self.assertIsNone(result['plan'])

    def test_safe_explanation_need_not_end_with_another_question(self):
        self.fresh();self.reply('晚餐前一般饿不饿？')
        self.chat('我38岁，172厘米，88公斤，想减重')
        text='明白，我们先弄清原因，不急着安排。两餐间隔较长可能让晚上的饥饿感更强，具体还要结合午餐份量和当天活动，不能据此认定是意志力差。'
        self.reply(text)
        self.assertEqual(self.chat('别急着安排，我就想知道为什么这么饿')['reply'],text)

    def test_continue_and_refusal_are_not_meal_or_health_facts(self):
        for field in ('lunch_habit','conditions','medications'):
            for text in ('好，那继续吧，别再问刚才不想说的了','暂时不想说','那继续吧','别急着安排，我就想知道为什么这么饿'):
                self.assertEqual(intake.short_answer(field,text),{})

    def test_explanation_request_cannot_be_saved_as_dinner_by_model(self):
        self.fresh();self.reply('晚餐通常吃什么？')
        self.chat('我38岁，172厘米，想减重')
        text='别急着安排，我就想知道为什么这么饿'
        self.reply('两餐间隔可能影响饥饿感，但不能据此推断个人血糖。')
        self.output['profile_changes']=[{'field':'dinner_habit','value':text,'evidence':text}]
        result=self.chat(text)
        self.assertEqual(result['reply'],self.output['reply'])
        self.assertNotIn('dinner_habit',product.snapshot(server)['profile'])

    def test_short_calorie_unit_is_checked_but_cards_are_not_nutrients(self):
        self.assertTrue(coach_actions.has_unverified_nutrients('下午加餐（200-300卡）'))
        self.assertFalse(coach_actions.has_unverified_nutrients('有300卡片'))
        clean,removed=coach_actions.redact_unverified_nutrients('先了解饥饿感。\n下午加餐（200-300卡）。\n不急着安排。')
        self.assertTrue(removed);self.assertNotIn('200',clean)
        self.assertIn('先了解饥饿感',clean)


if __name__ == '__main__':
    unittest.main()
