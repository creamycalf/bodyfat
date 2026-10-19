"""Arithmetic follow-ups avoid transport without swallowing health questions."""
import unittest
import json
import product
import server
import nutrition_reports
import test_workbench


class LocalPhotoCalculationTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def seed(self,partial=False):
        foods=[{'name':'餐食','nutrition_basis':'portion_estimate',
                'nutrition':{'kcal':[600,900],**({} if partial else {
                    'protein_g':[30,45],'carbs_g':[60,90],'fat_g':[0,0]})}}]
        if partial:foods.append({'name':'另一项未知食物'})
        server.save_json(server.MEDIA,[{'id':'meal-photo','type':'food','review':{
            'summary':'测试照片报告','report':nutrition_reports.food_report({'foods':foods})}}])

    def test_numeric_question_is_local_correct_idempotent_and_does_not_log_intake(self):
        self.seed()
        for text in ('如果这份只吃一半，热量和蛋白质各是多少？只是分析，不要记录。',
                     '只吃这份的1/2，热量和蛋白质分别是多少？',
                     '请算一下这份的50%，热量和营养是多少？'):
            with self.subTest(text=text):
                result=self.chat(text,media_id='meal-photo')
                self.assertEqual(self.prompt,[])
                self.assertEqual(result.get('reply_source'),'portion_calculator')
                self.assertEqual(result['reply'].count('按照片中各组成同比例'),1)
                self.assertIn('300–450',result['reply']);self.assertIn('15–22.5',result['reply'])
                self.assertFalse(server.records())

    def test_partial_report_stays_partial_and_unknown_does_not_become_zero(self):
        self.seed(partial=True)
        result=self.chat('这份只吃一半，热量和蛋白质是多少？',media_id='meal-photo')
        self.assertEqual(self.prompt,[])
        self.assertIn('仅已估算部分，不是整餐总量',result['reply'])
        self.assertIn('蛋白质',result['reply']);self.assertIn('未知，不能按零计算',result['reply'])
        self.assertNotIn('蛋白质约 0',result['reply'])

    def test_whole_plate_restatement_and_natural_followup_keep_photo_context(self):
        self.seed()
        result=self.chat('这份热量和蛋白质各是多少？',media_id='meal-photo')
        self.assertEqual(self.prompt,[]);self.assertIn('600–900',result['reply']);self.assertIn('30–45',result['reply'])
        self.assertFalse(result.get('ai_error'))
        self.output['reply']='这份照片可作参考，还需结合全天饮食判断是否足够。'
        self.chat('蛋白质够吗？')
        facts=json.loads(self.prompt[1]['content'])
        self.assertEqual(facts['linked_images'][0]['id'],'meal-photo')
        self.chat('我昨晚睡得不好。')
        self.chat('蛋白质够吗？')
        self.assertEqual(json.loads(self.prompt[1]['content'])['linked_images'],[])

    def test_disabled_media_is_excluded_but_dismissed_intake_can_still_be_analyzed(self):
        self.seed()
        media=server.load_json(server.MEDIA,[])
        for flag in ({'memory_enabled':False},{'status':'retracted'},{'status':'deleted'}):
            with self.subTest(flag=flag):
                server.save_json(server.MEDIA,[{**media[0],**flag}])
                result=self.chat('这份热量多少？',media_id='meal-photo')
                self.assertTrue(self.prompt)
                self.assertNotEqual(result.get('reply_source'),'portion_calculator')
                self.assertEqual(json.loads(self.prompt[1]['content'])['linked_images'],[])
        server.save_json(server.MEDIA,[{**media[0],'review_status':'dismissed'}])
        result=self.chat('这份热量多少？',media_id='meal-photo')
        self.assertEqual(self.prompt,[]);self.assertIn('600–900',result['reply'])

    def test_existing_allergen_warning_is_kept_in_local_answer(self):
        self.seed();server.save_json(server.PROFILE,{'allergies':['对花生过敏']})
        result=self.chat('这份只吃一半，热量是多少？',media_id='meal-photo')
        self.assertEqual(self.prompt,[]);self.assertIn('花生',result['reply'])
        self.assertIn('份量换算不能判断',result['reply'])

    def test_followup_keeps_the_last_calculated_share_without_trusting_model_numbers(self):
        self.seed()
        result=self.chat('这份只吃一半，蛋白质多少？',media_id='meal-photo')
        self.assertEqual(result['photo_calculation']['fraction'],'1/2')
        self.output['reply']='这份一半蛋白质约15–22.5克，是否足够还要结合全天饮食。'
        for text in ('蛋白质够吗？','脂肪会不会太多？'):
            with self.subTest(text=text):
                result=self.chat(text)
                self.assertTrue(self.prompt)
                self.assertIn('蛋白质约 15–22.5 克',result['reply'])
                self.assertEqual(result['photo_calculation']['fraction'],'1/2')
        self.chat('先不聊吃的，我昨晚睡得不好。')
        result=self.chat('蛋白质够吗？')
        self.assertNotIn('photo_calculation',result)

    def test_disabled_calculation_source_is_not_reused(self):
        self.seed()
        self.chat('这份只吃一半，蛋白质多少？',media_id='meal-photo')
        conversations=server.load_json(server.CONVERSATIONS,[])
        conversations[0]['messages'][-2]['memory_enabled']=False
        server.save_json(server.CONVERSATIONS,conversations)
        result=self.chat('蛋白质够吗？')
        self.assertNotIn('photo_calculation',result)
        self.assertNotIn('按照片中各组成同比例吃一半估算',result['reply'])

    def test_richer_questions_actual_intake_and_volunteered_facts_use_normal_flow(self):
        self.seed()
        for text in ('这份只吃一半热量多少，能减肥吗？',
                     '这份只吃一半热量多少，我有糖尿病可以这样吃吗？',
                     '这份只吃一半热量多少，还需要补什么？',
                     '这份我吃了一半，热量多少，请记录。',
                     '这份只吃一半热量多少，我40岁。'):
            with self.subTest(text=text):
                result=self.chat(text,media_id='meal-photo')
                self.assertTrue(self.prompt)
                self.assertNotEqual(result.get('reply_source'),'portion_calculator')

    def test_unclear_share_or_no_linked_photo_does_not_use_local_calculation(self):
        self.seed()
        for text in ('米饭吃一半，配菜全吃，热量多少？','这份只吃一点热量多少？'):
            with self.subTest(text=text):
                result=self.chat(text,media_id='meal-photo')
                self.assertTrue(self.prompt)
                self.assertNotEqual(result.get('reply_source'),'portion_calculator')
        server.save_json(server.DATA/'workspace.json',{})
        result=self.chat('如果这份只吃一半，热量多少？',conversation_id='no-photo')
        self.assertTrue(self.prompt)
        self.assertNotEqual(result.get('reply_source'),'portion_calculator')


if __name__=='__main__':unittest.main()
