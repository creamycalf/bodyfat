"""Opt-in remote smoke test with a synthetic image and isolated application data."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qa_current_vision_live import synthetic_png

with tempfile.TemporaryDirectory(prefix='zhiheng-sol-live-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server
    config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    server.CONFIG=config
    assert config['ai']['model']==config['ai']['vision_model']=='gpt-6.1-sol'
    results=[]
    requests=[('text',[{'role':'user','content':'软件连接测试。请仅返回 JSON：{"ok":true,"reply":"连接正常"}'}],False),
        ('image',[{'role':'user','content':[{'type':'text','text':'这是一张合成测试图。只返回JSON，字段description用中文简短描述图案颜色和形状。'},
        {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(synthetic_png()).decode()}}]}],True)]
    for name,messages,vision in requests:
        started=time.monotonic()
        raw=server.call_ai(messages,vision=vision)
        parsed=server.parse_json(raw)
        row={'test':name,'requested_model':'gpt-6.1-sol','success':bool(raw) and isinstance(parsed,dict),
             'error':server.ai_meta().get('ai_error'),'elapsed_seconds':round(time.monotonic()-started,2),
             'reply':parsed if isinstance(parsed,dict) else None}
        # Redact the controlled credential even if a provider unexpectedly echoes it.
        key=os.environ.get(config['ai'].get('api_key_env','ZHIHENG_AI_API_KEY'),'')
        row=json.loads(json.dumps(row,ensure_ascii=False).replace(key,'[REDACTED]')) if key else row
        results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (ROOT/'tmp/sol-live-0.4.35.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if all(row['success'] for row in results) else 1)
