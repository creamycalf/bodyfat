import json
import threading
from unittest.mock import patch
import unittest
import server
import product
import image_jobs
import test_workbench


class ChatImageConcurrencyTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def test_queue_and_unrelated_image_completion_do_not_discard_reply(self):
        def model(*args, **kwargs):
            w=product.workspace(server)
            w['image_jobs']={'background-job':{'status':'failed','error':'AI_TIMEOUT'}}
            server.save_json(server.DATA/'workspace.json',w)
            media=server.load_json(server.MEDIA,[])
            media.append({'id':'new-background-image','review':{'summary':'后台图片已分析'}})
            server.save_json(server.MEDIA,media)
            return json.dumps({'reply':'可以，我们先聊聊。','decision':{'action':'none'},'plan':None})
        with patch.object(server,'call_ai',side_effect=model), patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            result=product.chat(server,{'text':'想先聊聊','conversation_id':'test-conversation','client_message_id':'concurrent-text-1'})
        self.assertIn('我们先聊聊',result['reply'])
        self.assertEqual(product.workspace(server)['image_jobs']['background-job']['status'],'failed')
        self.assertTrue(any(m['id']=='new-background-image' for m in server.load_json(server.MEDIA,[])))

    def test_health_edit_still_conflicts_and_is_never_overwritten(self):
        def model(*args, **kwargs):
            server.save_json(server.PROFILE,{'age':52})
            return json.dumps({'reply':'收到','decision':{'action':'none'},'plan':None})
        with patch.object(server,'call_ai',side_effect=model), patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}):
            with self.assertRaises(product.ProductError):
                product.chat(server,{'text':'想先聊聊','conversation_id':'test-conversation','client_message_id':'concurrent-text-2'})
        self.assertEqual(server.load_json(server.PROFILE,{})['age'],52)

    def test_unrelated_media_deletion_is_not_resurrected(self):
        def model(*args,**kwargs):
            server.save_json(server.MEDIA,[])
            return json.dumps({'reply':'我们继续聊。','decision':{'action':'none'},'plan':None})
        with patch.object(server,'call_ai',side_effect=model):
            product.chat(server,{'text':'先聊聊','conversation_id':'test-conversation','client_message_id':'media-deleted-test'})
        self.assertEqual(server.load_json(server.MEDIA,[]),[])

    def test_selected_media_edit_is_never_overwritten(self):
        def model(*args,**kwargs):
            media=server.load_json(server.MEDIA,[])
            media[0]['review']['summary']='用户已重新核对图片'
            server.save_json(server.MEDIA,media)
            return json.dumps({'reply':'收到。','decision':{'action':'none'},'plan':None})
        with patch.object(server,'call_ai',side_effect=model):
            with self.assertRaises(product.ProductError):
                product.chat(server,{'text':'分析这张图片','media_id':'food-1',
                    'conversation_id':'test-conversation','client_message_id':'media-overlap-test'})
        self.assertEqual(server.load_json(server.MEDIA,[])[0]['review']['summary'],'用户已重新核对图片')

    def test_background_report_needs_no_second_model_request(self):
        with patch.object(server,'call_ai') as model:
            answer=product.chat(server,{'text':'这份还没吃，请看照片','media_id':'food-1',
                'conversation_id':'test-conversation','client_message_id':'report-only-test'},image_review_only=True)
            model.assert_not_called()
        self.assertIn('米饭',answer['reply'])
        self.assertIsNone(answer['ai_error'])
        self.assertEqual(product.snapshot(server)['records'],[])
        self.assertEqual(server.load_json(server.MEDIA,[])[0]['food_decision']['status'],'reference')

    def test_report_publication_waits_for_chat_without_spending_retries(self):
        w=product.workspace(server)
        w['image_jobs']={'report-wait-test':{'id':'report-wait-test','stage':'followup','status':'pending',
            'attempts':2,'next_at':0,'media_id':'food-1','payload':{'context':'','followup':{
                'text':'分析照片','conversation_id':'test-conversation'}}}}
        server.save_json(server.DATA/'workspace.json',w)
        started=threading.Event();release=threading.Event();answers=[]
        def model(*args,**kwargs):
            started.set();release.wait(3)
            return json.dumps({'reply':'可以先聊聊。','decision':{'action':'none'},'plan':None})
        def foreground():
            answers.append(product.chat(server,{'text':'先聊聊','conversation_id':'test-conversation',
                'client_message_id':'foreground-wait-test'}))
        with patch.object(server,'call_ai',side_effect=model) as remote:
            thread=threading.Thread(target=foreground);thread.start()
            try:
                self.assertTrue(started.wait(2))
                for _ in range(4):self.assertFalse(image_jobs.run_one(server))
                self.assertEqual(image_jobs.list_jobs(server)[0]['attempts'],2)
            finally:release.set();thread.join(4)
            self.assertEqual(len(answers),1)
            self.assertTrue(image_jobs.run_one(server))
            self.assertEqual(remote.call_count,1)
        self.assertFalse(product.chat_active(server))
        self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'succeeded')
