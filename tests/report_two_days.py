"""Build a human-readable report from actual isolated test outputs."""
import html
import json
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'tmp'/os.environ.get('TWO_DAY_RUN','two-day-live-20260916')
def read(name,default=None):
    path=root/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
def esc(v):return html.escape(str(v))
steps=read('steps.json',[]);checks=read('checks.json',[]);browser=read('browser-checks.json',{})
parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>两天真实模型流程验收</title><style>body{font:16px/1.7 system-ui;margin:auto;padding:28px;max-width:1100px;background:#f3f7f3;color:#203e31}section{background:white;padding:24px;border-radius:14px;margin:20px 0}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #dce4dc;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%;border:1px solid #ccc}a{color:#18633f}.fail{color:#a32}.pass{color:#18633f}</style><h1>两天流程验收 · 虚构资料</h1><p>模拟日期：2026-09-15 至 2026-09-16。真实调用当前配置模型，时间快进；测试数据独立保存，未写入正式资料。合成营养标签图不代表自然餐食识别准确率。</p><p><a href="http://127.0.0.1:8797/">进入独立测试环境查看最终状态</a></p>']
parts.append(f'<section><h2>实际验证结果</h2><p>{sum(c["passed"] for c in checks)} / {len(checks)} 项数据检查通过。{len(steps)} 轮真实对话。</p><table><tr><th>检查</th><th>结果</th></tr>')
for c in checks:parts.append(f'<tr><td>{esc(c["name"])}</td><td class="{"pass" if c["passed"] else "fail"}">{"通过" if c["passed"] else "未通过"} {esc(c.get("detail",""))}</td></tr>')
parts.append('</table><p>浏览器检查：'+esc(json.dumps(browser,ensure_ascii=False))+'</p></section>')
findings=read('findings.json',[])
parts.append('<section><h2>本次实际发现的问题</h2><ul>')
for finding in findings:parts.append('<li>'+esc(finding)+'</li>')
parts.append('</ul></section>')
for day in [1,2]:
    state=read(f'day{day}.json',{})
    parts.append(f'<section><h2>第 {day} 天结束的数据</h2>')
    parts.append(f'<p>累计健康记录 {len(state.get("records",[]))} 条，计划版本 {len(state.get("plans",[]))} 份，待核实信息 {len(state.get("pending",[]))} 条。</p>')
    parts.append('<table><tr><th>日期</th><th>类型</th><th>实际保存内容</th></tr>')
    for r in state.get('records',[]):parts.append(f'<tr><td>{esc(r.get("occurred_at",r.get("created_at","")))}</td><td>{esc(r["type"])}</td><td>{esc(json.dumps(r["value"],ensure_ascii=False))}</td></tr>')
    parts.append('</table><details><summary>已保存的档案与计划</summary><pre>'+esc(json.dumps({'profile':state.get('profile'),'plans':state.get('plans'),'pending':state.get('pending')},ensure_ascii=False,indent=2))+'</pre></details></section>')
parts.append('<section><h2>逐轮对话与真实处理结果</h2>')
for s in steps:
    r=s['result'];parts.append(f'<details><summary>{esc(s["label"])} · {s["seconds"]} 秒 · {esc(r.get("ai_status",r.get("error","")))}</summary><h3>发送</h3><pre>{esc(s["input"]["text"])}</pre><h3>回复</h3><pre>{esc(r.get("reply",r))}</pre><h3>实际写入回执</h3><pre>{esc(json.dumps(r.get("receipts",[]),ensure_ascii=False,indent=2))}</pre></details>')
parts.append('</section><section><h2>第二天结束的实际页面</h2>')
for view,label in [('dashboard','看板'),('plan','计划'),('archive','档案'),('chat','对话')]:
    parts.append(f'<details><summary>{label}：桌面和手机截图</summary><img src="{view}-1280.png" alt="{label}桌面截图"><p><a href="{view}-390.png">查看手机长截图</a></p></details>')
parts.append('</section><p>范围限制：两天为虚拟日期快进，未覆盖真实麦克风、手机拍照、自然餐食准确率及真实连续运行48小时；真实模型回复的质量以逐轮内容和保存数据为准。</p>')
(root/'report.html').write_text('\n'.join(parts).replace('127.0.0.1:8797','127.0.0.1:'+os.environ.get('TWO_DAY_PORT','8797')),encoding='utf-8')
print(root/'report.html')
