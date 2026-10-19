"""Verify packaged offline Chinese speech assets and both native ABIs, without keys."""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

apk=Path(sys.argv[1])
root=Path(__file__).resolve().parents[1]
with zipfile.ZipFile(apk) as package:
    manifest=json.loads(package.read('assets/voice/manifest.json'))
    assert manifest['processing']=='on_device_offline'
    assert manifest['downloads_at_runtime'] is False
    model=package.read('assets/voice/vosk-model-small-cn-0.22.zip')
    digest=hashlib.sha256(model).hexdigest()
    assert digest==manifest['sha256']=='3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba'
    assert len(model)==manifest['bytes']==43898754
    assert package.getinfo('assets/voice/vosk-model-small-cn-0.22.zip').compress_type==zipfile.ZIP_STORED
    with zipfile.ZipFile(io.BytesIO(model)) as resource:
        assert resource.testzip() is None
        for name in ['am/final.mdl','conf/model.conf','conf/mfcc.conf','graph/HCLr.fst','graph/Gr.fst']:
            assert resource.getinfo('vosk-model-small-cn-0.22/'+name).file_size>0
    native=[]
    for abi in ['arm64-v8a','x86_64']:
        for name in ['libvosk.so','libjnidispatch.so']:
            path='lib/'+abi+'/'+name
            data=package.read(path)
            assert data.startswith(b'\x7fELF')
            native.append(path)
    for name in ['APACHE-2.0.txt','JNA-LICENSE.txt']:
        assert len(package.read('assets/voice/'+name))>500
    for name in package.namelist():
        if name.startswith('assets/voice/') and not name.endswith('/'):
            expected=root/'android/standalone/app/src/main'/name
            assert package.read(name)==expected.read_bytes(),'Stale voice resource '+name
print(json.dumps({'passed':True,'model_sha256':digest,'bundled_model_bytes':len(model),
    'native_libraries':native,'runtime_downloads':False,'apk_bytes':apk.stat().st_size},ensure_ascii=False))
