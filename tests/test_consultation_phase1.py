"""Phase-one regressions: scoped consultation, durable summary and memory."""
import json
import unittest
from unittest.mock import patch

import consultation
import product
import server
import test_workbench


class ConsultationPhaseOneTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def complete_profile(self):
        server.save_json(server.PROFILE,{
            'age':38,'sex':'男','height_cm':172,'goals':'先改善晚餐并稳步减重',
            'preferences':'工作日晚餐容易吃多','conditions':['没有确诊疾病或近期不适'],
            'medications':['没有'],'allergies':['没有'],'dinner_habit':'一碗米饭、一份炒菜和一杯饮料',
            'activity_baseline':'白天久坐，每周散步两次','available_time':'晚饭后20分钟',
            'weight_history':'近三个月体重基本稳定，以前节食很难坚持',
            'surgeries':['没有'],'breakfast_habit':'两个鸡蛋和一杯牛奶',
            'lunch_habit':'一碗米饭和一份炒菜','snacks_drinks':'不喝含糖饮料，不吃零食',
            'sleep_schedule':'23点睡7点起',
        })
        server.save_json(server.RECORDS,[{
            'id':'record-weight','type':'weight','value':{'kg':100},'status':'confirmed',
            'memory_enabled':True,'observed_at':'2026-09-23T08:00:00',
        }])

    def plan_output(self, reply='可以先从一个晚餐习惯开始。'):
        return {'reply':reply,'decision':{'action':'update','reason':'已具备制定阶段行动的必要信息'},
            'plan':{'title':'一周晚餐试行','goal':'改善晚餐并观察饥饿感','duration_days':7,
                'items':[{'title':'记录晚餐后的感受','detail':'晚餐后记一句饥饿或饱腹感',
                          'when':'每天·晚餐后','minimum':'只记一句','basis_record_ids':[]}]}}

    def test_request_classification_keeps_education_and_meal_out_of_full_intake(self):
        self.assertEqual(consultation.decision_kind('减肥期间可以喝牛奶吗？'),'general')
        self.assertEqual(consultation.decision_kind('早餐一杯牛奶两个鸡蛋'),'meal')
        self.assertEqual(consultation.decision_kind('请为我制定一周减重方案'),'personal_weight_plan')
        self.assertEqual(consultation.required_information('general',{},[]),{})

    def test_formal_weight_plan_requires_durable_summary_confirmation(self):
        self.complete_profile();self.output=self.plan_output()
        first=self.chat('请为我制定一周减重方案')
        self.assertIsNone(first['plan'])
        self.assertIn('请核对我理解的情况',first['reply'])
        pending=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(pending['status'],'pending')
        self.assertTrue(pending['digest'])

        self.output=self.plan_output('收到确认，开始整理一周行动。')
        second=self.chat('确认',mid='summary-confirmed')
        self.assertIsNotNone(second['plan'])
        confirmed=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(confirmed['status'],'confirmed')
        self.assertEqual(second['request_kind'],'general')
        self.assertIn('本轮必须推进到可保存的一周行动方案',self.prompt[0]['content'])

    def test_personal_plan_does_not_require_entire_legacy_profile(self):
        self.complete_profile();w=product.workspace(server)
        w['interview']={'skipped':[]}
        w['assessment_state']['answered_topics']={'goal_barrier':{'text':'先改善晚餐'},
            'meal_pattern':{'text':'已说明三餐'},'sleep_activity':{'text':'已说明作息和活动'}}
        server.save_json(server.DATA/'workspace.json',w)
        self.output=self.plan_output()
        first=self.chat('请为我制定一周减重方案，明天开始')
        self.assertIn('请核对我理解的情况',first['reply'])
        second=self.chat('确认')
        self.assertIsNotNone(second['plan'])
        self.assertTrue(second['plan']['items'])

    def test_confirmation_with_prose_only_stays_resumable(self):
        self.complete_profile()
        self.chat('请为我制定一周减重方案，明天开始')
        self.output={'reply':'情况已确认，我们接着改善晚餐。','decision':{'action':'none'},'plan':None}
        answer=self.chat('确认')
        self.assertIsNone(answer['plan'])
        self.assertEqual(answer['ai_error'],'AI_PLAN_MISSING')
        self.assertTrue(answer['retry_chat'])
        self.assertIn('无需重新填写',answer['reply'])

    def test_all_meals_volunteered_to_breakfast_question_stay_separate(self):
        w=product.workspace(server)
        w['sessions']['test-conversation'].update(asked_field='breakfast_habit',interview_request=True,
            dialogue_mode='assessment',consultation_kind='personal_weight_plan',request='我想减肥')
        server.save_json(server.DATA/'workspace.json',w)
        self.chat('早餐两个鸡蛋一杯牛奶；午餐一碗米饭和蔬菜；晚餐一盒炒面。')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile['breakfast_habit'],'早餐两个鸡蛋一杯牛奶')
        self.assertEqual(profile['lunch_habit'],'午餐一碗米饭和蔬菜')
        self.assertEqual(profile['dinner_habit'],'晚餐一盒炒面')

    def test_fact_correction_invalidates_summary_and_keeps_source_history(self):
        self.complete_profile();w=product.workspace(server)
        digest=consultation.facts_digest(server.load_json(server.PROFILE,{}),server.records())
        w['assessment_state']['summary_confirmation']={'status':'confirmed','digest':digest,
            'summary':'旧摘要','confirmed_at':'2026-09-23T09:00:00'}
        w['profile_sources']['age']={'status':'confirmed','at':'2026-09-23T08:00:00','text':'我38岁'}
        server.save_json(server.DATA/'workspace.json',w)
        self.output={'reply':'收到，年龄已按你的更正处理。','decision':{'action':'none'},'plan':None}
        self.chat('刚才说错了，我今年39岁')
        state=product.snapshot(server)
        self.assertEqual(state['profile']['age'],39)
        self.assertEqual(state['profile_history'][-1]['value'],38)
        self.assertEqual(state['profile_history'][-1]['status'],'corrected')
        confirmation=consultation.confirmation_state(product.workspace(server)['assessment_state'],state['profile'],state['records'])
        self.assertEqual(confirmation['status'],'stale')
        self.assertFalse(confirmation['confirmed'])

    def test_weight_saved_in_summary_turn_can_be_confirmed_once(self):
        self.complete_profile();self.output=self.plan_output()
        first=self.chat('今天体重95公斤，请制定一周减重方案，明天开始')
        self.assertIsNone(first['plan'])
        self.assertIn('95.0公斤',first['reply'])
        state=product.snapshot(server)
        self.assertEqual(len(state['records']),2)
        confirmation=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(confirmation['digest'],consultation.facts_digest(state['profile'],state['records']))
        second=self.chat('确认')
        self.assertIsNotNone(second['plan'])
        self.assertEqual(product.workspace(server)['assessment_state']['summary_confirmation']['status'],'confirmed')

    def test_model_weight_is_validated_before_binding_summary(self):
        self.complete_profile();server.save_json(server.RECORDS,[])
        self.output=self.plan_output()
        self.output['record_events']=[{'type':'weight','value':{'kg':95},'evidence':'称重结果九十五公斤'}]
        first=self.chat('请制定一周减重方案，明天开始；称重结果九十五公斤')
        self.assertIn('95.0公斤',first['reply'])
        state=product.snapshot(server)
        self.assertEqual(len(state['records']),1)
        confirmation=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(confirmation['digest'],consultation.facts_digest(state['profile'],state['records']))
        self.output=self.plan_output()
        self.assertIsNotNone(self.chat('确认')['plan'])

    def test_retry_resumes_guidance_after_target_only_goal_and_timeout(self):
        self.complete_profile()
        profile=server.load_json(server.PROFILE,{})
        profile.pop('weight_history')
        server.save_json(server.PROFILE,profile)
        w=product.workspace(server)
        w['sessions']['test-conversation']={'consultation_kind':'personal_weight_plan',
            'request':'想减到78公斤','interview_request':True,'dialogue_mode':'assessment','guidance_policy':1}
        server.save_json(server.DATA/'workspace.json',w)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'role':'user','text':'想减到78公斤'},{'role':'assistant','text':'你平时主要久坐还是走动？'}]}])
        self.output={'reply':'','decision':{'action':'none'},'plan':None}
        with patch.object(server,'ai_meta',return_value={'ai_status':'fallback','ai_error':'AI_TIMEOUT'}):
            failed=self.chat('我现在100公斤，办公室久坐')
        self.assertTrue(failed['retry_chat'])
        record_count=len(server.records())
        self.output={'reply':'可以接着了解。','decision':{'action':'none'},'plan':None}
        with patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            resumed=self.chat('继续这次请求',retry_chat=failed['retry_chat'])
        self.assertIn('最近几个月',resumed['reply'])
        self.assertEqual(len(server.records()),record_count)
        self.assertEqual(product.workspace(server)['sessions']['test-conversation']['dialogue_mode'],'assessment')

    def test_complete_durable_intake_shows_summary_when_model_is_unavailable(self):
        self.complete_profile()
        with patch.object(server,'call_ai',side_effect=TimeoutError('service unavailable')) as call:
            first=product.chat(server,{'text':'请为我制定一周减重方案',
                'conversation_id':'test-conversation','client_message_id':'local-summary-1'})
        call.assert_not_called()
        self.assertIsNone(first['ai_error'])
        self.assertIsNone(first['plan'])
        self.assertIn('请核对我理解的情况',first['reply'])
        state=product.snapshot(server)
        pending=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(pending['digest'],consultation.facts_digest(state['profile'],state['records']))
        self.output=self.plan_output()
        self.assertIsNotNone(self.chat('确认')['plan'])

    def seed_pending_preference(self):
        self.complete_profile()
        w=product.workspace(server)
        w['pending'].append({'id':'pending-preference','kind':'profile','field':'preferences',
            'old':'工作日晚餐容易吃多','value':'需要方便的外卖选择','evidence':'需要方便的外卖选择',
            'source':{'conversation_id':'test-conversation','message_id':'prior-user-message',
                      'text':'需要方便的外卖选择','at':'2026-10-08T10:00:00'}})
        server.save_json(server.DATA/'workspace.json',w)

    def test_pending_fact_is_resolved_in_conversation_before_summary(self):
        self.seed_pending_preference()
        first=self.chat('请为我制定一周减重方案')
        self.assertIn('保留原记录',first['reply'])
        self.assertIn('工作日晚餐容易吃多',first['reply'])
        self.assertIn('需要方便的外卖选择',first['reply'])
        self.assertIsNone(first['plan'])
        self.assertEqual(self.prompt,[])
        # A summary acknowledgement does not approve a different pending fact.
        self.assertIn('用新记录',self.chat('确认')['reply'])
        self.assertEqual(len(product.workspace(server)['pending']),1)
        second=self.chat('保留原记录')
        self.assertIn('请核对我理解的情况',second['reply'])
        self.assertEqual(product.snapshot(server)['profile']['preferences'],'工作日晚餐容易吃多')
        self.assertEqual(product.workspace(server)['pending'],[])
        self.output=self.plan_output()
        self.assertIsNotNone(self.chat('确认')['plan'])

    def test_pending_fact_acceptance_requires_its_question_in_same_conversation(self):
        self.seed_pending_preference()
        self.chat('请为我制定一周减重方案')
        self.chat('用新记录',conversation_id='other-conversation')
        self.assertEqual(len(product.workspace(server)['pending']),1)
        second=self.chat('用新记录')
        self.assertIn('请核对我理解的情况',second['reply'])
        self.assertIn('需要方便的外卖选择',second['reply'])
        self.assertEqual(product.snapshot(server)['profile']['preferences'],'需要方便的外卖选择')
        self.assertEqual(product.workspace(server)['pending'],[])
        self.output=self.plan_output()
        self.assertIsNotNone(self.chat('确认')['plan'])

    def test_meal_description_does_not_replace_saved_preference(self):
        self.complete_profile()
        self.output={'reply':'这餐次情况收到。','decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':'preferences','value':'晚餐经常一份外卖炒面',
                               'evidence':'晚餐经常一份外卖炒面'}]}
        self.chat('晚餐经常一份外卖炒面')
        state=product.snapshot(server)
        self.assertEqual(state['profile']['preferences'],'工作日晚餐容易吃多')
        self.assertFalse(any(x.get('field')=='preferences' for x in state['pending']))

    def test_explicit_no_medication_is_saved_without_model_extraction(self):
        self.chat('没有确诊疾病，没有用药，没有手术史，没有食物过敏。')
        self.assertEqual(product.snapshot(server)['profile']['medications'],['没有用药'])

    def test_volunteered_meal_is_not_saved_as_medication_answer(self):
        self.complete_profile()
        profile=server.load_json(server.PROFILE,{})
        profile.pop('medications');server.save_json(server.PROFILE,profile)
        w=product.workspace(server)
        w['sessions']['test-conversation'].update(asked_field='medications',interview_request=True,
            dialogue_mode='assessment',consultation_kind='personal_weight_plan',request='我想减肥')
        server.save_json(server.DATA/'workspace.json',w)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'role':'assistant','text':'目前有没有在用药物或保健品？'}]}])
        self.chat('早餐两个鸡蛋一杯牛奶；午餐吃米饭和蔬菜。')
        state=product.snapshot(server)
        self.assertNotIn('medications',state['profile'])
        self.assertFalse(any(x.get('field')=='medications' for x in state['pending']))

    def test_mixed_routine_answer_keeps_sleep_and_work_separate(self):
        w=product.workspace(server)
        w['sessions']['test-conversation'].update(asked_field='sleep_schedule',interview_request=True,
            dialogue_mode='assessment',consultation_kind='personal_weight_plan',request='我想减肥')
        server.save_json(server.DATA/'workspace.json',w)
        self.chat('平时凌晨一点睡，早上七点起。办公室久坐，晚上八点下班，每天可以抽20分钟活动。')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile['sleep_schedule'],'平时凌晨一点睡，早上七点起')
        self.assertEqual(profile['occupation'],'办公室久坐')

    def test_confirmation_in_another_conversation_does_not_approve_summary(self):
        self.complete_profile();self.output=self.plan_output()
        self.chat('请为我制定一周减重方案')
        self.output=self.plan_output('未经请求给出整套建议。')
        answer=self.chat('可以',conversation_id='other-conversation')
        self.assertEqual(answer['ai_status'],'local')
        self.assertIsNone(answer['plan'])
        self.assertIn('还没有待确认的内容',answer['reply'])
        self.assertEqual(self.prompt,[])
        state=product.workspace(server)['assessment_state']['summary_confirmation']
        self.assertEqual(state['status'],'pending')
        self.assertNotIn('confirmed_by',state)

    def test_yes_to_unrelated_question_does_not_reopen_plan_confirmation(self):
        self.complete_profile();self.output=self.plan_output()
        self.chat('请为我制定一周减重方案')
        self.output={'reply':'你要先聊聊牛奶的选择吗？','decision':{'action':'none'},'plan':None}
        self.chat('减肥期间可以喝牛奶吗？')
        self.output=self.plan_output()
        answer=self.chat('可以')
        self.assertIsNone(answer['plan'])
        self.assertEqual(product.workspace(server)['assessment_state']['summary_confirmation']['status'],'pending')
        self.assertNotIn('请核对我理解的情况',answer['reply'])

    def test_summary_can_be_confirmed_after_returning_to_its_conversation(self):
        self.complete_profile();self.output=self.plan_output()
        self.chat('请为我制定一周减重方案')
        self.output={'reply':'可以按口味选择。','decision':{'action':'none'},'plan':None}
        self.chat('牛奶怎么选？',conversation_id='other-conversation')
        self.output=self.plan_output()
        answer=self.chat('确认')
        self.assertIsNotNone(answer['plan'])

    def test_explicit_retraction_removes_current_fact_but_keeps_audit_history(self):
        self.complete_profile();w=product.workspace(server)
        w['profile_sources']['allergies']={'status':'confirmed','at':'2026-09-23T08:00:00','text':'没有过敏'}
        server.save_json(server.DATA/'workspace.json',w)
        self.output={'reply':'好的，后续不再把这项当作当前事实。','decision':{'action':'none'},'plan':None}
        self.chat('请撤回并删除我的过敏信息')
        state=product.snapshot(server)
        self.assertNotIn('allergies',state['profile'])
        self.assertEqual(state['profile_history'][-1]['field'],'allergies')
        self.assertEqual(state['profile_history'][-1]['status'],'retracted')

    def test_general_question_does_not_consume_pending_assessment_topic(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'你最容易在哪个时段卡住？','decision':{'action':'clarify','question_topic':'goal_barrier'},'plan':None}
        self.chat('我想减肥，请给我计划')
        self.output={'reply':'可以喝；如果乳糖不耐受，可按实际反应选择无乳糖奶。','decision':{'action':'none'},'plan':None}
        result=self.chat('减肥期间可以喝牛奶吗？')
        self.assertEqual(result['request_kind'],'general')
        self.assertEqual(result['reply'],self.output['reply'])
        state=product.workspace(server)['assessment_state']
        self.assertNotIn('goal_barrier',state.get('answered_topics',{}))
        self.assertIn('哪个时段',state['next_question']['text'])

    def test_invalid_background_plan_keeps_safe_natural_reply(self):
        output={'reply':'你可以先记录三天最难处理的餐次，再决定改哪里。',
                'decision':{'action':'update','reason':'尝试整理'},
                'plan':{'title':'损坏计划','goal':'观察','items':[]}}
        with patch.object(server,'call_ai',return_value=json.dumps(output,ensure_ascii=False)):
            result=product.chat(server,{'text':'请先给初步计划','conversation_id':'phase-one',
                'client_message_id':'background-failure'})
        self.assertIn('先记录三天',result['reply'])
        self.assertIn('后台整理未完成',result['reply'])
        self.assertEqual(result['background']['status'],'failed')
        self.assertIn('model_structuring',result['background']['failed_operations'])
        self.assertIsNone(result['plan'])


if __name__=='__main__':
    unittest.main()
