# Exporbit POC-01 Validation Report

日期：2026-11-15  
结论：PASS

## 范围

React → FastAPI → Application Service → SQLAlchemy → PostgreSQL 的 Inquiry 创建、列表、详情与乐观并发纵向切片。未实现 AI、知识 Provider、产品匹配算法、客户调查或文件解析。

## 实际验证

| 项目 | 结果 | 证据 |
|---|---|---|
| Docker Engine | PASS | Docker 27.0.3 |
| PostgreSQL | PASS | postgres:16-alpine；health=healthy |
| Alembic | PASS | production/test 均升级至 `20261115_0001` |
| Health Check | PASS | `/health` → database connected |
| 创建 Inquiry | PASS | `POST /api/v1/inquiries` → 201 |
| 列表/详情 | PASS | GET 返回 PostgreSQL 中的真实记录 |
| 输入校验 | PASS | 非法输入 → 422 structured error |
| 乐观并发 | PASS | stale `If-Match` → 409；有效 revision +1 |
| Pytest | PASS | 5 passed |
| 后端重启持久化 | PASS | 重启 Uvicorn 后记录仍存在 |
| 数据库重启持久化 | PASS | 重启 PostgreSQL 容器后记录仍存在 |
| 浏览器刷新 | PASS | 刷新后真实询盘仍显示，记录数保持 |
| 前后端联调 | PASS | 浏览器创建第二条询盘，列表从 1 更新为 2 |
| 前端生产构建 | PASS | Vite production build |
| Sites Worker | PASS | 4 passed |

## API 示例

```http
POST /api/v1/inquiries
Content-Type: application/json

{
  "subject": "POC-01 persistence check",
  "raw_text": "We need 500 smart devices for the German market.",
  "source_type": "TEXT",
  "customer_name": "POC Demo GmbH"
}
```

```json
{
  "id": "6694d214-fc0f-4c0c-bf83-981cc568ba3e",
  "customer_name": "POC Demo GmbH",
  "workflow_status": "NEW",
  "revision": 1,
  "extracted_fields": {}
}
```

## 已知边界

- POC-01 文件导入只保留 PDF/图片/EML UI 入口，明确显示“尚未上传”；真实文件持久化与解析不在本 POC。
- Snapshot 仅展示真实原文和待补充字段；没有伪装 AI 抽取。
- 产品匹配、知识研究、Evidence 与 Communication 仍是 DEMO，并在真实 Snapshot 中标出边界。
- 本机端口 8000 被系统 integration 进程占用，因此开发 API 使用 8010；API path 保持 `/api/v1` 不变。
- 测试产生一条 Starlette/AnyIO deprecation warning，不影响功能；升级依赖前需验证兼容性。

## 架构偏差

无业务架构偏差。运行端口从常见的 8000 调整为 8010，属于本机环境配置差异。TypeScript、Tailwind 与 shadcn 的迁移未在 POC-01 执行，符合“不重写原型”的限制。

