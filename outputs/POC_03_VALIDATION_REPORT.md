# Exporbit POC-03 验证报告：PDF/图片/EML 解析

- 验证时间（UTC）：2026-11-16T06:25:52.384666+00:00
- 语料：backend/data/poc03_corpus/manifest.json（13 个合成样本；不含真实客户数据）
- 解析栈：pdfplumber 0.11.4 / pypdf 5.1.0 / Pillow 11.1.0 / RapidOCR 3.10.0（onnxruntime 1.32.0）
- 附件策略：不执行任何附件内容；可执行文件与未知类型仅登记后跳过
- 结论：**PASS**

## 1. 成功标准

| 标准 | 目标 | 实测 | 通过 |
|---|---|---|---|
| 有效样本解析成功率 | ≥ 90.0% | 100.0%（8/8） | ✅ |
| 页级定位/溯源校验 | 100% | 100.0%（11/11） | ✅ |
| 受控失败错误码精确率 | 100% | 100.0%（5/5） | ✅ |
| 附件策略校验 | 100% | 100.0%（2/2） | ✅ |

## 2. 逐样本结果

| 样本 | 格式 | 结果 | 页数 | OCR 页 | 耗时 ms | 页面校验 | 判定 |
|---|---|---|---|---|---|---|---|
| PDF-TEXT-EN-2P | pdf | success | 2 | 0 | 6 | 2/2 | ✅ |
| PDF-TEXT-CN-1P | pdf | success | 1 | 0 | 24 | 1/1 | ✅ |
| PDF-SCAN-EN-1P | pdf | success | 1 | 1 | 9652 | 1/1 | ✅ |
| IMG-EXIF90 | image | success | 1 | 1 | 4512 | 1/1 | ✅ |
| IMG-ROT180 | image | success | 1 | 1 | 4777 | 1/1 | ✅ |
| EML-PLAIN-PDF | eml | success | 3 | 0 | 66 | 3/3 | ✅ |
| EML-HTML-ONLY | eml | success | 1 | 0 | 1 | 1/1 | ✅ |
| EML-EXE-ATTACH | eml | success | 1 | 0 | 14 | 1/1 | ✅ |
| PDF-CORRUPTED | pdf | error:CORRUPTED | — | — | 0 | — | ✅ |
| PDF-ENCRYPTED | pdf | error:ENCRYPTED | — | — | 72 | — | ✅ |
| IMG-CORRUPTED | image | error:CORRUPTED | — | — | 1244 | — | ✅ |
| PDF-BLANK-SCAN | pdf | error:EMPTY_TEXT | — | — | 4314 | — | ✅ |
| UNSUPPORTED-DOCX | other | error:UNSUPPORTED_FORMAT | — | — | 0 | — | ✅ |

## 3. 页级溯源样本

`source` 取值：`text_layer`（PDF 文本层）、`ocr`（渲染后 OCR）、`email_body`（邮件正文）、`attachment:<filename>`（附件内页）。

| 样本 | 页级来源 |
|---|---|
| PDF-TEXT-EN-2P | text_layer, text_layer |
| PDF-TEXT-CN-1P | text_layer |
| PDF-SCAN-EN-1P | ocr |
| IMG-EXIF90 | ocr |
| IMG-ROT180 | ocr |
| EML-PLAIN-PDF | email_body, attachment:quotation.pdf, attachment:quotation.pdf |
| EML-HTML-ONLY | email_body |
| EML-EXE-ATTACH | email_body |

## 4. 受控失败

| 样本 | 期望错误码 | 实际错误码 | 细节 |
|---|---|---|---|
| PDF-CORRUPTED | CORRUPTED | CORRUPTED | {"type": "PdfStreamError"} |
| PDF-ENCRYPTED | ENCRYPTED | ENCRYPTED | {} |
| IMG-CORRUPTED | CORRUPTED | CORRUPTED | {"type": "UnidentifiedImageError"} |
| PDF-BLANK-SCAN | EMPTY_TEXT | EMPTY_TEXT | {"pages": 1} |
| UNSUPPORTED-DOCX | UNSUPPORTED_FORMAT | UNSUPPORTED_FORMAT | {"extension": ".docx"} |

## 5. 附件策略

| 样本 | 附件 | 大小 B | 已解析 | 跳过原因 |
|---|---|---|---|---|
| EML-PLAIN-PDF | quotation.pdf | 1983 | True | — |
| EML-EXE-ATTACH | invoice.exe | 31 | False | executable_blocked |

## 6. 性能

| 指标 | 数值 |
|---|---|
| 样本耗时 中位数 / 均值 / 最大 | 66 / 1898 / 9652 ms |
| OCR 渲染页数合计 | 3 |
| 解析告警 | 2 条 |

## 7. 边界与限制

- OCR 依赖 RapidOCR（PP-OCRv6，Apache-2.0）+ onnxruntime，本地推理；首次加载模型约 2.5 秒，单页 2 秒级，不适合同步请求路径，接入时应走后台任务。
- 旋转检测仅在 OCR 置信度低或文本过短时尝试 90/180/270；真实照片的透视、模糊、复杂版式未覆盖，OCR 语句级准确率不参与本次评分。
- 页级定位为页号 + 文本块拼接级别，未保留字符级坐标；如需高亮引用，后续需保存 bbox。
- EML 只读取正文与受支持附件（PDF/图片），不执行内容、不解析压缩包、不递归嵌套邮件；HTML 正文仅做标签剥离。
- 附件上限 10 MB、文件上限 25 MB、PDF 上限 50 页为当前默认值，需按业务确认（docs/DEVELOPMENT_ROADMAP.md 未决策项）。
- 语料为合成数据；未包含加密 Office、宏文档、多语言混排、双栏排版等真实分布样本。
- 未接入 /inquiries 业务路径；解析结果持久化与原文快照属下一步（阶段 1 Inquiry Foundation）。
