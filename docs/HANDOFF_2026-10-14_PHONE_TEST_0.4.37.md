# 知衡 0.4.37：内置离线中文语音

用户在中国无代理使用时遇到语音网络错误。旧版仍会在系统设备端中文识别不可用时切到默认联网识别服务，因而可能受识别服务可达性影响。错误来自语音识别路径，与当前对话模型密钥无直接关系；代码没有确认具体厂商服务，不能据此认定是某一家服务被阻断。

## 本次实现

- “语音”在 Android APK 中改为本机 Vosk 中文识别，随包提供 `vosk-model-small-cn-0.22`，不需要手机下载模型、代理或新的服务密钥。
- 录音使用 16kHz 单声道 PCM，音频只在内存处理，没有录音文件或上传请求；转出的文字先留在草稿中，核对后手动发送。
- 模型首次使用从 APK 后台解压到应用自己的 `files/voice`，核验完整 ZIP 的 SHA-256，限制路径、文件数量与大小，完整安装后写入就绪标记。原有健康资料目录不参与。
- 模型加载后复用。准备、录音、结束、取消有明确状态；录音最多 50 秒，结束时拼合已确定分段和最终片段，取消后丢弃旧会话回调。
- 处理麦克风权限、音频占用、存储、模型及本地库不可用等错误，恢复草稿和按钮。失败后保留输入法语音入口。
- `MainActivity` 的实际录入路径不再打开系统联网识别服务或语音窗口。手机型号、系统语言包与云识别服务不再决定本包的识别引擎。
- 语音转文字可以离线；发送文字给 `gpt-6.1-sol` 对话模型仍需要网络。

使用官方 [Vosk Android API](https://alphacephei.com/vosk/android) 与 [中文小模型](https://alphacephei.com/vosk/models)。模型 ZIP 为 43,898,754 字节，解压后约 68.3MB，官方标注适用于 Android，Apache 2.0。本包使用 `vosk-android:0.3.75` 和 `JNA:5.18.1`，许可证随包保留。构建前核验模型和依赖哈希，资源缺失或损坏会明确失败。

## 验证及限制

- `tests/test_offline_voice.py`：13 项控制器检查通过。使用实际 Java 源码、实际模型 ZIP、模拟 Android 麦克风及 Vosk 调用，验证首次解压与复用、哈希/路径保护、中文分段、停止时末帧、取消/旧回调、超时及权限/音频/JNI错误恢复。
- `tests/qa_offline_voice_ui.mjs --app-url=http://127.0.0.1:8798`：4 组浏览器检查通过，包含实际 App 集成。离线提示、partial 不写草稿、final 回填、手动发送、操作锁及键盘回退正常；语音步骤无外网请求、无 Web Speech 调用。证据 `tmp/offline-voice-ui-0.4.37.json` 与对应截图。
- 原有语音 22 项生命周期检查、6 组浏览器/App 回归仍通过。
- `tests/qa_offline_voice_model.py`：在 Windows 上使用同一模型实际解码本机合成中文 WAV，屏蔽 socket 连接，正确识别“今天我吃了一个苹果喝了一杯牛奶晚上准备散步三十分钟”，四个关键词均命中。约 1.8 秒包含解压/加载与解码，音频约 7.67 秒；这不是手机录音速度或准确率指标。证据 `tmp/offline-voice-model-0.4.37.json`。
- Android x86_64 模拟器实际 JNI 解码通过：独立 `cn.zhiheng.offlineqa` 验收包没有 INTERNET 或麦克风权限，使用本包同一 Vosk/JNA 依赖、中文模型和合成 WAV，约 3.726 秒识别出完整句子，四个关键词均命中。验证后仅卸载所创建的验收包，未修改模拟器已有其他应用或本项目健康资料。证据 `tmp/offline-android-jni-0.4.37.json` / `.log`。这验证原生加载与解码，不代表用户手机麦克风或 arm64 实机已测试。
- 尚未在用户手机验证真实收音、普通话/方言、噪声、数值和运行内存。本地小模型可能漏词或认错数字，识别后仍须核对，不代表已达到云端转写质量。

## 私人测试 APK

- `release/android-0.4.37/Zhiheng-0.4.37-embedded-model-test.apk`，101,667,957 字节，约 102MB（97MiB）。旧 APK 保留。
- 包名 `cn.zhiheng.mobile`，versionCode `45`，versionName `0.4.37-test`。
- 继续内置当前远程模型接口 `https://code.leessmin.com/v1`、对话及图片模型 `gpt-6.1-sol` 与 Windows User 环境中的 Key。9 个配置字段与当前配置一致，29 个引擎资源与源码一致；源码资源中的临时明文配置已清理，未打入 `.data`。
- 模型 ZIP 完整校验通过；APK 同时包含 arm64-v8a 与 x86_64 的 Vosk/JNA 原生库、中文模型和许可证，手机运行时不下载模型。控制器最终源码已重新编译进入本包。
- 模型 ZIP SHA-256：`3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba`。
- APK 签名验证通过，证书与旧版一致：`3c6601691d1036d7561b3bb3a928e435bfeedbd8492044eb9599654eefa1e481`。
- APK SHA-256：`42811c781d5a3f2a067f56878b578492e9dbd954bfdb99bbad832eadd0ff0ebf`。
- 记录：`tmp/build-0.4.37-final.log`、`tmp/apk-verification-0.4.37.log`、`tmp/apk-signature-0.4.37.log`、`tmp/apk-badging-0.4.37.log`、`tmp/offline-voice-apk-0.4.37.log`。

先备份，再覆盖安装，不卸载旧版。包内远程模型密钥可提取，仅供本人手机测试。

上一版：[0.4.36 系统语音兼容修复](HANDOFF_2026-10-13_PHONE_TEST_0.4.36.md)。
