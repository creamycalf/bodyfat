# 知衡 · AI 健康师原型

知衡是一个本地运行的健康管理原型。用户通过文字、语音或图片交流，系统按保存设置整理明确的本人陈述，不确定信息进入待核实。对话、看板、计划和档案共同展示持续更新的健康状态。它不承担诊断、处方或急救职责。

## 当前状态

- 2026-10-19 私人测试版 0.4.43：精简手机欢迎页，让四个常用入口首屏可见；整份/明确比例营养换算在本地完成，连续营养追问保留照片和已计算份量；修复旧评估/计划来源的记忆旁路及图片长重试叠加。最终 545 项程序回归通过，并完成真实模型连续对话、雷电覆盖升级与真实 Enter 发送验收。首次图片识别仍可能较慢，物理手机麦克风和软键盘未验收。见[最新交接记录](docs/HANDOFF_2026-10-19_PHONE_TEST_0.4.43.md)。
- 2026-10-15 私人测试版 0.4.38：修复语音录入完成入口不明显、发送一直禁用的问题。识别文字实时显示到输入框，录音时右侧主按钮显示“完成录入”，完成后恢复“发送”；语音分句后停顿可自动结束。结束收音不再在 UI 线程调用麦克风停止；收尾超时保留文字并恢复编辑。控制器与实际网页集成检查通过，手机真实收音仍待验证。见[录入完成和发送修复](docs/HANDOFF_2026-10-15_PHONE_TEST_0.4.38.md)。
- 2026-10-14 私人测试版 0.4.37：针对国内无代理时的语音网络错误，改为内置离线中文识别，录音不经过系统云服务，首次使用本地解压模型。控制器及界面检查通过，同一模型在断网条件下及无联网权限的 Android 模拟器中成功解码合成中文语音；APK约102MB。AI对话仍需联网，真实手机收音与识别质量待验证。见[离线语音交付与限制](docs/HANDOFF_2026-10-14_PHONE_TEST_0.4.37.md)。
- 2026-10-13 私人测试版 0.4.36：修复语音录入的系统兼容及等待恢复问题，增加系统识别服务与窗口回退、取消和超时、草稿保护及输入法语音入口。22 项语音前端检查、10 项原生控制器检查、6 组浏览器检查和图片聊天回归通过。当前没有连接手机，真实麦克风与厂商语音服务仍需真机验证。见[本次语音修复与限制](docs/HANDOFF_2026-10-13_PHONE_TEST_0.4.36.md)。
- 2026-10-13 私人测试版 0.4.35：按要求把对话和图片模型切换到 `gpt-6.1-sol`，新增覆盖安装时的旧默认模型迁移。当前中转的文字请求约14.45秒、合成图片请求约8.47秒成功，迁移策略检查通过。见[本次模型切换与验证](docs/HANDOFF_2026-10-13_PHONE_TEST_0.4.35.md)。
- 2026-10-13 私人测试版 0.4.34：修复发送后聊天未跟随到底部的问题，覆盖长回复、图片完成、输入框增高及键盘视口变化；上翻查看历史时暂停跟随，可点“回到最新”。沿用当前模型配置。347 项 Python 测试、24 项滚动检查和整体图片聊天回归通过，尚未连接真机。见[本次修复与验证](docs/HANDOFF_2026-10-13_PHONE_TEST_0.4.34.md)。
- 2026-10-12 私人测试版 0.4.33：图片详细分析改为弹窗，支持弹窗内核对修改和返回继续聊天；输入框固定底部悬浮，适配底部导航及可见视口变化。347 项自动测试、三图聊天流程与手机/电脑宽度检查通过，键盘为浏览器缩小视口模拟，未连接真机。详情见[弹窗与悬浮输入框验收](docs/HANDOFF_2026-10-12_PHONE_TEST_0.4.33.md)。
- 2026-10-12 私人测试版 0.4.32：照片、等待进度、回复和简短结果统一到聊天回合；详细报告折叠，输入框明确显示正在接着聊的照片，可取消关联。修复图片轮询闪动、延迟完成后的排序和跨会话任务展示。347 项自动测试及连续三图的手机/电脑宽度检查通过；本轮使用模拟模型验收界面，未连接真机。详情见[本次界面调整与验收](docs/HANDOFF_2026-10-12_PHONE_TEST_0.4.32.md)。
- 2026-10-10 私人测试版 0.4.31：修复照片热量在解析和聊天发布时丢失的问题，支持没有可靠克重时的可见整份区间估计。用用户提供的真实餐食照片复现旧问题并完成两次修复后实测，约70秒和66秒返回可展示的热量报告；346项自动检查和390px界面检查通过。估计范围仍较宽，尚未连接真机。详情见[本次交付与实际限制](docs/HANDOFF_2026-10-10_PHONE_TEST_0.4.31.md)。
- 正式后端：`server.py`；`server.mjs` 仅用于 mock 演示。
- 本地地址：`http://127.0.0.1:8787/`。
- 当前请求模型名：以根目录 `config.json` 为准；本次私人测试包使用 `gpt-6.1-sol`（对话和图片）。第三方中转返回的模型字段不能单独证明底层模型身份。
- 已验证协议：OpenAI-compatible `POST /v1/chat/completions`。
- 历史回归（2026-09-17）：142 项 Python 测试通过；真实营养专项9项、食谱专项23项、两天流程24项及电脑/手机浏览器检查通过。详见[此前功能测试交接](docs/HANDOFF_2026-09-17_TEST_READY.md)，不能代替新版本验收。
- 当前阶段：单机原型，不具备账号隔离、数据加密和公网部署能力。

## 快速启动

需要 Windows PowerShell 和 Python 3，项目本身只使用 Python 标准库。

```powershell
cd F:\aiworkspace\codexworkspace\bodyfat
powershell -ExecutionPolicy Bypass -File .\start-server.ps1
```

需要在前台崩溃后自动拉起时，可使用有限次数的守护模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-supervised.ps1
```

该脚本默认最多重启 10 次，每次间隔 2 秒；它不会安装系统服务或创建开机启动项。

也可以直接运行：

```powershell
python server.py
```

浏览器打开 `http://127.0.0.1:8787/`。不要直接双击 `index.html`，否则前端无法访问本地 API。

## AI 配置

公开仓库只包含源码、合成演示材料及必要的离线语音资源，不包含个人 API Key、`config.json`、健康资料、备份、签名密钥或私人测试 APK。离线语音资源的许可和校验信息位于 `android/standalone/app/src/main/assets/voice/`；健康对话和图片模型仍通过远程服务运行。

`config.example.json` 中的地址和模型是占位符，使用前需替换为你自己的服务地址、文字及图片模型 ID。

复制 `config.example.json` 为 `config.json`，真实 Key 推荐放在环境变量中：

```powershell
$env:ZHIHENG_AI_API_KEY = '你的 Key'
powershell -ExecutionPolicy Bypass -File .\start-server.ps1
```

核心配置示例：

```json
{
  "ai": {
    "enabled": true,
    "base_url": "https://your-provider.example/v1",
    "api_key_env": "ZHIHENG_AI_API_KEY",
    "model": "YOUR_MODEL_ID",
    "vision_model": "YOUR_VISION_MODEL_ID",
    "protocol": "chat_completions",
    "timeout_seconds": 75,
    "retry_count": 1
  }
}
```

`config.json` 已被忽略，不应提交。配置状态接口不会返回 Key：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/config-status
```

## Android 私人测试包

`android/standalone/build.ps1` 默认构建包含远程模型接口配置及访问密钥的私人测试 APK。构建前需在本机准备 `config.json`、其 `api_key_env` 指定的环境变量、Android SDK/JDK/Gradle 和 `.mobile-private/` 内的测试签名；脚本中的工具路径是原开发环境路径，可通过参数及本地 Gradle 配置调整。接口、模型或密钥缺失会明确失败，不会静默生成无模型包。

```powershell
powershell -ExecutionPolicy Bypass -File .\android\standalone\build.ps1 -Offline
```

只有明确需要无凭据包时才使用 `-NoEmbedModel`，这种包需在设备上配置自己的 AI 服务。含密钥 APK 中的凭据可被提取，仅供本人测试，不能上传公开仓库、GitHub Releases 或应用商店。公开分发前应改用安全的服务端凭据方案。`release/`、签名、配置及构建生成的 `default_model.json` 均已加入忽略规则。

## 已实现能力

- 文本对话、浏览器语音输入和食物图片入口；
- 减脂/健康方案场景提供全部选填的资料表单，也可跳过后使用文字或语音；
- 睡眠、体重、饮食、饮料、化验和症状候选提取；
- 候选值编辑、批量确认、120 秒整批撤销；
- 单条档案修改、删除和模型记忆开关；
- 近 14 日真实体重趋势；
- 基于已确认数据并显示依据的今日建议；
- 本地健康记忆检索和命中原因解释；
- 个人资料编辑及服务端校验；
- 真实对话摘要和独立删除；
- 原图确认保留、到期清理和永久删除；
- 数据导出和全部清空；
- 12 MB 默认请求体总上限、JSON 请求格式校验和根目录静态文件保护；
- 档案记录页面内联修改，不依赖浏览器原生弹窗；
- 模型超时、重试、并发限制、安全降级和错误分类；
- 胸痛、呼吸困难等关键词由本地规则优先处理。

## 数据位置

运行数据保存在项目下的 `.data/`：

```text
.data/
├── records.json
├── profile.json
├── conversations.json
├── media.json
├── metadata.json
├── media/
└── backups/
```

写入 JSON 时采用临时文件替换，降低中断导致文件损坏的风险。该目录仍是明文存储，应只在可信本机使用。

## 验证

```powershell
python -m py_compile server.py
python -m unittest discover -s tests -v
```

完整验收步骤见 [测试与验收](docs/TEST_AND_ACCEPTANCE.md)。

## 文档索引

- [系统架构](docs/ARCHITECTURE.md)
- [运行与故障处理](docs/OPERATIONS.md)
- [API 参考](docs/API_REFERENCE.md)
- [数据、隐私与安全边界](docs/SECURITY_AND_DATA.md)
- [测试与验收](docs/TEST_AND_ACCEPTANCE.md)
- [可选资料采集流程](docs/OPTIONAL_INTAKE_FLOW.md)
- [最新交接文档：0.4.43 小屏交互与照片连续问答](docs/HANDOFF_2026-10-19_PHONE_TEST_0.4.43.md)
- [需求说明](docs/REQUIREMENTS.md)
- [数据采集规范](docs/DATA_SPEC.md)

## 上线前仍需完成

- 账号、会话鉴权和多用户数据隔离；
- 正式密钥托管和静态数据加密；
- 日志轮转、保留策略和异常告警；
- 向量语义检索；
- 独立部署、进程守护和运行监控；
- 更完整的医疗安全评审。
