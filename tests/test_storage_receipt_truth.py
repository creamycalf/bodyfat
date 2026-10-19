"""Natural replies and receipts must agree with confirmed state changes."""
import copy
import json
import unittest
from unittest.mock import patch

import product
import server
import test_workbench


class StorageReceiptTruthTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_checkpoint_weights_keep_successful_reply(self):
        self.output.update(reply='已记录：9月1日体重85公斤，今天体重82公斤。',
                           record_events=[{'type':'weight','value':{'weight_kg':85},'evidence':'2026年9月1日体重85公斤'},
                                          {'type':'weight','value':{'weight_kg':82},'evidence':'今天体重82公斤'}])
        result=self.chat('2026年9月1日体重85公斤，今天体重82公斤。请记录，先不要给建议。')
        self.assertEqual(len(server.records()),2)
        self.assertEqual(result['reply'],self.output['reply'])
        self.assertIn('记录已保存',result['receipts'])
        self.assertNotIn('本轮未保存',result['reply'])

    def test_checkpoint_profile_keeps_successful_reply(self):
        self.output['reply']='已保存你的年龄：38岁。'
        result=self.chat('我今年38岁，先聊聊。')
        self.assertEqual(server.load_json(server.PROFILE,{})['age'],38)
        self.assertEqual(result['reply'],self.output['reply'])
        self.assertIn('档案已保存',result['receipts'])

    def test_pending_change_does_not_claim_confirmed_profile_save(self):
        server.save_json(server.PROFILE,{'height_cm':165})
        self.output.update(reply='已保存身高168厘米。',profile_changes=[{'field':'height_cm','value':168,'evidence':'身高168厘米'}])
        result=self.chat('我的身高168厘米，先聊聊。')
        self.assertEqual(server.load_json(server.PROFILE,{})['height_cm'],165)
        self.assertNotIn('档案已保存',result['receipts'])
        self.assertIn('待核实',result['reply'])
        self.assertNotIn('已保存身高168',result['reply'])

    def test_failure_receipt_cannot_validate_false_save_claim(self):
        self.output.update(reply='已保存你的记录。',page_changes=[{'id':'bad-module','page':'invalid','body':'内容'}])
        result=self.chat('请把说明更新到计划页面。')
        self.assertTrue(result.get('page_error'))
        self.assertEqual(server.records(),[])
        self.assertNotIn('已保存你的记录',result['reply'])
        self.assertNotIn('记录已保存',result['receipts'])

    def test_existing_unrelated_record_does_not_authorize_new_save_claim(self):
        previous=server.prepare_record({'type':'weight','value':{'kg':80}})
        server.save_json(server.RECORDS,[previous])
        self.output['reply']='已记录你的体重。'
        result=self.chat('看一下之前的体重记录，先聊聊。')
        self.assertEqual(server.records(),[previous])
        self.assertIn('本轮未保存',result['reply'])
        self.assertNotIn('记录已保存',result['receipts'])

    def test_failed_extraction_cannot_claim_weight_save_despite_profile_success(self):
        self.output.update(reply='已保存体重82公斤。',record_events=[{'type':'weight','value':{'kg':82},'evidence':'今天体重82公斤'}])
        result=self.chat('我今年38岁，先聊聊。')
        self.assertEqual(server.records(),[])
        self.assertEqual(server.load_json(server.PROFILE,{})['age'],38)
        self.assertNotIn('已保存体重82',result['reply'])
        self.assertIn('本轮未保存新的体重记录',result['reply'])
        self.assertIn('其他实际保存结果请查看回执',result['reply'])
        self.assertNotIn('本轮未保存新的记录或变更',result['reply'])
        self.assertIn('档案已保存',result['receipts'])

    def test_retry_retains_original_records_without_claiming_new_save(self):
        text='今天体重82公斤，先聊聊。'
        with patch.object(server,'call_ai',side_effect=TimeoutError('timeout')):
            first=product.chat(server,{'text':text,'conversation_id':'test-conversation','client_message_id':'receipt-retry-origin'})
        self.assertIn('记录已保存',first['receipts'])
        self.output['reply']='已记录你的体重82公斤。'
        result=self.chat('继续',retry_chat=first['retry_chat'])
        self.assertEqual(len(server.records()),1)
        self.assertIn('此前保存的记录仍保留',result['reply'])
        self.assertIn('未新增重复记录',result['reply'])
        self.assertNotIn('记录已保存',result['receipts'])

    def test_repeated_client_message_returns_same_receipt_without_model_or_duplicate(self):
        self.output['reply']='已记录今天体重82公斤。'
        request={'text':'今天体重82公斤，先聊聊。','conversation_id':'test-conversation','client_message_id':'receipt-idempotent'}
        with patch.object(server,'call_ai',return_value=json.dumps(self.output,ensure_ascii=False)):
            first=product.chat(server,copy.deepcopy(request))
        with patch.object(server,'call_ai',side_effect=AssertionError('must not call model')):
            second=product.chat(server,copy.deepcopy(request))
        self.assertEqual(second,first)
        self.assertEqual(len(server.records()),1)
        self.assertIn('记录已保存',second['receipts'])

    def test_plan_and_feedback_false_claims_still_blocked(self):
        self.output['reply']='已完成打卡。'
        result=self.chat('我还没去散步，先聊聊。')
        self.assertIn('本轮没有保存完成打卡',result['reply'])
        self.assertNotIn('执行反馈已记录',result['receipts'])


if __name__=='__main__':unittest.main()
