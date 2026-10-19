"""Isolated, controllable image/chat fixture; no remote model or real health data."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8798)
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='zhiheng-image-chat-ui-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,storage
    storage.initialize(server.DATA)
    permit=threading.Semaphore(0)
    failures=[]
    def model(messages,vision=False,**kwargs):
        server.AI_STATE.error='';server.AI_STATE.meta={}
        if vision:
            if not permit.acquire(timeout=50):
                server.AI_STATE.error='AI_TIMEOUT';return None
            if failures:
                failures.pop();server.AI_STATE.error='AI_AUTH_FAILED';return None
            return json.dumps({'category':'food','summary':'这是一份米饭配蔬菜。可以先看看搭配，再结合你实际吃的份量讨论。',
                'question':'你这次吃了多少，还是准备吃？','foods':[{'name':'米饭和蔬菜','grams':None,
                'nutrition_basis':'portion_estimate','nutrition':{'kcal':[450,650],'protein_g':[15,25],
                'carbs_g':[65,90],'fat_g':[12,20]},'uncertainty':'合成界面验收用估计'}]},ensure_ascii=False)
        request_text=str(messages[-1].get('content','')) if messages else ''
        time.sleep(2 if '滚动验收慢回复' in request_text else .2)
        reply='可以，我们接着聊。你刚才提到的实际情况我会一起考虑。'
        if '滚动验收长回复' in request_text:
            reply='\n\n'.join(f'第 {i+1} 段界面验收回复：这是用于检查滚动位置的合成内容，未添加健康事实。' for i in range(30))
        return json.dumps({'reply':reply,
                           'decision':{'action':'none'},'plan':None},ensure_ascii=False)
    server.call_ai=model
    server.STARTUP_STATUS={'ok':True,'checks':['isolated_image_chat_ui']}
    class Handler(server.Handler):
        def do_POST(self):
            if self.path=='/__qa__/release':
                request=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
                if request.get('fail'):failures.append(True)
                permit.release();self.send_json(200,{'ok':True});return
            super().do_POST()
    print('Isolated image/chat UI fixture ready',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
