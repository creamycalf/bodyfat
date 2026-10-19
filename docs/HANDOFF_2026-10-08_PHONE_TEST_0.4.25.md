# 知衡 0.4.25：新接口实测与私人测试包

按用户本轮要求使用更新后的 config.json 和 Windows 用户环境变量，覆盖此前默认地址约定。本次接口为 `https://cc-vibe.com/v1`，文本与图片模型均为 `gpt-5.5`，协议为 `chat_completions`。密钥未写入本文档或源码。

## 实测结果

- 文本请求返回 OK，ai_status=connected，耗时 31031 ms。
- 合成数字图片经应用 analyze_image 流程成功识别 6729，ai_status=connected，耗时 12781 ms，无健康记录候选。
- 使用临时目录进行测试，未读取或修改项目 .data 中的健康资料。
- Android 运行层 4 项单元测试通过，release 构建和 lintVital 成功。
- 以上为电脑端接口实测，未连接用户手机；不能替代手机网络及 DNS 验证。

## 覆盖安装

新增一次性 model_migration_v8：此前 max-tabs/GPT-5.5 默认组合，以及更早 IP/vibecd/Opus 默认组合迁移为本包内置配置。其他模型或服务组合保留。如手机有手动配置，需在 AI 设置恢复内置测试模型，等待保存成功后关闭设置再重新打开测试，避免旧表单保存回旧值。

## 交付校验

- 文件：release/android-0.4.25/Zhiheng-0.4.25-embedded-model-test.apk
- 包名 cn.zhiheng.mobile；versionCode 33；versionName 0.4.25-test。
- SHA-256：8ab3779f7331879d4ea6e5e17cad658090bef24c72c63b639f8e71ab9dc1a588。
- 签名验证通过；证书 SHA-256：3c6601691d1036d7561b3bb3a928e435bfeedbd8492044eb9599654eefa1e481，与旧版本一致。
- APK 内置地址、模型、协议与 config.json 一致，Key 与本次测试所用用户环境变量一致。
- 29 个公开引擎文件与源码逐字节一致，引擎资源仅包含公开文件和内置模型配置，源码临时明文模型资源已清理。
- 旧 APK 保留。先备份，再覆盖安装，不卸载旧版；仅供本人私人测试，不公开分发。
