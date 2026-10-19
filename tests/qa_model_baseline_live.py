"""A minimal current-service probe, isolated from all application health data."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
import re

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifact-version',default='0.4.29')
args=parser.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+',args.artifact_version):parser.error('Expected a numeric version label')
with tempfile.TemporaryDirectory(prefix='zhiheng-model-baseline-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server
    server.CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    started=time.monotonic()
    reply=server.call_ai([{'role':'user','content':'只回复：连接正常。'}],total_timeout=35)
    result={'probe':'minimal_text_request','elapsed_ms':round((time.monotonic()-started)*1000),
            'reply':reply,'error':server.ai_meta().get('ai_error'),'deadline_seconds':35}
    (ROOT/f'tmp/model-baseline-{args.artifact_version}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    raise SystemExit(0 if reply and not result['error'] else 1)
