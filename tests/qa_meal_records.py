"""Isolated local meal correction fixture; no model calls or personal data."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import storage
import product

with tempfile.TemporaryDirectory(prefix='zhiheng-meal-correction-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
        setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    record=server.prepare_record({'type':'meal','value':{'description':'测试午餐米饭和蔬菜',
        'nutrition':{'kcal':[400,600],'protein_g':[10,20]}}})
    record['occurred_at']=product.today()
    server.save_json(server.RECORDS,[record])
    server.call_ai=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('No upstream calls allowed'))
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-meal-correction']}
    print('Meal correction fixture ready on 8795',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler).serve_forever()
