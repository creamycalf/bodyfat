# 内置模型安卓测试包交接（最新入口）

最新接续：[Android连接排查0.2.2](HANDOFF_2026-09-18_ANDROID_CONNECTION.md)。用户反馈模型连接未成功，以新文档边界为准。

## 继续修订：0.2.1（当前交付）

使用 `release/android-0.2.1/Zhiheng-0.2.1-embedded-model-test.apk`，校验值见同目录SHA256.txt；以下0.2.0记录为历史。

- versionCode升为3，可覆盖安装。修复旧版保存了disabled配置时无法自动启用的问题，内置默认配置只自动补入一次；已有有效密钥不覆盖。
- prepare.py新增显式 `--embed-model`；默认构建无凭据，重复准备资源会清理旧默认配置。build.ps1提供 `-EmbedModel`，输出0.2.1到独立目录，不覆盖已交付0.2.0。
- 不再将default_model.json复制到手机engine目录，运行时设置由Keystore加密存储。**APK中的default_model.json仍是可提取配置，不是加密且不可提取的秘密。前面的加密措辞只适用于手机SharedPreferences。**
- 修复内置测试的错误断言：顶部原生状态不在网页DOM；等待时间扩展到120秒；明确要求assistant result.ai_status=connected且无ai_error，避免本地规则保存被误报为真实模型通过。
- 最终release/lintVital及签名校验通过。全量145项回归通过，日志 `tmp/embedded-apk-20260918/tests.log`。
- `tests/verify_embedded_apk.py`读取APK内实际配置，在一次性目录运行真实product.chat，返回connected、无错误、1条体重记录；报告 `tmp/embedded-apk-20260918/result.json`。不打印或保存密钥。
- 重新启动既有雷电模拟器，但adb仍offline；本轮没有卸载、清空模拟器或正式数据。Android内置模型联网验收仍未完成，未以电脑专项冒充安卓验证。

---

日期：2026-09-18。接续 `HANDOFF_2026-09-18_ANDROID_STANDALONE.md`。用户要求先整体测试流程，因此生成了含当前模型配置的测试包。

## 交付物

- `release/android-standalone-model-20260918/Zhiheng-0.2.0-embedded-model-test.apk`
- SHA-256：`8a69d638a8bdf57d27a25e9b845b9609ceadbc278d7b9436429b229c759e49f4`
- 包名 `cn.zhiheng.mobile`、versionCode2、0.2.0-standalone，Android 8.0+，arm64-v8a/x86_64。
- APK中的 `assets/engine/default_model.json` 由构建时读取电脑环境变量 `ZHIHENG_AI_API_KEY` 生成；检查确认模型为当前 `claude-opus-4-8`、接口为当前 HTTPS 地址、密钥存在但没有打印内容。源码和桌面正式数据没有写入密钥。

## 启动行为

- 首次启动没有 AI 设置也没有电脑连接页。Java从内置默认配置读取后，立即使用 Android Keystore AES/GCM 加密保存到手机私有SharedPreferences；随后内置Python服务直接使用规范化配置。
- 后续启动优先读取手机加密配置。顶端仍显示 AI 状态，主要供排查；本包不需要手动填写。
- 删除应用会删除本地健康数据和加密密钥。覆盖升级保留它们。AI密钥不是普通健康备份的一部分。
- 内置模型不是离线模型：手机需要联网访问模型服务。只是模型凭据已随测试包预置，不需要用户手动配置。

## 验证

- `android/standalone/prepare.py` 只打包白名单产品引擎，并在构建期生成默认模型配置；不打包桌面数据库、媒体或 `config.json`。
- release 构建和 lintVital 通过；apksigner v2通过；aapt核对包名、版本、权限和 ABI。APK大小约35.2MiB。
- 不含模型配置的独立版已在安卓9模拟器通过：内置Python/SQLite、首页、离线体重72公斤、备份、强制结束重启、Keystore加密配置，输出 `PASS standalone first/restart`。Python全量145项通过。
- 为内置模型新增 `SmokeInstrumentation` 的 `embedded` 阶段：检查 AI 已配置、真实发送一条体重请求并核对本地记录。测试 APK已编译；由于模拟器随后断开，**该阶段本轮没有运行成功，不能声称真实模型请求已通过**。真实测试请在你的手机安装本交付包执行。

## 重要边界

这是测试包，凭据可被有能力的用户从 APK 中提取；不要转发。正式发布必须改为首次手动配置、服务器代理或平台安全凭据。接口、模型、密钥沿用当前电脑配置，若过期会在应用中显示AI请求失败，需要换正式不含凭据包。

本次没有改变电脑 `.data`，没有重启或写入正式桌面数据；前一版独立 APK 和电脑连接 APK 仍保留用于回退。详见安装说明。
