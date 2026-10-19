"""Real gateway smoke test, isolated storage, no credential or health-data output."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    photo=Path(sys.argv[1])
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    ai=config['ai']
    if not os.environ.get(ai.get('api_key_env','ZHIHENG_AI_API_KEY')):
        raise SystemExit('Controlled model credential is missing')
    results={'base_url':ai['base_url'],'model':ai['model'],'text':[],'image':[],'model_calls':[]}
    with tempfile.TemporaryDirectory(prefix='zhiheng-request-audit-') as folder:
        os.environ['ZHIHENG_DATA_DIR']=folder
        import server,storage,image_jobs
        server.CONFIG=config;storage.initialize(server.DATA)
        server.STARTUP_STATUS={'ok':True,'checks':['isolated-live-audit']}
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        origin=f'http://127.0.0.1:{httpd.server_port}'
        cid='request-audit-chat';original=server.call_ai
        def counted(messages,vision=False,**kwargs):
            started=time.monotonic()
            answer=original(messages,vision,**kwargs)
            results['model_calls'].append({'vision':vision,'elapsed_ms':round((time.monotonic()-started)*1000),
                                         'error':server.ai_meta().get('ai_error')})
            return answer
        server.call_ai=counted
        def post(path,payload,stream=False):
            req=urllib.request.Request(origin+path,data=json.dumps(payload).encode(),headers={'content-type':'application/json'})
            with urllib.request.urlopen(req,timeout=240) as response:
                if not stream:return json.load(response)
                for line in response:
                    item=json.loads(line)
                    if item['type']=='result':return item['result']
                    if item['type']=='error':raise RuntimeError(str(item))
        def chat(n,text):
            started=time.monotonic()
            answer=post('/api/work/chat-stream',{'text':text,'conversation_id':cid,'client_message_id':f'audit-live-text-{n}'},True)
            row={'elapsed_ms':round((time.monotonic()-started)*1000),'reply':answer['reply'],
                 'ai_error':answer.get('ai_error'),'extraction_error':answer.get('extraction_error')}
            results['text'].append(row);print(json.dumps({'text':n,**row},ensure_ascii=False),flush=True)
            assert not answer.get('ai_error') and answer['reply']
        try:
            # Drive the persistent worker manually, avoiding an unbounded daemon
            # after this temporary data directory has been removed.
            with patch.object(image_jobs,'ensure_worker'):
                payload={'data':base64.b64encode(photo.read_bytes()).decode(),'mime':'image/png',
                         'category':'food','context':'只分析截图上方餐盘里的食物，忽略界面文字。这份是参考图片，我没有吃。',
                         'followup':{'text':'这是参考照片，我没有吃，请分析照片。','conversation_id':cid},'background':True}
                for n in (1,2):post('/api/analyze-image',{**payload,'client_job_id':f'audit-live-image-{n}'})
                failures=[]
                def images():
                    try:
                        for n in (1,2):
                            started=time.monotonic();assert image_jobs.run_one(server)
                            results['image'].append({'number':n,'elapsed_ms':round((time.monotonic()-started)*1000)})
                            print(json.dumps({'image_attempt':n,'jobs':image_jobs.list_jobs(server)},ensure_ascii=False),flush=True)
                    except Exception as e:failures.append(type(e).__name__)
                worker=threading.Thread(target=images);worker.start()
                chat(1,'想先聊聊减重，不急着制定计划。你会怎么了解我的情况？')
                chat(2,'我只是想知道为什么晚饭后容易饿，先解释原因，别给我安排。')
                worker.join(430)
                assert not worker.is_alive() and not failures
                # Publish any reports deferred while the foreground was active.
                for _ in range(4):
                    jobs=image_jobs.list_jobs(server)
                    pending=[j for j in jobs if j['status']=='pending']
                    if not pending:break
                    for j in pending:image_jobs.update(server,j['id'],next_at=0)
                    image_jobs.run_one(server)
                jobs=image_jobs.list_jobs(server)
                state=server.product.snapshot(server)
                assert all(j['status']=='succeeded' for j in jobs),str([(j['status'],j.get('error')) for j in jobs])
                assert len(state['media'])==2
                assert all(m.get('review',{}).get('report') for m in state['media'])
                assert not any(r['type']=='meal' for r in state['records'])
                assert sum(not c['vision'] for c in results['model_calls'])==2
                chat(3,'接着说，只有饿的感觉，能不能直接说明我血糖低？')
                results.update(passed=True,jobs=[{'status':j['status'],'stage':j['stage']} for j in jobs],
                               report_count=len(state['media']),record_count=len(state['records']))
        finally:
            httpd.shutdown();httpd.server_close()
            (ROOT/'tmp/request-audit-live-0.4.27.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'calls':results['model_calls']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
