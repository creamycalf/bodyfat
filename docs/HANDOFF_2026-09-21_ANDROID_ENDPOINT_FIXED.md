# 安卓模型直连验证成功：0.2.3（最新入口）

用户明确指定baseURL改为http://47.110.38.211:8080。沿用当前模型/密钥，电脑禁用代理访问 `/v1/chat/completions` 成功，因此实际base设置为 `http://47.110.38.211:8080/v1`。

产物：release/android-0.2.3/Zhiheng-0.2.3-embedded-model-test.apk，versionCode5，相同签名，覆盖安装；SHA256同目录。电脑config.json与正式健康数据库未修改。

修改：prepare.py可传--base-url；build.ps1提供-BaseUrl。Android原生传输允许精确IP/端口HTTP例外；系统network-security-config仅为此IP新增明文域规则，Python验证再次限制端口8080。其他HTTP仍拒绝。无证书绕过，禁自动重定向。旧vibecd默认配置首次升级自动迁移至新内置配置；用户其他自定义配置保留。手动输入指定HTTP根地址自动补/v1。

实际验证：

- Android9 emulator-5554直接安装release APK，连接探测真实调用成功，正式WebView聊天收到模型回复，体重保存。
- 再次增强测试并执行：先断言Activity实际加载的新baseURL（不是只测试临时替换），然后验证当前会话最新assistant.result.ai_status=connected且无ai_error，避免旧消息造成假通过。输出PASS，见tmp/android-0.2.3/android-real-test.txt。
- 全量147项Python通过，新增精确HTTP白名单/端口与伪域名拒绝测试，见tmp/android-0.2.3/tests.log。
- release构建及签名验证通过。无桌面代理依赖的Android端真实成功与先前电脑验证不同。

边界：模型云端联网运行；HTTP明文传输凭据和内容已告知用户，仅个人测试，不能公开分发。模拟器成功不代表所有手机网络可达。原生语音/直接拍照等旧边界未改变。
