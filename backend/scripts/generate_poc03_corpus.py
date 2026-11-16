"""Generate the synthetic POC-03 document corpus (no real customer data).

Creates digital/scanned PDFs, rotated photos, EML variants, corrupted and
encrypted files plus a manifest with expected outcomes and page-level tokens.
Run from backend/:  ../.venv/Scripts/python.exe scripts/generate_poc03_corpus.py
"""
from __future__ import annotations

import hashlib
import io
import json
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

BACKEND_DIR = Path(__file__).resolve().parents[1]
CORPUS_DIR = BACKEND_DIR / "data" / "poc03_corpus"
FONT_EN = "C:/Windows/Fonts/arial.ttf"

page_one_lines = [
    "Nordlicht GmbH inquiry",
    "QUANTITY 500 UNITS",
    "Wireless earbuds with logo printing",
    "FOB Shenzhen",
]
page_two_lines = ["Delivery: end of June", "PAGE-TWO-7Q4"]


def digital_pdf_en(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 720
    for line in page_one_lines:
        c.drawString(64, y, line)
        y -= 28
    c.showPage()
    y = 720
    for line in page_two_lines:
        c.drawString(64, y, line)
        y -= 28
    c.save()


def digital_pdf_cn(path: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("STSong-Light", 16)
    for offset, line in enumerate(["询盘：3000 条智能手环，发往德国", "CN-TOKEN-3000", "要求 5 月前交货"]):
        c.drawString(64, 720 - offset * 30, line)
    c.save()


def render_text_image(lines: list[str], width: int = 1100, height: int = 420) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_EN, 42)
    y = 40
    for line in lines:
        draw.text((36, y), line, fill="black", font=font)
        y += 80
    return image


def scanned_pdf(path: Path, image: Image.Image) -> None:
    image.save(path, "PDF", resolution=200)


def photo_exif90(path: Path, image: Image.Image) -> None:
    rotated = image.rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW when displayed
    rotated.save(path, quality=92, exif=exif)


def photo_rot180(path: Path, image: Image.Image) -> None:
    image.rotate(180, expand=True).save(path)


def eml_plain_with_pdf(path: Path, pdf_bytes: bytes) -> None:
    message = EmailMessage()
    message["From"] = "buyer@example.com"
    message["To"] = "sales@exporbit.example"
    message["Subject"] = "Inquiry with quotation attachment"
    message.set_content("Please find our inquiry attached. EML-BODY-771 - 500 units, FOB Shenzhen.")
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="quotation.pdf")
    path.write_bytes(message.as_bytes())


def eml_html_only(path: Path) -> None:
    message = EmailMessage()
    message["From"] = "buyer@example.com"
    message["To"] = "sales@exporbit.example"
    message["Subject"] = "HTML inquiry"
    message.set_content(
        "<html><body><p>We need 2000 smart doorbells. EML-HTML-882</p>"
        "<p>Please quote CIF Hamburg.</p></body></html>",
        subtype="html",
    )
    path.write_bytes(message.as_bytes())


def eml_with_exe_attachment(path: Path) -> None:
    message = EmailMessage()
    message["From"] = "buyer@example.com"
    message["To"] = "sales@exporbit.example"
    message["Subject"] = "Inquiry with invoice"
    message.set_content("Our purchase order is attached. EML-EXE-990 - 1200 units.")
    message.add_attachment(b"MZ\x90\x00synthetic-not-a-real-binary", maintype="application", subtype="octet-stream", filename="invoice.exe")
    path.write_bytes(message.as_bytes())


def encrypted_pdf(source: Path, target: Path) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("synthetic-password", algorithm="RC4-128")
    with target.open("wb") as handle:
        writer.write(handle)


def corrupted_pdf(source: Path, target: Path) -> None:
    data = source.read_bytes()
    target.write_bytes(data[: int(len(data) * 0.6)])


def blank_scan(target: Path) -> None:
    Image.new("RGB", (1000, 300), "white").save(target, "PDF", resolution=200)


def corrupted_image(target: Path) -> None:
    target.write_bytes(b"\xff\xd8\xff" + b"\x00" * 64 + b"not-an-image")


def unsupported_file(target: Path) -> None:
    target.write_bytes(b"PK\x03\x04synthetic-docx-placeholder")


def manifest(samples_meta: list[dict]) -> dict:
    files = {}
    for entry in samples_meta:
        path = CORPUS_DIR / entry["file"]
        files[entry["file"]] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    return {
        "meta": {
            "note": "Synthetic POC-03 corpus; no real customer data.",
            "generator": "backend/scripts/generate_poc03_corpus.py",
        },
        "files": files,
        "samples": samples_meta,
    }


def build() -> dict:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    digital_pdf_en(CORPUS_DIR / "pdf_text_en_2p.pdf")
    digital_pdf_cn(CORPUS_DIR / "pdf_text_cn_1p.pdf")
    scanned_pdf(
        CORPUS_DIR / "pdf_scan_en_1p.pdf",
        render_text_image(["SCAN-TOKEN-9K2", "quantity 800 units", "delivery end of June"]),
    )
    photo_exif90(
        CORPUS_DIR / "img_photo_en_exif90.jpg",
        render_text_image(["EXIF-OK-441", "quantity 500 units", "FOB Shenzhen"]),
    )
    photo_rot180(
        CORPUS_DIR / "img_rot180_noexif.png",
        render_text_image(["ROT180-553", "quantity 1200 units", "CIF Hamburg"]),
    )
    eml_plain_with_pdf(CORPUS_DIR / "eml_plain_with_pdf_attachment.eml", (CORPUS_DIR / "pdf_text_en_2p.pdf").read_bytes())
    eml_html_only(CORPUS_DIR / "eml_html_only.eml")
    eml_with_exe_attachment(CORPUS_DIR / "eml_with_exe_attachment.eml")
    encrypted_pdf(CORPUS_DIR / "pdf_text_en_2p.pdf", CORPUS_DIR / "pdf_encrypted.pdf")
    corrupted_pdf(CORPUS_DIR / "pdf_text_en_2p.pdf", CORPUS_DIR / "pdf_corrupted.pdf")
    blank_scan(CORPUS_DIR / "pdf_blank_scan.pdf")
    corrupted_image(CORPUS_DIR / "img_corrupted.jpg")
    unsupported_file(CORPUS_DIR / "file_unsupported.docx")

    samples = [
        {
            "id": "PDF-TEXT-EN-2P",
            "file": "pdf_text_en_2p.pdf",
            "format": "pdf",
            "expect": {
                "outcome": "success",
                "min_pages": 2,
                "checks": [
                    {"page": 1, "contains": ["QUANTITY 500 UNITS", "FOB Shenzhen"]},
                    {"page": 2, "contains": ["PAGE-TWO-7Q4", "end of June"]},
                ],
            },
        },
        {
            "id": "PDF-TEXT-CN-1P",
            "file": "pdf_text_cn_1p.pdf",
            "format": "pdf",
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [{"page": 1, "contains": ["3000 条智能手环", "CN-TOKEN-3000"], "min_matches": 1}],
            },
        },
        {
            "id": "PDF-SCAN-EN-1P",
            "file": "pdf_scan_en_1p.pdf",
            "format": "pdf",
            "ocr_required": True,
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [
                    {"page": 1, "contains": ["SCAN-TOKEN-9K2", "quantity 800 units", "end of June"], "min_matches": 2}
                ],
            },
        },
        {
            "id": "IMG-EXIF90",
            "file": "img_photo_en_exif90.jpg",
            "format": "image",
            "ocr_required": True,
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [
                    {"page": 1, "contains": ["EXIF-OK-441", "quantity 500 units", "FOB Shenzhen"], "min_matches": 2}
                ],
            },
        },
        {
            "id": "IMG-ROT180",
            "file": "img_rot180_noexif.png",
            "format": "image",
            "ocr_required": True,
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [{"page": 1, "contains": ["ROT180-553", "quantity 1200 units", "CIF Hamburg"], "min_matches": 2}],
            },
        },
        {
            "id": "EML-PLAIN-PDF",
            "file": "eml_plain_with_pdf_attachment.eml",
            "format": "eml",
            "expect": {
                "outcome": "success",
                "min_pages": 3,
                "checks": [
                    {"page": 1, "contains": ["EML-BODY-771"]},
                    {"page": 2, "contains": ["QUANTITY 500 UNITS"]},
                    {"page": 3, "contains": ["PAGE-TWO-7Q4"]},
                ],
                "attachments": [{"filename": "quotation.pdf", "parsed": True}],
            },
        },
        {
            "id": "EML-HTML-ONLY",
            "file": "eml_html_only.eml",
            "format": "eml",
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [{"page": 1, "contains": ["EML-HTML-882", "2000 smart doorbells"]}],
            },
        },
        {
            "id": "EML-EXE-ATTACH",
            "file": "eml_with_exe_attachment.eml",
            "format": "eml",
            "expect": {
                "outcome": "success",
                "min_pages": 1,
                "checks": [{"page": 1, "contains": ["EML-EXE-990"]}],
                "attachments": [{"filename": "invoice.exe", "parsed": False, "skip_reason": "executable_blocked"}],
            },
        },
        {"id": "PDF-CORRUPTED", "file": "pdf_corrupted.pdf", "format": "pdf", "expect": {"outcome": "error", "code": "CORRUPTED"}},
        {"id": "PDF-ENCRYPTED", "file": "pdf_encrypted.pdf", "format": "pdf", "expect": {"outcome": "error", "code": "ENCRYPTED"}},
        {"id": "IMG-CORRUPTED", "file": "img_corrupted.jpg", "format": "image", "expect": {"outcome": "error", "code": "CORRUPTED"}},
        {"id": "PDF-BLANK-SCAN", "file": "pdf_blank_scan.pdf", "format": "pdf", "expect": {"outcome": "error", "code": "EMPTY_TEXT"}},
        {"id": "UNSUPPORTED-DOCX", "file": "file_unsupported.docx", "format": "other", "expect": {"outcome": "error", "code": "UNSUPPORTED_FORMAT"}},
    ]
    data = manifest(samples)
    (CORPUS_DIR / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    result = build()
    print(f"corpus written to {CORPUS_DIR} ({len(result['samples'])} samples)")
