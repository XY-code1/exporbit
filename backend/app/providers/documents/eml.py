"""EML parsing with stdlib email: body text plus attachment policy.

Attachments are decoded for size/type inspection only. Executables and
unknown types are recorded and skipped; supported PDFs/images are parsed
through the injected dispatcher with provenance labelled by attachment name.
"""
from __future__ import annotations

import email
import os
from email import policy
from html.parser import HTMLParser
from typing import Callable

from app.providers.documents.contracts import (
    EXECUTABLE_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
    SUPPORTED_ATTACHMENT_EXTENSIONS,
    AttachmentInfo,
    PageText,
    ParsedDocument,
    ParseError,
    ParseErrorCode,
)


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.chunks.append(data)


def _html_to_text(html: str) -> str:
    parser = _HtmlText()
    parser.feed(html)
    return " ".join(" ".join(parser.chunks).split())


def parse_eml(
    filename: str,
    data: bytes,
    parse_attachment: Callable[[str, bytes, str | None], ParsedDocument],
) -> ParsedDocument:
    try:
        message = email.message_from_bytes(data, policy=policy.default)
    except Exception as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "EML cannot be parsed", {"type": type(exc).__name__}) from exc

    plain_parts: list[str] = []
    html_parts: list[str] = []
    raw_attachments: list[tuple[str, str, bytes]] = []

    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        attachment_name = part.get_filename()
        if part.get_content_disposition() == "attachment" or attachment_name:
            payload = part.get_payload(decode=True) or b""
            safe_name = os.path.basename(attachment_name) if attachment_name else "attachment.bin"
            raw_attachments.append((safe_name, content_type, payload))
            continue
        if content_type == "text/plain":
            try:
                plain_parts.append(part.get_content())
            except (LookupError, UnicodeDecodeError):
                plain_parts.append((part.get_payload(decode=True) or b"").decode("utf-8", errors="replace"))
        elif content_type == "text/html":
            try:
                html_parts.append(part.get_content())
            except (LookupError, UnicodeDecodeError):
                html_parts.append((part.get_payload(decode=True) or b"").decode("utf-8", errors="replace"))

    body = "\n".join(part.strip() for part in plain_parts if part and part.strip())
    if not body:
        body = "\n".join(filter(None, (_html_to_text(html).strip() for html in html_parts)))
    if not body:
        raise ParseError(ParseErrorCode.EMPTY_TEXT, "email has no readable body")

    pages: list[PageText] = [PageText(1, body, "email_body")]
    attachments: list[AttachmentInfo] = []
    warnings: list[str] = []
    next_page = 2
    for name, content_type, payload in raw_attachments:
        ext = os.path.splitext(name)[1].lower()
        if len(payload) > MAX_ATTACHMENT_BYTES:
            attachments.append(AttachmentInfo(name, content_type, len(payload), skip_reason="too_large"))
            warnings.append(f"attachment {name}: too_large")
            continue
        if ext in EXECUTABLE_EXTENSIONS:
            attachments.append(AttachmentInfo(name, content_type, len(payload), skip_reason="executable_blocked"))
            warnings.append(f"attachment {name}: executable_blocked")
            continue
        if ext == ".eml":
            attachments.append(AttachmentInfo(name, content_type, len(payload), skip_reason="nested_email"))
            warnings.append(f"attachment {name}: nested_email")
            continue
        if ext not in SUPPORTED_ATTACHMENT_EXTENSIONS:
            attachments.append(AttachmentInfo(name, content_type, len(payload), skip_reason="unsupported_type"))
            warnings.append(f"attachment {name}: unsupported_type")
            continue
        try:
            parsed = parse_attachment(name, payload, content_type)
        except ParseError as exc:
            attachments.append(
                AttachmentInfo(name, content_type, len(payload), skip_reason=f"parse_failed:{exc.code.value}")
            )
            warnings.append(f"attachment {name}: parse_failed:{exc.code.value}")
            continue
        attachments.append(AttachmentInfo(name, content_type, len(payload), parsed=True))
        for page in parsed.pages:
            pages.append(PageText(next_page, page.text, f"attachment:{name}"))
            next_page += 1

    return ParsedDocument(
        filename=filename, format="eml", pages=tuple(pages), attachments=tuple(attachments), warnings=tuple(warnings)
    )
