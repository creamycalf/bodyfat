# 安卓模型连接0.2.2排查交接（最新入口）

最新实测：[2026-09-21安卓网络定位](HANDOFF_2026-09-21_ANDROID_NETWORK_FINDING.md)。已在Android复现20秒连接超时，并确认电脑系统代理与安卓直连路径不同。

用户反馈0.2.1配置后仍无法连接。尚未拿到手机具体错误码，不能确定根因。前次电脑环境模型成功不能证明Android成功。

产物：release/android-0.2.2/Zhiheng-0.2.2-embedded-model-test.apk；versionCode4，沿用签名，可覆盖安装。SHA256同目录。

改动：server.model_urlopen作为可替换传输边界，默认仍urllib以保持桌面行为。Android运行时改用ModelTransport.java的HttpsURLConnection，系统信任库、默认主机名验证、禁重定向、连接/读取超时、8MiB响应上限。Python适配保持HTTP错误码，单独传递DNS/TLS/超时，不暴露响应正文或密钥。普通桌面请求不变。

原生AI设置增加“测试已保存的模型连接”和“恢复内置测试模型”。测试发送简单OK请求，不带健康数据；界面显示明确错误码与排查说明。恢复需用户点击确认，仅改变AI配置，保留健康数据。

验证：release及lintVital成功、apksigner通过；全量146测试通过，tmp/android-0.2.2/tests.log。新增测试模拟Java传输结果，覆盖请求头、毫秒超时、成功数据、401、DNS/TLS/超时映射。此测试不是Android网络实测。adb当前无设备，本次不能声称用户问题已解决。

下一步根据用户测试连接的完整结果定位域名解析、证书、权限或超时，必要时在用户设备收集去敏错误。严禁通过关闭SSL校验绕过证书失败。新包含私人测试凭据，可被提取，不用于公开分发。
