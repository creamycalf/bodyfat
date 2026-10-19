"""Synthetic image/text probes; credentials stay in the configured environment."""
import base64,io,json,os,sys,urllib.request,time
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))['ai']
key=os.environ[config.get('api_key_env','ZHIHENG_AI_API_KEY')]
results=[]
for model in ('claude-opus-4-8','claude-sonnet-4-6'):
    for code in ('6729','3841'):
        picture=Image.new('RGB',(500,180),'white');draw=ImageDraw.Draw(picture)
        draw.text((30,50),code,fill='black',font_size=70)
        stream=io.BytesIO();picture.save(stream,format='PNG')
        messages=[{'role':'user','content':[{'type':'text','text':'Read the four digits in the image. Return digits only.'},
            {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()}}]}]
        start=time.monotonic()
        request=urllib.request.Request('http://47.110.38.211:8080/v1/chat/completions',
            data=json.dumps({'model':model,'messages':messages,'max_tokens':100}).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        row={'model':model,'expected':code}
        try:
            with urllib.request.urlopen(request,timeout=45) as response:result=json.load(response)
            row['reply']=result['choices'][0]['message']['content'];row['pass']=row['reply'].strip()==code
        except Exception as error:row['error']=type(error).__name__
        row['seconds']=round(time.monotonic()-start,2);results.append(row);print(json.dumps(row),flush=True)
(ROOT/'tmp/model-image-candidates-20260928.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
