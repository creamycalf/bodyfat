import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import image_jobs
import server
import storage
import workbench


class ImageJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)
        self.paths=[patch.object(server,'DATA',self.data),patch.object(image_jobs,'ensure_worker')]
        for p in self.paths:p.start()
        storage.initialize(self.data)
        self.payload={'background':True,'client_job_id':'test-job-1234','retry_id':'image-1',
                      'context':'准备吃','followup':{'conversation_id':'test-conversation','text':'准备吃这个'}}

    def tearDown(self):
        for p in reversed(self.paths):p.stop()
        self.temp.cleanup()

    def submit(self):
        with patch.object(server,'analyze_image',return_value={'id':'image-1'}) as analyze:
            result=image_jobs.submit(server,self.payload)
            self.assertTrue(analyze.call_args.kwargs['prepare_only'])
            return result

    def test_submit_idempotent_and_private_payload(self):
        first=self.submit()
        with patch.object(server,'analyze_image') as analyze:
            self.assertEqual(image_jobs.submit(server,self.payload),first);analyze.assert_not_called()
        self.assertNotIn('payload',first['job']);self.assertNotIn('fingerprint',first['job'])
        self.assertEqual(first['job']['message_text'],'准备吃')
        self.assertEqual(first['job']['client_message_id'],'image-job-test-job-1234')
        with self.assertRaises(server.product.ProductError):image_jobs.submit(server,{**self.payload,'context':'different'})

    def test_public_caption_defaults_without_leaking_private_upload_or_followup(self):
        result=image_jobs.public({'id':'caption-job','payload':{'data':'private-image-bytes',
            'followup':{'private_field':'private-followup'}},'fingerprint':'private-fingerprint'})
        self.assertEqual(result['message_text'],'请帮我看看这张照片。')
        self.assertNotIn('private',str(result))

    def test_image_then_followup_once(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':None}) as analyze,patch.object(server.product,'chat',return_value={'conversation_id':'test-conversation','client_message_id':'message-1'}) as chat:
            self.assertTrue(image_jobs.run_one(server));self.assertFalse(image_jobs.run_one(server))
            self.assertEqual(chat.call_count,1);self.assertEqual(analyze.call_count,1)
        job=image_jobs.list_jobs(server)[0];self.assertEqual(job['status'],'succeeded');self.assertEqual(job['stage'],'followup')

    def test_timeout_has_one_automatic_retry(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':'AI_TIMEOUT'}),patch.object(server.product,'chat') as chat:
            image_jobs.run_one(server);job=image_jobs.list_jobs(server)[0]
            self.assertEqual(job['status'],'pending');self.assertEqual(job['attempts'],1)
            image_jobs.update(server,job['id'],next_at=0);image_jobs.run_one(server)
            self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'failed');chat.assert_not_called()
        image_jobs.retry_job(server,job['id']);self.assertEqual(image_jobs.list_jobs(server)[0]['attempts'],0)

    def test_restart_resumes_followup_with_same_message_id(self):
        self.submit();image_jobs.update(server,'test-job-1234',stage='followup',status='running',attempts=1)
        image_jobs.recover(server)
        with patch.object(server,'analyze_image') as analyze,patch.object(server.product,'chat',return_value={'conversation_id':'test-conversation','client_message_id':'message-1'}) as chat:
            image_jobs.run_one(server);analyze.assert_not_called()
            self.assertEqual(chat.call_args.args[1]['client_message_id'],'image-job-test-job-1234')

    def test_partial_is_not_reported_as_success(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={}),patch.object(server.product,'chat',return_value={'conversation_id':'test-conversation','client_message_id':'message-1','food_error':'FOOD_REVIEW_REQUIRED'}):
            image_jobs.run_one(server)
        self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'partial')

    def test_auth_error_not_automatically_retried(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':'AI_AUTH_FAILED'}):image_jobs.run_one(server)
        self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'failed')

    def test_transport_retries_are_not_multiplied_by_the_background_queue(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':'AI_UPSTREAM_UNAVAILABLE',
                'attempts':2,'elapsed_ms':2000}) as analyze,patch.object(server.product,'chat') as chat:
            image_jobs.run_one(server)
            self.assertFalse(image_jobs.run_one(server))
            job=image_jobs.list_jobs(server)[0]
            self.assertEqual(job['status'],'failed');self.assertEqual(job['media_id'],'image-1')
            analyze.assert_called_once();chat.assert_not_called()
        image_jobs.retry_job(server,job['id'])
        self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'pending')

    def test_slow_timeout_does_not_start_another_long_automatic_wait(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':'AI_TIMEOUT',
                'attempts':1,'elapsed_ms':180000}) as analyze:
            image_jobs.run_one(server)
            self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'failed')
            self.assertFalse(image_jobs.run_one(server));analyze.assert_called_once()

    def test_brief_local_busy_still_has_one_background_retry(self):
        self.submit()
        with patch.object(server,'analyze_image',return_value={'ai_error':'AI_BUSY',
                'attempts':0,'elapsed_ms':2000}):
            image_jobs.run_one(server)
            self.assertEqual(image_jobs.list_jobs(server)[0]['status'],'pending')

    def test_prepare_only_saves_image_without_model_and_retry_reuses_original(self):
        import base64
        png=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(10).to_bytes(4,'big')+(10).to_bytes(4,'big')+b'x'*12
        with patch.object(server,'MEDIA',self.data/'media.json'),patch.object(server,'MEDIA_DIR',self.data/'media'),patch.object(server,'call_ai') as model:
            image=server.analyze_image({'data':base64.b64encode(png).decode(),'mime':'image/png','category':'food'},prepare_only=True)
            same=server.analyze_image({'retry_id':image['id']},prepare_only=True)
            model.assert_not_called();self.assertEqual(image['id'],same['id'])
            self.assertEqual(len(server.load_json(server.MEDIA,[])),1)
            self.assertTrue(server.resolve_media_path(image['path']).exists())

    def test_deleted_queue_is_not_resurrected(self):
        self.submit();server.save_json(server.DATA/'workspace.json',{})
        self.assertFalse(image_jobs.update(server,'test-job-1234',status='succeeded'))
        self.assertEqual(image_jobs.list_jobs(server),[])

    def test_empty_image_model_response_cannot_complete_job(self):
        import base64
        png=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+(10).to_bytes(4,'big')+(10).to_bytes(4,'big')+b'x'*12
        with patch.object(server,'MEDIA',self.data/'media.json'),patch.object(server,'MEDIA_DIR',self.data/'media'), \
             patch.object(server,'call_ai',return_value=None), \
             patch.object(server,'ai_meta',return_value={'ai_status':'connected','ai_error':None}), \
             patch.object(server.product,'chat') as chat:
            result=image_jobs.submit(server,{'client_job_id':'empty-image-model','data':base64.b64encode(png).decode(),
                'mime':'image/png','category':'food','followup':self.payload['followup']})
            image_jobs.run_one(server)
            job=next(j for j in image_jobs.list_jobs(server) if j['id']==result['job']['id'])
            self.assertEqual(job['status'],'failed')
            self.assertEqual(job['error'],'AI_INVALID_STRUCTURED_RESPONSE')
            chat.assert_not_called()

    def test_grounding_current_explicit_half_portion(self):
        source={'text':'虚构测试继续：刚才那个吃了一半，请记录实际食用量。','at':'2026-09-15T12:00:00'}
        media=[{'id':'m','type':'food'}];records=[];w={'settings':{'confirm_each':False}}
        decision={'media_id':'m','status':'consumed','evidence':'用户吃了半份','nutrition':{'kcal':[300,300]}}
        workbench.apply_food(server,w,[decision],source,records,media)
        self.assertEqual(len(records),1);self.assertIn(media[0]['food_decision']['evidence'],source['text'])
        for text in ['刚才那个还没吃，准备吃一半','如果刚才那个吃了一半呢','别人刚才那个吃了一半']:
            with self.subTest(text=text),self.assertRaises(ValueError):
                workbench.apply_food(server,w,[decision],{**source,'text':text},[],[{'id':'m','type':'food'}])

    def test_unknown_model_status_with_explicit_not_eaten_is_reference(self):
        source={'text':'这是菜单，还没吃','at':'2026-09-15T12:00:00'}
        media=[{'id':'m','type':'food'}];records=[]
        workbench.apply_food(server,{'settings':{'confirm_each':False}},[{'media_id':'m','status':'do_not_record','evidence':'not eaten'}],source,records,media)
        self.assertEqual(records,[]);self.assertEqual(media[0]['food_decision']['status'],'reference')

    def test_missing_model_action_uses_explicit_fraction_only(self):
        image={'id':'m','review':{'record_candidates':[{'type':'meal','label':'测试米饭','value':{'nutrition':{'kcal':[600,600],'protein_g':[20,20]}}}]}}
        d=workbench.grounded_food_decision('刚才那个吃了一半',image)
        self.assertEqual(d['status'],'consumed');self.assertEqual(d['nutrition']['kcal'],[300,300])
        self.assertEqual(d['nutrition']['protein_g'],[10,10]);self.assertIsNone(d['nutrition']['fat_g'])
        self.assertIsNone(workbench.grounded_food_decision('如果刚才那个吃了一半',image))
        self.assertIsNone(workbench.grounded_food_decision('我午饭吃完了',image))
        self.assertEqual(workbench.grounded_food_decision('这份还没吃',image)['status'],'reference')
        image['type']='food';records=[]
        workbench.apply_food(server,{'settings':{'confirm_each':False}},[{'media_id':'m','status':'record','evidence':'ate half'}],{'text':'刚才那个吃了一半','at':'2026-09-15T12:00:00'},records,[image])
        self.assertEqual(records[0]['value']['nutrition']['kcal'],[300,300])
        records=[]
        workbench.apply_food(server,{'settings':{'confirm_each':False}},[{'media_id':'m','status':'consumed','evidence':'刚才那个吃了一半','nutrition':{'kcal':None}}],{'text':'刚才那个吃了一半','at':'2026-09-15T12:00:00'},records,[image])
        self.assertEqual(records[0]['value']['nutrition']['kcal'],[300,300])

    def test_shared_plate_with_vague_small_portion_never_uses_model_total(self):
        image={'id':'m','type':'food','review':{'record_candidates':[{'type':'meal','label':'测试菜',
            'value':{'nutrition':{'kcal':[900,900]}}}]}}
        records=[]
        source={'text':'3个人吃，我只吃了一点','at':'2026-09-15T12:00:00'}
        workbench.apply_food(server,{'settings':{'confirm_each':False}},[{'media_id':'m',
            'status':'consumed','evidence':'我只吃了一点','nutrition':{'kcal':[900,900]}}],source,records,[image])
        self.assertEqual(len(records),1)
        self.assertIsNone(records[0]['value']['nutrition']['kcal'])
        records=[]
        workbench.apply_food(server,{'settings':{'confirm_each':False}},[{'media_id':'m',
            'status':'consumed','evidence':'我没吃多少','nutrition':{'kcal':[900,900]}}],
            {'text':'这份三个人分着吃，我没吃多少','at':'2026-09-15T12:00:00'},records,[image])
        self.assertEqual(len(records),1)
        self.assertIsNone(records[0]['value']['nutrition']['kcal'])
        self.assertEqual(image['food_decision']['status'],'consumed')


if __name__=='__main__':unittest.main()
