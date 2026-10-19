"""Isolated synthetic workflow; --live calls configured model, otherwise serves UI fixtures."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
root=Path(__file__).resolve().parents[1]
data=root/'tmp'/'workbench-v3-qa'/'.data'
os.environ['ZHIHENG_DATA_DIR']=str(data)
data.mkdir(parents=True,exist_ok=True)
import server
import product
import storage


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--serve',action='store_true');parser.add_argument('--followup',action='store_true');parser.add_argument('--serve-only',action='store_true');args=parser.parse_args()
    storage.initialize(data)
    # This directory is dedicated to synthetic QA only.
    if not args.followup and not args.serve_only:
        for name,default in storage.NAMES.items():storage.write(data,name,default)
    if args.live:
        import ctypes
        # Launch shell loads user key; never print it.
        if not server.resolve_ai_key(server.CONFIG.get('ai',{}))[0]:raise RuntimeError('Missing configured AI key')
    original=server.call_ai
    if args.live:
        def observed(*a,**kw):
            raw=original(*a,**kw);value=server.parse_json(raw)
            (data.parent/'last-model-result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            if isinstance(value,dict):print(json.dumps({'module_shapes':[{'id':m.get('id'),'type':m.get('type'),'page':m.get('page')} for m in value.get('page_changes',[]) if isinstance(m,dict)],'decision':value.get('decision')},ensure_ascii=False),flush=True)
            return raw
        server.call_ai=observed
    outputs=[
        {'reply':'通常晚饭怎么解决？','decision':{'action':'clarify','reason':'先了解饮食与生活条件'},'plan':None,
         'profile_changes':[{'field':'age','value':35,'evidence':'35岁'},{'field':'height_cm','value':175,'evidence':'175厘米'}]},
        {'reply':'先从适合工作节奏的安排开始。','decision':{'action':'update','reason':'已有基础情况与日常约束'},
         'plan':{'title':'第一周轻松开始','goal':'建立能坚持的饮食与活动习惯','duration_days':7,'items':[{'title':'午休轻松走一走','detail':'按舒适节奏步行，结合工作安排','when':'每天','minimum':'起身活动片刻'}]},
         'page_changes':[{'id':'diet','page':'plan','type':'checklist','title':'外卖也能执行的饮食安排','body':'结合你平时的选择，先观察每餐搭配和饱腹感。','items':['记录常吃的午餐','吃完后告诉我实际食用量'],'reason':'用户常吃外卖'},
                         {'id':'background','page':'plan','type':'text','title':'你的起点与待了解情况','body':'工作日时间有限，先从小的日常改变开始。','reason':'根据本轮生活条件制定'},
                         {'id':'weight','page':'dashboard','type':'trend','title':'体重变化','body':'只展示实际测量记录','reason':'用真实数据观察变化'}]},
        {'reply':'晚间时间紧张，方案说明已经更新。','decision':{'action':'update','reason':'晚饭时间发生变化'},'plan':None,
         'page_changes':[{'id':'diet','page':'plan','type':'text','title':'晚归时的饮食安排','body':'晚归时优先选择方便取得、符合平常习惯的晚餐。继续记录实际食用情况。','reason':'近期晚间加班'}]},
    ]
    messages=[
        '这是隔离的虚构验收案例。我35岁，身高175厘米，体重80公斤，想减肥。请通过对话逐步了解我整体情况，先问一个问题。',
        '以下仍为虚构测试：我工作久坐，平时外卖，晚上十二点睡七点起，自述没有已知疾病、用药或过敏，每天午休有二十分钟。请先形成一周初步方案和方案页面的文字模块，从今天开始执行，未知项标出来。',
        '虚构测试继续：最近晚上一直工作到九点，回家很晚才吃晚饭。午休还是有空。',
    ]
    if args.followup:messages=['虚构测试继续：请把当前方案的完整文字说明、饮食策略、活动建议和复盘安排分别整理到方案页面，保留现有执行安排。']
    if args.serve_only:messages=[]
    for i,text in enumerate(messages):
        if not args.live:server.call_ai=lambda *a,**kw:json.dumps(outputs[i],ensure_ascii=False)
        import uuid
        result=product.chat(server,{'text':text,'conversation_id':'synthetic-v3','client_message_id':f'synthetic-message-{uuid.uuid4().hex}'})
        print(json.dumps({'step':i,'ai_status':result.get('ai_status'),'ai_error':result.get('ai_error'),
                          'reply':result['reply'],'plan':bool(result.get('plan')),'updates':result.get('page_updates'),
                          'receipts':result.get('receipts')},ensure_ascii=False),flush=True)
    server.call_ai=original
    if args.serve:
        server.image_jobs.ensure_worker(server)
        server.STARTUP_STATUS={'ok':True,'checks':['isolated_synthetic_qa']}
        httpd=server.ThreadingHTTPServer(('127.0.0.1',8795),server.Handler)
        print('Serving synthetic QA on 8795',flush=True)
        try:httpd.serve_forever()
        finally:httpd.server_close()


if __name__=='__main__':main()
