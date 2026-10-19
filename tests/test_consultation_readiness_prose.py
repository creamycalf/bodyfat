import unittest
from unittest.mock import patch
import product
import server
import consultation
import intake
import test_workbench


class ProseReadinessTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_plain_goal_then_basics_cannot_bypass_health_history(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'你的年龄、身高、性别和体重是多少？','decision':{'action':'clarify'},'plan':None}
        self.chat('我想减肥，请先了解我')
        self.output={'reply':'热量计算\n减肥建议\n每周至少3次30分钟运动，每天2-2.5升水。',
                     'decision':{'action':'none'},'plan':None}
        result=self.chat('男，28岁，身高172厘米，体重200斤，目标150斤，久坐，不吃辣')
        self.assertIn('确诊疾病',result['reply'])
        self.assertNotIn('30分钟',result['reply'])
        self.assertNotIn('2.5',result['reply'])
        self.assertNotIn('热量计算',result['reply'])
        self.assertIsNone(result['plan'])
        self.assertNotIn('conditions',product.snapshot(server)['profile'])
        self.output={'reply':'现在可以开始每天跑步30分钟。','decision':{'action':'none'},'plan':None}
        reply=self.chat('没有')['reply']
        # A bare denial after several health topics is not assigned to one
        # arbitrary field. The user can answer all named topics in one turn.
        self.assertNotIn('conditions',product.snapshot(server)['profile'])
        self.chat('没有确诊疾病，没有用药，没有过敏，没有手术史')
        saved=product.snapshot(server)['profile']
        for field in ('conditions','medications','allergies','surgeries'):
            self.assertIn('没有',saved[field][0])

    def test_unknown_health_is_not_negative_history_and_general_question_can_interrupt(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'每周跑步30分钟。','decision':{'action':'none'},'plan':None}
        self.chat('我28岁，男，172厘米，100公斤，想减肥，请先了解我')
        result=self.chat('不清楚')
        self.assertIsNone(result['plan'])
        self.assertNotIn('跑步',result['reply'])
        self.assertIn('安全边界',consultation.required_information('personal_weight_plan',product.snapshot(server)['profile'],server.records()))
        self.output={'reply':'牛奶能否接受取决于过敏和乳糖耐受情况。','decision':{'action':'none'},'plan':None}
        self.assertEqual(self.chat('减肥期间可以喝牛奶吗？')['reply'],self.output['reply'])

    def test_surgery_and_daily_pattern_are_required_without_user_prompting(self):
        missing=consultation.required_information('personal_weight_plan',{'age':28,'sex':'男','height_cm':172,
            'conditions':['没有'],'medications':['没有'],'allergies':['没有']},[])
        self.assertIn(['surgeries'],missing['安全边界'])
        self.assertIn(['breakfast_habit'],missing['代表性饮食'])
        self.assertIn(['lunch_habit'],missing['代表性饮食'])
        self.assertIn(['dinner_habit'],missing['代表性饮食'])

    def test_unknown_list_is_not_a_completed_health_answer(self):
        for value in (['不清楚'],['不知道'],['跳过'],[]):
            missing=consultation.required_information('personal_weight_plan',{'conditions':value},[])
            self.assertIn(['conditions'],missing['安全边界'])

    def test_legacy_numbered_answer_keeps_weight_consultation(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'请说年龄、身高和体重？','decision':{'action':'clarify'},'plan':None}
        self.chat('我想减肥，请先了解我')
        server.save_json(server.PROFILE,{'age':28,'sex':'男','height_cm':172})
        server.save_json(server.RECORDS,[{'id':'known-weight','type':'weight','value':{'kg':100}}])
        self.output={'reply':'好的，每天2升水，每周3次30分钟跑步。','decision':{'action':'none'},'plan':None}
        result=self.chat('1 男 28 172 200  2 150  3久坐 4不吃辣')
        self.assertIn('确诊疾病',result['reply'])
        self.assertNotIn('跑步',result['reply'])

    def test_bounded_starter_choice_can_survive_assessment_gate(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'你下班晚又常吃外卖，可以先留意哪种晚餐吃后更舒服，暂时不用逼自己跑步。以前或目前有确诊疾病、运动时不适或医生限制吗？',
                     'decision':{'action':'clarify'},'plan':None}
        result=self.chat('我想减肥，下班晚，常吃外卖，暂时运动很少')
        self.assertIn('下班晚',result['reply'])
        self.assertIn('确诊疾病',result['reply'])
        self.assertIsNone(result['plan'])
        self.assertIn('plan_readiness',self.prompt[1]['content'])

    def test_fallback_starter_uses_actual_constraint_instead_of_only_form(self):
        self.assertIn('线下评估',consultation.assessment_starter('快走时头晕',{}))
        self.assertIn('晚饭',consultation.assessment_starter('晚班九点到家，只能买现成晚饭',{}))
        self.assertIn('咖啡因',consultation.assessment_starter('每天两瓶咖啡',{}))

    def test_mixed_health_answer_does_not_merge_surgery_and_disease(self):
        facts=intake.explicit_health_facts('我做过阑尾切除、有高血压和过敏性鼻炎，目前吃降压药')
        self.assertIn('阑尾切除',str(facts['surgeries']))
        self.assertIn('高血压',str(facts['conditions']))
        self.assertIn('鼻炎',str(facts['conditions']))
        self.assertNotIn('allergies',facts)
        self.assertIn('降压药',str(intake.explicit_medication('目前吃降压药')))

    def test_goal_age_height_without_units_are_grounded(self):
        patch,events=product.explicit_facts(server,'我身高164，年纪43，目前88公斤，想减到73公斤')
        self.assertEqual(patch['age'],43)
        self.assertEqual(patch['height_cm'],164)
        self.assertIn('73公斤',patch['goals'])
        self.assertEqual(events[0]['value']['kg'],88)

    def test_invalid_model_json_keeps_consultation_moving_safely(self):
        server.save_json(server.DATA/'workspace.json',{})
        with patch.object(server,'call_ai',return_value='{invalid json'):
            result=product.chat(server,{'text':'我现在88公斤，想减重',
                'conversation_id':'invalid-consultation','client_message_id':'invalid-consultation-1'})
        self.assertEqual(result['ai_error'],'AI_INVALID_STRUCTURED_RESPONSE')
        self.assertEqual(result['ai_status'],'fallback')
        self.assertIn('年龄',result['reply'])
        self.assertTrue(result['safe_local_reply'])
        self.assertIsNotNone(result['retry_chat'])
        self.assertIsNone(result['plan'])
