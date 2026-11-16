# Exporbit MVP 开发路线图

## 原则

采用纵向切片，不按“先做完所有数据库/所有 API/所有 UI”分层交付。每个迭代都提供可运行路径、迁移、测试和明确的 DEMO/LIVE 标识。

## 阶段 0：架构评审与 POC（1–3 周）

- 完成本轮文档评审与待确认项。
- 建立 PostgreSQL、FastAPI 最小骨架和 inquiry vertical slice POC。
- 验证 DeepSeek structured output、文件解析和 evidence provenance。
- 输出知乎获取 go/no-go；no-go 时保留 DEMO + 手工导入。

**退出条件：** POC 闸门通过；API/数据模型变更有记录；无密钥或客户数据进入仓库。

## 阶段 1：Inquiry Foundation（1–2 周）

- 询盘列表、文本创建、文件元数据、解析运行、Snapshot 读取。
- 将当前原型的询盘切换和 Snapshot 从固定数据迁移到 API。
- 人工编辑保护、revision/409、基础审计。

**验收：** 创建→解析→修改→刷新后保留；失败可重试；原始输入可追溯。

## 阶段 2：Product & Customer Intelligence（1–2 周）

- 产品档案最小字段、候选关联、五维匹配与人工确认。
- 客户背景字段、来源状态和风险信号边界。
- 不引入精确风险分数。

**验收：** 多产品多询盘关系正确；UNKNOWN 不被自动当作 MATCH；人工值不被 AI 覆盖。

## 阶段 3：Knowledge & Evidence（2 周）

- Business Question、研究运行、Provider 模式、手工/企业/客户证据。
- 知乎依据 POC 结果接入 LIVE 或保留显式 DEMO；单源失败隔离。
- Evidence Drawer 展示快照、来源、时间、可信状态和关联。

**验收：** Provider 关闭后核心流程继续；历史证据仍可访问；所有 DEMO 有机器字段与 UI 标识。

## 阶段 4：Insight, Action & Communication（1–2 周）

- Evidence→Insight→Action lineage；信息不足时降级。
- 回复生成、人工编辑、不可变版本、恢复为新版本。
- 禁止自动发送和未经确认的商务承诺。

**验收：** 每项重要建议可追到证据；回复只使用允许字段；历史版本不可篡改。

## 阶段 5：Hardening & Demo Release（1 周）

- 端到端、可访问性、桌面响应、错误/空/加载状态。
- Docker Compose、迁移、备份恢复演练、日志脱敏、安全检查。
- 完成 DEMO 数据清单和能力声明。

## 首批工程任务建议

1. ADR/配置规范与后端骨架。
2. Inquiry + audit + model_run 迁移。
3. `POST/GET /inquiries` 与 Snapshot fixture。
4. 原型列表/Snapshot API vertical slice。
5. DeepSeek adapter POC（不进入业务主路径前先验证）。

## 非本路线范围

邮箱自动同步、自动发信、多用户复杂权限、微服务、Celery/Redis、Kubernetes、自动观点冲突、向量数据库和完整 CRM/ERP。

## 未决策与风险

- 生产认证与 tenant 模型。
- 数据驻留、隐私、原文与证据保留/删除策略。
- 上传限制、恶意文件扫描和 OCR 选型。
- DeepSeek 数据处理条款、模型/区域/预算和速率限制。
- 知乎内容的授权获取、引用和快照保留边界。
- MVP 部署环境、域名、TLS、备份与监控责任人。

## 是否可开始后端开发

**建议：可以开始受控 POC 和第一个纵向切片；暂不批准大规模后端实现。** 技术结构已经足够明确，但四个闸门（PostgreSQL、前后端切片、结构化抽取、证据 lineage）必须用运行证据验证。知乎实时集成不是启动核心开发的前置条件。
