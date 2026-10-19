"""Compact vision output retains the same calculations and readable OCR rows."""
import base64
import copy
import json
import unittest
from unittest.mock import patch

import image_jobs
import nutrition_reports
import server
import test_workbench


class VisionCompactNormalizationTests(unittest.TestCase):
    def test_density_nutrition_is_computed_identically_without_duplicate_model_numbers(self):
        raw={'category':'food','summary':'混合餐食。','foods':[{'name':'复合餐食，主料待核对','included':True,
             'grams':[200,250],'nutrition_basis':'weight_density','per_100g':{'kcal':[150,200],'protein_g':[5,10],
             'carbs_g':[20,30],'fat_g':[5,8]},'nutrition':{'kcal':[9999,9999],'protein_g':[80,80]},
             'portion_basis':'依据可见份量','weight_basis':'熟重','uncertainty':'用油待核对'}],
             'advice':['结合过敏限制核对配料。'],'tests':[],'record_candidates':[]}
        compact=copy.deepcopy(raw);compact['foods'][0].pop('nutrition');compact.pop('tests');compact.pop('record_candidates')
        full=server.normalize_image_analysis(raw,'auto');reduced=server.normalize_image_analysis(compact,'auto')
        self.assertEqual(reduced,full)
        self.assertEqual(reduced['report']['totals']['kcal'],[300,500])
        self.assertEqual(reduced['record_candidates'][0]['value']['nutrition']['kcal'],[300,500])
        self.assertEqual(reduced['report']['foods'][0]['uncertainty'],'用油待核对')

    def test_portion_estimate_omits_unused_density_without_changing_unknowns(self):
        raw={'category':'food','summary':'按可见份量估算。','foods':[{'name':'复合菜，主料待核对','included':True,
             'grams':None,'nutrition_basis':'portion_estimate','per_100g':{'kcal':None,'protein_g':None,'carbs_g':None,'fat_g':None},
             'nutrition':{'kcal':[400,650],'protein_g':[10,20],'carbs_g':None,'fat_g':[10,30]},
             'uncertainty':'未称量，配料和用油待核对'}],'advice':['先按盘中比例调整。']}
        compact=copy.deepcopy(raw);compact['foods'][0].pop('per_100g');compact['foods'][0].pop('grams')
        self.assertEqual(server.normalize_image_analysis(compact,'auto'),server.normalize_image_analysis(raw,'auto'))
        report=server.normalize_image_analysis(compact,'auto')['report']
        self.assertIsNone(report['totals']['carbs_g']);self.assertEqual(report['totals']['kcal'],[400,650])

    def test_report_only_schema_preserves_two_hundred_ocr_rows(self):
        tests=[{'name':'检查项目'+str(i),'value':str(i),'unit':'U/L','reference':'0-100',
                'flag':'原报告标记待核对','date':'2026-10-01'} for i in range(200)]
        raw={'category':'report','summary':'请核对原报告。','tests':tests,'advice':['不要自行改药。'],'foods':[],'record_candidates':[]}
        compact=copy.deepcopy(raw);compact.pop('foods');compact.pop('record_candidates')
        full=server.normalize_image_analysis(raw,'report');reduced=server.normalize_image_analysis(compact,'report')
        self.assertEqual(reduced,full);self.assertEqual(reduced['report']['tests'],tests)
        self.assertEqual(reduced['report']['coverage']['saved_count'],200)


class VisionCompactPipelineTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def test_image_job_uses_one_canonical_vision_call_then_local_publication(self):
        png=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(10).to_bytes(4,'big')+(10).to_bytes(4,'big')+b'x'*12
        raw={'category':'food','summary':'一盘餐食。','foods':[{'name':'混合餐食','nutrition_basis':'portion_estimate',
             'nutrition':{'kcal':[400,600],'protein_g':[15,25],'carbs_g':[50,75],'fat_g':[10,20]},
             'uncertainty':'未经称量'}],'advice':['结合过敏限制核对配料，按盘中比例调整。']}
        with patch.object(image_jobs,'ensure_worker'),patch.object(server,'call_ai',return_value=json.dumps(raw,ensure_ascii=False)) as model, \
             patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            image_jobs.submit(server,{'client_job_id':'compact-vision-only','data':base64.b64encode(png).decode(),
                'mime':'image/png','category':'auto','context':'分析食物并说说如何搭配。',
                'followup':{'conversation_id':'test-conversation','text':'分析食物并说说如何搭配。'}})
            image_jobs.run_one(server)
        self.assertEqual(model.call_count,1)
        self.assertTrue(model.call_args.args[1])
        prompt=model.call_args.args[0]
        self.assertTrue(prompt[0]['content'].startswith(nutrition_reports.VISION_INSTRUCTION))
        self.assertNotIn('Extract candidates only',str(prompt))
        self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'succeeded')
        self.assertEqual(server.records(),[])


if __name__=='__main__':unittest.main()
