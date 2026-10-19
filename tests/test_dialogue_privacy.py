"""Memory exclusions also remove old prose and assistant echoes from payloads."""
import base64
import json
import unittest
from unittest.mock import patch

import product
import server
import test_workbench


class DialoguePrivacyTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def seed(self, *, disabled_message=False, disabled_conversation=False):
        messages=[
            {'id':'private-source','role':'user','text':'我家里没有冰箱，隐私原文PRIVATE_SOURCE。',
             'created_at':'2026-09-01T12:00:00'},
            {'id':'private-answer','role':'assistant','text':'隐私回声PRIVATE_ECHO：没有冰箱。你今晚准备怎么吃？',
             'created_at':'2026-09-01T12:00:01'},
        ]
        if disabled_message:messages[0]['memory_enabled']=False
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':messages,
                                               'memory_enabled':not disabled_conversation}])
        return messages

    def assert_payload_private(self):
        self.chat('今天晚饭怎么安排？')
        payload=json.dumps(self.prompt,ensure_ascii=False)
        self.assertNotIn('PRIVATE_SOURCE',payload)
        self.assertNotIn('PRIVATE_ECHO',payload)
        self.assertIn('今天晚饭怎么安排',payload)
        facts=json.loads(self.prompt[1]['content'])
        self.assertNotIn('PRIVATE_ECHO',facts.get('last_displayed_question',''))

    def test_disabled_user_and_assistant_echo_are_absent_from_actual_chat_payload(self):
        self.seed(disabled_message=True)
        self.assert_payload_private()

    def test_disabled_record_excludes_its_source_and_echo_from_actual_chat_payload(self):
        self.seed()
        server.save_json(server.RECORDS,[{'id':'disabled-record','type':'meal',
            'value':{'description':'PRIVATE_SOURCE'},'confirmed':True,'memory_enabled':False,
            'source_message_id':'private-source'}])
        self.assert_payload_private()

    def test_undone_source_and_echo_are_absent_from_actual_chat_payload(self):
        self.seed()
        w=product.workspace(server);w['receipts']['private-source']={'undone':True}
        server.save_json(server.DATA/'workspace.json',w)
        self.assert_payload_private()

    def test_retracted_profile_source_and_echo_are_absent_from_actual_chat_payload(self):
        self.seed()
        w=product.workspace(server)
        w['profile_history']=[{'field':'preferences','value':'PRIVATE_SOURCE',
            'status':'retracted','source_message_id':'private-source'}]
        server.save_json(server.DATA/'workspace.json',w)
        self.assert_payload_private()

    def test_disabled_conversation_history_is_excluded_but_new_user_input_is_answered(self):
        self.seed(disabled_conversation=True)
        self.assert_payload_private()

    def test_next_permitted_turn_and_its_complete_question_survive(self):
        messages=self.seed(disabled_message=True)
        messages.extend([
            {'id':'private-answer-2','role':'assistant','text':'PRIVATE_ECHO continued'},
            {'id':'public-user','role':'user','text':'今天散步感觉不错。'},
            {'id':'public-assistant','role':'assistant','text':'今天走完是否舒服？'},
        ])
        history=product.bounded_dialogue_history(messages)
        self.assertEqual(history,[{'role':'user','content':'今天散步感觉不错。'},
                                  {'role':'assistant','content':'今天走完是否舒服？'}])

    def test_explicitly_disabled_assistant_is_not_reused_as_last_question(self):
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[
            {'id':'public-user','role':'user','text':'今天晚餐想吃清淡些。'},
            {'id':'private-answer','role':'assistant','text':'PRIVATE_ECHO？','memory_enabled':False},
        ]}])
        self.assert_payload_private()

    def test_image_payload_uses_the_same_source_and_echo_exclusions(self):
        for mode in ('message','record','conversation','retracted'):
            with self.subTest(mode=mode):
                self.seed(disabled_message=mode=='message',disabled_conversation=mode=='conversation')
                server.save_json(server.RECORDS,[{'id':'private-record','type':'meal',
                    'value':{'description':'PRIVATE_SOURCE'},'confirmed':True,
                    'memory_enabled':False,'source_message_id':'private-source'}] if mode=='record' else [])
                w=product.workspace(server)
                w['profile_history']=([{'field':'preferences','value':'PRIVATE_SOURCE',
                    'status':'retracted','source_message_id':'private-source'}] if mode=='retracted' else [])
                server.save_json(server.DATA/'workspace.json',w)
                png=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(12).to_bytes(4,'big')+(8).to_bytes(4,'big')+b'x'*12
                output=json.dumps({'category':'general','summary':'测试图片内容。'})
                with patch.object(server,'call_ai',return_value=output) as mock:
                    server.analyze_image({'data':base64.b64encode(png).decode(),'mime':'image/png',
                        'category':'general','conversation_id':'test-conversation','context':'请分析今天的晚饭。'})
                payload=json.dumps(mock.call_args[0][0],ensure_ascii=False)
                self.assertNotIn('PRIVATE_SOURCE',payload)
                self.assertNotIn('PRIVATE_ECHO',payload)
                self.assertIn('请分析今天的晚饭',payload)


if __name__=='__main__':unittest.main()
