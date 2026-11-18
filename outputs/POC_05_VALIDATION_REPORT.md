# Exporbit POC-05 验证报告：Evidence Provenance

- 验证时间（UTC）：2026-11-18T08:57:15.916960+00:00
- 环境：本地 dev PostgreSQL 16.2；迁移链 0001→0002→0003→0004（head `20261117_0004`）；每次运行替换同名合成询盘数据
- 数据：合成询盘（POC-05 synthetic provenance inquiry）、LIVE-like fixture、知乎 DEMO 固定文本、手工导入；不含真实客户或外部来源内容
- 结论：**PASS**

## 1. 成功标准

| 标准 | 目标 | 实测 | 通过 |
|---|---|---|---|
| 每个 insight 可追到 evidence 与 source | 100% | 4/4（100.0%） | ✅ |
| 快照 sha256 校验一致 | 100% | 4/4（100.0%） | ✅ |
| 外链失效仍显示快照 | 100% | UNAVAILABLE，快照 145 字 | ✅ |
| DEMO 无漏标 | 100% | 1/1，模式一致率 100.0% | ✅ |
| Provider 失效隔离 | 可控 UNAVAILABLE | UNAVAILABLE/PROVIDER_UNAVAILABLE，证据仍 4 条 | ✅ |

## 2. 场景与检查

| 步骤 | 预期 | 实际 | 判定 |
|---|---|---|---|
| 采集 LIVE / LIVE / DEMO / MANUAL 证据 | 4 条 CAPTURED | 3 + 1 manual | ✅ |
| 洞察证据链完整 | 4/4 条证据可解析 | 4/4 | ✅ |
| 快照哈希校验 | 100% | 100.0% | ✅ |
| 外链失效仍显示快照 | UNAVAILABLE + 快照可读 | UNAVAILABLE, 145 chars | ✅ |
| DEMO 强制标注 | DEMO 全部 is_demo=true | 1 条 DEMO，模式/标志一致 4/4 | ✅ |
| Provider 离线隔离 | UNAVAILABLE，不新增证据 | UNAVAILABLE/PROVIDER_UNAVAILABLE，证据仍 4 条 | ✅ |
| 离线后洞察仍可解释 | 快照链路完好 | links=4，verified=4 | ✅ |
| PLANNED Provider 不可执行 | disabled + PLANNED | enabled=False, mode=PLANNED | ✅ |
| 洞察必须有证据 | EVIDENCE_REQUIRED | EVIDENCE_REQUIRED | ✅ |

## 3. 洞察证据链

| 证据 | 支撑关系 | Provider | 模式 | DEMO | 可用性 | 获取时间 | 快照 | Hash 校验 |
|---|---|---|---|---|---|---|---|---|
| 海外公开资料：欧盟无线耳机进口合规要点（合成 fixture） | SUPPORTS | fixture_live | LIVE | 否 | UNAVAILABLE | 2026-11-18T16:57:15 | 145 字 | ✅ |
| 海外公开资料：德国包装回收标识（合成 fixture） | CONTEXT | fixture_live | LIVE | 否 | AVAILABLE | 2026-11-18T16:57:15 | 107 字 | ✅ |
| 知乎演示：蓝牙耳机出口德国的常见问题（DEMO） | CONTEXT | zhihu_demo | DEMO | 是 | AVAILABLE | 2026-11-18T16:57:15 | 96 字 | ✅ |
| 客户邮件摘要（手工导入，合成） | SUPPORTS | manual_import | MANUAL | 否 | AVAILABLE | 2026-11-18T08:57:15 | 59 字 | ✅ |

洞察语句：回复客户时可以说明：欧盟/德国市场通常需要 CE 文件与包装回收标识，德语说明书可作为可选项向客户确认（依据证据时间 2026-10）。

洞察状态：`INFERRED`（origin `AI`，revision 1）。AI 推断不得标为已确认事实。

## 4. Provider 状态

| code | 模式 | 类别 | 启用 | 最近健康状态 |
|---|---|---|---|---|
| fixture_live | LIVE | OVERSEAS | True | UNAVAILABLE |
| manual_import | MANUAL | — | True | — |
| zhihu_demo | DEMO | ZHIHU | True | AVAILABLE |
| zhihu_live | PLANNED | ZHIHU | False | — |

## 5. 故障隔离行为

- LIVE-like Provider 离线后再次采集返回 `UNAVAILABLE`（`PROVIDER_UNAVAILABLE`），不抛错、不写入新证据；已有 4 条证据与洞察链路仍可读取。
- 模拟外链失效（`mark_unavailable`）后，该证据状态为 `UNAVAILABLE`，快照文本（145 字）与 hash 仍可用于解释洞察来源。
- DEMO 证据由已注册 Provider 模式强制派生 `is_demo`，数据库约束 `is_demo = (provider_mode = 'DEMO')` 阻止漏标；PLANNED Provider 处于禁用状态，采集前即被拒绝。

## 6. 时间与快照语义

- `captured_at` 为系统获取证据的时间；`source_published_at` 为来源自身发布时间，可为空，两者分开保存，界面不得混用。
- 快照保存在 `evidence.captured_text`，`content_hash` 为快照文本的 sha256；本次验证对全部洞察证据逐条重算并比对通过。
- 快照与证据行在同一事务写入，避免“有行无快照”；外链失效只改 `availability_status`，不删除快照。

## 7. 边界与限制

- Provider 为本地 fixture/DEMO，不执行网络请求；真实知乎/海外来源的授权、限流与条款仍待 POC-06，不因本报告视为可用集成。
- 失败采集（Provider UNAVAILABLE）仅返回运行时结果并更新 Provider 健康状态，尚未持久化 research_run/partial failure 表；阶段 3 接入研究运行时补齐。
- 未实现 discovery candidate 到 Evidence 的人工接受流程、证据编辑/删除、审计日志，也未接入前端 Evidence Drawer。
- 证据可信状态默认 `NEEDS_CONFIRMATION`，未做来源间的自动交叉验证；`usage_note` 只记录文本说明，许可证与保留期限策略待确认。
- 未验证多用户并发、租户隔离、快照容量/清理与敏感信息脱敏。
- 合成数据结论不能外推到真实来源质量；本 POC 只验证 provenance 机制与故障隔离。

补充：4 条证据均生成 64 位 sha256（4 条校验通过），洞察链路共 4 条。
