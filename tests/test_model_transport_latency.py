"""Avoid redundant model POSTs while preserving bounded transient retries."""
import io
import json
import socket
import ssl
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

import server


class ModelTransportLatencyTests(unittest.TestCase):
    def setUp(self):
        previous=dict(server.AI_STATE.__dict__)
        def restore():
            server.AI_STATE.__dict__.clear();server.AI_STATE.__dict__.update(previous)
        self.addCleanup(restore)
        self.config={'ai':{'api_key':'test-only-secret','base_url':'https://example.invalid/v1',
                           'model':'test-model','protocol':'auto','retry_count':1}}

    def http_error(self,status):return urllib.error.HTTPError('https://example.invalid',status,'test',{},io.BytesIO())
    def response(self,endpoint='chat'):
        value={'choices':[{'message':{'content':'useful full reply'},'finish_reason':'stop'}]} if endpoint=='chat' else {'output_text':'useful full reply'}
        return io.BytesIO(json.dumps(value).encode())

    def run_model(self,effects,**kwargs):
        with patch.object(server,'CONFIG',self.config),patch.object(server,'model_urlopen',side_effect=effects) as transport:
            reply=server.call_ai([{'role':'user','content':'private test health text'}],**kwargs)
            return reply,server.ai_meta(),transport

    def test_dns_tls_failures_do_not_repeat_or_switch_protocol(self):
        failures=[urllib.error.URLError('AI_DNS_FAILED'),urllib.error.URLError('AI_TLS_FAILED'),
                  urllib.error.URLError(socket.gaierror('unresolved')),urllib.error.URLError(ssl.SSLError('invalid certificate'))]
        for failure in failures:
            with self.subTest(error=type(failure.reason).__name__),patch.object(server.time,'sleep') as sleep:
                reply,meta,transport=self.run_model(failure)
                self.assertIsNone(reply);self.assertEqual(transport.call_count,1);sleep.assert_not_called()
                self.assertIn(meta['ai_error'],('AI_DNS_FAILED','AI_TLS_FAILED'))

    def test_transient_service_errors_keep_retry_without_duplicate_protocol_post(self):
        for status in (429,500,503):
            with self.subTest(status=status),patch.object(server.time,'sleep') as sleep:
                reply,meta,transport=self.run_model(self.http_error(status))
                self.assertIsNone(reply);self.assertEqual(transport.call_count,2)
                self.assertEqual([call.args[0].full_url for call in transport.call_args_list],['https://example.invalid/v1/chat/completions']*2)
                sleep.assert_called_once_with(.35)
                self.assertEqual(meta['attempts'],2)

    def test_transient_service_retry_can_still_succeed(self):
        with patch.object(server.time,'sleep'):
            reply,meta,transport=self.run_model([self.http_error(503),self.response()])
        self.assertEqual(reply,'useful full reply');self.assertEqual(transport.call_count,2)
        self.assertIsNone(meta['ai_error'])

    def test_auto_endpoint_incompatibility_switches_without_retry_sleep(self):
        for status in (404,405,501):
            with self.subTest(status=status),patch.object(server.time,'sleep') as sleep:
                reply,meta,transport=self.run_model([self.http_error(status),self.response('responses')])
                self.assertEqual(reply,'useful full reply');self.assertEqual(transport.call_count,2)
                self.assertTrue(transport.call_args_list[1].args[0].full_url.endswith('/responses'))
                sleep.assert_not_called()

    def test_explicit_chat_protocol_never_switches(self):
        self.config['ai']['protocol']='chat_completions'
        reply,meta,transport=self.run_model(self.http_error(404))
        self.assertIsNone(reply);self.assertEqual(transport.call_count,1)
        self.assertEqual(meta['ai_error'],'AI_HTTP_404')

    def test_unknown_connection_failure_retains_one_retry_but_no_protocol_switch(self):
        with patch.object(server.time,'sleep') as sleep:
            reply,meta,transport=self.run_model(urllib.error.URLError(ConnectionResetError('reset')))
        self.assertIsNone(reply);self.assertEqual(transport.call_count,2);sleep.assert_called_once_with(.35)

    def test_timeout_is_not_retried(self):
        with patch.object(server.time,'sleep') as sleep:
            reply,meta,transport=self.run_model(TimeoutError('timed out'))
        self.assertIsNone(reply);self.assertEqual(transport.call_count,1);sleep.assert_not_called()

    def test_invalid_model_response_does_not_generate_duplicate_under_another_protocol(self):
        reply,meta,transport=self.run_model([io.BytesIO(b'not JSON')])
        self.assertIsNone(reply);self.assertEqual(transport.call_count,1)
        self.assertEqual(meta['ai_error'],'AI_INVALID_RESPONSE')

    def test_no_backoff_when_deadline_cannot_accommodate_it(self):
        slots=threading.BoundedSemaphore(1)
        with patch.object(server,'AI_LIMIT',slots),patch.object(server.time,'sleep') as sleep:
            reply,meta,transport=self.run_model(self.http_error(503),total_timeout=.05)
        self.assertIsNone(reply);self.assertEqual(transport.call_count,1);sleep.assert_not_called()
        self.assertTrue(slots.acquire(blocking=False));slots.release()
        self.assertEqual(meta['retry_wait_ms'],0)

    def test_attempt_metadata_has_only_safe_sizes_codes_paths_and_timings(self):
        reply,meta,transport=self.run_model([self.http_error(503),self.response()])
        self.assertEqual(reply,'useful full reply')
        self.assertGreaterEqual(meta['retry_wait_ms'],300)
        self.assertLess(meta['transport_ms'],meta['retry_wait_ms'])
        self.assertEqual(len(meta['attempt_trace']),2)
        for trace in meta['attempt_trace']:
            self.assertLessEqual(set(trace),{'endpoint','request_bytes','status','error','elapsed_ms'})
            self.assertGreater(trace['request_bytes'],0)
        safe=json.dumps(meta)
        self.assertNotIn('test-only-secret',safe);self.assertNotIn('private test health text',safe)
        self.assertNotIn('example.invalid',safe)

    def test_queue_time_is_measured_separately(self):
        slots=threading.BoundedSemaphore(1);slots.acquire()
        released=threading.Timer(.03,slots.release);released.start()
        try:
            with patch.object(server,'AI_LIMIT',slots):reply,meta,_=self.run_model([self.response()])
        finally:released.join()
        self.assertEqual(reply,'useful full reply');self.assertGreaterEqual(meta['queue_ms'],15)
        self.assertGreaterEqual(meta['elapsed_ms'],meta['queue_ms'])


if __name__=='__main__':unittest.main()
