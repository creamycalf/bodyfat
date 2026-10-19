# 知衡 AI 配置与接口排查

> 历史配置说明：本文部分示例仍来自早期中转服务。当前已验证配置和测试流程请以根目录 `README.md`、`OPERATIONS.md` 和 `TEST_AND_ACCEPTANCE.md` 为准，切勿复制本文中的旧 Base URL 或模型名作为当前配置。

## 1. 配置文件位置

推荐使用：

```text
E:\workspace\codexworkspace\bodyfat\config.json
```

当前程序在找不到 `config.json` 时，会临时读取 `config.example.json`，但正式使用不要把真实 Key 留在 example 文件里。

## 2. 推荐配置格式

```json
{
  "ai": {
    "enabled": true,
    "provider": "openai-compatible",
    "base_url": "https://server.max-tabs.com/v1",
    "api_key": "你的API_KEY",
    "model": "gpt-5.5",
    "vision_model": "gpt-5.5",
    "protocol": "auto",
    "timeout_seconds": 45
  },
  "storage": {
    "max_image_mb": 8,
    "delete_original_after_days": 30
  },
  "app": {
    "name": "知衡",
    "timezone": "Asia/Shanghai",
    "require_confirmation_before_record": true
  }
}
```

也兼容驼峰写法：`baseURL`、`apiKey`、`visionModel`。

注意：`base_url` 或 `baseURL` 必须是纯 URL，不能写 Markdown 链接格式：

```text
正确：https://server.max-tabs.com/v1
错误：[https://server.max-tabs.com/v1](https://server.max-tabs.com/v1)
```

## 3. 启动

在项目目录运行：

```powershell
cd E:\workspace\codexworkspace\bodyfat
python server.py
```

浏览器打开：

```text
http://127.0.0.1:8787
```

不要直接双击 `index.html`，否则前端无法调用本地 API。

## 4. 协议模式

当 `protocol` 为 `auto` 且模型名以 `gpt-5` 开头时，程序按以下顺序尝试：

### Responses API

```text
POST {base_url}/responses
Authorization: Bearer {api_key}
Content-Type: application/json
```

```json
{
  "model": "gpt-5.5",
  "input": [{"role": "user", "content": "..."}],
  "max_output_tokens": 1200
}
```

### Chat Completions 回退

```text
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json
```

```json
{
  "model": "gpt-5.5",
  "messages": [{"role": "user", "content": "..."}],
  "max_tokens": 1200
}
```

程序已移除 `temperature`，以兼容不接受该字段的推理模型或中转服务。

如果服务商明确只支持某一种协议，可以设置：

```json
"protocol": "responses"
```

或：

```json
"protocol": "chat_completions"
```

## 5. 图片请求

前端读取图片后发送到：

```text
POST /api/analyze-image
```

后端先保存图片，再把图片转成视觉模型常见的 data URL：

```json
{
  "type": "image_url",
  "image_url": {
    "url": "data:image/jpeg;base64,..."
  }
}
```

返回结果必须经过用户确认，不能直接写入健康档案。

## 6. 本地诊断接口

```text
GET http://127.0.0.1:8787/api/health
```

检查服务是否启动。

```text
GET http://127.0.0.1:8787/api/config-status
```

只返回配置状态，不返回 Key。

可能结果：

```json
{
  "enabled": true,
  "key_present": true,
  "key_storage": "environment"
}
```

该接口不会返回模型名、接口地址或协议。需要核对这些字段时，应直接在可信本机查看配置文件。

## 7. 错误判断

### `URLError` / `WinError 10013`

网络连接阶段失败，尚未得到模型服务器的 HTTP 响应。常见原因：网络、代理、防火墙或运行环境权限。

### HTTP 400

请求体或字段不符合服务商要求。

### HTTP 401

API Key 无效、过期或鉴权头不对。

### HTTP 403

Key没有使用权限、IP受限或账户被限制。

### HTTP 404

`base_url` 或协议路径不对，例如服务商只支持 `/chat/completions`，却请求了 `/responses`。

### HTTP 429

额度、频率或并发限制。

### 返回 `mock-rule-engine`

真实模型没有返回结果，程序退回本地规则模式。查看响应中的 `ai_error` 和服务端终端日志。

## 8. 安全注意事项

- API Key 不要发到聊天里；
- 如果 Key 曾经写入公开文件或发给别人，应立即撤销并重新生成；
- `config.json` 已加入 `.gitignore`；
- 不要把 `config.example.json` 当作长期生产配置；
- 体检单、身体照片和食物照片应设置保存期限；
- AI 只做健康管理，不诊断、不改药、不替代医生。
