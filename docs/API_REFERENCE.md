# API 参考

基础地址：`http://127.0.0.1:8787`。除页面资源外，接口使用 JSON。当前没有鉴权，只适用于可信本机。

## 1. 状态与初始化

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务健康状态 |
| GET | `/api/config-status` | 仅返回启用、Key 是否存在及存储方式，不返回 Key、模型名、接口地址或协议 |
| GET | `/api/bootstrap` | 前端初始化所需资料、记录、对话摘要、媒体和看板 |
| GET | `/api/dashboard` | 体重趋势、记录统计和今日建议 |
| GET | `/api/export` | 导出 JSON 数据和媒体元数据，不包含原图 |
| GET | `/api/backup` | 下载含 JSON、媒体原图和 SHA-256 清单的 ZIP 完整备份 |
| POST | `/api/restore` | 上传 ZIP 完整替换当前数据；需 `Content-Type: application/zip` 和 `X-Zhiheng-Confirm: restore` |
| POST | `/api/reset` | 清空档案、资料、对话和媒体，要求 `{"confirm": true}` |

## 2. 对话

### POST `/api/chat`

```json
{
  "text": "我最近的体重是多少",
  "intake_mode": "chat",
  "intake_saved": false,
  "messages": [
    {"role": "user", "content": "上一轮问题"},
    {"role": "assistant", "content": "上一轮回复"}
  ]
}
```

后端最多接受最近 6 条历史消息，每条截断到 2000 字符；当前文本上限 8000 字符。

典型响应：

```json
{
  "reply": "...",
  "extracted_data": [],
  "risk": "none",
  "model": "claude-opus-4-8",
  "ai_status": "connected",
  "ai_error": null,
  "request_id": "...",
  "attempts": 1,
  "elapsed_ms": 1234,
  "memory_matches": [
    {
      "id": "rec-...",
      "type": "weight",
      "reason": "与问题中的记录类型一致；近14天记录"
    }
  ]
}
```

如果触发本地紧急规则，`ai_status` 为 `safety_rule`，不会调用远程模型。

当基本资料不足且需要制定方案时，响应可额外包含：

```json
{
  "reply": "为了更了解你的情况……",
  "intake_form": true,
  "intake_defaults": {"age": 39, "goals": "稳定减脂"},
  "ai_status": "intake_rule"
}
```

- `intake_mode: "chat"`：用户选择跳过表单，后续通过文字或语音说明；
- `intake_mode: "submitted"`：用户刚提交表单；
- `intake_saved: true`：该轮摘要来自已经确认保存的表单，后端不会重复生成候选记录。

模型身份、密钥、接口地址、内部配置或系统提示词询问由本地规则处理，返回“我是你的知衡健康师。”，`ai_status` 为 `brand_rule`，不调用上游。

## 3. 健康记录

记录基本结构：

```json
{
  "id": "rec-...",
  "type": "weight",
  "value": {"kg": 76.8},
  "created_at": "2026-09-02T16:00:00",
  "source": "conversation",
  "confirmed": true,
  "memory_enabled": true
}
```

| 方法 | 路径 | 请求要点 |
|---|---|---|
| GET | `/api/records` | 返回全部记录 |
| POST | `/api/records` | `record` 或直接传记录对象 |
| POST | `/api/records/confirm` | `records` 数组，1–20 条，原子批量写入 |
| POST | `/api/records/undo` | `undo_token`，120 秒内一次性撤销 |
| POST | `/api/records/update` | `id` 和 `record` |
| POST | `/api/records/delete` | `id` 和 `confirm: true` |
| POST | `/api/records/memory` | `id` 和布尔值 `enabled` |

允许的记录类型：`sleep`、`weight`、`waist`、`meal`、`beverage`、`energy`、`hunger`、`symptom`、`medication`、`lab_or_measurement`、`elimination_symptom`、`activity`、`safety`。

## 4. 记忆检索

### POST `/api/memory/search`

```json
{"query": "最近的睡眠", "limit": 6}
```

只搜索已确认且允许参与记忆的记录。`limit` 限制在 1–12。响应中的每项包含裁剪后的记录和命中原因。

## 5. 个人资料

### POST `/api/intake`

用于对话中的可选资料表单（以下为虚构示例）：

```json
{
  "profile": {
    "age": 38,
    "height_cm": 175,
    "sex": "男",
    "goals": "稳定减脂",
    "conditions": ["没有确诊疾病"]
  },
  "weight_kg": 85,
  "confirm": true
}
```

所有字段均可省略，但至少需要填写一项，并且必须显式传入 `confirm: true`。资料字段合并到 `profile.json`，体重单独写入 `records.json`。空白字段不会清空已有资料。

详见[可选资料采集流程](./OPTIONAL_INTAKE_FLOW.md)。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/profile` | 获取资料 |
| POST | `/api/profile` | 合并更新经过校验的字段 |

允许字段：`nickname`、`age`、`sex`、`height_cm`、`goals`、`preferences`、`conditions`、`surgeries`、`allergies`、`medications`。

- 年龄：1–120；
- 身高：50–250 cm；
- 称呼和性别：最多 50 字符；
- 目标和偏好：字符串最多 500 字符，或最多 20 项数组；
- 疾病、手术、过敏、用药：最多 20 项，每项最多 100 字符。

删除单个资料字段时传入 `clear_fields` 和显式确认，例如 `{"profile":{},"clear_fields":["allergies"],"confirm":true}`。只允许清除上述白名单字段。

## 6. 对话历史

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/conversations` | 返回完整数据及最近 100 段摘要；`q` 参数全文搜索，`id` 参数读取单段完整对话 |
| POST | `/api/conversations` | 不传 `id` 时创建对话；传已有 `id` 时追加消息，每次最多 20 条、每段最多保留 400 条 |
| POST | `/api/conversations/delete` | `id` 和 `confirm: true` |

删除对话不会删除已确认的健康记录。

## 7. 图片与媒体

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/media` | 返回媒体元数据 |
| POST | `/api/media` | 已停用，返回 410 `use_analyze_image`；通过 `/api/analyze-image` 上传真实图片 |
| POST | `/api/analyze-image` | 保存并分析 Base64 图片 |
| POST | `/api/media/review` | 显式确认结构化候选，并原子写入记录与媒体核对状态 |
| POST | `/api/media/confirm` | 使用 `id` 确认长期保留 |
| POST | `/api/media/delete` | 使用 `id` 和 `confirm: true` 永久删除 |
| POST | `/api/media/cleanup` | 清理过期且未确认的原图 |

图片请求：

```json
{
  "data": "data:image/png;base64,...",
  "mime": "image/png",
  "category": "food"
}
```

支持 JPEG、PNG、WebP、GIF；默认上限 8 MB。图片分析后元数据初始为 `confirmed: false`，响应中的 `review` 包含 `summary`、`question` 和 `record_candidates`，候选不会自动进入健康记录。

确认核对结果：

```json
{
  "id": "media-...",
  "records": [
    {"type": "weight", "value": {"kg": 80.2}}
  ],
  "confirm": true
}
```

`records` 最多 20 条。成功后记录带有 `source: "image"` 和对应 `media_id`；记录与媒体状态在同一事务中提交。相同媒体再次确认返回 409。

## 8. 常见 HTTP 状态

| 状态 | 含义 |
|---:|---|
| 200/201 | 成功 |
| 400 | 请求缺字段、确认缺失或数据校验失败 |
| 404 | 资源或接口不存在 |
| 410 | 撤销令牌已过期 |
| 413 | 文本或图片过大 |
| 415 | 不支持的图片格式、内容不是有效图片或声明 MIME 与真实文件头不一致 |
| 429 | 本机请求超过每分钟限制 |

错误响应统一包含 `error` 字段，但当前尚未形成正式版本化错误协议。

## 9. 新版计划操作

`GET /api/work/state` 返回的计划对象在修改既有建议中或暂停计划后会包含可选 `changes` 数组。每项包含 `kind`、`label`，以及变更前后的 `before` / `after` 值（新增或删除事项只提供存在的一侧）；无结构变化时数组为空，不会凭空生成差异。

示例：

```json
{
  "version": 2,
  "status": "suggested",
  "changes": [
    {"kind": "item", "label": "第1项·时间/频率", "before": "每天", "after": "每周三次"}
  ]
}
```

`POST /api/work/action` 的单项延期请求：

```json
{
  "action": "feedback",
  "task_id": "plan-id:1:item-id:2026-09-08",
  "status": "deferred",
  "deferred_to": "2026-09-09"
}
```

目标日期必须比原任务日期晚 1–30 天。原任务保留并显示“已延期”，目标日期生成待反馈事项；目标日期原本已有相同事项时合并显示。
