"""Temporary UI server for a fictional guided consultation, with a model stub."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='zhiheng-guided-ui-') as folder:
    os.environ['ZHIHENG_DATA_DIR']=folder
    import server,storage
    storage.initialize(server.DATA)

    def model(messages,**kwargs):
        facts=json.loads(messages[1]['content'])
        ready=facts.get('plan_readiness',{}).get('ready')
        result={'reply':'收到这些情况，我们接着了解。','profile_changes':[],
            'record_events':[],'feedback':[],'plan':None,'page_changes':[],
            'food_decisions':[],'decision':{'action':'none','reason':'承接本轮回答'}}
        if messages[-1]['content'].startswith('早餐两个鸡蛋一杯牛奶；'):
            result['profile_changes']=[{'field':field,'value':evidence,'evidence':evidence} for field,evidence in [
                ('breakfast_habit','早餐两个鸡蛋一杯牛奶'),
                ('lunch_habit','午餐一碗米饭、鸡肉和蔬菜'),
                ('dinner_habit','晚餐经常一份外卖炒面，份量一大盒'),
                ('snacks_drinks','下午喝一杯奶茶，晚上偶尔吃薯片')]]
        if ready:
            result.update(reply='先试一周：下班前选好晚餐，记录晚餐后的饥饿感，一周后调整。',
                decision={'action':'update','reason':'资料已核对，制定可执行的一周试行'},
                plan={'title':'一周晚餐试行','goal':'改善加班后的晚餐选择并观察饥饿感',
                    'duration_days':7,'basis':'基于已确认的加班、外卖与晚间饥饿情况',
                    'unknowns':'具体菜单可得性与执行感受待反馈','items':[
                        {'title':'下班前选好晚餐','detail':'在常用平台选一份含主食、蛋白质食物和蔬菜的搭配，核对实际菜单。',
                         'when':'每天·下班前','minimum':'先选好一顿','alternatives':'先查看一份可选菜单',
                         'feedback':'反馈是否方便、餐后饥饿感','basis_record_ids':[]},
                        {'title':'记录饥饿感','detail':'晚餐后记一句饥饿或饱腹感。','when':'每天·晚餐后',
                         'minimum':'记一句','alternatives':'次日回忆一次','feedback':'是否太饿或吃撑','basis_record_ids':[]}]})
        return json.dumps(result,ensure_ascii=False)

    server.call_ai=model
    server.ai_meta=lambda:{'ai_status':'connected','ai_error':None}
    server.STARTUP_STATUS={'ok':True,'checks':['fictional-guided-consultation']}
    print('Fictional guided UI on 8812',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8812),server.Handler).serve_forever()
