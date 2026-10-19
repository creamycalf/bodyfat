"""Explicit opt-in real-model smoke test with synthetic data and no real memories."""
import json
import sys
import tempfile
import threading
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

def main():
    with tempfile.TemporaryDirectory(prefix="zhiheng-live-") as directory, ExitStack() as stack:
        root=Path(directory);data=root/".data";data.mkdir()
        paths={"ROOT":root,"DATA":data,"MEDIA_DIR":data/"media"}
        paths.update({key:data/name for key,name in {"PROFILE":"profile.json","RECORDS":"records.json","CONVERSATIONS":"conversations.json","MEDIA":"media.json","METADATA":"metadata.json"}.items()})
        for key,value in paths.items():stack.enter_context(patch.object(server,key,value))
        server.startup_check();server.migrate_data()
        httpd=server.ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        success=True
        try:
            history=[]
            for text in ("以下均为虚构测试资料：30岁，身高175厘米，体重78公斤，希望逐步改善作息。请简短给出一个可执行的下一步，不要再给表单。", "继续上面的虚构案例，今天只能留出十分钟，请据此调整，简短回答。"):
                payload=json.dumps({"text":text,"messages":history,"intake_mode":"chat"}).encode()
                request=urllib.request.Request(f"http://127.0.0.1:{httpd.server_port}/api/chat",data=payload,headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(request,timeout=100) as response:result=json.loads(response.read())
                print(json.dumps({key:result.get(key) for key in ("ai_status","ai_error","elapsed_ms","attempts","request_id")}|{"reply_chars":len(result.get("reply") or ""),"synthetic_data":True},ensure_ascii=False),flush=True)
                success=success and result.get("ai_status")=="connected" and bool(result.get("reply"))
                history.extend([{"role":"user","content":text},{"role":"assistant","content":result.get("reply","")}])
        finally:httpd.shutdown();httpd.server_close();thread.join(3)
    return 0 if success else 1

if __name__=="__main__":sys.exit(main())
