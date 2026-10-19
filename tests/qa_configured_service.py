"""Exercise configured text and two image jobs using disposable synthetic data."""
import base64,io,json,os,tempfile,sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='zhiheng-configured-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,storage,product,image_jobs
    storage.initialize(server.DATA)
    rows=[]
    answer=product.chat(server,{'text':'我想瘦一点，但不想马上做计划，先聊聊行吗？',
        'conversation_id':'configured-live','client_message_id':'configured-text-1'})
    rows.append({'kind':'chat','status':answer.get('ai_status'),'error':answer.get('ai_error'),'reply':answer['reply']})
    print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    for n,code in enumerate(('6729','3841'),1):
        picture=Image.new('RGB',(500,180),'white');ImageDraw.Draw(picture).text((30,50),code,fill='black',font_size=70)
        buffer=io.BytesIO();picture.save(buffer,format='PNG')
        with patch.object(image_jobs,'ensure_worker'):
            image_jobs.submit(server,{'client_job_id':f'configured-image-{n}',
                'data':base64.b64encode(buffer.getvalue()).decode(),'mime':'image/png','category':'general',
                'context':'这是一张测试数字图，请读出图中的数字，不估算营养。',
                'followup':{'conversation_id':'configured-live','text':'请告诉我这张测试图片上的数字，不保存健康事实。'}})
        image_jobs.run_one(server)
        job=image_jobs.list_jobs(server)[-1]
        media=server.load_json(server.MEDIA,[])[-1]
        rows.append({'kind':'image','number':n,'expected':code,'status':job['status'],'error':job.get('error'),
                     'review':media.get('review'),'result':job.get('result')})
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    Path('tmp/configured-service-0.4.23.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    assert rows[0]['status']=='connected'
    assert all(row['status']=='succeeded' and row['expected'] in json.dumps(row['review']) for row in rows[1:])
    assert len(server.load_json(server.CONVERSATIONS,[])[0]['messages'])==6
