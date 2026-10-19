"""Pacing survives followups and cannot authorize plan mutations implicitly."""
import json
import unittest
from unittest.mock import patch
import product
import server
import test_workbench


class ConversationPacingTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchTests.setUp
    tearDown = test_workbench.WorkbenchTests.tearDown
    chat = test_workbench.WorkbenchTests.chat

    def fresh(self):
        server.save_json(server.DATA/'workspace.json', {})

    def say(self, text):
        self.output = {'reply':text, 'decision':{'action':'none'}, 'plan':None}

    def test_goal_starts_guidance_without_premature_plan(self):
        self.fresh()
        text='你更在意体重数字，还是最近身体的感受？'
        self.say(text)
        answer=self.chat('我想减肥')
        self.assertEqual(answer['reply'],text)
        self.assertIn('plan_readiness',self.prompt[1]['content'])
        self.assertIsNone(answer['plan'])

    def test_guidance_keeps_asking_after_answers_when_model_stalls(self):
        self.fresh();self.say('可以聊聊，你的情况我了解了。')
        first=self.chat('我想减肥')
        self.assertIn('年龄',first['reply'])
        second=self.chat('38岁')
        self.assertIn('性别',second['reply'])
        third=self.chat('男')
        self.assertIn('身高',third['reply'])
        fourth=self.chat('身高175厘米，体重85公斤')
        self.assertNotIn('身高是多少',fourth['reply'])
        self.assertIn('？',fourth['reply'])
        self.assertIsNone(fourth['plan'])
        self.assertEqual(product.snapshot(server)['profile']['age'],38)

    def test_old_passive_goal_session_resumes_guidance_on_upgrade(self):
        self.fresh();w=product.workspace(server)
        w['sessions']['test-conversation']={'dialogue_mode':'chat','consultation_kind':'personal_weight_plan','request':'我想减肥'}
        server.save_json(server.DATA/'workspace.json',w)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'role':'user','text':'我想减肥'},{'role':'assistant','text':'可以先聊聊你的感受。'}]}])
        self.say('可以继续聊。')
        answer=self.chat('继续')
        self.assertIn('年龄',answer['reply'])
        self.assertIn('plan_readiness',self.prompt[1]['content'])

    def test_guidance_retains_volunteered_goal_and_routine_details(self):
        self.fresh();self.say('你今年多大？');self.chat('我想减肥')
        self.say('有没有确诊疾病？')
        self.chat('我38岁，男，身高175厘米，体重85公斤，想先减到78公斤，最难是加班后吃多，常吃外卖。')
        saved=product.snapshot(server)['profile']
        self.assertIn('78公斤',saved['goals'])
        self.assertNotIn('occupation',saved)
        patch,events=product.explicit_facts(server,'平时凌晨一点睡，早上七点起。办公室久坐，一天走路约20分钟，晚上八点下班，每天可以抽20分钟活动。')
        self.assertEqual(patch['sleep_schedule'],'平时凌晨一点睡，早上七点起')
        self.assertEqual(patch['occupation'],'办公室久坐')
        self.assertEqual(patch['activity_baseline'],'一天走路约20分钟')
        self.assertEqual(patch['work_schedule'],'晚上八点下班')
        self.assertEqual(patch['available_time'],'每天可以抽20分钟活动')

    def test_explain_then_continue_does_not_resume_interview(self):
        self.fresh();self.say('以前最难坚持的是什么？')
        self.chat('我想瘦一点，先聊聊')
        self.say('两餐间隔和餐量都可能影响饥饿感，仅凭时间还不能确定原因。')
        self.chat('先解释原因，别给安排')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'explain')
        self.chat('继续')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'explain')
        self.assertNotIn('plan_readiness',self.prompt[1]['content'])
        self.chat('我想先知道，为什么会这样？')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'explain')
        self.chat('接着说，先不要给办法')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'explain')
        self.chat('换个话题，食品标签是什么意思？')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'discuss')
        self.chat('现在给我一点建议')
        self.assertEqual(json.loads(self.prompt[1]['content'])['reply_focus'],'discuss')

    def test_chat_can_interrupt_assessment_and_explicitly_resume(self):
        self.fresh();self.say('你今年多大？')
        self.chat('请制定减重方案')
        self.assertIn('plan_readiness',self.prompt[1]['content'])
        text='可以，先说说这件事让你困扰的地方。'
        self.say(text)
        self.assertEqual(self.chat('先聊聊，不急着做方案')['reply'],text)
        self.chat('我今年41岁')
        self.assertEqual(product.snapshot(server)['profile']['age'],41)
        self.assertNotIn('plan_readiness',self.prompt[1]['content'])
        self.chat('现在请帮我制定减重方案')
        self.assertIn('plan_readiness',self.prompt[1]['content'])

    def test_chat_blocks_unsolicited_plan_and_page_with_existing_plan(self):
        self.fresh();w=product.workspace(server)
        w['plans']=[{'id':'existing','status':'active','goal':'原目标','items':[],'actions':[],
                     'start_date':product.today(),'end_date':product.today(),'duration_days':7}]
        server.save_json(server.DATA/'workspace.json',w)
        self.say('先聊你的困难。')
        self.output.update(plan={'title':'不请自来的方案'},page_changes=[{'page':'plan','body':'偷偷改动'}])
        self.output['decision']={'action':'update','reason':'模型自作主张'}
        answer=self.chat('先聊聊，不急着安排')
        self.assertIsNone(answer['plan'])
        self.assertEqual(product.workspace(server)['plans'],w['plans'])
        self.assertEqual(answer['page_updates'],[])

    def test_correction_does_not_force_followup(self):
        self.fresh();self.say('可以先聊。')
        self.chat('我想减重，先聊聊')
        text='明白，你说的是周六，不是周日。'
        self.say(text)
        self.assertEqual(self.chat('更正，是周六，只回应这个更正')['reply'],text)
        self.assertNotIn('plan_readiness',self.prompt[1]['content'])

    def test_reply_and_explicit_facts_return_in_one_call(self):
        self.fresh()
        utterance='先聊聊，我每天晚上八点下班'
        extraction={'reply':'下班后最让你困扰的是什么？','decision':{'action':'none'},
                    'profile_changes':[{'field':'work_schedule','value':'每天晚上八点下班',
                                        'evidence':'我每天晚上八点下班'}],
                    'plan':{'title':'ignored'},'page_changes':[{'page':'plan'}]}
        with patch.object(server,'call_ai',return_value=json.dumps(extraction)) as call:
            answer=product.chat(server,{'text':utterance,'conversation_id':'split-chat','client_message_id':'split-message-1'})
        self.assertEqual(answer['reply'],'下班后最让你困扰的是什么？')
        self.assertIsNone(answer['plan'])
        self.assertEqual(call.call_count,1)
        self.assertTrue(call.call_args.args[0][-1]['content'].startswith(utterance))
        self.assertIn('profile_changes',call.call_args.args[0][-1]['content'])
        self.assertNotIn(answer['reply'],str(call.call_args.args[0]))
        self.assertIn('每天晚上八点下班',product.snapshot(server)['profile']['work_schedule'])

    def test_legacy_plain_reply_is_preserved_without_second_request(self):
        self.fresh()
        with patch.object(server,'call_ai',return_value='可以，我们先聊你的感受。') as call, \
             patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            answer=product.chat(server,{'text':'我想减重，先聊聊','conversation_id':'split-chat','client_message_id':'split-failed'})
        self.assertEqual(answer['reply'],'可以，我们先聊你的感受。')
        self.assertIsNone(answer['ai_error'])
        self.assertTrue(any('模型未返回资料整理结构' in item for item in answer['receipts']))
        self.assertEqual(call.call_count,1)
        self.assertIsNone(answer['plan'])

    def test_model_reply_is_not_evidence_for_profile_change(self):
        self.fresh()
        output={'reply':'你可能每天晚上八点下班。','decision':{'action':'none'},'plan':None,
                'profile_changes':[{'field':'work_schedule','value':'每天晚上八点下班',
                                    'evidence':'每天晚上八点下班'}]}
        with patch.object(server,'call_ai',return_value=json.dumps(output)):
            product.chat(server,{'text':'先聊聊我的生活','conversation_id':'single-call-chat','client_message_id':'single-call-no-inference'})
        self.assertNotIn('work_schedule',product.snapshot(server)['profile'])


if __name__ == '__main__':
    unittest.main()
