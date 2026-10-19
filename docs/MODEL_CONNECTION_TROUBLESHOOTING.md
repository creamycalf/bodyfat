# 模型连不上排查说明

> 兼容性说明：模型目前已经接通。本文保留通用排查经验；当前配置和验证命令请以 `OPERATIONS.md` 为准。

本文档记录本项目中“模型连不上”这一类问题的排查结论、根因和验证方法，方便后续快速定位。

## 现象

启动项目后，界面或接口看起来正常，但对话返回的不是模型结果，而是本地规则结果，或者前端/后端提示模型调用失败。

## 根因

本项目里存在两个后端入口：

- `server.mjs`：本地 mock 服务，只返回规则结果，不会真正请求模型
- `server.py`：真正会读取 `config.json` 并调用外部模型接口的后端

如果把 `npm start` 或 `npm run dev` 指向了 `server.mjs`，就会出现“模型连不上”的错觉，因为实际上根本没有走真实模型调用链。

## 已确认的正确启动方式

当前应使用：

```bash
python server.py
```

如果必须通过 npm 启动，脚本也应指向 Python 后端，而不是 mock 服务。

## 快速检查项

### 1. 检查服务入口

确认启动命令是否实际执行了 `server.py`。

### 2. 检查配置文件

确认项目根目录存在 `config.json`，并且包含有效的 AI 配置：

- `ai.enabled: true`
- `ai.base_url` 正确
- `ai.api_key` 或 `ai.apiKey` 正确
- `ai.model` 正确
- 如需要视觉能力，检查 `ai.vision_model`

### 3. 检查健康接口

```bash
GET /api/health
GET /api/config-status
```

其中 `config-status` 可以帮助确认：

- 是否启用了 AI
- 是否读取到了 Key
- Key 来自配置文件、环境变量还是缺失

为减少内部配置暴露，该接口不再返回模型名、接口地址或协议；这些内容应直接在可信本机检查配置文件。

### 4. 检查对话接口

```bash
POST /api/chat
```

如果返回内容里出现 `mock-rule-engine`，说明当前跑的是 mock 路径，而不是真实模型调用。

## 推荐验证步骤

1. 启动后端：
   ```bash
   python server.py
   ```
2. 打开健康检查：
   ```bash
   http://127.0.0.1:8787/api/health
   ```
3. 检查配置状态：
   ```bash
   http://127.0.0.1:8787/api/config-status
   ```
4. 发送一条测试消息到 `/api/chat`
5. 确认返回结果不是本地 mock 回复，而是模型输出

## 结论

如果出现“模型连不上”，优先检查：

1. 启动入口是否指向了 `server.py`
2. `config.json` 是否存在并配置正确
3. 真实模型接口是否可访问
4. 返回值是否其实来自 mock 规则引擎

## 备注

`server.mjs` 更适合作为本地演示或前端静态预览，不适合作为真实模型连接入口。
