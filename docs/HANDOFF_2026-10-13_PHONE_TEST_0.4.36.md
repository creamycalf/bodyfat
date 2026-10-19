# 知衡 0.4.36：语音录入兼容与恢复

用户反馈手机语音录入无法使用。本轮未获得具体手机错误信息，先修复代码中可确认的兼容性及状态问题。

## 原因与修复

旧版仅启动外部 `RecognizerIntent` 语音窗口。如果手机没有提供该窗口，就只能失败；没有系统识别服务路径。前端还存在原生请求无超时、权限正忙时原生静默返回、语音桥尚未注入时可能启动 WebView 不支持的 Web Speech、聊天请求期间仍可开始语音等问题。

- 新增 `NativeVoiceInput.java` 调用系统 `SpeechRecognizer`。Android 12 及以上有设备端识别服务时优先使用，缺少中文语言包时尝试默认服务；服务不兼容或不能启动时再尝试外部系统语音窗口。
- Manifest 补齐语音服务和语音窗口的查询声明。[Android SpeechRecognizer 文档](https://developer.android.com/reference/android/speech/SpeechRecognizer)要求 Android 11 及以上声明服务查询，识别对象不用时必须销毁。
- 统一监听、结束识别、处理结果、取消和错误状态；原生识别设 50 秒等待上限，前端另有桥连接、启动响应和结果超时，超时后恢复按钮并保留草稿。
- 每次识别独立标识。取消或换一次识别后，迟到的旧回调不再回填；结束、失败、取消及退出应用时释放识别资源。
- Android 原生语音桥就绪前先等待，不调用 WebView 的浏览器识别接口。系统权限正忙时明确回失败事件，避免一直等待。
- 录音期间保护发送、照片、相机、新对话和历史切换。结果仅追加到原草稿，派发输入事件，核对后手动发送；结果不自动提交或记账。
- 所有识别方式不可用时，提供“使用输入法语音”按钮，聚焦输入框并请求显示系统键盘，提示点击键盘的麦克风。

设备仍需提供至少一种可用的系统识别服务或具有语音功能的输入法。新增调用不能给缺少识别引擎的手机安装引擎，也不会把录音当成文字/图片发给当前模型。

## 检查与限制

- `tests/voice_test.mjs`：22 项前端生命周期检查通过，包括草稿、输入事件、取消、停止、旧回调、空结果、同步异常、启动/结果/桥超时、重试和禁用输入框。
- `tests/qa_voice_ui.mjs --app-url=http://127.0.0.1:8798`：6 组 Edge 移动宽度检查通过，包含真实 `app.js` 的按钮保护、会话保护、手动发送 `input_source=voice` 和输入法入口。语音桥及识别事件使用模拟，不是真实录音。记录 `tmp/voice-ui-0.4.36.json`，截图 `tmp/voice-app-ui-0.4.36.png`。
- 原图片聊天全流程回归通过：`tmp/image-chat-ui-0.4.36.log`，包含图片、弹窗、草稿、重试、会话、键盘视口与宽度检查。
- `tests/test_android_voice.py`：使用 JDK 编译实际 `NativeVoiceInput.java`，配合最小 Android 假对象运行 10 项验证通过，包含中文 Intent、监听/结束/结果、Android 12 设备端优先、缺中文语言包回退、服务不可用、取消后旧回调与新会话隔离、权限/网络/无语音错误、50 秒期限与资源释放。该检查不使用真实麦克风或厂商识别服务。
- 本次 `adb devices -l` 未发现连接设备。没有真机麦克风、厂商识别服务或语音准确率实测；需要手机验证。所有本地测试使用隔离临时数据，没有访问真实 `.data`。

## 私人测试 APK

- 文件：`release/android-0.4.36/Zhiheng-0.4.36-embedded-model-test.apk`。
- 包名 `cn.zhiheng.mobile`，versionCode `44`，versionName `0.4.36-test`。旧 APK 保留。
- 继续使用当前接口 `https://code.leessmin.com/v1`，对话和图片模型 `gpt-6.1-sol`。包内 29 个引擎资源与源码一致，9 个配置字段与当前配置一致，密钥与 Windows User 环境一致；临时明文模型资源已清理，未打入 `.data`。
- 签名验证通过，证书 SHA-256 与旧版一致：`3c6601691d1036d7561b3bb3a928e435bfeedbd8492044eb9599654eefa1e481`。
- APK SHA-256：`67c6dc26a9b416549071fb50e2ece7d096c2bd0912b3526d9d6b80671bf6e4e3`。
- 记录：`tmp/build-0.4.36.log`、`tmp/apk-verification-0.4.36.log`、`tmp/apk-signature-0.4.36.log`、`tmp/apk-badging-0.4.36.log`、`tmp/apk-manifest-0.4.36.log`。APK 中的麦克风权限及语音查询声明已核对。

先备份，再覆盖安装，不卸载旧版。内置远程模型密钥可提取，仅供本人手机测试。

上一版：[0.4.35 模型切换](HANDOFF_2026-10-13_PHONE_TEST_0.4.35.md)。
