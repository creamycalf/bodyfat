# 知衡产品方向原型

打开 index.html 即可体验。独立静态页面，没有后端请求，不读取或修改正式数据。

最新版从“开始体验”进入线性引导：发送首次访谈样例 → 查看档案 → 查看计划 → 发送未食用照片 → 确认半份并查看今日 → 加班反馈后查看计划 V2 → 查看同步更新的今日。每一步都有下一步按钮，无需自行切换阶段。完成后可自由查看页面。支持上一步和重新体验；返回步骤会恢复该步骤的预设状态，刷新回到开场，不持久保存。顶部旧阶段导航已隐藏，保留原有样例供自由查看。

原型浏览器回归入口：node tests/qa_journey.mjs（替代旧 qa_direction_prototype.mjs 的手动阶段导航测试）。

这份原型用于确认产品方向，不表示既有程序已经实现全部交互。样例中的首次访谈为压缩后的多轮对话；完整产品还需支持继续追问、跳过、恢复与更正。原型不接入真实 AI、上传、摄像头、语音或真实营养识别，也不承诺自动更新的可靠性已经验收。

核心边界：对话是入口；计划与档案是持续维护的页面。上传照片不等于食用；实际餐次与长期档案、计划调整分别判断。每次变更展示依据，替换受影响模块，保留未受影响模块。

图像：lunch.png 由内置 image_gen 工具生成，仅用于演示。未依据图片真实分析营养，界面的数值为预设样例。

最终图像提示词：Use case: photorealistic-natural. Asset type: food photo inside a Chinese nutrition app interactive prototype. Generate one realistic casual smartphone overhead photograph of a simple lunch on a white ceramic plate: cooked white rice, sliced cooked chicken thigh with a little brown sauce, steamed broccoli and carrots. Entire plate visible on a warm light oak tabletop, natural window lighting, appetizing but everyday realistic portion, no text, no logos, no hands. Square composition. This is fictional sample food, not nutritional evidence.
