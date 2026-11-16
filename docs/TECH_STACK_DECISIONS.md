# Exporbit 技术栈决策

状态：Architecture Review Baseline  
范围：MVP；不表示所有候选技术已经实现。

## 决策分类

| 层 | 选择 | 状态 | 说明 |
|---|---|---|---|
| Frontend | React + TypeScript + Vite | Selected | 现有原型为 React/Vite/JSX；产品化时增量迁移 TypeScript，不重写页面 |
| UI | Tailwind CSS + shadcn/ui | Selected baseline | 当前原型仍使用手写 CSS；引入前先建立 token 与组件迁移顺序 |
| Server state | TanStack Query | To Validate | 仅在真实 API 接入后验证；本地 UI 状态继续使用 React state |
| Frontend tests | Vitest + Testing Library | To Validate | 当前仅有 Sites worker tests |
| Backend | Python 3.12+, FastAPI, Pydantic | Selected | API 与结构化输入输出边界 |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic | Selected | 单一关系数据库与迁移机制 |
| File storage | Local file storage | Selected for MVP | 只保存受控文件；元数据与哈希进入数据库 |
| LLM | DeepSeek through adapter | Selected / POC required | 业务服务不得调用专属 SDK；结构化输出须验证 |
| Orchestration | Python application services | Selected | LangGraph 仅在多步恢复/分支状态经 POC 证明后考虑 |
| Knowledge | Replaceable providers | Selected design | 知乎无已确认公开 API；不得假设实时接入 |
| Deployment | Docker + Docker Compose | Selected | 单体应用、PostgreSQL 和本地开发环境 |
| Nginx / S3 | Candidate | To Validate | 生产部署需求明确后验证 |
| pgvector / Langfuse | Deferred | Deferred | MVP 无必要证据 |
| Redis / Celery / Kubernetes | Not selected | Out of scope | 当前吞吐和运维需求不足以证明必要性 |

## 已实现与未实现

- **已实现：** React/Vite 交互原型、localStorage 演示持久化、静态 DEMO 知识数据、Sites 构建和 4 个 worker tests。
- **未实现：** TypeScript 迁移、Tailwind/shadcn、FastAPI、PostgreSQL、DeepSeek、真实文件解析、真实知识 Provider、认证与生产部署。
- **规则：** 文档中的 Selected 表示批准的开发基线，不等于仓库已有生产实现。

## 决策依据

模块化单体足以覆盖 Inquiry、Product、Customer、Knowledge、Evidence、Action 和 Communication 的首期事务边界，部署与调试成本最低。Provider Adapter 隔离模型与信息源变化。PostgreSQL 负责主数据、关联关系、版本和审计；源文件使用文件存储，不把二进制塞入数据库。

## 触发复审的条件

- 队列：出现可量化的长任务积压或请求超时，才评估后台任务机制。
- RAG/向量库：内部文档规模和检索基准证明关键词/结构化检索不足。
- LangGraph：多步 AI 流程需要可恢复分支，普通服务编排无法清晰维护。
- 对象存储：多实例部署、容量、备份或合规要求超出本地文件系统。
