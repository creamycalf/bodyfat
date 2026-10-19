# 独立安卓应用交接

最新接续：[内置模型安卓测试包交接](HANDOFF_2026-09-18_ANDROID_EMBEDDED_MODEL.md)。

2026-09-18。用户明确要求独立应用，替代此前0.1.0电脑连接版。最新产物 `release/android-standalone-20260918/Zhiheng-0.2.0-standalone.apk`，安装说明同目录。

## 架构与行为

- Android Activity + WebView + APK内置CPython3.12/Chaquopy17。产品现有6个Python模块与13个网页资源按白名单打包，不复制电脑数据库、媒体、config.json或密钥。
- 内置业务服务只监听手机127.0.0.1:18787，随机进程会话Cookie、HttpOnly、SameSite及Host/Origin核验。此地址完全由应用内部使用，用户不需要配置；不开放手机LAN服务。WebView阻止外部网络导航和资源，本地明文仅允许loopback，AI配置要求HTTPS。
- SQLite与原图在 `files/health-data/`，引擎在 `files/engine/`。稳定本机origin保留WebView会话历史选择；强制结束后由新进程重新启动内置引擎。
- 顶部AI设置是可选入口，不阻挡首页。不含私人默认密钥。可手动设置或导入JSON；保存前规范化并验证接口协议、模型和密钥。凭据使用Android Keystore AES/GCM加密后存SharedPreferences，不写入健康备份。
- 原生实现本地导出文件到系统保存选择器；恢复、图片上传走系统文件选择器。JS导出按钮通过固定自定义导航触发本机导出，仅允许json/backup两种路径；未开放任意JavaScript接口。
- 增加旧WebView缺失Array.at的兼容补充，模拟器WebView91可用。

## 构建与产物

- 项目 `android/standalone/`；与旧 `android/build.py` 联网壳构建独立。复现用 `android/standalone/build.ps1`，可用 `-Offline` 利用已下载缓存。
- AGP9.2.1、Gradle9.5、JDK17、SDK36、Chaquopy17、Python3.12。按[Chaquopy官方文档](https://chaquo.com/chaquopy/doc/current/android.html)配置。构建依赖位于项目 `android/.gradle-standalone/`；SDK/JDK只读复用已有工具路径。
- 包名cn.zhiheng.mobile，versionCode2，0.2.0-standalone，minSdk26/targetSdk34，arm64-v8a/x86_64，仅INTERNET权限。相同本地测试签名，可覆盖旧版本；手机初始数据为空，不自动同步电脑。
- APK 36,862,744字节；SHA256 `da50e9b2fce8cf14701a17b4bdf448830575e288f4aa842f2a2e215c965c9432`；apksigner v2校验通过。发布包无调试服务器、无androidTest类。
- 编译经历Java CookieManager重名和network-security-config缺少includeSubdomains两处错误，均修复后通过正常release构建及lintVital，未关闭检查。

## 验证证据

- `tests/test_mobile_standalone.py`：配置校验；全新独立子进程启动内置引擎，未认证拒绝；禁用AI情况下记录体重；重启后数据库与会话完全一致；新进程使用新Cookie。
- Python全量145项通过：`tmp/standalone-20260918/tests.log`。
- 使用已存在的Android9模拟器emulator-5554，原先没有cn.zhiheng.mobile包，安装release APK成功，首页截图 `tmp/standalone-20260918/screen.png`。
- `SmokeInstrumentation.java` 位于androidTest，不进入交付APK。直接运行签名release Activity，通过真实WebView提交体重消息，核验SQLite记录、三页切换、备份返回ZIP；验证Keystore合成凭据加密保存。first阶段输出PASS。
- adb force-stop 后重新运行restart阶段，核对72公斤只有一条、凭据成功解密；清除合成AI配置，输出PASS。最终截图 `tmp/standalone-20260918/final-screen.png`。
- 包内容白名单检查 `tmp/standalone-20260918/package-audit.json`：19个引擎文件、内置libpython、无数据库/config.json/签名私钥。未向正式桌面数据注入任何模拟资料。

## 准确边界

1. Android上的真实模型网络调用尚未验收；本轮未得到用户对凭据导入方式的选择，未自动导出或嵌入电脑密钥。手动设置与导入均已实现。
2. 实际系统文件选择/保存交互、个人手机适配、实拍与输入法仍需用户实测；备份生成和应用内运行已验证，不能扩大表述为所有原生文件流程通过。
3. 独立表示不依赖电脑，不表示模型离线运行。未配置AI时可查看/编辑本地数据及使用有限本地提取，生成计划/图像识别需联网模型。
4. 没有常驻前台服务；Android结束后台进程时未完成请求可能中止。已提交SQLite事务保留，重新打开加载数据。后台长期运行与原生录音/直接拍照不在本版完成范围。
5. 不自动迁移电脑数据。电脑完整备份可通过现有恢复流程导入，恢复会替换手机数据；凭据单独配置。卸载删除本地数据，应先导出备份。
