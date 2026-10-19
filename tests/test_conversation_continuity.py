"""Conversational regressions use isolated storage and controlled model replies."""
import unittest
from unittest.mock import patch
import intake
import product
import server
import test_workbench


class ContinuityTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def fresh(self):
        server.save_json(server.DATA/'workspace.json',{})

    def model(self,reply,topic='goal_barrier',action='clarify'):
        self.output={'reply':reply,'decision':{'action':action,'question_topic':topic,'reason':'根据本轮对话继续了解'},'plan':None}

    def test_numeric_filter_preserves_model_question_without_adding_another(self):
        self.fresh()
        self.model('每天1800千卡。你平时早餐吃什么？')
        result=self.chat('我现在200斤，想减到150斤，请给我计划')
        self.assertEqual(result['reply'],'你平时早餐吃什么？')
        state=product.workspace(server)
        self.assertEqual(state['sessions']['test-conversation']['asked_topic'],'meal_pattern')
        self.assertEqual(state['assessment_state']['next_question']['topic'],'meal_pattern')
        self.model('面条通常吃多大一碗？','meal_pattern')
        self.assertEqual(self.chat('面条')['reply'],self.output['reply'])
        self.assertIn('meal_pattern',product.workspace(server)['assessment_state']['answered_topics'])

    def test_completed_topic_keeps_next_model_question(self):
        self.fresh()
        self.model('晚餐后通常是什么不舒服？','meal_symptom')
        self.chat('晚餐后不舒服，想减肥')
        self.model('明白。医生有没有给过饮食限制？','meal_symptom')
        result=self.chat('晚餐后一个小时胃胀')
        self.assertEqual(result['reply'],self.output['reply'])
        self.assertNotIn('这一部分已记下',result['reply'])
        self.assertNotIn('surgeries',product.snapshot(server)['profile'])

    def test_short_answers_to_barrier_are_accepted_without_inventing_facts(self):
        for answer in ('晚餐','加班','零食'):
            with self.subTest(answer=answer):
                self.assertTrue(intake.topic_answered('goal_barrier',answer))
        self.assertFalse(intake.topic_answered('goal_barrier','不知道'))
        self.assertEqual(intake.reply_question('你是男性还是女性？')['topic'],'profile_basics')

    def test_personal_goal_gets_next_question_when_model_stops_guiding(self):
        self.fresh();self.model('我会结合你已提供的情况继续分析。',action='none')
        result=self.chat('我现在200斤，想减肥')
        self.assertIn('年龄',result['reply'])
        self.assertIsNone(result['plan'])

    def test_removed_entire_answer_and_empty_reply_are_retryable_errors(self):
        for reply in ('每天1800千卡。',''):
            with self.subTest(reply=reply):
                self.fresh();self.model(reply)
                result=self.chat('我今年38岁，想减肥')
                self.assertEqual(result['ai_error'],'AI_INVALID_STRUCTURED_RESPONSE')
                self.assertIn('继续这次请求',result['reply'])
                self.assertNotIn('卡在哪一餐',result['reply'])
                self.assertEqual(product.snapshot(server)['profile']['age'],38)

    def test_timeout_is_disclosed_while_safe_consultation_continues(self):
        self.fresh()
        with patch.object(server,'call_ai',return_value=None),patch.object(server,'ai_meta',return_value={'ai_status':'fallback','ai_error':'AI_TIMEOUT'}):
            result=product.chat(server,{'text':'我今年38岁，想减肥，请先了解我','conversation_id':'timeout-test','client_message_id':'timeout-test'})
        self.assertEqual(result['ai_error'],'AI_TIMEOUT')
        self.assertTrue(result['safe_local_reply'])
        self.assertIn('模型这次响应超时',result['reply'])
        self.assertIn('性别',result['reply'])
        self.assertNotIn('错误码',result['reply'])
        self.assertEqual(product.snapshot(server)['profile']['age'],38)

    def test_basic_question_resumes_and_answer_closes_without_repeat(self):
        self.fresh();self.model('你的年龄、身高、性别是什么？')
        self.chat('想减肥，请给我计划')
        self.assertEqual(product.workspace(server)['assessment_state']['next_question']['topic'],'profile_basics')
        self.chat('继续评估',conversation_id='another-session')
        self.assertEqual(product.workspace(server)['sessions']['another-session']['asked_topic'],'profile_basics')
        self.model('谢谢，我会结合这些情况分析。',action='none')
        self.chat('38岁，172厘米，男生',conversation_id='another-session')
        state=product.snapshot(server)
        self.assertEqual(state['profile']['age'],38)
        self.assertEqual(state['profile']['height_cm'],172)
        self.assertIn('profile_basics',product.workspace(server)['assessment_state']['answered_topics'])
        self.assertFalse(product.workspace(server)['assessment_state']['next_question'])

    def test_related_model_questions_can_be_displayed_together(self):
        parsed=intake.reply_question('有没有用药？早餐吃什么？平时几点睡？')
        self.assertEqual(parsed['topic'],'')
        self.assertEqual(set(parsed['topics']),{'meal_symptom','meal_pattern','sleep_activity'})
        self.fresh();self.model('有没有用药？早餐吃什么？平时几点睡？')
        result=self.chat('想减肥，请给我计划')
        state=product.workspace(server)
        question=state['assessment_state']['next_question']
        self.assertEqual(result['reply'].count('？'),3)
        self.assertEqual(set(question['topics']),{'meal_symptom','meal_pattern','sleep_activity'})
        self.assertIn('有没有用药',result['reply'])

    def test_fresh_chat_grouped_basics_are_saved_once_and_health_follows(self):
        self.fresh()
        self.model('你的年龄、身高和性别是什么？')
        first=self.chat('我目前体重200斤，想减肥，请先了解我')
        self.assertIn('年龄',first['reply'])
        self.assertEqual(server.records()[-1]['value']['kg'],100)
        self.assertNotIn('asked_field',product.workspace(server)['sessions']['test-conversation'])
        self.model('根据身高年龄先给你完整方案：每天少吃，每周跑步。')
        answer=self.chat('38岁，男，身高172厘米')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile['height_cm'],172)
        self.assertEqual(profile['age'],38)
        self.assertEqual(profile['sex'],'男')
        self.assertIn('确诊疾病',answer['reply'])
        self.assertNotIn('完整方案',answer['reply'])
        self.assertIsNone(answer['plan'])
        self.assertFalse(product.snapshot(server)['plans'])

    def test_new_chat_uses_saved_basics_and_rejects_repeat_question(self):
        self.fresh()
        server.save_json(server.PROFILE,{'age':38,'sex':'男','height_cm':172})
        server.save_json(server.RECORDS,[{'id':'prior-weight','type':'weight','value':{'kg':100}}])
        self.model('你的年龄和身高再说一次？')
        result=self.chat('我想减肥，请先了解我的情况')
        self.assertNotIn('年龄是多少',result['reply'])
        self.assertNotIn('身高是多少',result['reply'])
        self.assertIn('确诊疾病',result['reply'])
        self.assertIsNone(result['plan'])

    def test_open_health_answer_stays_in_consultation_and_blocks_model_regimen(self):
        self.fresh()
        self.model('你今年多大？')
        self.chat('我想减重，请先了解情况')
        self.model('有没有确诊疾病？现在用什么药？')
        self.chat('女，42岁，身高165厘米，现在84公斤，目标是72公斤')
        self.model('减肥建议：\n1. 每天吃固定热量\n2. 每周跑步三次，每次30分钟')
        result=self.chat('有膝盖旧伤，快走时会头晕，晚班九点到家，目前吃降压药')
        self.assertIsNone(result['plan'])
        self.assertNotIn('每周跑步',result['reply'])
        self.assertNotIn('固定热量',result['reply'])
        self.assertIn('停',result['reply'])
        self.assertIn('胸痛',result['reply'])
        self.assertIn('conditions',product.snapshot(server)['profile'])
        self.assertIn('medications',product.snapshot(server)['profile'])
        self.assertIn('当前不是生成计划的轮次',self.prompt[0]['content'])

    def test_model_cannot_infer_sex_from_unrelated_evidence(self):
        self.fresh()
        self.output={'reply':'你今年多大？','decision':{'action':'clarify'},'plan':None}
        self.chat('我想减重')
        self.output={'reply':'以前有过什么病或手术？','decision':{'action':'clarify'},'plan':None,
            'profile_changes':[{'field':'sex','value':'女','evidence':'我43岁'}]}
        self.chat('我43岁，身高164厘米，体重88公斤')
        self.assertNotIn('sex',product.snapshot(server)['profile'])

    def test_new_schedule_detail_replaces_stale_breakfast_question(self):
        self.fresh()
        server.save_json(server.PROFILE,{'age':43,'sex':'男','height_cm':164,
            'conditions':['没有'],'medications':['没有'],'allergies':['没有'],'surgeries':['没有']})
        server.save_json(server.RECORDS,[{'id':'weight-known','type':'weight','value':{'kg':88}}])
        self.model('早餐通常吃什么？')
        self.chat('我想减重，先了解我的情况')
        self.model('收到你说的工作安排。回到刚才的问题：早餐通常吃什么？')
        result=self.chat('我晚上九点才到家，工作日久坐，几乎不运动')
        self.assertNotIn('早餐通常吃什么',result['reply'])
        self.assertIn('晚餐',result['reply'])

    def test_schedule_does_not_become_unproved_weight_gain_cause(self):
        self.fresh()
        server.save_json(server.PROFILE,{'age':43,'height_cm':164,'sex':'男',
            'conditions':['没有'],'medications':['没有'],'allergies':['没有'],'surgeries':['没有']})
        server.save_json(server.RECORDS,[{'id':'weight-known','type':'weight','value':{'kg':88}}])
        self.model('平常晚餐怎么解决？')
        self.chat('我想减重，先了解我的情况')
        self.model('工作日久坐不运动，这是体重上涨的重要原因。平时吃零食吗？')
        result=self.chat('我晚上九点才到家，工作日久坐，几乎不运动')
        self.assertNotIn('重要原因',result['reply'])
        self.assertIn('晚餐',result['reply'])

    def test_symptom_detail_is_answered_before_reasking_gender(self):
        self.fresh()
        server.save_json(server.PROFILE,{'age':43,'height_cm':164,'goals':'稳步减重',
            'conditions':['有高血压','快走时头晕'],'medications':['降压药']})
        server.save_json(server.RECORDS,[{'id':'weight-known','type':'weight','value':{'kg':88}}])
        state=product.workspace(server)
        state['sessions']['test-conversation']={'consultation_kind':'personal_weight_plan',
            'request':'我想减重','interview_request':True}
        server.save_json(server.DATA/'workspace.json',state)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'role':'assistant','text':'有没有胸痛或晕倒？'}]}])
        self.model('没有胸痛也没晕倒是好的。你是男性还是女性？')
        result=self.chat('没有胸痛，也没晕倒，偶尔心跳快。')
        self.assertNotIn('男性还是女性',result['reply'])
        self.assertIn('心跳快',result['reply'])
        self.assertIsNone(result['plan'])
