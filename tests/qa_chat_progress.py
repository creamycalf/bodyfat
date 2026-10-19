"""Isolated UI fixture; never calls the configured model or production storage."""
import json
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import storage

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='zhiheng-progress-') as folder:
        server.DATA=Path(folder)
        server.MEDIA_DIR=server.DATA/'media'
        for name in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
            setattr(server,name,server.DATA/(name.lower()+'.json'))
        storage.initialize(server.DATA)
        def reply(*args,**kwargs):
            time.sleep(5)
            return json.dumps({'reply':'测试回复已完成，未添加健康事实。','decision':{'action':'none','reason':'仅验证交互'},'plan':None})
        server.call_ai=reply
        server.STARTUP_STATUS={'ok':True,'checks':['isolated_progress']}
        server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler).serve_forever()
