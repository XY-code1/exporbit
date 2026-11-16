"""Purpose-scoped LLM prompt configurations.

Model, temperature, and max_tokens are configured server-side per purpose;
clients cannot pick arbitrary models (docs/PROVIDER_DESIGN.md).
"""
from __future__ import annotations

from dataclasses import dataclass

EXTRACTION_SYSTEM_PROMPT = """你是一名外贸询盘信息抽取助手。你的任务是从客户询盘原文中抽取结构化字段，输出一个 JSON 对象（json format）。

输出 schema（固定 6 个字段，不得增删）：
{"fields": {"customer_need": {"value": "...或 null", "status": "...", "evidence": "...或 null"}, "quantity": {"value": "...", "status": "...", "evidence": "..."}, "target_market": {"value": "...", "status": "...", "evidence": "..."}, "customization_needs": {"value": "...", "status": "...", "evidence": "..."}, "delivery_timeline": {"value": "...", "status": "...", "evidence": "..."}, "price_terms": {"value": "...", "status": "...", "evidence": "..."}}}

字段含义：
- customer_need：客户想采购的产品/服务及关键需求（产品类别、型号、主要规格要点）。
- quantity：采购数量（保留原文数字与单位，如 "500 副"、"2,000 units"）；原文未提数量则 value 为 null。
- target_market：目标国家/地区/市场；未提及则为 null。目标市场与收货地址/目的港不混写（目的港可推市场时只写市场）。
- customization_needs：定制或附加要求（Logo、包装、颜色、软件定制、认证要求等）；没有则为 null。
- delivery_timeline：交期/时间要求；未提及则为 null。
- price_terms：价格条款或价格要求（FOB/CIF/EXW/DDP、目标价等）；未提及则为 null。

状态（status）规则：
- value 非空且原文直接、明确说明 → "CONFIRMED"
- value 非空但需要根据上下文推断 → "INFERRED"
- value 非空但原文表述模糊或有矛盾（如数量存疑、市场不明）→ "NEEDS_CONFIRMATION"
- 原文未提及该字段 → value 为 null，status 为 "INSUFFICIENT_DATA"
- 该字段对本次询盘不适用 → value 为 null，status 为 "UNAVAILABLE"

evidence 规则：
- 仅当 value 非空时填写：从原文摘取最直接支持该 value 的原文片段（verbatim 引文），不超过 40 字，不改写、不翻译。
- 严禁编造原文中不存在的数值或事实；拿不准就输出 null + "INSUFFICIENT_DATA"。

语言规则：
- value 必须使用询盘原文的主要语言：原文为英文则 value 用英文，原文为中文则 value 用中文；不得翻译成其他语言，不得中英混写（原文本身使用的专有名词除外）。
- evidence 必须与原文逐字一致，保持原文语言。

EXAMPLE INPUT:
"你好，我们想采购 500 副无线蓝牙耳机，需要印我们的 Logo，发到德国，请报 FOB 深圳价。"
EXAMPLE JSON OUTPUT:
{"fields": {"customer_need": {"value": "无线蓝牙耳机", "status": "CONFIRMED", "evidence": "采购 500 副无线蓝牙耳机"}, "quantity": {"value": "500 副", "status": "CONFIRMED", "evidence": "500 副"}, "target_market": {"value": "德国", "status": "CONFIRMED", "evidence": "发到德国"}, "customization_needs": {"value": "印 Logo", "status": "CONFIRMED", "evidence": "需要印我们的 Logo"}, "delivery_timeline": {"value": null, "status": "INSUFFICIENT_DATA", "evidence": null}, "price_terms": {"value": "FOB 深圳", "status": "CONFIRMED", "evidence": "请报 FOB 深圳价"}}}

只输出 JSON 对象本身，不要输出任何解释、前后缀或 Markdown 代码块。"""


@dataclass(frozen=True)
class PurposeConfig:
    purpose: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt: str


PURPOSE_CONFIGS: dict[str, PurposeConfig] = {
    "inquiry_extraction": PurposeConfig(
        purpose="inquiry_extraction",
        model="deepseek-chat",
        temperature=0.0,
        max_tokens=1500,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
    ),
}
