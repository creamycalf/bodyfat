"""Relevant history reaches every conversational route with current provenance."""
import copy
import json
import unittest
import product
import server
import test_workbench


class MemoryReportFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_old_relevant_record_is_retrieved_after_many_meals(self):
        old={'id':'old-retina','type':'lab_or_measurement','value':{'description':'眼底病变 RETINAL_SCAR_426'},
             'confirmed':True,'status':'confirmed','memory_enabled':True,'created_at':'2026-09-01T12:00:00'}
        meals=[{'id':f'meal-{i}','type':'meal','value':{'description':'午餐'},'confirmed':True,
                'memory_enabled':True,'created_at':'2026-10-16T12:00:00'} for i in range(16)]
        server.save_json(server.RECORDS,[old,*meals])
        self.chat('你还记得以前的眼底检查吗？结合它考虑运动。',conversation_id='new-retina-chat')
        self.assertIn('RETINAL_SCAR_426',self.prompt[1]['content'])

    def test_disabled_retracted_and_pending_records_are_not_restored_by_search(self):
        entries=[]
        for key,flags in [('disabled',{'memory_enabled':False}),('retracted',{'status':'retracted'}),
                          ('pending',{'confirmed':False})]:
            entries.append({'id':key,'type':'symptom','value':{'description':'眼底 '+key},'confirmed':True,**flags})
        server.save_json(server.RECORDS,entries)
        self.assertEqual(product.chat_record_context(server,'眼底',entries),[])

    def test_weight_context_does_not_replay_superseded_profile_paragraph(self):
        server.save_json(server.PROFILE,{'height_cm':168})
        records=[{'id':'weight-1','type':'weight','value':{'kg':65},'confirmed':True,
                  'source_message':{'text':'身高165cm，65kg'},'evidence':'身高165cm，65kg'}]
        server.save_json(server.RECORDS,records)
        w=product.workspace(server)
        w['profile_history']=[{'field':'height_cm','value':165,'status':'corrected'}]
        server.save_json(server.DATA/'workspace.json',w)
        self.chat('我的身高记住了吗？',conversation_id='corrected-new-chat')
        facts=json.loads(self.prompt[1]['content'])
        self.assertEqual(facts['profile']['height_cm'],168)
        self.assertIn('height_cm',facts['profile_authority']['corrected_fields'])
        # A clock's microseconds can coincidentally contain "165". Test the
        # health context rather than interpreting timestamp digits as height.
        health_facts={key:value for key,value in facts.items() if key not in ('date','local_datetime')}
        self.assertNotIn('165',json.dumps(health_facts,ensure_ascii=False))

    def test_retracted_profile_is_absent_immediately_and_cannot_be_reintroduced(self):
        server.save_json(server.PROFILE,{'allergies':['花生']})
        self.output={'reply':'已了解撤回需求。','decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':'allergies','value':['花生'],'evidence':'过敏资料'}]}
        self.chat('请删除我的过敏资料。')
        self.assertNotIn('allergies',product.snapshot(server)['profile'])
        facts=json.loads(self.prompt[1]['content'])
        self.assertNotIn('allergies',facts['profile'])
        self.assertIn('allergies',facts['profile_authority']['retracted_fields'])

    def reports(self):
        media=[]
        for key,value,date in [('old','4.2','2026-09-01'),('new','3.0','2026-10-17')]:
            media.append({'id':'report-'+key,'type':'report','review':server.normalize_image_analysis({
                'category':'report','summary':'血脂报告。','tests':[{'name':'LDL','value':value,'unit':'mmol/L',
                'reference':'<3.4','date':date}]},'report')})
        server.save_json(server.MEDIA,media)
        for key in ('old','new'):
            product.chat(server,{'text':'解读报告','media_id':'report-'+key,'conversation_id':'test-conversation',
                'client_message_id':'report-publication-'+key},image_review_only=True)
        return media

    def test_report_comparison_receives_both_values_and_dates(self):
        self.reports()
        self.chat('这两次报告相比有什么变化？',media_id='report-new')
        reports=json.loads(self.prompt[1]['content'])['related_reports']
        self.assertEqual([r['tests'][0]['value'] for r in reports],['4.2','3.0'])
        self.assertEqual([r['tests'][0]['date'] for r in reports],['2026-09-01','2026-10-17'])

    def test_single_report_question_keeps_focus_and_excluded_report_is_absent(self):
        self.reports()
        self.chat('请解释这张报告',media_id='report-new')
        self.assertEqual(len(json.loads(self.prompt[1]['content'])['related_reports']),1)
        server.save_json(server.RECORDS,[{'id':'disabled-old','type':'lab_or_measurement','value':{},
            'media_id':'report-old','memory_enabled':False,'confirmed':True}])
        self.chat('对比两次报告',media_id='report-new')
        self.assertNotIn('4.2',json.dumps(json.loads(self.prompt[1]['content'])['related_reports']))

    def test_report_context_does_not_expand_food_consumption_target(self):
        reports=self.reports()
        food={'id':'food-current','type':'food','review':{'summary':'米饭'}}
        server.save_json(server.MEDIA,[*reports,food])
        self.chat('这份吃了一半，请记录',media_id='food-current')
        linked=json.loads(self.prompt[1]['content'])['linked_images']
        self.assertEqual([item['id'] for item in linked],['food-current'])


if __name__=='__main__':unittest.main()
