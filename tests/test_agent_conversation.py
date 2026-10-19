"""User journeys: bundled intake, durable memory and advice-first images."""
import unittest
from unittest.mock import patch
import consultation
import intake
import product
import server
import test_workbench


class AgentConversationTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def fresh(self):
        server.save_json(server.DATA/'workspace.json',{})

    def model(self,reply):
        self.output={'reply':reply,'decision':{'action':'none'},'plan':None}

    def test_grouped_start_is_not_rewritten_to_one_field(self):
        self.fresh()
        reply='可以，我先了解几个基础情况。你多大、性别、身高和目前体重是多少？希望减多少？用一段话说就行。'
        self.model(reply)
        result=self.chat('我想减肥')
        self.assertEqual(result['reply'],reply)
        self.assertNotIn('asked_field',product.workspace(server)['sessions']['test-conversation'])

    def test_whole_paragraph_saved_and_reused_in_new_conversation(self):
        self.fresh();self.model('先按这些情况一起看。')
        self.chat('我想减肥，我38岁；男；身高1.75米；85公斤；想减到75公斤，没有确诊疾病，没有手术史，没有过敏，没有用药。')
        state=product.snapshot(server)
        self.assertEqual(state['profile']['age'],38)
        self.assertEqual(state['profile']['sex'],'男')
        self.assertEqual(state['profile']['height_cm'],175)
        self.assertEqual([r['value']['kg'] for r in state['records'] if r['type']=='weight'],[85])
        self.model('我们可以从外卖的搭配看起。你今年多大？你的身高是多少？')
        answer=self.chat('先聊聊外卖怎么选择。',conversation_id='another-conversation')
        self.assertNotRegex(answer['reply'],'多大|身高是多少')
        self.assertIn('外卖',answer['reply'])
        self.assertIn('175',str(self.prompt))

    def test_ambiguous_number_after_bundle_is_not_age_or_height(self):
        self.fresh();self.model('你多大、身高和目前体重是多少？')
        self.chat('我想减肥')
        self.model('这个数字是体重还是年龄？')
        self.chat('85')
        state=product.snapshot(server)
        self.assertNotIn('age',state['profile'])
        self.assertNotIn('height_cm',state['profile'])
        self.assertFalse(state['records'])

    def test_complete_advice_does_not_acquire_mandatory_question(self):
        self.fresh()
        reply='你下班晚，可以先保留正常午餐，晚饭点单时优先比较带蔬菜和蛋白质配菜的组合，不必要求自己每天做饭。'
        self.model(reply)
        self.assertEqual(self.chat('我想减肥，但加班晚只能点外卖。')['reply'],reply)

    def test_new_question_with_more_facts_does_not_resume_assessment(self):
        self.fresh();self.model('可以一起说下年龄、身高、性别和体重吗？')
        self.chat('我想减肥')
        reply='盖饭可以更方便地看清主食与配菜，具体还要看实际菜单和份量。'
        self.model(reply)
        answer=self.chat('我38岁，男，身高175厘米，体重85公斤，先帮我比较盖饭和炒面怎么选。')
        self.assertEqual(answer['reply'],reply)
        self.assertNotIn('请核对',answer['reply'])
        self.assertEqual(product.snapshot(server)['profile']['age'],38)

    def test_detailed_meal_comparison_is_not_replaced_by_generic_reply(self):
        self.fresh()
        reply='\n'.join(['- 盖饭可以看清主食、蔬菜和肉类的搭配，份量以实际餐盘为准。',
            '- 炒面也能吃，留意配菜和用油，选择时结合自己的口味和饱腹感。',
            '- 你下班晚只能点外卖，就从常点菜单中选愿意吃的组合，不必改成自己做饭。'])*3
        self.model(reply)
        self.assertEqual(self.chat('晚餐盖饭和炒面怎么选？')['reply'],reply)

    def test_image_advice_visible_without_consumption_interview(self):
        self.fresh()
        raw={'category':'food','summary':'一份炸物。','question':'你已经吃完了吗？',
             'foods':[{'name':'炸物','nutrition_basis':'portion_estimate','nutrition':{'kcal':[600,900]}}],
             'advice':['如果当作一餐，可以留出一部分搭配蔬菜和主食。','整份吃完可能比较油腻，需结合其他餐和饱腹感判断。']}
        media=server.load_json(server.MEDIA,[]);media[0]['review']=server.normalize_image_analysis(raw,'food');server.save_json(server.MEDIA,media)
        with patch.object(server,'call_ai') as model:
            result=product.chat(server,{'text':'帮我看看怎么吃','media_id':'food-1',
                'conversation_id':'test-conversation','client_message_id':'advice-photo'},image_review_only=True)
        model.assert_not_called()
        self.assertIn('600–900 kcal',result['reply'])
        self.assertIn('搭配蔬菜',result['reply'])
        self.assertIn('整份吃完',result['reply'])
        self.assertNotIn('吃完了吗',result['reply'])
        self.assertFalse(product.snapshot(server)['records'])

    def test_report_advice_is_also_published(self):
        result=product.image_report_reply({'summary':'可读到两项指标。',
            'report':{'kind':'report','advice':['先核对报告日期和参考范围，再结合症状与医生讨论。']}})
        self.assertIn('参考范围',result)

    def test_mixed_question_keeps_only_unknown_basics_but_recheck_survives(self):
        result=consultation.remove_answered_questions('你的年龄、身高是多少？',{'age':38},[])
        self.assertIn('身高',result)
        self.assertNotIn('年龄',result)
        reply='你现在体重有变化吗？'
        self.assertEqual(consultation.remove_answered_questions(reply,{'age':38},[]),reply)


if __name__=='__main__':unittest.main()
