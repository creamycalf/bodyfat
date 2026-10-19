"""Exact photo estimates remain readable without authorizing intake targets."""
import copy
import unittest

import coach_actions
import server
import test_workbench


REPORT={'kind':'food','totals':{'kcal':[600,800],'protein_g':[30,45],'carbs_g':[60,90],'fat_g':[20,30]},
        'partial_totals':{'kcal':[600,800],'protein_g':[30,45],'carbs_g':[60,90],'fat_g':[20,30]},
        'counted_count':1,'coverage':{'kcal':1,'protein_g':1,'carbs_g':1,'fat_g':1},'foods':[]}


class PhotoNutrientBoundaryTests(unittest.TestCase):
    def clean(self,text,report=REPORT):return coach_actions.redact_unverified_nutrients(text,verified_food_report=report)

    def test_exact_photo_ranges_keep_explanation(self):
        text='按照片中这份餐食估算，蛋白质约30–45克，热量约600–800千卡。是否适合还要结合全天饮食和身体情况。'
        self.assertEqual(self.clean(text),(text,False))
        reverse='这份照片估算含30到45g蛋白质，脂肪约20.0～30.0克。'
        self.assertEqual(self.clean(reverse),(reverse,False))

    def test_missing_context_source_or_matching_nutrient_does_not_authorize(self):
        for text,report in [('蛋白质约30–45克。',REPORT),('这份照片蛋白质约30–45克。',None),
                            ('这份照片糖约30–45克。',REPORT),('这份照片饱和脂肪约20–30克。',REPORT)]:
            with self.subTest(text=text):
                safe,removed=self.clean(text,report)
                self.assertTrue(removed);self.assertNotIn(text,safe)

    def test_wrong_units_ranges_and_single_midpoint_are_not_allowed(self):
        for text in ('这份照片蛋白质约30–45毫克。','这份照片蛋白质约30–45g/L。','这份照片蛋白质约30–45g / L。',
                     '这份照片蛋白质约30–50克。','这份照片蛋白质约37.5克。','这份照片热量约600–800千焦。'):
            safe,removed=self.clean(text)
            self.assertTrue(removed);self.assertFalse(safe)

    def test_same_numbers_cannot_become_daily_or_meal_prescriptions(self):
        for text in ('建议这份照片每天蛋白质30–45克。','这份照片每餐蛋白质30–45克。',
                     '这份照片需要摄入蛋白质30–45克。','这份照片蛋白质建议吃30–45克。',
                     '这份照片中的标准是蛋白质30–45克。'):
            safe,removed=self.clean(text)
            self.assertTrue(removed);self.assertNotIn('30–45',safe)

    def test_mixed_daily_targets_are_removed_without_losing_verified_photo_amount(self):
        for separator in ('，建议','且建议','，','且'):
            for target in ('每天蛋白质80克','每餐蛋白质30–45克','每天热量600–800千卡','需要摄入蛋白质30–45克'):
                with self.subTest(separator=separator,target=target):
                    text='这份照片蛋白质粗估30–45克'+separator+target+'。能否满足个人需要还要看全天饮食。'
                    safe,removed=self.clean(text)
                    self.assertTrue(removed);self.assertIn('粗估30–45克',safe)
                    self.assertNotIn(target,safe);self.assertIn('全天饮食',safe)

    def test_partial_estimate_requires_both_limitations_in_same_clause(self):
        partial=copy.deepcopy(REPORT);partial['totals']['protein_g']=None
        safe_text='这份照片蛋白质粗估30–45克（仅已估算部分，不是整餐总量）。'
        self.assertEqual(self.clean(safe_text,partial),(safe_text,False))
        for text in ('这份照片蛋白质粗估30–45克。',
                     '这份照片蛋白质粗估30–45克（仅已估算部分）。',
                     '这份照片蛋白质粗估30–45克。仅已估算部分，不是整餐总量。'):
            safe,removed=self.clean(text,partial)
            self.assertTrue(removed);self.assertNotIn('30–45',safe)

    def test_unavailable_and_invalid_totals_cannot_authorize_numbers(self):
        for pair in (None,[float('nan'),45],[45,30],[True,45]):
            report=copy.deepcopy(REPORT);report['totals']['protein_g']=pair;report['partial_totals']['protein_g']=None
            safe,removed=self.clean('这份照片蛋白质约30–45克。',report)
            self.assertTrue(removed);self.assertFalse(safe)


class PhotoNutrientChatTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_richer_photo_question_keeps_source_backed_value_and_reasoning(self):
        server.save_json(server.MEDIA,[{'id':'food-estimate','type':'food','review':{'summary':'餐食照片估算','report':REPORT}}])
        self.output['reply']='这份照片蛋白质粗估30–45克。仅凭这张照片无法判断全天是否足够，还需结合其他餐次。'
        result=self.chat('这份照片里的蛋白质够吗？我想听听原因。',media_id='food-estimate')
        self.assertIn('30–45克',result['reply']);self.assertIn('其他餐次',result['reply'])
        self.assertFalse(result.get('ai_error'));self.assertEqual(server.records(),[])

    def test_richer_reply_does_not_authorize_adjacent_daily_target(self):
        server.save_json(server.MEDIA,[{'id':'food-estimate','type':'food','review':{'summary':'餐食照片估算','report':REPORT}}])
        self.output['reply']='这份照片蛋白质粗估30–45克，建议每天蛋白质80克。仅凭照片不能判断个人需要。'
        result=self.chat('这份照片里的蛋白质够吗？我想听听原因。',media_id='food-estimate')
        self.assertIn('30–45克',result['reply']);self.assertNotIn('80克',result['reply'])
        self.assertIn('不能判断个人需要',result['reply']);self.assertEqual(server.records(),[])


if __name__=='__main__':unittest.main()
