# 知衡 0.4.35：切换 gpt-6.1-sol

按用户明确要求，将根目录 `config.json` 的对话和图片模型都改为 `gpt-6.1-sol`。接口沿用 `https://code.leessmin.com/v1`，协议 `chat_completions`，密钥从现有 Windows User 环境读取。

[OpenAI 模型文档](https://developers.openai.com/api/docs/models/gpt-6.1-sol)描述该模型支持文字及图片输入，无工具的 Chat Completions 请求可用。本项目实际使用第三方中转，官方文档不能证明此服务的底层模型身份；以下验证的是中转对指定模型名的实际响应。

## 实测与升级

- 文字 JSON 连接测试成功：14.45 秒，返回有效 JSON。
- 合成图片请求成功：8.47 秒，正确描述红色长方形、绿色圆形和蓝色三角形。
- 测试使用临时隔离存储，无真实健康资料。脚本 `tests/qa_sol_live.py`，记录 `tmp/sol-live-0.4.35.json`。这两次请求属于连接和输入格式验证，不代表餐食识别、热量估算或多轮健康对话质量已全面验收。
- 覆盖安装新增一次性模型迁移：已知旧内置默认配置切换到本包配置；其他手动服务、不同图片模型、不同协议，以及已设置的目标模型均保留。
- 编译实际 Java 迁移策略并运行合成配置断言通过：`tests/test_android_model_migration.py`。包括旧默认迁移、只执行一次、首次安装及自定义配置保留。
- 本轮未调整提示词、界面或健康数据处理逻辑，未连接 Android 真机。

## 私人 APK

包名 `cn.zhiheng.mobile`，versionCode `43`，versionName `0.4.35-test`。

- 文件：`release/android-0.4.35/Zhiheng-0.4.35-embedded-model-test.apk`。
- 默认含模型构建成功，29 个引擎资源与源码一致；对话和图片模型均为 `gpt-6.1-sol`，9 个配置字段与当前配置一致，包内密钥与 Windows User 环境一致。没有打入 `.data`，源码资源目录的临时明文模型配置已清理。
- 签名验证通过，证书 SHA-256 与旧包相同：`3c6601691d1036d7561b3bb3a928e435bfeedbd8492044eb9599654eefa1e481`。
- APK SHA-256：`396642f84d6e221fc9021ff82a6c930f625f5a515e1d04a40883afab0578cc83`。
- 构建校验记录：`tmp/build-0.4.35.log`、`tmp/apk-verification-0.4.35.log`、`tmp/apk-signature-0.4.35.log`、`tmp/apk-badging-0.4.35.log`。

先备份，再覆盖安装，不卸载旧版。此包内置可提取的远程模型密钥，仅供本人手机测试；旧 APK 保留。
