# 知衡 0.4.24：内置模型配置回退修复

## 本轮结论

0.4.23 APK 中的内置 Key 与当前 Windows 用户环境变量的 Key 指纹一致，电脑端使用同一配置请求文字接口正常，因此不是打包时混入了另一把 Key。

本轮修复了覆盖安装后的配置恢复路径：如果旧版 Android Keystore 配置无法解密，应用现在会回退到本 APK 的内置模型配置；如果保存配置没有有效 Key，也会使用内置配置。用户仍然有有效的手动配置时会保留，不会被覆盖。

## 配置与验证

- Base URL：`https://server.max-tabs.com/v1`
- 对话模型：`gpt-5.5`
- 图片模型：`gpt-5.5`
- 协议：`chat_completions`
- 当前 APK 内置 Key 与受控环境 Key 的 SHA-256 指纹一致；本文不记录 Key 内容。
- Android Java 编译、签名和资源打包成功。
- `tests.test_mobile_standalone`：4 项通过。
- 之前的 Python 回归 277 项和重复图片 UI 回归仍通过。

## 私人测试 APK

- [Zhiheng-0.4.24-embedded-model-test.apk](../release/android-0.4.24/Zhiheng-0.4.24-embedded-model-test.apk)
- 包名 `cn.zhiheng.mobile`，versionCode 32，versionName `0.4.24-test`。
- SHA-256：`cf85147febb3c29b317de93d4cd3b5c120585e84e107a9734e3bc39bda553202`。
- 证书 SHA-256：`3c6601691d1036d7561b3bb3a928e435bfeedbd8492044eb9599654eefa1e481`。
- APK 内置地址、模型和协议已核对；源码临时明文资源已清理，没有读取或打包项目 `.data` 中的真实健康资料。

先备份，再覆盖安装，不卸载旧版。覆盖后如果仍显示旧设置，可在「AI 设置」中点「恢复内置测试模型」，再点「测试已保存的模型连接」。包内含可提取的远程访问密钥，仅供本人手机测试，不可公开分发。
