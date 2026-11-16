# Exporbit Provider 设计

## 1. 目标

Provider 层隔离 DeepSeek、文档解析器和知识来源。业务服务依赖接口和规范化结果，不依赖专属 SDK、网页结构或未经确认的 API。

## 2. LLM Provider

```python
class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        purpose: str,
        messages: list[Message],
        output_schema: type[BaseModel],
        model: str | None = None,
        timeout_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> LLMResult: ...
```

`LLMResult` 包含 validated data、provider、model、usage、latency、request/provider run id、finish reason；不得把未通过 Pydantic 校验的文本当作业务对象。

### DeepSeek Adapter 规则

- 凭据只从后端 secret/config 注入；日志和 API 响应不得包含 key。
- 连接/429/5xx 最多 2 次指数退避重试并带 jitter；校验错误允许一次受约束的修复请求；4xx 配置错误不重试。
- 每次调用记录 purpose、model、token usage、耗时、状态和输入哈希。敏感原文不默认写日志。
- timeout、rate limit、invalid output、configuration、provider unavailable 使用稳定内部错误码。
- 失败时返回可恢复状态；保留已有事实和人工编辑。没有第二 Provider 时不伪造结果。
- 模型名、温度、最大 token 等按 purpose 由服务端配置；客户端不能任意传模型。

## 3. Knowledge Provider

```python
class KnowledgeProvider(Protocol):
    code: str
    category: SourceCategory
    mode: ProviderMode

    async def search(self, query: ResearchQuery) -> SearchResultPage: ...
    async def fetch(self, ref: SourceRef) -> SourceDocument: ...
    async def health(self) -> ProviderHealth: ...
```

规范化 `SourceDocument`：title、canonical_url/source_ref、author/publisher（可空）、published_at（可空）、captured_at、content、content_hash、source_category、provider_mode、is_demo、license/usage note、availability。

### 来源模式

| 模式 | 含义 | UI/数据规则 |
|---|---|---|
| LIVE | 经验证且允许的实时集成 | 展示 Provider、抓取时间、来源链接 |
| MANUAL | 用户导入/粘贴 | 标记手工导入与操作者 |
| DEMO | 固定演示数据 | 强制 `is_demo=true`，不得称实时搜索 |
| PLANNED | 规划但不可用 | 不出现在可执行 Provider 中 |

### Provider 计划

- **Zhihu：** 当前只有 DEMO 数据；公开、授权、稳定的获取方式尚未验证。禁止依赖未记录接口或规避访问控制。可先支持用户提供链接/内容的手工导入。
- **Overseas/Official：** 需分别验证搜索服务和官方站点使用条件；官方来源类别不等于内容自动可信，仍保存时间和上下文。
- **Enterprise：** MVP 可从已上传且授权的企业产品文件生成证据；解析结果与原文件哈希关联。
- **Customer Inquiry：** 系统内部来源，原文和文件快照是第一方证据，但客户主张仍不等于外部验证事实。

## 4. 文档解析 Provider

`DocumentParser.parse(file_ref) -> ParsedDocument`。路由按 MIME 和魔数，不信任扩展名。PDF 提取文本；扫描 PDF/图片需要 OCR POC；EML 解析 header、plain/html body 与附件。解析器输出页码/段落定位、warnings 和置信信息，原文件只读保存。

## 5. Provenance 与证据晋升

Provider 结果先是 discovery candidate，只有用户收藏或受控规则接受后才成为 Evidence。Evidence 必须保存来源、快照、hash、captured_at、类别、模式和业务问题关联。摘要是派生内容，必须引用父 evidence id；摘要不能替代原始快照。

## 6. 故障隔离

- 单个知识源失败不使询盘处理失败；研究运行记录 partial failure。
- Zhihu 关闭时仍可使用客户原文、企业资料、人工证据和其他 Provider。
- 外链失效时展示历史快照和 unavailable 状态。
- LLM 不可用时允许手工填写 Snapshot、匹配、行动和回复。
