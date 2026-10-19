# 知衡 0.4.10 模型地址修复

用户再次明确模型地址为 `http://47.110.38.211:8080`。历史交接 `HANDOFF_2026-09-21_ANDROID_ENDPOINT_FIXED.md` 已记录同一地址，但当前 `config.json`、`config.example.json` 和 README 后来回退到旧域名，导致 0.4.9 内置配置打错地址。

已统一使用 OpenAI 兼容 API 基址 `http://47.110.38.211:8080/v1`。`android/standalone/build.ps1` 也将它设为默认打包地址；需要不同地址时仍可显式传 `-BaseUrl`。Android 的 `endpoint_migration_v6` 在覆盖安装后把已保存的旧默认域名或空地址更新为新包内置配置，保留用户手动设置的其他服务。项目默认值记录在根目录 `AGENTS.md`。

合成资料验证：该地址的两次简短请求分别约 4.3 秒、4.7 秒返回；与截图同类的完整咨询请求约 8.2 秒返回，`ai_error=null`，体重记录一条。219 项 Python 回归通过，Android 离线构建成功。APK 检查确认包名 `cn.zhiheng.mobile`、版本码 18、与旧版相同签名、内置基址准确、模型名和密钥存在、未包含健康资料，构建后的临时明文配置已清理。没有连接 Android 真机，升级迁移及手机网络仍待用户实测。

交付：`release/android-0.4.10/Zhiheng-0.4.10-embedded-model-test.apk`。SHA-256：`84f4fa8b4dcafec33c63645650f26c145dc7379892a273a19de86573e68424ce`。本包仅供私人测试；APK 内密钥可提取，指定 HTTP 服务的传输不加密。覆盖安装前备份，不要先卸载旧版。
