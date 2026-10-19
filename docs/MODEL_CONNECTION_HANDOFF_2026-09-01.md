# 模型连接问题交接记录（2026-09-01）

> 历史文档：本文记录 2026-09-01 模型尚未接通时的排查过程。当前模型已经接通，请以 `HANDOFF_2026-09-02.md`、`OPERATIONS.md` 和根目录 `README.md` 为准。

## 结论

本地服务、API Key 和模型列表均正常；当前真正的问题是：中转站的对话 POST 请求没有返回数据。

这不是前端 404，也不是 `api_key_env` 字段导致的 Key 丢失。

## 已确认事项

### 本地服务

- 真实后端是 `server.py`，不是 `server.mjs`。
- `GET /api/health` 返回 200。
- `GET /api/config-status` 返回 200。
- `POST /api/chat` 在本地返回 200；如果模型请求失败，会回退到 `mock-rule-engine`。
- 前端聊天请求使用 `POST /api/chat`。直接在浏览器地址栏打开 `/api/chat` 发出的是 GET，返回 404 属于预期行为。

### 配置

当前配置通过 `config.json` 缺失时回退读取 `config.example.json`，其中包括：

```text
base_url: https://server.max-tabs.com/v1
model: gpt-5.5
vision_model: gpt-5.5
```

`server.py` 会兼容 `api_key_env` 中直接填写 `sk-...` 的旧写法，因此当前 Key 能被读取；`/api/config-status` 已确认 `key_present: true`。

但字段名不准确。正式配置应使用环境变量名：

```json
{
  "ai": {
    "enabled": true,
    "base_url": "https://server.max-tabs.com/v1",
    "api_key_env": "ZHIHENG_AI_API_KEY",
    "model": "gpt-5.5",
    "vision_model": "gpt-5.5",
    "protocol": "chat_completions",
    "timeout_seconds": 45
  }
}
```

不要把真实 Key 提交到仓库或继续放在 `config.example.json` 中；已经暴露过的 Key 应轮换。

## 网络环境差异

在 Codex 沙箱内，Python 访问外部 HTTPS 会失败：

```text
WinError 10013
```

在宿主机网络环境中，同一个中转站地址可以访问。`/v1/models` 携带 Key 返回 200，并且返回的模型列表包含 `gpt-5.5`。因此中转站地址和 Key 至少在基础鉴权层面是可用的。

## 当前阻断点

在宿主机网络环境中直接测试：

```text
POST /v1/chat/completions  -> 20 秒无响应
POST /v1/responses         -> 20 秒无响应
```

Python `urllib` 和系统 `curl` 的 POST 测试结果一致，均为超时且没有响应体。服务端因此最终回退到本地规则引擎，界面看起来像“对话没反应”。

这说明 Hermes 与本项目使用的请求方式仍有差异，需对照 Hermes 的实际配置和请求：

1. 实际 Base URL（是否与 `https://server.max-tabs.com/v1` 完全一致）。
2. 实际模型 ID（是否为 `gpt-5.5`、`codetab/gpt-5.5` 或其他路由名）。
3. 使用 `Responses` 还是 `Chat Completions`。
4. 是否需要额外请求头、特殊参数或流式参数 `stream: true`。

## 正确启动方式

不要从 Codex 内置沙箱终端启动真实模型后端。请在 Windows PowerShell、Windows Terminal 或 VS Code 外部终端执行：

```powershell
cd E:\workspace\codexworkspace\bodyfat
powershell -ExecutionPolicy Bypass -File .\start-server.ps1
```

然后打开：

```text
http://127.0.0.1:8787/
```

## 快速验证

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
Invoke-RestMethod http://127.0.0.1:8787/api/config-status

$body = @{ text = '请只回复：连接测试成功' } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/chat `
  -ContentType 'application/json' `
  -Body $body
```

如果响应中的 `model` 是 `mock-rule-engine`，同时存在 `ai_error`，表示中转站对话请求仍未返回；此时应优先拿 Hermes 的实际请求参数做逐项对照。
