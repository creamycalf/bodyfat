# 知衡 0.4.8 内置模型配置手机测试包

用户在 0.4.7 无模型包之后明确要求：本项目今后的私人测试 APK 默认包含模型配置，并形成项目记忆。持久规则见项目根目录 `AGENTS.md`；`android/standalone/build.ps1` 现默认传入模型配置，仅显式 `-NoEmbedModel` 才产出无模型包。缺少环境密钥时构建失败，不会静默降级。`-EmbedModel` 仍可用于兼容旧命令。

本包：`release/android-0.4.8/Zhiheng-0.4.8-embedded-model-test.apk`，包名 `cn.zhiheng.mobile`，`versionCode=16`、`versionName=0.4.8-test`，与 0.4.7/0.4.6 相同的本地测试签名。SHA-256：`f8e9b5ab5ee3d2352ccb0c3906fb505a31ebbd8e55b5fb840b9d6be44eaee1ed`。

验证：Android 离线构建成功；签名和版本已核对；APK 内包含模型接口、模型名和密钥配置及最新 `report_editor.py`，不含 `.data` 健康资料或本地签名密钥；构建后源码资源目录中的临时明文配置已清理。功能回归与手机窄屏 UI 测试结果沿用 0.4.7 交接文档，本轮未连接真机或验证模型服务实时可用性。

“内置模型”仍是远程模型接口配置，**不是离线模型**。APK 内的访问密钥可被提取，本包只供用户本人手机测试；不要公开分享、上传应用市场或提交到公共仓库。安装前建议备份，在相同包名和签名的旧版上直接覆盖安装，不要先卸载。
