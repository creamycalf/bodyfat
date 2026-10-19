"""A factual correction does not grant consent to resume an old questionnaire."""
import json
import unittest

import product
import server
import test_workbench
import consultation


class FactUpdateRoutingFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_comparing_starting_points_answers_question_without_starting_intake(self):
        server.save_json(server.DATA/'workspace.json',{})
        text='我男，38岁，身高175厘米，体重85公斤，对花生过敏。如果我想减脂，先从饮食还是运动开始更合适？'
        useful='可以先从可持续的饮食调整着手，配合符合当前能力的活动；花生过敏要核对配料。'
        self.output={'reply':useful,'decision':{'action':'none'},'plan':None}
        answer=self.chat(text)
        self.assertEqual(consultation.decision_kind(text),'general')
        self.assertEqual(answer['reply'],useful)
        self.assertNotIn('plan_readiness',json.loads(self.prompt[1]['content']))
        self.assertEqual(product.snapshot(server)['profile']['age'],38)
        self.assertEqual(consultation.decision_kind('如果我要减脂，请制定一周计划。'),'personal_weight_plan')

    def assessment(self,previous='有没有确诊疾病、用药或手术史？'):
        server.save_json(server.PROFILE,{'age':38,'sex':'男','height_cm':175,'allergies':['花生']})
        server.save_json(server.RECORDS,[{'id':'current-weight','type':'weight','value':{'kg':85},
            'confirmed':True,'observed_at':product.now(),'occurred_at':product.now()}])
        w=product.workspace(server)
        w['sessions']['test-conversation']={'consultation_kind':'personal_weight_plan',
            'request':'我想减脂，先从哪里开始','interview_request':True,
            'dialogue_mode':'assessment','guidance_policy':1}
        server.save_json(server.DATA/'workspace.json',w)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'role':'user','text':'我想减脂，先从哪里开始'},
            {'role':'assistant','text':previous}]}])

    def test_exact_live_correction_keeps_model_explanation(self):
        self.assessment()
        useful='身高按168厘米理解，工作时间为下午3点到晚上11点。工作期间和下班后的进食安排都需要结合实际饥饿感讨论，运动可作为保留肌肉和改善体能的配合。'
        self.output={'reply':useful,'decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':'work_schedule','value':'下午三点到晚上十一点上班',
                                'evidence':'现在下午三点到晚上十一点上班'}]}
        answer=self.chat('更正一下，身高是168厘米，之前175记错了。现在下午三点到晚上十一点上班。')
        self.assertEqual(answer['reply'],useful)
        self.assertEqual(product.snapshot(server)['profile']['height_cm'],168)
        self.assertIn('十一点',product.snapshot(server)['profile']['work_schedule'])
        self.assertNotIn('plan_readiness',json.loads(self.prompt[1]['content']))
        self.assertFalse(product.snapshot(server)['plans'])

    def test_unsolicited_work_update_does_not_resume_old_health_question(self):
        self.assessment()
        useful='工作时间按下午3点到晚上11点理解，可以围绕上班前、工作中、下班后的实际情况继续聊。'
        self.output={'reply':useful,'decision':{'action':'none'},'plan':None}
        answer=self.chat('现在下午三点到晚上十一点上班。')
        self.assertEqual(answer['reply'],useful)
        self.assertFalse(product.workspace(server)['sessions']['test-conversation'].get('interview_request'))

    def test_explicit_continue_with_correction_still_resumes_assessment(self):
        self.assessment()
        self.output={'reply':'明白。','decision':{'action':'none'},'plan':None}
        self.chat('更正一下，身高168厘米，之前175记错了。继续做方案。')
        facts=json.loads(self.prompt[1]['content'])
        self.assertIn('plan_readiness',facts)
        self.assertTrue(product.workspace(server)['sessions']['test-conversation']['interview_request'])
        self.assertEqual(product.snapshot(server)['profile']['height_cm'],168)

    def test_explicit_continue_after_correction_pause_resumes_assessment(self):
        self.assessment()
        self.output={'reply':'身高按168厘米理解。','decision':{'action':'none'},'plan':None}
        self.chat('更正身高168厘米，之前175记错了。')
        self.chat('继续做方案。')
        self.assertIn('plan_readiness',json.loads(self.prompt[1]['content']))
        self.assertTrue(product.workspace(server)['sessions']['test-conversation']['interview_request'])

    def test_requested_schedule_answer_still_continues_assessment(self):
        self.assessment('你通常几点上班、几点下班？')
        self.output={'reply':'明白。','decision':{'action':'none'},'plan':None}
        self.chat('现在下午三点到晚上十一点上班。')
        self.assertIn('plan_readiness',json.loads(self.prompt[1]['content']))
        self.assertTrue(product.workspace(server)['sessions']['test-conversation']['interview_request'])

    def test_initial_grouped_basic_answer_still_continues_assessment(self):
        self.assessment('你的年龄、身高和性别是什么？')
        server.save_json(server.PROFILE,{})
        self.output={'reply':'明白。','decision':{'action':'none'},'plan':None}
        self.chat('38岁，男，175厘米。')
        self.assertIn('plan_readiness',json.loads(self.prompt[1]['content']))


if __name__=='__main__':unittest.main()
