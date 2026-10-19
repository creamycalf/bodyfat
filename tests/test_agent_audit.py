"""Regressions found by adversarial usage of 0.4.39, isolated fictional data."""
import unittest
import product
import server
import test_workbench
import consultation

class AgentAuditTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_friend_mention_does_not_discard_separate_self_facts(self):
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'会结合你的身高、膝盖情况和过敏来讨论。','plan':None,
            'decision':{'action':'none'},'profile_changes':[
                {'field':'conditions','value':['膝盖旧伤，跑步会疼'],'evidence':'我膝盖有旧伤，跑步会疼'},
                {'field':'allergies','value':['花生'],'evidence':'对花生过敏'}]}
        self.chat('我男，38岁，身高175厘米，体重85公斤。我朋友推荐跑步，但我膝盖有旧伤，跑步会疼。对花生过敏。')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile.get('age'),38)
        self.assertEqual(profile.get('height_cm'),175)
        self.assertEqual(profile.get('sex'),'男')
        self.assertIn('膝盖',str(profile.get('conditions')))
        self.assertIn('花生',str(profile.get('allergies')))
        self.assertEqual(server.records()[0]['value']['kg'],85)

    def test_third_party_and_hypothetical_still_never_become_self_facts(self):
        self.output={'reply':'会区分你和朋友的情况。','decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':'age','value':50,'evidence':'50岁'},
                               {'field':'conditions','value':['糖尿病'],'evidence':'糖尿病'}]}
        for text in ('朋友50岁，有糖尿病。','如果我50岁有糖尿病，应该怎么办？',
                     '我的朋友说：“我50岁，有糖尿病。”','不要保存：我50岁，有糖尿病。'):
            server.save_json(server.PROFILE,{})
            self.chat(text)
            self.assertEqual(product.snapshot(server)['profile'],{})

    def test_other_person_scope_persists_until_explicit_self_subject(self):
        self.assertEqual(product.self_fact_text('我朋友50岁。有糖尿病，身高180厘米。'),'')
        own=product.self_fact_text('我朋友50岁，有糖尿病。但我38岁，身高175厘米。')
        self.assertNotIn('50',own);self.assertNotIn('糖尿病',own)
        self.assertIn('38岁',own);self.assertIn('175厘米',own)

    def test_injury_question_does_not_become_declined_weight_questionnaire(self):
        server.save_json(server.DATA/'workspace.json',{})
        text='我38岁，男，175厘米，85公斤。想开始健身，每天20分钟，家里没有器械，膝盖旧伤下蹲会痛。请给一个适合的起步方向，不要先让我填减肥问卷。'
        useful='先避开诱发膝痛的动作，可以讨论不痛的上肢与核心练习。膝盖是否肿胀、卡住，平地走路是否也痛？'
        self.output={'reply':useful,'decision':{'action':'clarify'},'plan':None}
        answer=self.chat(text)
        self.assertEqual(consultation.decision_kind(text),'general')
        self.assertIn('膝',answer['reply']);self.assertIn('核心',answer['reply'])
        self.assertNotIn('公斤或斤',answer['reply'])
        self.assertNotIn('基础信息弄清楚',answer['reply'])
        self.assertIn('膝盖',str(product.snapshot(server)['profile'].get('conditions')))

    def test_known_weight_question_does_not_leave_orphan_unit_instruction(self):
        reply=consultation.remove_answered_questions('最近一次体重是多少？请带公斤或斤。可以继续聊膝盖。',{},
            [{'type':'weight','value':{'kg':85},'confirmed':True}])
        self.assertEqual(reply,'可以继续聊膝盖。')

    def test_meal_habits_are_saved_under_their_own_meal(self):
        self.output={'reply':'会结合食堂和做饭条件讨论。','decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':field,'value':'午餐只能食堂，晚餐自己做。','evidence':'午餐只能食堂，晚餐自己做。'}
                               for field in ('lunch_habit','dinner_habit')]}
        self.chat('午餐只能食堂，晚餐自己做。')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile['lunch_habit'],'午餐只能食堂')
        self.assertEqual(profile['dinner_habit'],'晚餐自己做')

    def food(self,partial=False):
        raw={'category':'food','summary':'测试餐盘','foods':[{'name':'米饭配菜',
             'nutrition_basis':'portion_estimate','nutrition':{'kcal':[500,700],'protein_g':[20,30]}}]}
        if partial:raw['foods'].append({'name':'看不清的配菜'})
        review=server.normalize_image_analysis(raw,'food')
        server.save_json(server.MEDIA,[{'id':'food-1','type':'food','review':review,'confirmed':False}])
        self.output={'reply':'按照片整份估计，半份热量250–350千卡，蛋白质10–15克。',
            'decision':{'action':'none'},'plan':None}

    def test_photo_half_estimate_survives_without_creating_intake(self):
        self.food()
        answer=self.chat('如果这份只吃一半，热量和蛋白质范围是多少？只是分析，不要记录。',media_id='food-1')
        self.assertIsNone(answer.get('ai_error'))
        self.assertIn('250',answer['reply']);self.assertIn('350',answer['reply'])
        self.assertIn('10',answer['reply']);self.assertIn('15',answer['reply'])
        self.assertFalse(server.records())

    def test_photo_partial_range_is_never_called_whole_meal(self):
        self.food(partial=True)
        answer=self.chat('如果这份只吃一半，热量是多少？',media_id='food-1')
        self.assertIn('部分',answer['reply'])
        self.assertIn('不是',answer['reply'])
        self.assertFalse(server.records())

    def test_half_of_one_ingredient_does_not_scale_entire_plate(self):
        self.food()
        self.output['reply']='只减少米饭无法直接把整餐热量除以二，需要分清食物组成。'
        answer=self.chat('这份米饭只吃一半，配菜全吃，热量是多少？',media_id='food-1')
        self.assertNotIn('250',answer['reply'])
        self.assertFalse(server.records())

if __name__=='__main__':unittest.main()
