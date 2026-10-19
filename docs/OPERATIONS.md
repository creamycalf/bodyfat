# 运行与故障处理

## 1. 启动

```powershell
cd F:\aiworkspace\codexworkspace\bodyfat
powershell -ExecutionPolicy Bypass -File .\start-server.ps1
```

脚本会按顺序寻找：项目虚拟环境、Hermes 自带 Python、Codex bundled Python、PATH 中非 WindowsApps 的 Python。如果 8787 已监听，脚本不会重复启动服务。

如需在前台进程异常退出后有限次数自动拉起，可运行 `start-supervised.ps1`。默认最多重启 10 次、间隔 2 秒；可用 `-MaxRestarts` 和 `-RestartDelaySeconds` 调整。该脚本不会安装系统服务或开机任务，手动停止仍由当前终端负责。

如果确认需要登录 Windows 后自动运行，可显式执行 `manage-startup-task.ps1 -Action Install`。它只为当前 Windows 用户创建名为 `Zhiheng Local Health Server` 的登录任务，并立即启动；用 `-Action Status` 查看状态，用 `-Action Remove` 删除。默认不带参数只查询，不会安装。安装属于系统持久化配置，应由用户明确决定后执行。2026-09-08 已按用户授权安装并启动；任务以 Limited 权限和 Interactive 登录触发运行，`0x41301` 表示任务当前正在运行。移除时脚本会停止任务，并仅在健康接口和进程命令均确认为知衡后清理可能遗留的 8787 监听进程；验证失败时拒绝终止进程。

## 2. 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
Invoke-RestMethod http://127.0.0.1:8787/api/config-status
```

预期 `health.ok`、`config-status.enabled`、`config-status.key_present` 均为 `true`。配置状态接口不会返回 Key 内容。

`health.startup` 显示数据目录可写、JSON 结构、配置边界及 AI 可用性自检。服务启动时若发现数据 JSON 损坏或版本高于当前程序支持版本，会拒绝启动。HTTP 与模型错误日志为单行 JSON，不记录请求正文、查询词、API Key 或完整上游响应。

## 3. 模型连通验证

```powershell
$body = @{ text = '请只回复：模型连接正常'; messages = @() } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/chat `
  -ContentType 'application/json' `
  -Body $body
```

成功时 `ai_status` 为 `connected`。出现 `fallback` 时查看 `ai_error`：

| 错误码 | 含义 | 优先检查 |
|---|---|---|
| `AI_DISABLED` | AI 被关闭 | `ai.enabled` |
| `AI_KEY_MISSING` | 没读到 Key | 环境变量名和启动终端 |
| `AI_AUTH_FAILED` | 401/403 | Key、模型权限、IP 限制 |
| `AI_RATE_LIMITED` | 429 | 额度、频率、并发 |
| `AI_UPSTREAM_UNAVAILABLE` | 5xx | 服务商状态 |
| `AI_TIMEOUT` | 请求超时 | 网络、模型耗时、超时配置 |
| `AI_CONNECTION_FAILED` | 连接失败 | DNS、代理、防火墙 |
| `AI_INVALID_RESPONSE` | 返回格式异常 | 模型兼容性、中转返回体 |

## 4. 常见问题

### 页面能打开但始终是本地规则

确认运行的是 `server.py`。`npm run dev:mock` 和 `server.mjs` 不会调用真实模型。

### 地址栏打开 `/api/chat` 返回 404

这是正常的，因为该接口只接受 POST。

### 修改配置后没有生效

配置在进程启动时读取，修改 `config.json` 或环境变量后需重启服务。

### Codex 内启动出现 Access denied 或 WinError 10013

这是运行环境权限或网络隔离问题。使用普通 Windows PowerShell/Terminal 启动，再从本机浏览器访问。

## 5. 数据备份与恢复

“我的”页面可以下载 ZIP 完整备份。备份包含资料、记录、对话、媒体元数据、原始图片和逐文件 SHA-256 清单。恢复入口会先验证版本、允许路径、JSON 结构、文件大小、媒体引用和哈希，全部通过后才替换 `.data/`；恢复会覆盖当前数据，因此仍建议先下载一份当前备份。

`storage.max_backup_mb` 控制备份恢复请求的最大未压缩与上传体积，默认 256 MB、允许范围 1–1024 MB；生成时包含清单及压缩包开销一并校验，且拒绝不存在的媒体引用。备份仍是明文 ZIP，应像健康数据本身一样妥善保管。

服务启动后、此后每小时检查一次自动备份：每天在项目 `.backups/` 下生成一份 `daily-YYYY-MM-DD.zip`，最多保留最近 14 份自动备份。程序未运行时不会备份；这些同盘副本不能应对硬盘损坏。恢复或清空应用数据不会删除 `.backups/`，需要彻底移除健康数据时须同时处理这些备份。恢复入口必须同时满足 ZIP 类型和 `X-Zhiheng-Confirm: restore`，服务会先完整校验上传包；正式替换前在临时目录构造并校验 SQLite/逻辑文档，校验不通过不会触碰当前数据。备份尚未加密。

结构化日志写入项目 `.logs/server.log`，每份最多约 2 MB，保留 5 份轮转文件。服务停止与崩溃分别记录 `server_stop`、`server_crash`；结构化模型结果无法接受时记录 `structured_output_rejected` 或 `structured_plan_rejected`，只含错误类别、耗时和长度等诊断字段，不记录健康正文。守护启动和退出写入 `.logs/supervisor.log`。自动备份失败会记录 `automatic_backup_failed`；当前没有系统通知或外部告警。

已直接配置 `ai.api_key` 的旧安装可运行 `migrate-key.ps1`，将 Key 存入当前 Windows 用户的 `ZHIHENG_AI_API_KEY` 环境变量，核验成功后再删除配置中的明文 Key。两个启动脚本均能从用户环境加载 Key，不依赖当前终端重开。环境变量不是加密密钥托管；同一用户进程仍可读取。若运行用户改变，需要重新配置 Key。

服务启动时会读取 `.data/metadata.json` 检查数据版本。旧版数据迁移前会自动在 `.data/backups/` 生成回滚 ZIP；相同版本重复启动不会重复迁移或重复生成回滚包。数据版本高于当前程序支持版本时，服务拒绝启动，避免旧程序破坏新数据。

## 6. 媒体清理

打开应用时会清理超过 `storage.delete_original_after_days` 的未确认原图。也可手动调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/media/cleanup `
  -ContentType 'application/json' -Body '{}'
```

已确认保留的原图不会被自动清理。

## 7. 停止服务

前台运行时按 `Ctrl+C`。后台运行时先通过 `Get-NetTCPConnection -LocalPort 8787 -State Listen` 查出精确 PID，再停止该 PID，不要盲目结束未知进程。
