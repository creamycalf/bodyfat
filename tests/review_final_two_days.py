"""Supplement flow assertions with manual-quality findings, without changing test data."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'tmp/two-day-final-20260916'
checks=json.loads((root/'checks.json').read_text(encoding='utf-8'))
extra=[
 {'name':'做饭选项提供可用食材步骤（内容审查）','passed':False,'detail':'真实模型返回“不适用”占位；随后生产代码增加占位过滤，尚未证明完整食谱质量'},
 {'name':'第二天可用时间同步至独立档案字段（内容审查）','passed':False,'detail':'本次快照缺available_time；随后增加明确原话提取，定向回归通过，未改写本次快照'},
 {'name':'早餐具备可汇总的营养估算（内容审查）','passed':False,'detail':'早餐已保存，但模型未给可用估算，数值保持未知'},
]
checks=[c for c in checks if c['name'] not in {x['name'] for x in extra}]+extra
(root/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
findings=[
 '24项流程与数据检查通过，但内容审查还有3项缺口；通过率不是模型准确率。',
 '真实模型已给外卖搭配/搜索词/备注，但做饭字段为“不适用”。测试后代码已过滤这些占位，不把它们当作真实做法；仍缺的步骤继续提供获取入口。',
 '第二天计划确实由晚间散步调整为午休散步，但独立available_time档案字段未同步。测试后代码已补明确原话提取并通过回归；此报告快照仍保留原结果。',
 '早餐实际记录已保存，营养估算仍未知；没有凭空补造热量。',
 '新计划版本把一周结束日期从9月21日顺延至9月22日；未细化“仅改某事项、保留原周期”的策略。',
 '本轮10次真实对话无超时，耗时8.2–49.8秒；不能据此保证长期稳定或消除上游超时。',
 '失败继续请求通过单独的模拟超时浏览器验收，不是本轮真实超时复现；原草稿只在可重新校验时恢复，非法页面仍会保留失败状态或从已保存资料恢复摘要。',
]
(root/'findings.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
print('Flow 24/24; content review 0/3; combined 24/27')
