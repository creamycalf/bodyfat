"""Actual bundled model decode on Windows, using synthetic Chinese PCM and no network."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import wave
import zipfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tmp/vosk-python-test'))
from vosk import Model,KaldiRecognizer,SetLogLevel
SetLogLevel(-1)
asset=root/'android/standalone/app/src/main/assets/voice/vosk-model-small-cn-0.22.zip'
assert hashlib.sha256(asset.read_bytes()).hexdigest()=='3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba'
audio=root/'tmp/voice-offline-downloads/synthetic-cn.wav'
def no_network(*args,**kwargs):raise AssertionError('Offline model attempted a network connection')
socket.socket.connect=no_network
socket.create_connection=no_network
started=time.monotonic()
with tempfile.TemporaryDirectory(prefix='zhiheng-offline-model-') as folder:
    with zipfile.ZipFile(asset) as package:package.extractall(folder)
    model=Model(str(Path(folder)/'vosk-model-small-cn-0.22'))
    recognizer=KaldiRecognizer(model,16000)
    chunks=[]
    with wave.open(str(audio),'rb') as source:
        assert (source.getnchannels(),source.getsampwidth(),source.getframerate())==(1,2,16000)
        duration=source.getnframes()/16000
        while data:=source.readframes(1600):
            if recognizer.AcceptWaveform(data):chunks.append(json.loads(recognizer.Result()).get('text',''))
        chunks.append(json.loads(recognizer.FinalResult()).get('text',''))
    text=''.join(chunks).replace(' ','')
    row={'passed':bool(text),'fixture':'Windows local Chinese synthesis, no microphone',
        'reference':'今天我吃了一个苹果，喝了一杯牛奶。晚上准备散步三十分钟。',
        'recognized':text,'network_connections_allowed':False,'audio_seconds':round(duration,2),
        'elapsed_seconds':round(time.monotonic()-started,2),'model':'vosk-model-small-cn-0.22',
        'keywords_recognized':[word for word in ['苹果','牛奶','散步','三十分钟'] if word in text]}
    # A smoke check of actual model data, not an accuracy benchmark.
    row['passed']=len(row['keywords_recognized'])>=3
    del recognizer,model
    print(json.dumps(row,ensure_ascii=False))
    (root/'tmp/offline-voice-model-0.4.37.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if row['passed'] else 1)
