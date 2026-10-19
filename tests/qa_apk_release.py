"""Validate a private APK without displaying its embedded credential."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
apk=Path(sys.argv[1])
config=json.loads((root/'config.json').read_text(encoding='utf-8'))['ai']
key=os.environ.get(config.get('api_key_env','ZHIHENG_AI_API_KEY'))
if not key:raise SystemExit('Controlled environment credential required for APK comparison')
tree=ast.parse((root/'android/standalone/prepare.py').read_text(encoding='utf-8'))
files=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='files' for t in n.targets))
assert len(files)==len(set(files))==29,'Unexpected public engine allowlist'
with zipfile.ZipFile(apk) as package:
    prefix='assets/engine/'
    names={n[len(prefix):] for n in package.namelist() if n.startswith(prefix) and not n.endswith('/')}
    assert names==set(files)|{'default_model.json'},'Unexpected engine resources'
    for name in files:
        assert package.read(prefix+name)==(root/name).read_bytes(),'Stale engine resource: '+name
    embedded=json.loads(package.read(prefix+'default_model.json'))['ai']
    assert embedded['api_key']==key,'Embedded credential does not match controlled user environment'
    expected={
        'enabled':True,
        'base_url':config['base_url'],
        'model':config['model'],
        'vision_model':config.get('vision_model') or config['model'],
        'protocol':config.get('protocol','chat_completions'),
        'timeout_seconds':config.get('timeout_seconds',75),
        'vision_timeout_seconds':config.get('vision_timeout_seconds',180),
        'retry_count':config.get('retry_count',1),
    }
    for name in ('max_tokens','max_output_tokens'):
        if name in config:expected[name]=config[name]
    for name,value in expected.items():
        assert name in embedded and embedded[name]==value,'Embedded model setting does not match current config: '+name
    assert not any('.data' in n.replace('\\','/').split('/') for n in package.namelist()),'Health data directory was packaged'
assert not (root/'android/standalone/app/src/main/assets/engine/default_model.json').exists(),'Temporary plaintext source resource remains'
print(json.dumps({'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
    'engine_files_verified':len(files),'config_fields_verified':sorted(expected),
    'credential_matches_user_environment':True,'temporary_source_config_removed':True},ensure_ascii=False))
