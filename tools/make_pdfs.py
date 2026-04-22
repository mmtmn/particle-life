#!/usr/bin/env python3
"""Generate small dependency-free PDFs from the docs Markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ("docs/overview.md", "docs/particle-life-overview.pdf"),
    ("docs/cuda-kernel-guide.md", "docs/cuda-kernel-guide.pdf"),
    ("docs/controls-and-tuning.md", "docs/controls-and-tuning.pdf"),
]

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

TextRun = Tuple[str, float, float, float, str]


def clean_inline(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("**", "")
    text = text.replace("*", "")
    return text


def wrap_text(text: str, font_size: float, indent: float = 0.0) -> List[str]:
    if not text:
        return [""]
    approx_char_width = font_size * 0.52
    max_chars = max(20, int((CONTENT_WIDTH - indent) / approx_char_width))
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def paginate(markdown: str) -> List[List[TextRun]]:
    pages: List[List[TextRun]] = [[]]
    y = PAGE_HEIGHT - MARGIN
    in_code = False

    def ensure_space(line_height: float) -> None:
        nonlocal y
        if y - line_height < MARGIN:
            pages.append([])
            y = PAGE_HEIGHT - MARGIN

    def add_line(text: str, font: str = "F1", size: float = 10.5,
                 indent: float = 0.0, line_height: float | None = None) -> None:
        nonlocal y
        if line_height is None:
            line_height = size * 1.35
        ensure_space(line_height)
        pages[-1].append((font, size, MARGIN + indent, y, text))
        y -= line_height

    def add_gap(amount: float) -> None:
        nonlocal y
        y -= amount
        if y < MARGIN:
            pages.append([])
            y = PAGE_HEIGHT - MARGIN

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            in_code = not in_code
            add_gap(4)
            continue

        if in_code:
            add_line(line[:95], "F3", 8.8, 10, 11.5)
            continue

        if not line.strip():
            add_gap(6)
            continue

        if line.startswith("# "):
            add_gap(4)
            for wrapped in wrap_text(clean_inline(line[2:]), 20):
                add_line(wrapped, "F2", 20, 0, 25)
            add_gap(8)
        elif line.startswith("## "):
            add_gap(8)
            for wrapped in wrap_text(clean_inline(line[3:]), 14):
                add_line(wrapped, "F2", 14, 0, 18)
            add_gap(3)
        elif line.startswith("### "):
            add_gap(6)
            for wrapped in wrap_text(clean_inline(line[4:]), 12):
                add_line(wrapped, "F2", 12, 0, 16)
        elif line.startswith("- "):
            text = "- " + clean_inline(line[2:])
            wrapped = wrap_text(text, 10.5, 14)
            for index, wrapped_line in enumerate(wrapped):
                add_line(wrapped_line, "F1", 10.5, 14 if index else 8)
            add_gap(2)
        else:
            for wrapped in wrap_text(clean_inline(line), 10.5):
                add_line(wrapped, "F1", 10.5)
            add_gap(3)

    return [page for page in pages if page]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_stream(page: Sequence[TextRun]) -> bytes:
    chunks: List[str] = []
    for font, size, x, y, text in page:
        chunks.append(
            f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td "
            f"({pdf_escape(text)}) Tj ET\n"
        )
    return "".join(chunks).encode("latin-1", "replace")


def stream_object(data: bytes) -> bytes:
    return b"<< /Length " + str(len(data)).encode("ascii") + b" >>\nstream\n" + data + b"endstream"


def write_pdf(pages: Sequence[Sequence[TextRun]], output: Path) -> None:
    objects: Dict[int, bytes] = {
        1: b"",
        2: b"",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    }

    page_ids: List[int] = []
    next_id = 6
    for page in pages:
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        objects[content_id] = stream_object(make_stream(page))
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("ascii")

    max_id = max(objects)
    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_id + 1)
    for object_id in range(1, max_id + 1):
        offsets[object_id] = len(buffer)
        buffer.extend(f"{object_id} 0 obj\n".encode("ascii"))
        buffer.extend(objects[object_id])
        buffer.extend(b"\nendobj\n")

    xref_at = len(buffer)
    buffer.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        buffer.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("ascii"))
    buffer.extend(
        f"trailer << /Size {max_id + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer)


def generate() -> None:
    for source_name, output_name in DOCS:
        source = ROOT / source_name
        output = ROOT / output_name
        pages = paginate(source.read_text(encoding="utf-8"))
        write_pdf(pages, output)
        print(f"wrote {output.relative_to(ROOT)} ({len(pages)} page(s))")


if __name__ == "__main__":
    generate()
