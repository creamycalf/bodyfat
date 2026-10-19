"""Read-only upstream probe with a synthetic image; never load personal records."""
import base64
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

image=Path('tmp/workbench-v3-qa/synthetic-menu.png').read_bytes()
messages=[{'role':'user','content':[{'type':'text','text':'This is a synthetic software test image, not personal health data. Read its title only. Answer in one sentence.'},
 {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(image).decode()}}]}]
result=server.call_ai(messages,True)
print(json.dumps({'image_bytes':len(image),'meta':server.ai_meta(),'reply':result},ensure_ascii=False),flush=True)
