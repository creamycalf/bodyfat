"""Derived local audit prose cannot bypass excluded record/message evidence."""
import base64
import copy
import json
import unittest
from unittest.mock import patch

import product
import server
import test_workbench
import workbench


class DerivedContextPrivacyTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def food(self):
        review=server.normalize_image_analysis({'category':'food','summary':'一份餐盘。',
            'foods':[{'name':'餐食','nutrition_basis':'portion_estimate','nutrition':{'kcal':[600,900]}}]},'food')
        server.save_json(server.MEDIA,[{'id':'food-1','type':'food','review':review}])

    def payload(self):
        self.output={'reply':'可以讨论餐盘搭配。','decision':{'action':'none'},'plan':None}
        self.chat('这份食物怎么搭配？',media_id='food-1',conversation_id='new-food-chat')
        return json.dumps(self.prompt,ensure_ascii=False),json.loads(self.prompt[1]['content'])

    def test_real_assessment_origin_no_longer_leaks_after_source_record_disabled(self):
        self.output={'reply':'带原检查结果咨询复查方向。','decision':{'action':'none'},'plan':None,
            'record_events':[{'type':'lab_or_measurement','value':{'description':'眼底 CLINIC_PRIVATE_MARKER'},
                              'evidence':'眼底检查的待复查事项是CLINIC_PRIVATE_MARKER'}]}
        self.chat('我去年眼底检查的待复查事项是CLINIC_PRIVATE_MARKER，计划近期咨询。',conversation_id='old-clinical-chat')
        records=server.records();self.assertTrue(records)
        records[0]['memory_enabled']=False;server.save_json(server.RECORDS,records)
        self.assertIn('CLINIC_PRIVATE_MARKER',product.workspace(server)['assessment_state']['primary_problem'])
        self.food()
        payload,facts=self.payload()
        self.assertEqual(facts['recent_records'],[])
        self.assertNotIn('CLINIC_PRIVATE_MARKER',payload)
        self.assertEqual(facts['assessment']['primary_problem'],'')

    def seed_derived(self, *, flags=None, undone=False):
        record={'id':'private-record','type':'lab_or_measurement','value':{'description':'CLINIC_PRIVATE_MARKER'},
                'confirmed':True,'source_message_id':'private-source',**(flags or {})}
        active={'id':'active-record','type':'lab_or_measurement','value':{'description':'ACTIVE_CLINIC_MARKER'},'confirmed':True}
        server.save_json(server.RECORDS,[record,active])
        server.save_json(server.PROFILE,{'age':38})
        w=product.workspace(server)
        w['assessment_state'].update(primary_problem='CLINIC_PRIVATE_MARKER',user_summary='CLINIC_PRIVATE_MARKER',
            next_question={'text':'CLINIC_PRIVATE_MARKER？'},
            history=[{'source_message_id':'private-source','reason':'CLINIC_PRIVATE_MARKER',
                      'question':'CLINIC_PRIVATE_MARKER？'}],evidence_record_ids=['private-record','active-record'])
        w['modules']=[{'id':'private-module','page':'archive','type':'text','title':'检查记录',
            'body':'CLINIC_PRIVATE_MARKER','source':{'message_id':'private-source','text':'SOURCE_PRIVATE_MARKER'},
            'basis_record_ids':['private-record']}]
        w['plans']=[{'id':'private-plan','version':1,'status':'active','title':'CLINIC_PRIVATE_MARKER',
            'goal':'CLINIC_PRIVATE_MARKER','basis':'CLINIC_PRIVATE_MARKER','start_date':product.today(),
            'end_date':product.today(),'review_date':product.today(),'duration_days':1,
            'source_message':{'message_id':'private-source','text':'SOURCE_PRIVATE_MARKER'},
            'basis_record_ids':['private-record'],'items':[{'id':'walk','title':'CLINIC_PRIVATE_MARKER',
                'detail':'CLINIC_PRIVATE_MARKER','minimum':'轻松活动','when':'每天'}]}]
        if undone:w['receipts']['private-source']={'undone':True}
        server.save_json(server.DATA/'workspace.json',w)
        self.food()

    def test_disabled_retracted_and_undone_derived_modules_plans_tasks_are_filtered(self):
        for flags,undone in (({'memory_enabled':False},False),({'status':'retracted'},False),({},True)):
            with self.subTest(flags=flags,undone=undone):
                self.seed_derived(flags=flags,undone=undone)
                payload,facts=self.payload()
                self.assertNotIn('CLINIC_PRIVATE_MARKER',payload)
                self.assertNotIn('SOURCE_PRIVATE_MARKER',payload)
                self.assertIn('ACTIVE_CLINIC_MARKER',payload)
                self.assertEqual(facts['modules'],[])
                self.assertEqual(facts['today_tasks'],[])
                self.assertTrue(facts['current_plan']['context_unavailable'])
                self.assertEqual(facts['assessment']['evidence_record_ids'],['active-record'])

    def test_disabled_original_session_request_does_not_replay_old_raw_input(self):
        self.seed_derived(flags={'memory_enabled':False})
        text='先处理CLINIC_PRIVATE_MARKER再讨论长期运动。'
        server.save_json(server.CONVERSATIONS,[{'id':'new-food-chat','messages':[
            {'id':'private-source','role':'user','text':text},
            {'id':'private-answer','role':'assistant','text':'SOURCE_PRIVATE_MARKER'},
        ]}])
        w=product.workspace(server);w['sessions']['new-food-chat']={'request':text}
        server.save_json(server.DATA/'workspace.json',w)
        payload,facts=self.payload()
        self.assertEqual(facts['original_request'],'这份食物怎么搭配？')
        self.assertNotIn('CLINIC_PRIVATE_MARKER',payload)
        self.assertNotIn('SOURCE_PRIVATE_MARKER',payload)

    def test_available_derived_content_is_kept_without_raw_source_metadata(self):
        self.seed_derived()
        payload,facts=self.payload()
        self.assertIn('CLINIC_PRIVATE_MARKER',payload)
        self.assertIn('ACTIVE_CLINIC_MARKER',payload)
        self.assertNotIn('SOURCE_PRIVATE_MARKER',payload)
        self.assertEqual(facts['modules'][0]['id'],'private-module')
        self.assertTrue(facts['today_tasks'])
        self.assertEqual(facts['current_plan']['id'],'private-plan')

    def test_unattributed_legacy_assessment_modules_and_plan_prose_stay_local(self):
        self.seed_derived()
        w=product.workspace(server)
        for item in w['modules']:item.pop('source');item['basis_record_ids']=[]
        for item in w['plans']:item.pop('source_message');item['basis_record_ids']=[]
        before=copy.deepcopy(w['assessment_state'])
        server.save_json(server.DATA/'workspace.json',w)
        derived=product.model_derived_context(w,{'age':38},[],w['plans'][0])
        self.assertNotIn('CLINIC_PRIVATE_MARKER',json.dumps(derived,ensure_ascii=False))
        self.assertEqual(w['assessment_state'],before)
        self.assertEqual(derived['assessment']['known_count'],1)
        self.assertEqual(derived['modules'],[])

    def test_model_assessment_recomputes_effective_record_ids_and_keeps_local_audit(self):
        state={'primary_problem':'LEGACY_PRIVATE_MARKER','history':[{'reason':'LEGACY_PRIVATE_MARKER'}]}
        records=[{'id':'withdrawn','type':'weight','status':'retracted'},
                 {'id':'active','type':'lab_or_measurement','confirmed':True}]
        local=workbench.assessment({'age':38},records,[],state)
        model=workbench.assessment({'age':38},records,[],state,for_model=True)
        self.assertIn('LEGACY_PRIVATE_MARKER',json.dumps(local))
        self.assertNotIn('LEGACY_PRIVATE_MARKER',json.dumps(model))
        self.assertEqual(model['evidence_record_ids'],['active'])
        self.assertFalse(model['has_weight'])

    def test_vision_payload_has_only_usable_records_without_derived_audit_prose(self):
        self.seed_derived(flags={'memory_enabled':False})
        png=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(12).to_bytes(4,'big')+(8).to_bytes(4,'big')+b'x'*12
        with patch.object(server,'call_ai',return_value=json.dumps({'category':'general','summary':'测试图像。'})) as model:
            server.analyze_image({'data':base64.b64encode(png).decode(),'mime':'image/png','category':'general',
                                  'conversation_id':'new-vision-chat','context':'结合检查情况分析。'})
        payload=json.dumps(model.call_args[0][0],ensure_ascii=False)
        self.assertNotIn('CLINIC_PRIVATE_MARKER',payload)
        self.assertNotIn('SOURCE_PRIVATE_MARKER',payload)
        self.assertIn('ACTIVE_CLINIC_MARKER',payload)


if __name__=='__main__':unittest.main()
