# 安卓电脑连接版测试包交付（已被独立版替代）

最新：[独立安卓应用交接](HANDOFF_2026-09-18_ANDROID_STANDALONE.md)。用户已明确要求不依赖电脑，请使用0.2.0独立APK；下文仅保留旧版历史。

接续 `HANDOFF_2026-09-17_TEST_READY.md`。2026-09-17。

## 产物

- `release/android-20260917/Zhiheng-0.1.0-test.apk`，包名 `cn.zhiheng.mobile`，版本0.1.0-test，minSdk26 / targetSdk34，仅声明 INTERNET 权限。无原生ABI依赖。
- 安装说明和 SHA256.txt 在同目录。APK不含模型密钥、健康数据库、连接码或其他项目资源。
- `.mobile-private/android-test.jks` 为本项目本地测试签名，后续更新需保留。测试签名不用于商店正式发布。
- 原生源代码 `android/src/cn/zhiheng/mobile/MainActivity.java`；`android/build.py` 使用已有 SDK36/JDK17 离线编译，依次aapt/javac/d8/zipalign/apksigner。工具默认引用相邻 moviedl 的工具目录，仅只读使用编译器；可传 --sdk / --jdk，不修改该项目。

## 连接与运行

- Android WebView加载受连接码保护的局域网页面，限制为私有IPv4，保存连接地址，支持文件选择、弹窗确认、返回和刷新、断线提示。
- `mobile_gateway.py` 只代理至本机127.0.0.1:8787，无单独数据库；监听当前Wi-Fi地址8788。用随机连接码换 HttpOnly / SameSite=Strict Cookie，校验请求Host/Origin；不记录连接URL或健康正文，转发保留聊天流式进度。
- 电脑入口 `启动手机测试.cmd` / `start-mobile.ps1`。连接码及地址仅在 `.mobile-private/`。当前已启动192.168.91.111:8788；原正式后端继续仅监听127.0.0.1。
- 现有电脑防火墙已允许对应Python入站，本次未修改规则。手机实网可达性仍需真机确认；HTTP仅适用于可信同网测试。
- 新增mobile-compat.js，用getRandomValues补充局域网HTTP缺少的randomUUID，避免手机端页面初始化/发消息/上传时报错。server.py仅增加该静态模块白名单。

## 验证

- APK编译成功，apksigner v2/v3签名校验通过，aapt检查包名/版本/入口/权限正确。SHA256 `4e01bce3c789c4e89c1c0b24e274101a4609fd6d8b43036d2694e7c9c1850333`。
- Python全量143项通过：`tmp/android-release-20260917/tests.log`。新增网关测试覆盖未认证拒绝、错误码拒绝、配对Cookie、代理响应、跨来源与错误Host拒绝。
- `tests/qa_mobile_gateway.mjs`：真实LAN HTTP入口390px四页无溢出/脚本错误，UUID回退有效，Cookie不可被JS读取，刷新保留登录；仅只读访问正式数据。截图 `tmp/android-release-20260917/lan-mobile.png`。
- adb没有连接设备，因此没有声称真机安装与运行通过。
- 正式发布前备份 `tmp/android-release-20260917/before-release.zip`。核实8787原PID11152后精确重启，既有守护拉起新进程，健康检查正常。重启前后导出SHA256均为 `4DF2100D0D713B599E20E5E2A34038CE5128965C024ABBC448439A908B8EC97A`。

## 未完成范围

安卓本地后端/离线运行、原生语音、直接调用相机、手机备份下载未实现。本版本允许选择现有照片，语音使用输入法，导出保留电脑端。用户安卓实测后再按设备反馈修复；原功能与真实模型边界见上一份交接，不因APK打包而视为通过。

WebView参考：[Android官方WebView指南](https://developer.android.com/develop/ui/views/layout/webapps/webview)。
