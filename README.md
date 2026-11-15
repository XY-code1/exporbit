# Exporbit — 出海罗盘

**AI-Powered Export Business Intelligence**

An AI-powered business intelligence platform for Chinese export businesses.

Exporbit helps export teams understand overseas inquiries, investigate customers, match business capabilities, discover relevant knowledge, and make evidence-driven business decisions.

> 从一封海外询盘开始，让 AI 帮助企业理解客户、匹配产品、研究市场，并将信息转化为可执行的商务行动。

---

## 1. What is Exporbit?

Exporbit 是一个面向中国中小型出口企业的 AI 跨境商务智能平台。

首期聚焦智能硬件和消费电子出口。

它不是传统 CRM，也不只是 AI 邮件生成工具。

Exporbit 以海外客户询盘为业务入口，结合企业产品资料、客户公开信息、海外市场信息和知乎社区知识，帮助外贸业务员完成从询盘理解到商务沟通的完整工作流程。

### Core Value

帮助外贸业务员回答五个关键问题：

1. 客户究竟需要什么？
2. 客户是否真实、是否具有采购意图？
3. 企业现有产品能否满足客户需求？
4. 当前业务有哪些风险、信息缺口和机会？
5. 下一步应该采取什么商务行动？

最终目标：

**将分散的信息转化为有依据、可追溯、可执行的业务决策。**

---

## 2. Target Users

### Primary Users

中国中小型智能硬件和消费电子出口企业的一线外贸业务员。

典型用户：

- 负责处理海外客户询盘。
- 需要同时维护多个潜在客户。
- 需要理解不同国家的市场和采购习惯。
- 需要匹配企业产品与客户需求。
- 需要准备英文商务回复。
- 希望减少重复调查和信息整理工作。

### Secondary Users

- 外贸企业负责人
- 外贸团队主管
- 跨境业务开发人员

---

## 3. Core Business Workflow

Exporbit 采用询盘驱动的业务工作流。

```text
Overseas Inquiry
       |
       v
Inquiry Understanding
       |
       v
Customer Intelligence
       |
       v
Product Matching
       |
       v
Knowledge Discovery
       |
       v
Evidence Analysis
       |
       v
Business Insights
       |
       v
Recommended Actions
       |
       v
Business Communication
       |
       v
Human Review & Save
```

### 3.1 Inquiry Understanding

支持：

- 粘贴询盘文本
- PDF 文件导入
- 图片导入
- EML 邮件文件导入
- 后续邮箱集成

AI 提取：

- 客户信息
- 产品需求
- 产品规格
- 采购数量
- 目标国家
- OEM/ODM 需求
- 交付要求
- 待确认事项

### 3.2 Customer Intelligence

帮助用户理解：

- 客户企业背景
- 采购意图
- 业务匹配度
- 潜在风险信号

所有调查结果必须标记来源和可信度。

不能将推测包装成已确认事实。

### 3.3 Business Context Matching

将客户询盘与企业产品资料建立业务关联。

匹配维度：

- 产品类型
- 技术规格
- MOQ
- OEM/ODM 能力
- 交付能力
- 认证要求

匹配状态：

- MATCH
- MISMATCH
- UNKNOWN

支持多个候选产品和人工修正。

### 3.4 Knowledge Intelligence

这是 Exporbit 的重要差异化能力。

结合：

- 知乎社区知识
- 海外公开信息
- 企业内部产品资料
- 当前客户询盘

系统根据当前业务问题推荐研究主题。

用户可以手动补充搜索。

知乎不应只是一个独立搜索页面。

社区经验需要与具体询盘、业务问题、证据和建议建立关联。

知乎是可插拔知识来源，不是核心业务运行的唯一依赖。

### 3.5 Evidence-to-Action

Exporbit 的核心业务机制：

```text
Business Question
       |
       v
Knowledge Discovery
       |
       v
Evidence Collection
       |
       v
Business Insight
       |
       v
Recommended Action
```

每项重要业务建议应尽可能关联：

- 原始业务问题
- 证据来源
- 来源时间
- 信息可信度
- AI 分析结论
- 待人工确认事项

不同来源必须明确区分：

- Zhihu Community
- Overseas Public Information
- Official Sources
- Enterprise Internal Data
- Customer Inquiry

### 3.6 Communication Studio

帮助外贸业务员生成商务回复。

支持：

- 中文
- 英文
- 正式商务语气
- 友好专业语气
- 简洁直接语气
- 人工编辑
- 保存
- 历史版本管理

MVP 不自动发送邮件。

---

## 4. Core Product Principles

### Progressive Intelligence

渐进式信息呈现。

Level 1 — Business Snapshot

首先展示当前询盘最重要的业务结论。

Level 2 — Business Intelligence

按需展开客户、产品和市场分析。

Level 3 — Research & Evidence

深入查看原始资料、来源、证据和分析依据。

不要默认向用户展示大量未经整理的信息。

### Evidence-Driven Decisions

重要结论必须尽可能有依据。

信息状态：

- CONFIRMED
- INFERRED
- NEEDS_CONFIRMATION
- INSUFFICIENT_DATA
- UNAVAILABLE

不能将 AI 推断冒充事实。

### Human-in-the-loop

AI 负责理解、研究、分析和建议。

用户负责关键业务确认。

用户的人工修改必须受到保护。

AI 不得擅自承诺价格、交期、认证和企业未确认的产品能力。

### Provider Independence

模型和知识来源必须具备可替换性。

未来允许扩展不同 LLM、知乎、海外搜索和其他企业知识来源。

---

## 5. Hackathon Edition vs Long-term Product

### Hackathon Edition

比赛版重点：

- 询盘处理
- 客户理解
- 企业产品匹配
- 知乎知识研究
- 海外信息辅助
- 证据关联
- 业务建议
- 商务回复

比赛重点展示：

一封海外询盘如何通过 AI、知乎知识和企业资料，转化为一套有证据支撑的商务行动方案。

### Long-term Product

长期发展方向：

- 更多海外市场和行业
- 更多知识来源
- 企业产品档案
- 客户历史记录
- 邮箱集成
- 多用户协作
- 团队业务管理
- 企业级权限与审计
- 双向跨境贸易支持

长期功能不应成为 MVP 的默认开发范围。

---

## 6. MVP Scope

### P0 — Must Have

1. Inquiry Import
2. Inquiry Parsing
3. Business Snapshot
4. Customer Intelligence
5. Product Matching
6. Knowledge Intelligence
7. Evidence Management
8. Evidence-to-Action
9. Business Actions
10. Communication Studio
11. Human Review
12. Data Persistence

### P1 — Later

- 自动观点冲突识别
- 邮箱自动同步
- 多用户协作
- 高级客户分析
- 历史业务趋势
- 更多市场情报来源
- 双向贸易业务

### Explicitly Out of Scope for MVP

- 自动向客户发送商务邮件
- 完整 ERP
- 完整 CRM 替代系统
- 微服务架构
- 不必要的复杂 Agent 集群
- 未经验证的外部 API 集成

---

## 7. Product Architecture Principles

技术实现应遵循：

1. Modular Monolith First
2. Clear Business Domain Boundaries
3. Provider Abstraction
4. Evidence Traceability
5. Explicit Data Status
6. Human-in-the-loop
7. Failure Isolation
8. Incremental Development

不要为了使用热门框架而增加系统复杂度。

具体技术栈必须经过独立评估和 POC 验证。

不要在技术选型尚未确认时，将候选技术描述为已经采用。

---

## 8. Project Status

当前阶段：

**Product Design Completed → Interactive Prototype Validation → Technical Selection & POC**

已完成：

- 产品定位与产品边界
- PRD V1.1
- Inquiry Workspace 产品设计
- 用户流程设计
- 产品决策文档
- 桌面端低保真设计
- 高保真 UI 探索
- 第一版交互原型

正在推进：

- 交互原型端到端验收
- DEMO 数据与真实数据边界检查
- 技术选型
- 技术验证计划

尚未完成：

- 生产级后端
- 真实知乎搜索接入
- 真实海外搜索接入
- 完整数据持久化
- 生产环境部署

不要将原型中模拟的功能描述为已经实现的生产能力。

---

## 9. Repository Documentation

核心文档：

```text
docs/
├── PRODUCT_DECISIONS_V1.0.md
├── INQUIRY_WORKSPACE_SPEC.md
├── INQUIRY_WORKSPACE_USER_FLOW.md
├── INQUIRY_WORKSPACE_ACCEPTANCE.md
├── INQUIRY_WORKSPACE_WIREFRAME.md
├── INQUIRY_WORKSPACE_UI_STATES.md
├── TECH_STACK_DECISIONS.md
├── TECHNICAL_ARCHITECTURE.md
├── DATA_MODEL_DESIGN.md
├── PROVIDER_DESIGN.md
├── POC_VALIDATION_PLAN.md
└── DEVELOPMENT_ROADMAP.md
```

以上是目标文档体系。实际文件以仓库现状为准，不得虚构已经存在的文档。

在开发前，优先阅读已有产品决策和 PRD。

---

## 10. Development Guidelines

所有开发工作遵循：

- 先理解产品，再编写代码。
- 先检查现有实现，再决定是否重构。
- 不覆盖已有有效功能。
- 不虚构 API。
- 不伪装 DEMO 数据。
- 不将未经核实的内容描述为事实。
- 不引入没有明确业务价值的依赖。
- 每个阶段都需要可验证的交付结果。
- 保留用户人工修改。
- 对重要数据操作保留必要记录。

---

## 11. Vision

Exporbit aims to become an intelligent business decision platform for cross-border trade.

从一封询盘开始，连接客户、产品、知识、证据和商务行动。

**Understand the Customer. Match the Business. Act with Evidence.**
