# Exporbit POC-02 验证报告：DeepSeek 结构化抽取

- 验证时间（UTC）：2026-11-16T04:27:51.515293+00:00 ~ 2026-11-16T04:28:36.389659+00:00
- 语料：backend/data/poc02_corpus.json（24 条合成询盘，中文 12 / 英文 12；不含任何真实客户数据）
- 模型：`deepseek-chat`（JSON 输出模式，temperature=0，max_tokens=1500）
- llm_runs 持久化：已写入 PostgreSQL
- 结论：**PASS**

## 1. 成功标准

| 标准 | 目标 | 实测 | 通过 |
|---|---|---|---|
| 响应通过 schema 校验 | ≥ 90% | 100.0% | ✅ |
| 关键字段 F1（macro） | ≥ 0.85 | 0.8854 | ✅ |

## 2. Schema 通过与修复

| 指标 | 数值 |
|---|---|
| 最终有效响应 | 24/24（100.0%） |
| 首次请求即通过 | 24（100.0%） |
| 触发一次修复请求并成功 | 0 |
| 修复成功率 | N/A |

## 3. 字段级 F1（golden 精确匹配 + 缺省检测）

| 字段 | Precision | Recall | F1 | 存在性准确率 |
|---|---|---|---|---|
| customer_need | 0.75 | 0.75 | 0.75 | 75.0% |
| quantity | 1.0 | 1.0 | 1.0 | 100.0% |
| target_market | 0.8333 | 0.8333 | 0.8333 | 83.3% |
| customization_needs | 0.9583 | 0.9583 | 0.9583 | 95.8% |
| delivery_timeline | 0.875 | 0.875 | 0.875 | 87.5% |
| price_terms | 0.875 | 0.913 | 0.8936 | 87.5% |
| **关键字段 macro F1** | | | **0.8854** | |
| **全部字段 macro F1** | | | **0.885** | |

> 方法论：golden 标注为期望抽取值（null=原文未提及）。预测值与 golden 归一化（去空白/大小写/尾标点）后精确相等或同为 null 计正确；golden 为 null 而预测有值计 FP（幻觉）；golden 有值而预测为 null 计 FN（漏抽）；两者均非空但不相等，同一字段同时计 FP 与 FN。status 标签（CONFIRMED/INFERRED）属主观判断，不参与评分。

## 4. 用量与延迟（仅成功调用）

- 输入 token：20216；输出 token：4415；合计：24631
- 平均 token/条：1026
- 延迟：平均 1374 ms，最小 981 ms，最大 1769 ms（24 次成功调用）

## 5. 错误分类

无失败调用。

## 6. 字段级差异明细（预测 vs golden）

共 17 处字段级差异。

| 语料 ID | 字段 | 预测值 | golden |
|---|---|---|---|
| CN-01 | customization_needs | 印我们的 Logo | 印 Logo |
| CN-02 | customer_need | 智能手表，支持心率监测和 GPS | 智能手表 |
| CN-05 | price_terms | 目标价 15 美元以内 | 15 美元以内 |
| CN-10 | delivery_timeline | 4 月底交货 | 4 月底 |
| CN-11 | customer_need | 10.1 英寸安卓平板，4GB+64GB，支持蓝牙 5.3 | 10.1 英寸安卓平板 |
| CN-12 | target_market | 中东市场 | 中东 |
| EN-02 | customer_need | smart watches with heart rate monitoring | smart watches |
| EN-02 | target_market | French market | France |
| EN-04 | delivery_timeline | by end of June | end of June |
| EN-05 | price_terms | target price under 15 USD | under 15 USD |
| EN-06 | customer_need | 便携式咖啡机，索取产品目录 | portable coffee machines |
| EN-07 | target_market | German and Polish markets | Germany and Poland |
| EN-09 | customer_need | 智能水瓶 | smart water bottles |
| EN-09 | target_market | 日本 | Japan |
| EN-10 | delivery_timeline | by end of April | end of April |
| EN-11 | customer_need | 10.1-inch Android tablets, 4GB+64GB, Bluetooth 5.3 | 10.1-inch Android tablets |
| EN-12 | price_terms | bulk pricing | — |

- 输出语言未跟随输入语言：3 处（EN-06.customer_need, EN-09.customer_need, EN-09.target_market），英文询盘返回了中文值。这是真实质量问题，建议在 system prompt 增加输出语言跟随输入语言的约束。

- 其余差异多为同义改写或粒度差异（预测带出原文修饰语、golden 更简略），内容大多无害，但按精确匹配计为不一致。

## 7. 边界与限制

- 本 POC 仅验证 Provider 接口 + DeepSeek Adapter + 抽取 schema 的线上可用性，未接入 /inquiries 业务路径（按 POC-02 范围约定）。
- 每轮调用均写入 `llm_runs` 表（purpose/model/token/延迟/输入哈希/错误码），原文不落库。
- 人工字段保护（CONFIRMED/INFERRED 不被 AI 重跑覆盖）由单元测试 `test_extraction_service.py` 验证，属纯函数行为演示，待 POC-03 接入业务路径后做端到端验证。
- 语料为合成数据；真实询盘的领域分布、噪音与语言混杂会带来偏差。
- 逐条明细见 `outputs/POC_02_RESULTS.json`。
