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
| POST | `/inquiries/{id}/files` | PDF/图片/EML 上传 |
| POST | `/inquiries/{id}/parse` | 启动/重试解析，返回 analysis run |
| GET | `/inquiries/{id}/snapshot` | Level 1 聚合读取模型 |
| GET | `/analysis-runs/{id}` | 轮询解析/研究/生成状态；MVP 不要求 WebSocket |

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
