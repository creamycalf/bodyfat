"""Rejected uploads must return their HTTP error without unbounded reads."""
import io
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock,patch

import server
import test_workbench


class RestoreRejectionHttpTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def test_large_rejected_upload_returns_error_without_retry_or_restore(self):
        body=b'x'*(1024*1024)
        with patch.object(server,'CONFIG',{'storage':{'max_backup_mb':8}}),patch.object(server,'restore_backup') as restore:
            httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            before=server.records()
            try:
                # Both production rejection branches, one attempt each.
                for headers,status,code in [({'Content-Type':'application/zip'},400,'confirmation_required'),
                    ({'Content-Type':'application/json','X-Zhiheng-Confirm':'restore'},415,'zip_content_type_required')]:
                    request=urllib.request.Request(f'http://127.0.0.1:{httpd.server_port}/api/restore',
                                                   data=body,headers=headers,method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request,timeout=3)
                    with caught.exception as response:
                        self.assertEqual(response.code,status)
                        self.assertEqual(json.loads(response.read())['error'],code)
                restore.assert_not_called()
                self.assertEqual(server.records(),before)
            finally:httpd.shutdown();httpd.server_close();thread.join(timeout=3)

    def handler(self,length,reader=None,timeout=None):
        handler=server.Handler.__new__(server.Handler)
        handler.headers={'Content-Length':str(length)}
        handler.rfile=reader or io.BytesIO(b'x'*70000)
        handler.connection=Mock();handler.connection.gettimeout.return_value=timeout
        handler.send_json=Mock()
        return handler

    def test_discard_uses_small_chunks_and_restores_socket_timeout(self):
        reader=Mock();reader.read1.side_effect=[b'x'*65536,b'x'*4464]
        handler=self.handler(70000,reader,timeout=3)
        handler.reject_restore(400,'confirmation_required')
        self.assertEqual([call.args[0] for call in reader.read1.call_args_list],[65536,4464])
        self.assertEqual(handler.connection.settimeout.call_args.args,(3,))
        handler.send_json.assert_called_once_with(400,{'error':'confirmation_required'})

    def test_invalid_negative_empty_and_oversized_lengths_are_not_read(self):
        with patch.object(server,'max_backup_bytes',return_value=1024):
            for length in ('invalid',-1,0,1025):
                with self.subTest(length=length):
                    reader=Mock();handler=self.handler(length,reader)
                    handler.reject_restore(413,'backup_too_large')
                    reader.read1.assert_not_called()
                    handler.connection.gettimeout.assert_not_called()
                    handler.send_json.assert_called_once_with(413,{'error':'backup_too_large'})

    def test_total_budget_stops_trickling_sender_and_restores_timeout(self):
        reader=Mock();reader.read1.return_value=b'x'
        handler=self.handler(100,reader)
        with patch.object(server.time,'monotonic',side_effect=[10,10.1,10.9,11.1]):
            handler.reject_restore(400,'confirmation_required')
        self.assertEqual(reader.read1.call_count,2)
        self.assertEqual(handler.connection.settimeout.call_args.args,(None,))

    def test_read_timeout_still_returns_original_rejection(self):
        reader=Mock();reader.read1.side_effect=TimeoutError('slow upload')
        handler=self.handler(100,reader,timeout=0.05)
        handler.reject_restore(415,'zip_content_type_required')
        self.assertLessEqual(handler.connection.settimeout.call_args_list[0].args[0],0.05)
        self.assertEqual(handler.connection.settimeout.call_args.args,(0.05,))
        handler.send_json.assert_called_once_with(415,{'error':'zip_content_type_required'})


if __name__=='__main__':unittest.main()
