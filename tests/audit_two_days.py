"""Audit actual saved snapshots, including quality failures beyond flow checks."""
import json
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'tmp'/os.environ.get('TWO_DAY_RUN','two-day-live-20260916')
def read(name,default=None):
    p=root/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
steps=read('steps.json',[]);checks=read('checks.json',[]);findings=[]
def add(name,passed,detail):checks.append({'name':name,'passed':passed,'detail':detail})
timeouts=[s for s in steps if s['result'].get('ai_error')=='AI_TIMEOUT']
if timeouts:findings.append(f'真实对话发生 {len(timeouts)} 次超时；最长等待 {max(s["seconds"] for s in steps)} 秒。超时后仅本地提取的部分资料被保存，其他背景没有完整入档。')
add('真实模型对话未超时',not timeouts,f'{len(timeouts)} 次超时')
state2=read('state-02.json',{})
habit=[r for r in state2.get('records',[]) if r['type']=='sleep' and '通常' in r.get('evidence','')]
add('作息习惯不当作实际睡眠',not habit,'检查“通常23点睡7点起”')
if habit:findings.append('作息习惯“通常23点睡7点起”被计为当天实际睡眠8小时；日常习惯与实际记录没有正确区分。')
half=next((s for s in steps if s['label']=='第一天：确认半份'),None)
if half:
    snap=read(f'state-{steps.index(half)+1:02}.json',{})
    meals=[r for r in snap.get('records',[]) if r.get('media_id')==half['input'].get('media_id')]
    correct=len(meals)==1 and meals[0]['value'].get('nutrition',{}).get('kcal')==[300,300]
    add('明确半份营养换算为300千卡',correct,'原合成标签600千卡整份')
    if not correct:findings.append('“刚才那份我吃了一半”保存了摄入，但未将已识别的600千卡换算成300千卡，营养仍未知。')
final=read('day2.json',{})
day1=read('day1.json',{})
if any(c['name']=='对话打卡落到同一任务' and not c['passed'] for c in checks):
    findings.append('对话打卡回复声称“已记录完成”，但没有执行反馈回执、任务状态也未变为完成；回复与实际保存结果不一致。')
    for c in checks:
        if c['name']=='第二天不会继承昨天完成状态':
            c['name']='第二天任务初始状态未完成（昨天对话打卡未成功，非跨天继承证明）'
weight_turn=next((s for s in steps if s['label']=='第二天：体重与睡眠'),None)
if weight_turn:
    relevant='这句话涉及不同餐次' not in weight_turn['result'].get('reply','')
    add('非饮食对话不受旧照片关联干扰',relevant,'今天体重和昨晚睡眠的回复')
    if not relevant:findings.append('第二天记录体重与睡眠时，旧照片关联触发了餐次歧义提示。体重和睡眠虽然保存，回复却要求核对照片，答非所问。')
for label,date in [('第一天：晚餐记录','2026-09-15'),('第二天：早餐记录','2026-09-16')]:
    step=next((s for s in steps if s['label']==label),None)
    if step:
        mid=step['input']['client_message_id']
        matches=[r for r in final.get('records',[]) if r.get('source_message',{}).get('message_id')==mid and r['type'] in ('meal','beverage') and str(r.get('occurred_at','')).startswith(date)]
        add(label+'保存独立餐次',bool(matches),'按本轮消息来源和日期核对')
        if not matches:findings.append(label+'没有保存为独立的当日餐次，需要核对同一会话上一次图片关联是否影响了新餐记录。')
structured=bool(day1.get('plans')) and any(i.get('meal_options') for p in day1['plans'] for i in p['items'])
add('真实计划提供结构化饮食选择',structured,'检查 meal_options')
if not structured:findings.append('实际生成的初版计划未提供结构化做法/外卖卡片，只能继续点击获取建议。')
failed=[s for s in steps if s['result'].get('page_error')]
add('页面说明更新无失败',not failed,f'{len(failed)} 轮失败')
if failed:findings.append(f'有 {len(failed)} 轮页面说明未成功保存，显示失败恢复入口；聊天成功不等于整轮整理成功。')
if final.get('pending'):findings.append(f'第二天结束仍有 {len(final["pending"])} 项资料待核实，需在档案页处理。')
wrong_occupation=[p for p in final.get('pending',[]) if p.get('field')=='occupation' and '饮水提醒完成' in str(p.get('value',''))]
add('打卡不产生虚假职业档案变更',not wrong_occupation,'检查工作日饮水提醒')
if wrong_occupation:findings.append('“工作日饮水提醒完成了”因包含“工作”被提取为职业变化，产生错误待核实项；该项还可能阻挡后续计划更新。本轮最终调整请求本身超时，因此不能把这次未调整全部归因于待核实项。')
scalar=[r for r in final.get('records',[]) if r['type'] in ('meal','beverage') and any(isinstance(v,(int,float)) for v in r.get('value',{}).get('nutrition',{}).values())]
add('文字餐食营养结构兼容看板统计',not scalar,'营养范围应为[min,max]或未知')
if scalar:findings.append('文字早餐记录保存了单值营养数字，而看板汇总只接受范围数组，导致记录里有估算值但看板仍无法统计；需统一文字与照片记录结构。')
root.joinpath('checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
root.joinpath('findings.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':checks,'findings':findings},ensure_ascii=False,indent=2))
