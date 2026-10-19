"""A saved lab concentration is not an unverified nutrient prescription."""
import unittest

import coach_actions
import nutrition_reports
import server
import test_workbench


TESTS=[{'name':'载脂蛋白B','value':'1.3','unit':'g/L','reference':'0.6-1.1','date':'2026-10-01'}]
REPORT_LINE='这份报告记录的载脂蛋白B为1.3 g/L，参考范围为0.6–1.1 g/L。'


class ReportNutrientBoundaryTests(unittest.TestCase):
    def test_exact_saved_result_unit_and_reference_survive(self):
        self.assertTrue(coach_actions.has_unverified_nutrients(REPORT_LINE))
        safe,removed=coach_actions.redact_unverified_nutrients(REPORT_LINE,TESTS)
        self.assertEqual(safe,REPORT_LINE);self.assertFalse(removed)

    def test_equivalent_numeric_and_unit_whitespace_is_supported(self):
        text='载脂蛋白 B 结果1.30 g / L，参考范围0.60～1.10 g / L。'
        self.assertEqual(coach_actions.redact_unverified_nutrients(text,TESTS),(text,False))

    def test_no_saved_report_cannot_authorize_a_concentration(self):
        safe,removed=coach_actions.redact_unverified_nutrients(REPORT_LINE)
        self.assertTrue(removed);self.assertNotIn('1.3 g/L',safe)
        for tests in ([{**TESTS[0],'name':'白蛋白'}],[{**TESTS[0],'unit':'g/dL'}],[] ):
            safe,removed=coach_actions.redact_unverified_nutrients(REPORT_LINE,tests)
            self.assertTrue(removed);self.assertNotIn('1.3 g/L',safe)

    def test_incorrect_value_or_reference_is_not_whitelisted(self):
        for text,bad in [('载脂蛋白B为1.5 g/L，参考范围0.6–1.1 g/L。','1.5 g/L'),
                         ('载脂蛋白B为1.3 g/L，参考范围0.6–1.2 g/L。','0.6–1.2 g/L')]:
            safe,removed=coach_actions.redact_unverified_nutrients(text,TESTS)
            self.assertTrue(removed);self.assertNotIn(bad,safe)

    def test_report_cannot_whitelist_adjacent_nutrient_targets(self):
        for target in ('每天蛋白质80克','每天蛋白质80g','每天1800千卡','每天脂肪50克'):
            for separator in ('，建议','且建议','，同时建议','，','且'):
                with self.subTest(target=target,separator=separator):
                    text=REPORT_LINE[:-1]+separator+target+'。'
                    safe,removed=coach_actions.redact_unverified_nutrients(text,TESTS)
                    self.assertTrue(removed)
                    self.assertIn('1.3 g/L',safe);self.assertIn('0.6–1.1 g/L',safe)
                    self.assertNotIn(target,safe)

    def test_non_report_nutrition_rules_are_unchanged(self):
        text='先保持正常作息。每天蛋白质80克。豆腐100克作为食材参考。'
        safe,removed=coach_actions.redact_unverified_nutrients(text,TESTS)
        self.assertTrue(removed);self.assertNotIn('80克',safe)
        self.assertIn('正常作息',safe);self.assertIn('豆腐100克',safe)


class ReportNutrientChatTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def save_report(self,**extra):
        server.save_json(server.MEDIA,[{'id':'apob-report','type':'report',
            'review':{'summary':'待核对的检查报告','report':nutrition_reports.report({'tests':TESTS},'report')},**extra}])

    def test_stored_report_line_survives_real_chat_validation(self):
        self.save_report();self.output['reply']=REPORT_LINE+'单项指标不能直接用于确诊。'
        result=self.chat('请解释这张报告的载脂蛋白B，按原结果、单位和参考范围解释。',media_id='apob-report')
        self.assertEqual(result['reply'],self.output['reply'])
        self.assertFalse(result.get('ai_error'));self.assertEqual(server.records(),[])

    def test_same_sentence_intake_target_is_still_filtered_in_chat(self):
        self.save_report();self.output['reply']=REPORT_LINE[:-1]+'，建议每天蛋白质80克。单项指标不能直接用于确诊。'
        result=self.chat('请解释这张报告的载脂蛋白B，按原结果、单位和参考范围解释。',media_id='apob-report')
        self.assertIn('1.3 g/L',result['reply']);self.assertIn('0.6–1.1 g/L',result['reply'])
        self.assertNotIn('80克',result['reply']);self.assertFalse(result.get('ai_error'))
        self.assertEqual(server.records(),[])


if __name__=='__main__':unittest.main()
