import time
import threading
import unittest
from unittest.mock import patch
import server


class VisionTimeoutTests(unittest.TestCase):
    def setUp(self):
        state=dict(server.AI_STATE.__dict__)
        def restore():
            server.AI_STATE.__dict__.clear()
            server.AI_STATE.__dict__.update(state)
        self.addCleanup(restore)

    def test_vision_has_separate_bounded_request_timeout(self):
        with patch.object(server, 'CONFIG', {'ai': {'timeout_seconds': 75}}):
            self.assertEqual(server.model_request_timeout(), 75)
            self.assertEqual(server.model_request_timeout(True), 180)
        for value, expected in [('invalid', 180), (9999, 240), (-1, 5)]:
            with self.subTest(value=value), patch.object(server, 'CONFIG', {'ai': {'vision_timeout_seconds': value}}):
                self.assertEqual(server.model_request_timeout(True), expected)

    def test_vision_survives_text_deadline_and_honors_explicit_budget(self):
        def response(*args,**kwargs):
            time.sleep(.03)
            return 'vision result'
        with patch.object(server, 'AI_TOTAL_TIMEOUT_SECONDS', .001), patch.object(server, '_call_ai_request', side_effect=response):
            self.assertEqual(server.call_ai([], vision=True), 'vision result')
            self.assertIsNone(server.call_ai([], vision=True, total_timeout=0))
            self.assertEqual(server.ai_meta()['ai_error'], 'AI_TIMEOUT')
        time.sleep(.05)

    def test_short_deadline_reaches_transport_and_releases_slot(self):
        finished=threading.Event();observed=[];slots=threading.BoundedSemaphore(1)
        def transport(request,timeout):
            observed.append(timeout)
            time.sleep(timeout)
            finished.set()
            raise TimeoutError('timed out')
        config={'ai':{'api_key':'test-only','timeout_seconds':75,'protocol':'chat_completions'}}
        with patch.object(server,'CONFIG',config),patch.object(server,'AI_LIMIT',slots),patch.object(server,'model_urlopen',side_effect=transport):
            self.assertIsNone(server.call_ai([],total_timeout=.06))
            self.assertTrue(finished.wait(1))
            self.assertTrue(slots.acquire(timeout=1))
            slots.release()
        self.assertEqual(len(observed),1)
        self.assertGreater(observed[0],0)
        self.assertLessEqual(observed[0],.060001)

    def test_zero_budget_never_starts_transport(self):
        with patch.object(server,'_call_ai_request') as request:
            self.assertIsNone(server.call_ai([],total_timeout=0))
            request.assert_not_called()
