# Exporbit 阶段 0 技术闸门收口报告

- 日期：2026-11-18
- 范围：`docs/DEVELOPMENT_ROADMAP.md` 阶段 0（架构评审与 POC）
- 结论：**PASS — 阶段 0 技术闸门关闭**
- 说明：本报告只记录已运行、可复核的结果；未运行的集成不因本文档视为可用。

## 1. 闸门结果

| 闸门 | 结论 | 关键运行证据 | 详细报告 |
|---|---|---|---|
| PostgreSQL 持久化 + 前后端纵向切片（POC-01） | PASS | 迁移可重复执行；创建/列表/详情走真实 PostgreSQL；刷新与重启后数据保留；stale `If-Match` 返回 409；Vite 生产构建通过 | [POC_01_VALIDATION_REPORT.md](../outputs/POC_01_VALIDATION_REPORT.md) |
| DeepSeek 结构化抽取（POC-02） | PASS | 24/24 合成询盘通过 schema（100%）；关键字段 macro F1 0.9062（目标 ≥0.85）；`llm_runs` 已持久化 | [POC_02_VALIDATION_REPORT.md](../outputs/POC_02_VALIDATION_REPORT.md) |
| 结构化抽取接入业务路径（POC-02 V2） | PASS | 30/30 合成询盘返回符合 V2 schema 的结果；不可变 `inquiry_extractions` 记录；快照页接入真实 API；人工字段不被覆盖 | [POC_02_V2_VALIDATION_REPORT.md](../outputs/POC_02_V2_VALIDATION_REPORT.md) |
| PDF/图片/EML 解析（POC-03） | PASS | 有效样本 8/8；页级溯源 11/11；受控失败错误码 5/5；附件策略 2/2；不执行附件内容 | [POC_03_VALIDATION_REPORT.md](../outputs/POC_03_VALIDATION_REPORT.md) |
| Evidence Provenance（产物编号 POC-05） | PASS | 洞察链路 4/4 可解析；sha256 校验 4/4；外链失效仍保留 145 字快照；DEMO 标注 1/1；Provider 离线后不新增证据且历史链路完好 | [POC_05_VALIDATION_REPORT.md](../outputs/POC_05_VALIDATION_REPORT.md) |
| 知乎知识获取 | NO-GO（LIVE） | 未确认存在合规、稳定、可维护的授权渠道；保留 DEMO + 手工导入 | [ZHIHU_PROVIDER_DECISION.md](ZHIHU_PROVIDER_DECISION.md) |

结论口径：

- POC-01/02/03 与 Provenance 均达到各自成功标准，未见阻断阶段 1 的缺陷。
- 知乎 LIVE 为显式 no-go，不阻塞核心流程；这是计划允许的结果，不代表 DEMO 数据可用于生产宣称。

## 2. 迁移链与数据库验证

本次收口在本机 PostgreSQL 上实际执行，dev 与 test 两个库均从空库升级到同一 head：

| 数据库 | 升级路径 | 最终版本 | 表 |
|---|---|---|---|
| `exporbit`（dev） | `0001 → 0002 → 0003 → 0004` | `20261117_0004` | customers, inquiries, llm_runs, source_providers, evidence, insights, insight_evidence, inquiry_extractions |
| `exporbit_test`（test） | `0001 → 0002 → 0003 → 0004` | `20261117_0004` | 同上 |

- 迁移文件：`20261115_0001_create_inquiry_tables.py` → `20261116_0002_create_llm_runs.py` → `20261116_0003_create_evidence_tables.py` → `20261117_0004_create_inquiry_extractions.py`。
- 两侧升级日志均为逐级 `Running upgrade`，无跳级、无手工补表。
- 验证环境为 PostgreSQL 16.2。项目部署基线仍是 `docker-compose.yml` 中的 `postgres:16-alpine`。
- 本次 Docker Desktop 引擎因本机 WSL 更新/数据盘缺失未能启动，故验证使用同一版本的本地便携实例；该环境差异不影响迁移与 SQL 行为，但正式部署前仍需在 Compose 环境重跑一次迁移与测试。

## 3. 测试与产物

| 项目 | 结果 |
|---|---|
| 后端全量测试 | **77 passed**（含 inquiry API、抽取 V2、文档解析、evidence provenance、LLM run 持久化） |
| POC-05 验证脚本 | `verdict: PASS`（可重复运行，运行前替换同名合成询盘数据） |
| 迁移离线渲染 | 全链路 `--sql` 渲染成功（0001→0004） |
| 产物 | `outputs/POC_05_RESULTS.json`、`outputs/POC_05_VALIDATION_REPORT.md` |

## 4. 数据与安全边界

- 测试与验证只使用合成询盘、LIVE-like fixture、固定 DEMO 文本和手工导入示例；不含真实客户数据。
- DeepSeek key 只存在于被 gitignore 的 `backend/.env`，不在仓库、报告、日志或 API 响应中出现。
- DEMO 证据由数据库约束 `is_demo = (provider_mode = 'DEMO')` 强制标注；PLANNED Provider 禁用，采集前拒绝。
- 附件只登记与解析文本，不执行内容（POC-03）。

## 5. 阶段 0 退出条件核对

| 退出条件 | 状态 |
|---|---|
| POC 闸门通过 | ✅ POC-01/02/02-V2/03/Provenance |
| API/数据模型变更有记录 | ✅ 迁移 0001–0004、POC 报告与设计文档 |
| 无密钥或客户数据进入仓库 | ✅ 合成数据；key 仅本地 `.env` |
| 知乎 go/no-go 已输出 | ✅ NO-GO（LIVE），保留 DEMO + 手工导入 |

## 6. 已知限制与后续事项

- 尚未实现：discovery candidate 人工接受、证据编辑/删除、审计日志、前端 Evidence Drawer、research_run 持久化。
- 尚未验证：多用户并发、租户隔离、快照容量/清理、许可证与保留期限策略。
- 知乎 LIVE、海外搜索与官方来源均未接入；不得在 UI 或报告中表述为已实现集成。
- 下一步进入阶段 1（Inquiry Foundation）：列表/文本创建/文件元数据/解析运行/Snapshot 从原型固定数据迁到 API，并补齐人工编辑保护、revision/409 与基础审计。