# Exporbit MVP API 设计

基线：REST/JSON，前缀 `/api/v1`。本文是契约规划，不代表接口已实现。

## 1. 通用约定

- UUID 资源 ID；ISO-8601 UTC 时间；分页使用 `cursor` + `limit`。
- 写操作支持 `Idempotency-Key`；更新携带 `If-Match`/revision，冲突返回 409。
- 响应中的信息字段包含 `value`, `status`, `origin`, `evidence_ids`, `revision`。
- 错误：`{"error":{"code":"PROVIDER_TIMEOUT","message":"...","details":{},"request_id":"..."}}`。
- 文件上传使用 multipart；密钥和 Provider 配置不返回前端。

## 2. Inquiry 与 Snapshot

| Method | Path | 用途 |
|---|---|---|
| GET | `/inquiries` | 状态、搜索、时间筛选和分页列表 |
| POST | `/inquiries` | 文本创建；返回重复候选但不自动合并 |
| GET | `/inquiries/{id}` | 原始询盘与处理状态 |
| PATCH | `/inquiries/{id}` | 人工修改允许字段 |
| POST | `/inquiries/import` | multipart 批量上传 PDF/图片/EML；逐文件解析并创建询盘，返回成功/失败结果 |
| GET | `/inquiries/{id}/files` | 查询询盘关联文件、解析预览与失败原因 |
| POST | `/inquiries/{id}/extract` | 创建新的结构化提取记录；重试不覆盖历史 |
| GET | `/inquiries/{id}/extractions/latest` | 查询最新提取记录；尚未提取时返回 `null` |
| GET | `/inquiries/{id}/extractions` | 查询提取历史，包含成功和失败状态 |
| GET | `/inquiries/{id}/extractions/{extraction_id}` | 查询指定提取记录 |
| POST | `/inquiries/{id}/parse` | 启动/重试解析，返回 analysis run |
| GET | `/inquiries/{id}/snapshot` | Level 1 聚合读取模型 |
| GET | `/analysis-runs/{id}` | 轮询解析/研究/生成状态；MVP 不要求 WebSocket |

### 已实现：提取记录读取与恢复

- 上表中的 `/extract` 与三个 `/extractions` 端点已实现。读取只访问数据库，不创建 Provider、不调用模型。
- 最新响应与 POST 提取响应结构相同，包含 `extraction_id`、`inquiry_id`、`structured_data`、`extraction_status`、`provider`、`model`、`error_code`、`created_at`。失败记录保留 `FAILED` 和错误码，`structured_data` 为 `null`，不会偷偷回退到旧成功结果。
- 历史响应为 `{ "items": [...], "total": N }`；当前 P0 返回该询盘完整历史，不分页。最新和历史均按 `created_at DESC, id DESC` 排序；ID 仅作相同时间戳的稳定排序，不表示提交先后。
- 询盘存在但尚未提取：最新返回 HTTP 200 / `null`，历史返回空列表。询盘不存在返回 `INQUIRY_NOT_FOUND` / 404；记录不存在或属于另一询盘返回 `EXTRACTION_NOT_FOUND` / 404。
- 每次 POST（包括失败后重试、再次成功提取）均新增记录，不改旧记录，不修改询盘原文、人工字段或 revision。读取历史同样不会改变最新记录。
- 工作台切换询盘或重新挂载页面时从 API 恢复最新成功/失败状态与历史；本地只保存选中询盘 ID，不把结果缓存作为数据库事实。可只读查看历史并返回最新。请求状态按询盘隔离，迟到读取不能覆盖更新结果。
- 尚无生产鉴权，按询盘 ID 限定记录范围不是用户权限控制；提取记录读取端点本身没有新增数据库约束或迁移（文件导入另有文件元数据迁移）。

## 3. Customer、Product、Matching

| Method | Path | 用途 |
|---|---|---|
| GET/PATCH | `/customers/{id}` | 客户信息与人工修正 |
| GET | `/products` | 产品候选查询 |
| POST | `/products` | 手工创建产品档案（若纳入首个开发迭代） |
| GET | `/inquiries/{id}/product-matches` | 候选与维度结果 |
| POST | `/inquiries/{id}/product-matches` | 添加候选产品 |
| PATCH | `/inquiries/{id}/product-matches/{match_id}` | 修改维度、主推/备选与确认状态 |
| DELETE | `/inquiries/{id}/product-matches/{match_id}` | 移除关联，不删除产品 |

## 4. Knowledge、Evidence、Insight、Action

| Method | Path | 用途 |
|---|---|---|
| GET/POST | `/inquiries/{id}/questions` | 列表/新增业务问题 |
| PATCH/DELETE | `/inquiries/{id}/questions/{qid}` | 编辑/移除问题 |
| POST | `/inquiries/{id}/research-runs` | 选择问题和 Provider 发起研究 |
| GET | `/research-runs/{id}/results` | 返回来源模式、状态与候选证据 |
| GET/POST | `/inquiries/{id}/evidence` | 列表/保存 Provider 或手工证据 |
| GET | `/evidence/{id}` | 来源、快照、可信状态和关联 |
| POST/DELETE | `/evidence/{id}/question-links` | 关联/解除业务问题 |
| GET/POST | `/inquiries/{id}/insights` | 查询/基于指定证据生成洞察 |
| PATCH | `/insights/{id}` | 人工修改/确认；保留 provenance |
| GET/POST | `/inquiries/{id}/actions` | 查询/生成建议行动 |
| PATCH | `/actions/{id}` | 修改、确认、完成、撤销确认 |

### 已实现：Evidence 与 Insight 溯源 API

- `GET /providers`：返回已登记 Provider 的 `code`、`category`、`display_name`、`mode`、`enabled`、`last_health_status`；不返回任何凭据或配置。
- `GET /inquiries/{id}/evidence`：按 `captured_at` 倒序返回该询盘证据；每条包含快照文本、sha256、`snapshot_verified`、来源类别、Provider 模式、`is_demo`、可用性与可信状态。
- `POST /inquiries/{id}/evidence`：
  - `kind=MANUAL`：保存手工导入证据，服务端生成快照与哈希，记录 `captured_by`，固定 `provider_mode=MANUAL`、`is_demo=false`。
  - `kind=PROVIDER`：仅执行已注册且具备适配器的 Provider。当前只有 `zhihu_demo`（DEMO）。`fixture_live` 是 POC 合成 fixture，不通过 API 暴露；`zhihu_live` 为 PLANNED，二者与未知/无适配器 Provider 均返回 409（未知 code 返回 404）。
  - Provider 不可用不返回 5xx：响应为 `status=UNAVAILABLE`、稳定错误码（如 `PROVIDER_UNAVAILABLE`），不新增证据，历史证据与洞察不受影响。
  - 成功返回 201 与 `{status, provider_code, provider_mode, evidence}`。
- `GET /evidence/{id}`：来源、快照、哈希校验、可信状态，以及引用该证据的洞察（含 `support_type`）。
- `GET/POST /inquiries/{id}/insights`：洞察必须关联至少一条本询盘证据；跨询盘引用返回 `EVIDENCE_INQUIRY_MISMATCH`，重复引用返回 `DUPLICATE_EVIDENCE_LINK`。本端点创建的洞察固定 `origin=HUMAN`，不把人工输入标成 AI 生成。
- `GET /insights/{id}/provenance`：返回洞察及其全部证据链，逐条包含 `provider_mode`、`is_demo`、`captured_at`、`source_published_at`、`content_hash`、`snapshot_verified` 与快照文本。
- P0 列表暂不分页，返回该询盘完整集合；尚无生产鉴权，按询盘 ID 限定范围不等于用户权限控制。

## 5. Communication

| Method | Path | 用途 |
|---|---|---|
| GET/POST | `/inquiries/{id}/communications` | 查询/创建回复目标 |
| POST | `/communications/{id}/generate` | 按语言、语气、证据和已确认字段生成草稿 |
| GET | `/communications/{id}/versions` | 不可变历史版本 |
| POST | `/communications/{id}/versions` | 保存人工编辑的新版本 |
| POST | `/communications/{id}/versions/{vid}/restore` | 基于历史版本创建新版本 |

不提供发送邮件端点。

## 6. Provider 可见性

- `GET /providers` 只返回 code、类别、mode（LIVE/MANUAL/DEMO/PLANNED）、enabled 与 health，不返回凭据。
- 研究结果必须返回 `provider_mode` 和 `is_demo`。
- Provider 不可用时研究运行可为 `PARTIAL_SUCCESS`；Snapshot、产品匹配、人工证据和 Communication 编辑仍可运行。

## 7. 示例：人工修改匹配

```json
PATCH /api/v1/inquiries/{id}/product-matches/{match_id}
If-Match: 7

{
  "dimension": "certification",
  "status": "UNKNOWN",
  "note": "现有 CE 文件尚未核对型号覆盖",
  "confirmation": "HUMAN_EDITED"
}
```

服务返回新 revision 和审计事件 ID；随后 AI 重跑不得覆盖该值。
