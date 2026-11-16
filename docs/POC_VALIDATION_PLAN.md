# Exporbit POC 验证计划

估算为单名熟悉项目的工程师工作量，不含采购、账号审批和外部等待。

| POC | 假设 | 实施与测试数据 | 成功标准 | 主要风险 | 估算 |
|---|---|---|---|---|---|
| DeepSeek 结构化抽取 | 可稳定输出符合 schema 的询盘字段和状态 | 20–30 份脱敏/合成中英文询盘；固定 Pydantic schema；记录 token/延迟/失败 | ≥90% 响应通过 schema；关键字段抽取 F1 ≥0.85；人工字段不被重跑覆盖；错误可分类 | 格式漂移、幻觉、成本/限流、数据出境 | 3–5 人日 |
| PDF/图片/EML 解析 | 常见格式可保留原文定位并产生可供抽取的文本 | 数字 PDF、扫描 PDF、旋转图片、含附件 EML、损坏/加密样本各若干 | 支持格式成功率 ≥90%；页/正文定位可追溯；损坏文件受控失败；不执行附件内容 | OCR 质量、编码、恶意文件、许可证 | 4–6 人日 |
| PostgreSQL 持久化 | 核心聚合、版本、审计可在单事务中可靠保存 | Docker Postgres；迁移；创建询盘→匹配→证据→版本；并发更新测试 | 迁移可重复；重启数据保留；冲突返回 409；回滚无部分写；关键查询满足演示规模 | schema 过宽、JSONB 滥用、迁移纪律 | 3–4 人日 |
| Evidence provenance | Provider 失效后仍能解释洞察来源 | LIVE-like fixture、MANUAL、DEMO、外链失效样本；保存 snapshot/hash/lineage | 每个 insight 可追到 evidence 与 source；外链失效仍显示快照；DEMO 无漏标 | 版权/存储、快照缺失、时间语义 | 3–4 人日 |
| 知乎知识获取 | 存在合规、稳定、可维护的获取方式或可接受替代流程 | 调研官方/授权渠道和条款；验证手工链接/内容导入；不使用未授权接口 | 给出 go/no-go；若 go，有可重复成功率/限流/字段/合规记录；若 no，手工导入与 DEMO 降级成立 | 无公开 API、条款、反爬、内容版权 | 2–5 人日 + 外部等待 |
| Frontend ↔ FastAPI | 现有流程可逐屏替换 mock 而不重写 UI | 先接 inquiry list/detail、snapshot、match PATCH；契约 fixture 和错误态 | 列表/切换/修改刷新后保留；loading/error/409 可见；不再依赖共享 localStorage | DTO 漂移、CORS、状态同步 | 3–5 人日 |

## 执行顺序

1. PostgreSQL persistence + provenance schema（建立真实数据边界）。
2. Frontend/FastAPI vertical slice（证明端到端契约）。
3. DeepSeek structured extraction。
4. 文档解析。
5. Evidence lineage。
6. 知乎可行性并行调研，但不阻塞核心流程。

## 统一测试原则

- 只使用合成、DEMO 或已脱敏授权数据；禁止真实客户询盘进入测试仓库。
- 固定输入集、期望 schema、原始响应 hash、运行配置和结果报告。
- 区分产品缺陷、Provider 不可用、样本质量不足和配置错误。
- 每个 POC 产出 go/no-go、证据、限制、成本和后续 ADR；未达到标准不得标为生产能力。

## 架构闸门

在开始完整 MVP 后端前，至少需要 PostgreSQL、前后端 vertical slice、DeepSeek 结构化输出和 provenance 四项通过。知乎可为 no-go，但必须证明关闭后核心流程完整可用。
