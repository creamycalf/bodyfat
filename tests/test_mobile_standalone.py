import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'android/standalone/app/src/main/python/mobile_runtime.py'
spec=importlib.util.spec_from_file_location('mobile_runtime_test',MODULE)
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class StandaloneTests(unittest.TestCase):
    def test_config_preserves_supported_request_limits(self):
        supplied={'base_url':'https://example.com/v1','model':'m','api_key':'synthetic-key',
                  'timeout_seconds':60,'vision_timeout_seconds':225,'retry_count':0,
                  'max_tokens':1200,'max_output_tokens':2048,'extra':'ignored'}
        normalized=runtime.validate_config(json.dumps({'ai':supplied}))['ai']
        for field in ('timeout_seconds','vision_timeout_seconds','retry_count','max_tokens','max_output_tokens'):
            self.assertEqual(normalized[field],supplied[field])
        self.assertNotIn('extra',normalized)
        defaults=runtime.validate_config(json.dumps({key:supplied[key] for key in ('base_url','model','api_key')}))['ai']
        self.assertEqual({field:defaults[field] for field in ('timeout_seconds','vision_timeout_seconds','retry_count')},
                         {'timeout_seconds':75,'vision_timeout_seconds':180,'retry_count':1})
        self.assertNotIn('max_tokens',defaults);self.assertNotIn('max_output_tokens',defaults)
        strings=runtime.validate_config(json.dumps({**supplied,'timeout_seconds':'75','max_tokens':'1200'}))['ai']
        self.assertEqual(strings['timeout_seconds'],75);self.assertEqual(strings['max_tokens'],1200)

    def test_config_rejects_invalid_request_limits_without_silent_defaults(self):
        supplied={'base_url':'https://example.com/v1','model':'m','api_key':'synthetic-key'}
        invalid={'timeout_seconds':[None,True,4,121,75.5,'slow','75.5',{},float('nan')],
                 'vision_timeout_seconds':[0,241,False,'no'],
                 'retry_count':[-1,3,1.5,True],
                 'max_tokens':[0,-1,True,1200.5,'large','1_200','1e3'],
                 'max_output_tokens':[0,-1,False,float('inf')]}
        for field,values in invalid.items():
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,field):
                    runtime.validate_config(json.dumps({**supplied,field:value}))

    def test_configure_retains_request_parameters_when_model_settings_are_edited(self):
        server_stub=SimpleNamespace(DATA_LOCK=__import__('threading').RLock(),CONFIG={})
        original={'base_url':'https://example.com/v1','model':'previous','api_key':'synthetic-key',
                  'timeout_seconds':75,'vision_timeout_seconds':210,'retry_count':1,
                  'max_tokens':1200,'max_output_tokens':1600}
        edited={**original,'model':'next','vision_model':'vision-next','protocol':'chat_completions'}
        with patch.dict(sys.modules,{'server':server_stub}):
            normalized=json.loads(runtime.configure(json.dumps(edited)))['ai']
        self.assertEqual(server_stub.CONFIG['ai'],normalized)
        self.assertEqual(normalized['model'],'next');self.assertEqual(normalized['vision_model'],'vision-next')
        for field in ('timeout_seconds','vision_timeout_seconds','retry_count','max_tokens','max_output_tokens'):
            self.assertEqual(normalized[field],original[field])

    def test_only_user_approved_http_endpoint_is_allowed(self):
        config={'base_url':'http://47.110.38.211:8080','model':'m','api_key':'fake'}
        self.assertEqual(runtime.validate_config(json.dumps(config))['ai']['base_url'],'http://47.110.38.211:8080/v1')
        for url in ('http://47.110.38.211:8081/v1','http://47.110.38.212:8080/v1','http://47.110.38.211.evil.test:8080/v1'):
            with self.assertRaises(ValueError):runtime.validate_config(json.dumps({**config,'base_url':url}))

    def test_android_transport_preserves_errors_and_payload(self):
        request=urllib.request.Request('https://example.com/v1/chat/completions',data=b'{"model":"test"}',headers={'Authorization':'Bearer fake'})
        replies=[{'status':200,'body':'{"ok":true}'},{'status':401,'body':'denied'},{'error':'AI_TLS_FAILED'},{'error':'AI_DNS_FAILED'},{'error':'AI_TIMEOUT'}]
        captured=[]
        def send(*args):captured.append(args);return json.dumps(replies.pop(0))
        with patch.dict(sys.modules,{'java':SimpleNamespace(jclass=lambda name:SimpleNamespace(request=send))}):
            with runtime.android_urlopen(request,12) as response:self.assertEqual(json.load(response),{'ok':True})
            self.assertEqual(captured[0][3],12000)
            self.assertEqual(json.loads(captured[0][1])['Authorization'],'Bearer fake')
            with self.assertRaises(urllib.error.HTTPError) as error:runtime.android_urlopen(request,12)
            self.assertEqual(error.exception.code,401)
            for code in ('AI_TLS_FAILED','AI_DNS_FAILED','AI_TIMEOUT'):
                with self.assertRaises(urllib.error.URLError) as error:runtime.android_urlopen(request,12)
                self.assertEqual(error.exception.reason,code)

    def test_config_rejects_insecure_and_incomplete_settings(self):
        self.assertFalse(runtime.validate_config('{}')['ai']['enabled'])
        for base in ('http://192.168.1.1:8787','file:///tmp/a','https://user:pass@example.com/v1','https://example.com/v1?token=x'):
            with self.assertRaises(ValueError):runtime.validate_config(json.dumps({'base_url':base,'model':'m','api_key':'test'}))
        with self.assertRaises(ValueError):runtime.validate_config('{"base_url":"https://example.com/v1","model":"m"}')
        config=runtime.validate_config('{"base_url":"https://example.com/v1","model":"m","api_key":"test","extra":"ignored"}')
        self.assertEqual(config['ai']['vision_model'],'m');self.assertNotIn('extra',config['ai'])

    def test_local_engine_offline_record_survives_process_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            session_file=Path(folder)/'session.json';data=Path(folder)/'data'
            code='''import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import mobile_runtime
Path(sys.argv[4]).write_text(mobile_runtime.start(sys.argv[2],sys.argv[3]),encoding="utf-8")
time.sleep(120)
'''
            def launch():
                p=subprocess.Popen([sys.executable,'-c',code,str(MODULE.parent),str(ROOT),str(data),str(session_file)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                import time
                for _ in range(100):
                    if session_file.exists():return p,json.loads(session_file.read_text('utf-8'))
                    if p.poll() is not None:self.fail(p.stderr.read().decode(errors='replace'))
                    time.sleep(.05)
                p.terminate();p.wait();self.fail('Local engine startup timeout')
            def request(session,path,payload=None):
                req=urllib.request.Request(session['url'].rstrip('/')+path,data=json.dumps(payload).encode() if payload else None,headers={'Cookie':session['cookie'],'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
            process,session=launch()
            try:
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(session['url']+'api/work/state')
                result=request(session,'/api/work/chat',{'text':'今天体重72公斤','conversation_id':'offline-test','client_message_id':'offline-record'})
                state=request(session,'/api/work/state')
                self.assertEqual(state['records'][0]['value']['kg'],72)
                self.assertTrue((data/'health.sqlite3').exists())
            finally:process.terminate();process.wait();process.stderr.close()
            session_file.unlink();process,session2=launch()
            try:
                self.assertNotEqual(session['cookie'],session2['cookie'])
                restored=request(session2,'/api/work/state')
                self.assertEqual(restored['records'],state['records'])
                self.assertEqual(restored['conversations'],state['conversations'])
            finally:process.terminate();process.wait();process.stderr.close()
