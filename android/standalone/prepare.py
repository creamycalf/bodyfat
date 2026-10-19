"""Package only explicit public code/assets, never desktop data or config."""
import shutil, json, os, argparse, hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
# The offline speech engine must ship completely; it never downloads on the phone.
voice=HERE/'app/src/main/assets/voice'
expected_voice={'vosk-model-small-cn-0.22.zip':'3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba'}
for name,digest in expected_voice.items():
    asset=voice/name
    if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest()!=digest:
        raise SystemExit('Missing or damaged bundled offline speech model: '+name)
for name,digest in {'vosk-android-0.3.75.aar':'ab2f8b91ac8051561aa325546b35fed9a68b36b8121bac5c6fb927525c4adfad',
                    'jna-5.18.1.aar':'7f053e3ec99e14dd71259c82c1c8a02738d64a13c31226b2acc170f3060951e0'}.items():
    library=HERE/'app/libs'/name
    if not library.is_file() or hashlib.sha256(library.read_bytes()).hexdigest()!=digest:
        raise SystemExit('Missing or damaged offline speech library: '+name)
parser=argparse.ArgumentParser()
parser.add_argument('--embed-model',action='store_true')
parser.add_argument('--base-url',default=None)
args=parser.parse_args()
engine=HERE/'app/src/main/assets/engine';engine.mkdir(parents=True,exist_ok=True)
files=['server.py','storage.py','product.py','workbench.py','meal_records.py','report_editor.py','image_jobs.py','intake.py','coach_review.py','coach_actions.py','nutrition_reports.py','food_catalog.py','consultation.py',
       'index.html','app.js','app.css','safety.css','health-pages.css','health-pages.js',
       'nutrition-info.js','nutrition-report-ui.js','nutrition-report.css','voice.js','archive-tools.js','meal-records.js','workbench-ui.js','image-jobs-ui.js','mobile-compat.js','image-upload.js']
for name in files:shutil.copyfile(ROOT/name,engine/name)
res=HERE/'app/src/main/res/drawable';res.mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'android/res/drawable/icon.xml',res/'icon.xml')
default_file=engine/'default_model.json'
if default_file.exists():default_file.unlink()
assert sorted(p.name for p in engine.iterdir())==sorted(files),'Unexpected packaged file'
if not args.embed_model:
    print('Prepared public files only; no embedded credentials')
    raise SystemExit(0)
config_path=ROOT/'config.json'
config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
ai=config.get('ai',{})
env_name=ai.get('api_key_env','ZHIHENG_AI_API_KEY')
key=os.environ.get(env_name,'')
if not key: raise SystemExit('No model key in the configured environment; refusing to build an embedded-model APK.')
embedded={'ai':{'enabled':True,'base_url':args.base_url or ai.get('base_url',''),'model':ai.get('model',''),
                 'vision_model':ai.get('vision_model') or ai.get('model',''),'protocol':ai.get('protocol','chat_completions'),
                 'api_key':key,'timeout_seconds':ai.get('timeout_seconds',75),'vision_timeout_seconds':ai.get('vision_timeout_seconds',180),'retry_count':ai.get('retry_count',1)}}
for field in ('max_tokens','max_output_tokens'):
    if field in ai:embedded['ai'][field]=ai[field]
if not str(embedded['ai']['base_url']).strip():raise SystemExit('No model API base URL; refusing to build an embedded-model APK.')
if not str(embedded['ai']['model']).strip():raise SystemExit('No model name; refusing to build an embedded-model APK.')
(engine/'default_model.json').write_text(json.dumps(embedded,ensure_ascii=False),encoding='utf-8')
print('Prepared',len(files),'public engine files; generated embedded model config for this test APK only')
