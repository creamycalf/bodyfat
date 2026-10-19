import unittest
from unittest.mock import patch
import image_jobs
import product
import server
import test_workbench


class ImageReportPublicationTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def install_review(self, raw):
        media=server.load_json(server.MEDIA,[])
        media[0]['review']=server.normalize_image_analysis(raw,'food')
        server.save_json(server.MEDIA,media)
        return media[0]['review']

    def publish(self):
        with patch.object(server,'call_ai') as model:
            result=product.chat(server,{'text':'这张照片大概多少热量？还没吃，请分析。',
                'media_id':'food-1','conversation_id':'test-conversation',
                'client_message_id':'calorie-report-publication'},image_review_only=True)
        model.assert_not_called()
        self.assertIsNone(result.get('ai_error'))
        self.assertEqual(product.snapshot(server)['records'],[])
        return result

    def test_photo_calories_use_report_not_unchecked_model_summary(self):
        review=self.install_review({'category':'food','summary':'一盘米饭，热量9999千卡。',
            'question':'这盘你本人吃了多少？',
            'foods':[{'name':'米饭','grams':[150,200],'weight_basis':'熟重'}]})
        self.assertNotIn('9999',review['summary'])
        result=self.publish()
        self.assertIn('195–260 kcal',result['reply'])
        self.assertNotIn('9999',result['reply'])
        self.assertIn('照片可见份量',result['reply'])
        self.assertNotIn('这盘你本人吃了多少',result['reply'])

    def test_legacy_food_candidate_recovers_report_and_auto_category(self):
        review=server.normalize_image_analysis({'summary':'一份炸物。','record_candidates':[
            {'type':'meal','label':'炸物','value':{'description':'一份炸物',
                'nutrition':{'kcal':[600,900]},'uncertainty':'份量与用油为照片估计'}}]},'auto')
        self.assertEqual(review['category'],'food')
        self.assertEqual(review['report']['totals']['kcal'],[600,900])
        self.assertEqual(review['record_candidates'][0]['value']['nutrition']['kcal'],[600,900])

    def test_general_image_does_not_become_food_from_prompt_or_stray_candidate(self):
        review=server.normalize_image_analysis({'category':'general','summary':'不是食物照片。',
            'record_candidates':[{'type':'meal','value':{'nutrition':{'kcal':600}}}]},'food')
        self.assertEqual(review['category'],'general')
        self.assertEqual(review['report']['kind'],'general')

    def test_unknown_component_publishes_only_partial_calories(self):
        self.install_review({'category':'food','summary':'一份米饭和不明菜。',
            'foods':[{'name':'米饭','grams':100,'weight_basis':'熟重'},{'name':'不明菜'}]})
        result=self.publish()
        self.assertIn('130 kcal',result['reply'])
        self.assertIn('不是整盘总量',result['reply'])

    def test_no_numeric_estimate_does_not_claim_structured_response_failure(self):
        self.install_review({'category':'food','summary':'大约800千卡。','foods':[{'name':'看不清的菜'}]})
        result=self.publish()
        self.assertIn('还没有可用的热量估算',result['reply'])
        self.assertNotIn('800',result['reply'])

    def test_image_job_with_calorie_only_summary_can_complete(self):
        self.install_review({'category':'food','summary':'260千卡。',
            'foods':[{'name':'米饭','grams':200,'weight_basis':'熟重'}]})
        w=product.workspace(server)
        w['image_jobs']={'calorie-job-123':{'id':'calorie-job-123','stage':'followup','status':'pending',
            'attempts':0,'next_at':0,'media_id':'food-1','payload':{'context':'','followup':{
                'text':'请分析这份照片的热量，尚未食用。','conversation_id':'test-conversation'}}}}
        server.save_json(server.DATA/'workspace.json',w)
        with patch.object(server,'call_ai') as model:
            self.assertTrue(image_jobs.run_one(server))
        model.assert_not_called()
        job=image_jobs.list_jobs(server)[0]
        self.assertEqual(job['status'],'succeeded')
        self.assertIsNone(job['error'])
        self.assertEqual(product.snapshot(server)['records'],[])


if __name__=='__main__':unittest.main()
