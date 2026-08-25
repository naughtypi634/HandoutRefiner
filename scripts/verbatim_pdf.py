#!/usr/bin/env python3
"""Render an MD handout word-for-word into a clean, print-ready PDF.

Unlike md_to_pdf.py (which keeps only question lines), this renderer
preserves every word of the source document: paragraphs, section headers,
bullet lists, and nested list items.

Visual style reuses the awesome-design-md design tokens via md_to_pdf.py.

Usage:
    python scripts/verbatim_pdf.py "path/to/handout.md"
    python scripts/verbatim_pdf.py --design claude "path/to/handout.md"
    python scripts/verbatim_pdf.py --out out.pdf "path/to/handout.md"
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from md_to_pdf import clean_title, design_tokens, load_design
from weasyprint import HTML


def inline(text: str) -> str:
    """Escape text and turn **bold** markers into <strong>."""
    out = []
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            out.append(f"<strong>{html.escape(part[2:-2])}</strong>")
        else:
            out.append(html.escape(part))
    return "".join(out)


def parse_verbatim(text: str, stem: str) -> tuple[str, list]:
    """Return (title, sections) preserving all words and list structure.

    Sections are (**Header**, [blocks]); a block is either
    {"kind": "para", "text": ...} or
    {"kind": "list", "items": [{"text": ..., "sub": [...]}, ...]}.
    A plain line following a bullet is a sub-item when it starts at column
    0, or a wrapped continuation when indented; plain lines after a header
    form a paragraph.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    nonempty = [(i, ln.strip()) for i, ln in enumerate(lines) if ln.strip()]
    title = ""
    start = 0
    if (len(nonempty) >= 2 and nonempty[1][1].startswith("**")
            and not nonempty[0][1].startswith(("-", "**", "#"))):
        title = nonempty[0][1]
        start = nonempty[0][0] + 1

    sections: list[tuple[str, list]] = []
    cur_name: str | None = None
    cur_blocks: list[dict] = []
    para_lines: list[str] = []
    cur_list: dict | None = None

    def flush_para() -> None:
        nonlocal para_lines
        if para_lines:
            cur_blocks.append({"kind": "para", "text": " ".join(para_lines)})
            para_lines = []

    def flush_list() -> None:
        nonlocal cur_list
        if cur_list is not None:
            cur_blocks.append(cur_list)
            cur_list = None

    i = start
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("**"):
            block_text = s
            j = i + 1
            if block_text.count("**") % 2 == 1:
                # A section header wrapped across multiple lines.
                while j < len(lines):
                    nxt = lines[j].strip()
                    j += 1
                    if not nxt:
                        continue
                    block_text += " " + nxt
                    if block_text.count("**") % 2 == 0:
                        break
            header_parts = []
            rest = ""
            for m in re.finditer(r"\*\*(.+?)\*\*", block_text):
                header_parts.append(m.group(1))
                rest = block_text[m.end():]
            flush_para()
            flush_list()
            if cur_name is not None:
                sections.append((cur_name, cur_blocks))
                cur_blocks = []
            cur_name = " ".join(header_parts)
            rest = rest.strip()
            if rest:
                para_lines.append(rest)
            i = j
            continue
        if cur_name is None:
            cur_name = "Content"
        if s == "-" or s.startswith("- "):
            flush_para()
            body = (s[2:] if s.startswith("- ") else "").strip()
            if not body:
                i += 1
                continue
            if cur_list is None:
                cur_list = {"kind": "list", "items": []}
            cur_list["items"].append({"text": body, "sub": []})
        elif cur_list is not None:
            last_item = cur_list["items"][-1]
            if lines[i][:1].isspace():
                if last_item["sub"]:
                    last_item["sub"][-1] += " " + s
                else:
                    last_item["text"] += " " + s
            else:
                last_item["sub"].append(s)
        else:
            para_lines.append(s)
        i += 1
    flush_para()
    flush_list()
    if cur_name is not None:
        sections.append((cur_name, cur_blocks))
    return title or clean_title("", stem), sections


def parse_idiom_blocks(text: str, stem: str) -> tuple[str, list]:
    """Parse '# Title' plus '## Category' headers and three-line idiom blocks.

    Every non-header line is grouped into three-line blocks
    (idiom, Chinese gloss, example). Returns a flat list of blocks where each
    block is either ("header", name) or ("entry", en, zh, ex). Malformed
    trailing lines (fewer than three) are dropped so the renderer never shows
    a half-finished entry.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    blocks: list = []
    pending: list[str] = []

    def flush() -> None:
        nonlocal pending
        if len(pending) == 3:
            blocks.append(("entry", pending[0], pending[1], pending[2]))
        pending = []

    for ln in lines:
        if ln.startswith("## "):
            flush()
            blocks.append(("header", ln[3:].strip()))
        else:
            pending.append(ln)
            if len(pending) == 3:
                flush()
    flush()
    return title or clean_title("", stem), blocks


def render_html(title: str, sections: list, tok: dict) -> str:
    body = []
    for name, blocks in sections:
        block_html = []
        for b in blocks:
            if b["kind"] == "para":
                block_html.append(f"<p>{inline(b['text'])}</p>")
            else:
                items = []
                for it in b["items"]:
                    sub = ""
                    if it["sub"]:
                        sub = ("<ul class='sub'>"
                               + "".join(
                                   f"<li>{inline(x)}</li>"
                                   for x in it["sub"])
                               + "</ul>")
                    items.append(f"<li>{inline(it['text'])}{sub}</li>")
                block_html.append("<ul>" + "".join(items) + "</ul>")
        body.append(
            f"<section class='sec'><h2>{html.escape(name)}</h2>"
            + "".join(block_html)
            + "</section>")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><style>
@page {{
  size: A4 portrait;
  margin: 14mm 17mm 18mm 17mm;
  @bottom-right {{
    content: counter(page);
    font: 8pt {tok['font_body']};
    color: {tok['muted']};
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: {tok['canvas']}; }}
body {{
  font-family: {tok['font_body']};
  color: {tok['body']};
  font-size: 10pt;
  line-height: 1.55;
}}
.masthead {{ padding-bottom: 3.5mm; margin-bottom: 6.5mm; }}
h1 {{
  font-family: {tok['font_body']};
  font-weight: 400; font-size: 21pt; color: {tok['ink']};
  line-height: 1.08;
  border-bottom: 2.5pt solid {tok['accent']};
  display: inline-block; padding-bottom: 1.8mm;
}}
.sec {{ margin-top: 5.5mm; break-inside: avoid; page-break-inside: avoid; }}
.sec:first-of-type {{ margin-top: 0; }}
h2 {{
  break-after: avoid; page-break-after: avoid;
  font-family: {tok['font_body']};
  font-size: 11.5pt; font-weight: 600; color: {tok['ink']};
  margin-bottom: 1.8mm;
}}
p {{ margin-bottom: 2mm; text-align: justify; }}
ul {{ list-style: none; margin: 0 0 1.5mm 0; }}
ul > li {{
  padding-left: 5mm; margin-bottom: 1.2mm;
  text-align: justify;
  break-inside: avoid; page-break-inside: avoid;
}}
ul:not(.sub) > li::before {{
  content: "–"; display: inline-block;
  width: 4mm; margin-left: -5mm;
  color: {tok['accent']};
}}
ul.sub {{ margin: 0.7mm 0 1.8mm 0; }}
ul.sub li {{
  padding-left: 9mm; margin-bottom: 0.4mm;
  font-size: 9.3pt; color: {tok['body']};
}}
ul.sub > li::before {{
  content: "·"; display: inline-block;
  width: 4mm; margin-left: -9mm;
  color: {tok['muted']};
}}
</style></head>
<body>
  <div class="masthead"><h1>{html.escape(title)}</h1></div>
  {''.join(body)}
</body></html>"""


def render_idiom_html(title: str, blocks: list,
                      tok: dict, per_page: int = 10) -> str:
    """Minimal black-and-white list: one styled block per idiom, N per page.

    Category headers flow inline between entries; a header is never left at
    the bottom of a full page (it starts the next page instead).
    """
    def entry_count(page_blocks: list) -> int:
        return sum(1 for b in page_blocks if b[0] == "entry")

    pages: list[list] = []
    page: list = []
    for block in blocks:
        if block[0] == "header" and entry_count(page) == per_page:
            pages.append(page)
            page = []
        elif block[0] == "entry" and entry_count(page) == per_page:
            pages.append(page)
            page = []
        page.append(block)
    if page:
        pages.append(page)

    pages_html = []
    for page_blocks in pages:
        items = []
        for block in page_blocks:
            if block[0] == "header":
                items.append(
                    f'<div class="cat">{html.escape(block[1])}</div>')
            else:
                _, en, zh, ex = block
                items.append(
                    '<div class="entry">'
                    f'<div class="id">{inline(en)}</div>'
                    f'<div class="zh">{html.escape(zh)}</div>'
                    f'<div class="ex">{html.escape(ex)}</div>'
                    '</div>')
        pages_html.append('<div class="page">' + "".join(items) + "</div>")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
@page {{
  size: A4 portrait;
  margin: 14mm 17mm 16mm 17mm;
  @bottom-right {{
    content: counter(page);
    font: 8pt {tok['font_body']};
    color: {tok['muted']};
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: {tok['canvas']}; }}
body {{
  font-family: {tok['font_body']};
  color: {tok['body']};
  font-size: 10pt;
  line-height: 1.45;
}}
.masthead {{ padding-bottom: 3.5mm; margin-bottom: 6mm; }}
h1 {{
  font-family: {tok['font_body']};
  font-weight: 400; font-size: 21pt; color: {tok['ink']};
  line-height: 1.08;
  border-bottom: 2.5pt solid {tok['accent']};
  display: inline-block; padding-bottom: 1.8mm;
}}
.page {{ break-after: page; page-break-after: always; }}
.page:last-child {{ break-after: auto; page-break-after: auto; }}
.cat {{
  break-after: avoid; page-break-after: avoid;
  font-size: 12pt; font-weight: 600; color: {tok['ink']};
  margin: 4mm 0 3.2mm 0; padding-bottom: 1.2mm;
  border-bottom: 0.5pt solid {tok['hairline']};
}}
.page > .cat:first-child {{ margin-top: 0; }}
.entry {{
  break-inside: avoid; page-break-inside: avoid;
  margin-bottom: 5mm;
}}
.entry:last-child {{ margin-bottom: 0; }}
.id {{
  font-weight: 700; font-size: 10.5pt; color: {tok['ink']};
}}
.zh {{
  font-size: 9.5pt; color: {tok['muted']};
  margin: 0.5mm 0;
}}
.ex {{
  font-size: 9.5pt; color: {tok['body']};
}}
</style></head>
<body>
  <div class="masthead"><h1>{html.escape(title)}</h1></div>
  {''.join(pages_html)}
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("md_file", type=Path, help="Input .md handout")
    parser.add_argument(
        "--design", default="cal",
        help="Design-system name or DESIGN.md path (default: cal)")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output PDF path (default: next to the MD, same stem)")
    parser.add_argument(
        "--idiom-list", action="store_true",
        help="Parse '# Title', '## Category' headers and three-line idiom "
             "blocks (idiom / gloss / example), N per page.")
    parser.add_argument(
        "--per-page", type=int, default=10,
        help="Idioms per page in --idiom-list mode (default: 10)")
    args = parser.parse_args()

    md_path = args.md_file.resolve()
    if not md_path.exists():
        print(f"File not found: {md_path}", file=sys.stderr)
        return 1
    design = load_design(args.design)
    tok = design_tokens(design)
    text = md_path.read_text(encoding="utf-8-sig")
    if args.idiom_list:
        title, blocks = parse_idiom_blocks(text, md_path.stem)
        final_html = render_idiom_html(title, blocks, tok, args.per_page)
    else:
        title, sections = parse_verbatim(text, md_path.stem)
        final_html = render_html(title, sections, tok)
    out = (args.out.resolve() if args.out else md_path.with_suffix(".pdf"))
    HTML(string=final_html).write_pdf(out)
    pages = len(HTML(string=final_html).render().pages)
    print(f"PDF written: {out}")
    print(f"Title     : {title}")
    print(f"Design    : {design['name']} ({design['source']})")
    if args.idiom_list:
        count = sum(1 for b in blocks if b[0] == "entry")
        print(f"Idioms    : {count}")
    else:
        print(f"Sections  : {len(sections)}")
    print(f"Pages     : {pages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
