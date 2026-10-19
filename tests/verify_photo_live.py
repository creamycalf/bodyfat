"""Send only the synthetic normalized browser test image to the actual vision model."""
import sys,json,base64,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,storage
out=Path('tmp')/('photo-live-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
server.DATA=out/'data';server.MEDIA_DIR=server.DATA/'media'
for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):setattr(server,key,server.DATA/(key.lower()+'.json'))
storage.initialize(server.DATA);server.CONFIG['ai']['base_url']='http://47.110.38.211:8080/v1'
photo=Path('tmp/normalized-camera-test.jpg').read_bytes()
print('START real vision',flush=True)
result=server.analyze_image({'data':base64.b64encode(photo).decode(),'mime':'image/jpeg','category':'general','context':'这是合成测试色块，不是真实餐食。只简要描述看到的图像，不要生成健康数据。'})
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert result.get('ai_status')=='connected' and not result.get('ai_error'),result.get('ai_error')
print('PASS real vision:',out,flush=True)
