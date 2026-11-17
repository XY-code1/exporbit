# Exporbit POC-02 验证报告 — DeepSeek Structured Inquiry Extraction

## 结论

**建议通过 POC-02。** 真实 DeepSeek API 的 30 条合成询盘全部返回符合 V2 Pydantic schema 的结果；后端完整测试 77 项通过，前端生产构建与 Sites Worker 4 项测试通过。未开始 POC-03。

## 实现范围

- 可替换 `LLMProvider` 合同；`DeepSeekProvider` 仅负责 DeepSeek 的 REST 适配。
- API key 只从服务端环境读取；模型、超时和有限重试可配置。
- `InquiryExtractionService` 与 Inquiry CRUD 分离。
- `POST /api/v1/inquiries/{inquiry_id}/extract` 手动触发提取。
- 新增不可变 `inquiry_extractions` 记录；重复提取保留历史；原询盘原文及人工字段不被覆盖。
- Business Snapshot 接入真实 API，包含加载、错误、字段状态、缺失信息和澄清问题。
- 产品匹配、知识研究和商务回复仍明确标记为 DEMO，不属于本 POC。

## 数据契约

`StructuredInquiryExtraction` 包含：

- `customer`: customer_name / company_name / email / country
- `products[]`: product_type / product_description / quantity / quantity_unit / specifications / customization_requirements / certification_requirements
- `business`: target_market / expected_delivery / target_price / purchasing_intent
- `missing_fields[]`、`clarification_questions[]`

每个业务字段均为 `{value, status, evidence}`。状态仅允许 `CONFIRMED`、`INFERRED`、`NEEDS_CONFIRMATION`、`INSUFFICIENT_DATA`；缺失值归一化为 `null`。

## 数据库与迁移

- 迁移：`20261117_0004_create_inquiry_extractions.py`
- 新表：`inquiry_extractions`
- 外键：`inquiry_id -> inquiries.id`，`llm_run_id -> llm_runs.id`
- `structured_data` 使用 JSONB；记录含 provider/model/status/error/created_at。
- 当前工作区已有未提交的 `20261116_0003` Evidence 迁移，0004 按现有迁移头衔接；未删除或改写该项外部工作。

## API 示例

请求：

```http
POST /api/v1/inquiries/7d10.../extract
```

响应（节选）：

```json
{
  "extraction_id": "...",
  "inquiry_id": "...",
  "structured_data": {
    "customer": {"company_name": {"value": "Nordlicht GmbH", "status": "CONFIRMED", "evidence": "Nordlicht GmbH"}},
    "products": [{"product_type": {"value": "ANC wireless earbuds", "status": "CONFIRMED", "evidence": "ANC wireless earbuds"}}],
    "business": {"target_market": {"value": "Germany", "status": "CONFIRMED", "evidence": "Germany"}},
    "missing_fields": [],
    "clarification_questions": []
  },
  "extraction_status": "SUCCESS",
  "provider": "deepseek",
  "model": "deepseek-chat",
  "created_at": "..."
}
```

## 30 条人工标注语料

- 文件：`backend/data/poc02_v2_corpus.json`
- 全部为合成数据，不含真实客户信息。
- 24 条继承并转换自既有人工复核语料，新增 6 条覆盖多产品、中英混合、非标准英语、缺失国家、模糊数量、认证/购买意图不清。
- 构建脚本是确定性的，不调用模型；模型不参与评分。

## 自动化测试

| 测试 | 结果 |
|---|---:|
| Pytest（schema/provider/API/persistence/preservation/multiple records/error handling 等） | 77 passed |
| Frontend production build | passed |
| Sites Worker | 4 passed |
| Alembic upgrade（开发库 + 测试库） | passed |

确定性测试使用 mocked provider；与下节真实 API 测试严格区分。

## 真实 DeepSeek 集成结果

- 执行：`backend/scripts/validate_extraction_v2.py`
- 结果文件：`outputs/POC_02_V2_RESULTS.json`
- Schema 成功率：**30/30（100%）**
- 真实纵向链路：创建询盘 `201`；调用 extraction endpoint `200 / SUCCESS / deepseek`；生成并持久化 extraction ID。
- 关键字段规范化精确匹配：
  - product_type：28/30（93.3%）
  - target_market：27/30（90.0%）
  - expected_delivery：28/30（93.3%）

该准确率是与固定人工标签做确定性匹配，不是 LLM 自评。严格字符串匹配会把语义等价但措辞不同的值计为错误，因此结果偏保守。

## 已知限制

1. 当前评估的可量化准确率聚焦三个关键字段；完整字段仍由 schema、mock 测试与人工抽查覆盖，后续需要扩充逐字段黄金标签。
2. 前端当前会话中展示刚生成的结果；尚未提供“读取历史提取列表”的 GET API。
3. Provider 失败返回持久化的 `FAILED` 提取响应，尚未实现后台队列或异步重试。
4. JSON 输出依赖 prompt 的精确 shape 示例；模型升级后应重新运行固定语料回归。
5. 现有 Evidence/POC-03 工作区文件并非本次创建范围，未纳入 POC-02 验收结论。
