# 2026-09-23 图片附件、营养报告与咨询评估

## 本轮交付（源代码，尚未重打 APK）

- 选择照片只做本机压缩预览；发送才上传，并向用户说明模型服务接收图片和说明。支持移除附件；发送失败保留原附件与说明，重试复用请求 ID。
- 默认自动分类：食物逐项估算，体检报告整理可读指标，其他图片概述。图片中的文字不作为系统指令。照片不等于已食用。
- 新增独立 HTML 报告：图片、总热量、蛋白质/碳水/脂肪、供能比例、多食物明细、每项估重依据、每100g参考值、换算公式、建议和待补充问题。手机两列营养卡片，展开计算依据。
- 数学计算由本地 Python 完成；每100g密度仍由模型提供，不声称查过数据库。未知不作零，部分合计标明覆盖项数，区间不是置信区间。食用确认候选复用同一计算结果，避免两套数字。
- 一般问题和单餐分析可直接回答。个人减重计划需先了解基础/目标、健康限制、三餐饮料、作息活动、体重及执行经历。模型每轮只追问1–2个关键问题。跳过不算已了解，不能猜测“代谢慢”。服务端拦截资料不足的减重计划，保持事实记录；格式/危险计划检查仍先执行。
- Android 打包白名单已加入新增模块和静态资源，未改已有数据和发布包。

## 调研与使用边界

| 来源 | 参考价值 | 本轮采用方式 |
| --- | --- | --- |
| [ask-guzhongyi](https://github.com/guzhong1/ask-guzhongyi) | 先回应问题、少量关键追问、结合生活条件、识别医疗边界 | 独立编写咨询规则，不复制真人身份或整段提示词。[许可](https://github.com/guzhong1/ask-guzhongyi/blob/main/LICENSE.md)限制商业使用，未直接集成其 skill |
| [foodwake](https://github.com/LuckyHookin/foodwake) | 食物营养字段和食物检索结构 | 未导入数据/图片。代码许可不等于原始营养数据准确性及图片版权已核验；发现营养字段存在缺值，需要清洗和来源核验 |
| [what-to-eat](https://github.com/liu-ziting/what-to-eat) | 营养卡片、菜谱与建议的展示组织 | 独立实现本项目原生 JS 组件，没有复制代码或未经校准的健康评分；调研时未发现明确许可 |
| [Waistline](https://github.com/davidhealey/waistline) | 本地饮食日记、食品来源与日汇总 | 借鉴估算/实际日记分离，无代码移植 |
| [wger](https://wger.readthedocs.io/en/stable/) | 食材—菜谱—餐次的结构 | 架构参考，无代码移植 |

后续可靠来源候选：[USDA FoodData Central](https://fdc.nal.usda.gov/api-guide/)、[Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/tutorial-off-api/)。本轮未接入，需分别考虑 API、许可、食品匹配与生熟口径，不能直接把模型密度标为数据库值。

咨询边界参考：[NIDDK 安全减重项目](https://www.niddk.nih.gov/health-information/weight-management/choosing-a-safe-successful-weight-loss-program)。供能比例采用常用蛋白质/碳水4、脂肪9 kcal/g换算，见[FAO 食物能量换算](https://www.fao.org/4/y5686e/y5686e04.htm)。供能比例不等同营养素重量比例或个人推荐目标。

## 验证与限制

- 206项 Python 回归通过，覆盖旧回复解析/事实保留，以及本次计算区间、缺失值、自动分类、评估门槛。
- 隔离临时数据库，390px Edge 自动化通过：选图片无上传、点击发送才上传、多食物报告渲染、图片未自动入摄入账、坏图提示、无横向溢出、档案未被照片污染。
- UI 使用受控模型响应和合成照片，验证流程与计算，不等于真实视觉识别精度测试。截图位于 tmp/nutrition-report-mobile.png。
- 需要后续真实食物/体检照片、长程问诊和 Android 真机验证；不能宣称等同注册营养师或医疗诊断。
- 当前仍不生成精确个人营养处方。图片报告的估算与聊天正文的处方安全规则分离。
