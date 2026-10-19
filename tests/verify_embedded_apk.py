"""Verify the built APK's actual configuration with isolated health data."""
import json, os, sys, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
apk=Path(sys.argv[1]);out=ROOT/'tmp/embedded-apk-20260918';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='zhiheng-embedded-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,storage,product
    with zipfile.ZipFile(apk) as archive:
        config=json.loads(archive.read('assets/engine/default_model.json'))
    server.CONFIG=config;storage.initialize(server.DATA)
    result=product.chat(server,{'text':'今天体重71.9公斤，请只记录体重，不要制定计划。','conversation_id':'embedded-check','client_message_id':'embedded-check-1'})
    state=product.snapshot(server)
    passed=result.get('ai_status')=='connected' and not result.get('ai_error') and any(r['type']=='weight' and r['value'].get('kg')==71.9 for r in state['records'])
    report={'passed':passed,'ai_status':result.get('ai_status'),'ai_error':result.get('ai_error'),'records':len(state['records']),'source':'APK embedded configuration; host runtime in disposable data directory; not Android network verification'}
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    if not passed:raise SystemExit(1)
