"""Disposable browser fixture for estimated/unknown meals and recipe portions."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import storage
import product
import workbench

with tempfile.TemporaryDirectory(prefix='zhiheng-nutrition-') as folder:
    server.DATA=Path(folder);server.MEDIA_DIR=server.DATA/'media'
    for key in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA'):
        setattr(server,key,server.DATA/(key.lower()+'.json'))
    storage.initialize(server.DATA)
    records=[]
    for description,nutrition in [('测试早餐',{'kcal':[300,400],'protein_g':[10,15]}),('测试晚餐，份量不清楚',{})]:
        value={'description':description,'nutrition':workbench.nutrition_ranges(nutrition),
               'uncertainty':'份量为粗略描述，品牌和用油未知。' if nutrition else '没有具体食物和份量，暂不估算。'}
        value['nutrition_context']=workbench.nutrition_context(value,'conversation_estimate',description)
        record=server.prepare_record({'type':'meal','value':value});record['occurred_at']=product.today();records.append(record)
    server.save_json(server.RECORDS,records)
    w=product.workspace(server)
    plan=product.normalize_plan({'title':'测试份量计划','goal':'核对份量','items':[{'title':'午餐','when':'每天',
        'meal_options':{'cook':{'dish':'米饭配豆腐','ingredients':'米饭150克、豆腐150克','steps':'加热食用',
            'servings':'1人1餐参考量','weight_basis':'米饭熟重、豆腐烹饪前重量'},
            'takeout':{'dish':'旧版外卖建议','search':'家常菜','ordering':'核对食材'}}}]},'今天',w,None)
    plan['status']='active';w['plans']=[plan];server.save_json(server.DATA/'workspace.json',w)
    server.call_ai=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('No real calls in UI fixture'))
    server.STARTUP_STATUS={'ok':True,'checks':['isolated-nutrition']}
    print('Nutrition fixture ready on 8796',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8796),server.Handler).serve_forever()
