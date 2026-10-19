"""A precise practical forget request removes persisted clauses before model use."""
import json
import unittest
from unittest.mock import patch

import product
import server
import test_workbench


class PracticalProfilePrivacyTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def seed(self,profile=None):
        profile=profile or {'food_habits':'家里没有冰箱。每餐预算20元。',
            'preferences':['不吃鱼','家里没有冰箱'], 'allergies':['鱼类过敏']}
        server.save_json(server.PROFILE,profile)
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'id':'old-practical','role':'user','text':'家里没有冰箱。每餐预算20元。',
             'created_at':'2026-09-01T12:00:00'},
            {'id':'old-answer','role':'assistant','text':'结合你家里没有冰箱的条件讨论。',
             'created_at':'2026-09-01T12:00:01'},
        ]}])
        w=product.workspace(server)
        for field in profile:w['profile_sources'][field]={'source_message_id':'old-practical',
            'message_id':'old-practical','at':'2026-09-01T12:00:00'}
        server.save_json(server.DATA/'workspace.json',w)

    def test_forget_persists_removal_preserves_other_clauses_and_does_not_recur(self):
        self.seed()
        # A model trying to reinterpret the forget command as a fresh fact must
        # not restore the deleted clause, including via a different field.
        self.output={'reply':'了解你的要求。','decision':{'action':'none'},'plan':None,
            'profile_changes':[{'field':field,'value':'家里没有冰箱','evidence':'冰箱情况'}
                               for field in ('food_habits','preferences','dinner_habit')]}
        answer=self.chat('忘掉我的冰箱情况。')
        profile=server.load_json(server.PROFILE,{})
        self.assertEqual(profile['food_habits'],'每餐预算20元')
        self.assertEqual(profile['preferences'],['不吃鱼'])
        self.assertEqual(profile['allergies'],['鱼类过敏'])
        self.assertNotIn('dinner_habit',profile)
        self.assertNotIn('没有冰箱',json.dumps(self.prompt,ensure_ascii=False))
        self.assertTrue(any('已移除相关生活条件条目' in value for value in answer['receipts']))
        history=product.workspace(server)['profile_history']
        self.assertTrue(any(item.get('field')=='food_habits' and item.get('status')=='corrected'
                            and '没有冰箱' in str(item.get('value')) for item in history))
        self.output={'reply':'按预算和饮食偏好讨论晚餐。','decision':{'action':'none'},'plan':None}
        self.chat('结合我以前的生活条件，晚餐怎么安排？',conversation_id='new-dinner-conversation')
        self.assertNotIn('没有冰箱',json.dumps(self.prompt,ensure_ascii=False))
        self.assertNotIn('没有冰箱',json.dumps(server.load_json(server.PROFILE,{}),ensure_ascii=False))

    def test_single_or_shared_clause_removes_field_without_partial_inference(self):
        self.seed({'meal_schedule':'没有冰箱又不能热饭','occupation':'每天上班八小时'})
        self.chat('请忘掉我的冰箱情况。')
        profile=server.load_json(server.PROFILE,{})
        self.assertNotIn('meal_schedule',profile)
        self.assertEqual(profile['occupation'],'每天上班八小时')
        history=product.workspace(server)['profile_history']
        self.assertTrue(any(item.get('field')=='meal_schedule' and item.get('status')=='retracted' for item in history))

    def test_negated_hypothetical_third_party_quoted_and_question_do_not_remove(self):
        original={'food_habits':'家里没有冰箱。每餐预算20元。'}
        for text in ('不要忘掉我的冰箱情况。','如果忘掉我的冰箱情况会怎样。',
                     '我老公要你忘掉他的冰箱情况。','我朋友说：“忘掉我的冰箱情况。”',
                     '忘掉我的冰箱情况会怎样？','是否忘掉我的冰箱情况。'):
            with self.subTest(text=text):
                self.seed(original)
                self.chat(text)
                self.assertEqual(server.load_json(server.PROFILE,{}),original)

    def test_no_save_command_removes_practical_data_without_deleting_clinical_fields(self):
        self.seed({'food_habits':'家里没有冰箱','conditions':['糖尿病'],'allergies':['鱼过敏']})
        self.chat('不要保存我的冰箱情况。')
        self.assertEqual(server.load_json(server.PROFILE,{}),{'conditions':['糖尿病'],'allergies':['鱼过敏']})

    def test_pending_clause_is_removed_and_confirmation_setting_does_not_delay_privacy(self):
        self.seed({'food_habits':'家里没有冰箱。每餐预算20元。'})
        w=product.workspace(server);w['settings']['confirm_each']=True
        w['pending']=[{'id':'pending-private','kind':'profile','field':'food_habits',
                       'value':'没有冰箱','source':{},'evidence':'冰箱'}]
        server.save_json(server.DATA/'workspace.json',w)
        self.chat('忘掉我的冰箱情况。')
        self.assertEqual(server.load_json(server.PROFILE,{}),{'food_habits':'每餐预算20元'})
        self.assertFalse(any(item.get('id')=='pending-private' for item in product.workspace(server)['pending']))

    def test_deletion_is_on_disk_before_model_call_and_survives_model_failure(self):
        self.seed({'food_habits':'没有冰箱。每餐预算20元。'})
        def fail_after_checking_saved(*args,**kwargs):
            self.assertEqual(server.load_json(server.PROFILE,{}),{'food_habits':'每餐预算20元'})
            raise TimeoutError('isolated model failure')
        with patch.object(server,'call_ai',side_effect=fail_after_checking_saved):
            product.chat(server,{'text':'忘掉我的冰箱情况。','conversation_id':'test-conversation',
                                 'client_message_id':'forget-before-model-failure'})
        self.assertEqual(server.load_json(server.PROFILE,{}),{'food_habits':'每餐预算20元'})


if __name__=='__main__':unittest.main()
