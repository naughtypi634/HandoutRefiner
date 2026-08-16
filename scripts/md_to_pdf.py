#!/usr/bin/env python3
"""Render HandoutRefiner MD content into print-ready A4 PDFs.

The visual style comes from the awesome-design-md design-system collection
(local sibling repo ../awesome-design-md/design-md/). The renderer reads the
YAML token frontmatter of the chosen DESIGN.md (colors / typography /
rounded) and maps it onto the worksheet layout -- no ESL Assistant styling.
  - Two A4 pages; header with title + accent rule; footer page number.
  - One row per question: chunked question (question_segments) + answer hint
    on top, bordered scaffold block below; full-width row separator.
  - Scaffold typography only (no labels): keywords regular, phrases italic,
    idioms bold + Chinese gloss, frames with ellipsis.
  - Vocabulary reference sheets (two-column MD tables, no questions) render
    automatically as a table sheet in the same design tokens; sheets with
    both tables and questions render vocab on page 1 and discussion on
    page 2.

Content comes from the MD (source of truth) plus an optional sidecar
"<name>.scaffold.json" that adds segments, hints and scaffolds per question.

Usage:
    python scripts/md_to_pdf.py "path/to/handout.md"
    python scripts/md_to_pdf.py --design claude "path/to/handout.md"
    python scripts/md_to_pdf.py --design notion --questions-only "path/to/handout.md"
    python scripts/md_to_pdf.py "Spoken/English for WeChat.md"  # vocab + discussion

Questions-only variant (no scaffold blocks, elegant question list):
    python scripts/md_to_pdf.py --questions-only "path/to/handout.md"
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml
from weasyprint import HTML


# Local awesome-design-md collection, sibling of the HandoutRefiner repo.
DESIGN_REPO = (Path(__file__).resolve().parents[2]
               / "awesome-design-md" / "design-md")
DEFAULT_DESIGN = "cal"


def font_stack(family: str, generic: str) -> str:
    """Append print-safe fallbacks to a design-system font stack."""
    parts = [p.strip() for p in family.split(",") if p.strip()]
    parts = [p for p in parts if p.lower() not in ("serif", "sans-serif")]
    if generic == "serif":
        fallback = ("Georgia, 'Times New Roman', 'Microsoft YaHei', "
                    "'SimSun', 'Segoe UI Emoji', serif")
    else:
        fallback = ("'Segoe UI', 'Microsoft YaHei', 'PingFang SC', "
                    "'Segoe UI Emoji', sans-serif")
    return ", ".join(parts + [fallback])


def resolve_design_path(spec: str) -> Path:
    """Resolve --design to a DESIGN.md: direct file path or collection name."""
    direct = Path(spec)
    if direct.is_file():
        return direct
    candidate = DESIGN_REPO / spec / "DESIGN.md"
    if candidate.is_file():
        return candidate
    names = sorted(d.name for d in DESIGN_REPO.iterdir()
                   if (d / "DESIGN.md").is_file())
    raise SystemExit(
        f"Design '{spec}' not found. Pass a DESIGN.md path or one of:\n"
        + ", ".join(names))


def load_design(spec: str) -> dict:
    """Load the YAML token frontmatter of a design-system DESIGN.md."""
    path = resolve_design_path(spec)
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
    if not m:
        raise SystemExit(
            f"{path} has no YAML token frontmatter; it cannot be applied "
            "automatically.")
    data = yaml.safe_load(m.group(1)) or {}
    return {
        "name": data.get("name") or path.parent.name,
        "source": str(path),
        "colors": data.get("colors") or {},
        "typography": data.get("typography") or {},
        "rounded": data.get("rounded") or {},
    }


def design_tokens(design: dict) -> dict:
    """Flatten the tokens the worksheet CSS needs, with safe fallbacks."""
    c, t, r = (design["colors"], design["typography"],
               design.get("rounded", {}))
    ink = c.get("ink") or "#111111"
    body = c.get("body") or ink
    surface_soft = c.get("surface-soft") or c.get("surface-card") or "#f5f5f5"
    display = (t.get("display-md") or t.get("display-sm")
               or t.get("title-lg") or {})
    body_face = (t.get("body-md") or t.get("body-sm")
                 or t.get("title-sm") or {})
    return {
        "canvas": c.get("canvas") or "#ffffff",
        "ink": ink,
        "body": body,
        "muted": c.get("muted") or "#777777",
        "hairline": c.get("hairline") or "#dddddd",
        "surface_soft": surface_soft,
        "surface_card": c.get("surface-card") or surface_soft,
        "accent": c.get("primary") or "#0066cc",
        "radius_lg": r.get("lg") or "12px",
        "radius_md": r.get("md") or "8px",
        "font_display": font_stack(
            display.get("fontFamily", "Georgia, 'Times New Roman', serif"),
            "serif"),
        "font_body": font_stack(
            body_face.get("fontFamily",
                          "'Segoe UI', 'Microsoft YaHei', sans-serif"),
            "sans-serif"),
    }


def split_aligned_row(line: str) -> list[str]:
    """Split an aligned-table row into cells on column gaps (>=2 spaces)."""
    return [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]


PIPE_SEP = re.compile(r"^[\s|+\-=]+$")
DASH_SEP = re.compile(r"^[\s\-—]+$")


def parse_md(text: str) -> tuple[str, list[tuple[str, list[dict]]]]:
    """Parse the markdown into (title, [(section_name, items)]).

    Besides questions/paragraphs, two-column reference tables are parsed
    from aligned dash tables and pipe tables as items with
    {"kind": "table", "rows": [[cn, en], ...]}.
    """
    title = ""
    sections: list[tuple[str, list[dict]]] = []
    current: tuple[str, list[dict]] | None = None
    pending = ""
    pending_lines: list[str] = []
    table_rows: list[list[str]] | None = None
    in_aligned = False

    def flush_pending() -> None:
        nonlocal pending, pending_lines
        if not pending or current is None:
            pending = ""
            pending_lines = []
            return
        kind = "question" if "?" in pending else "para"
        current[1].append({"kind": kind, "text": pending})
        pending = ""
        pending_lines = []

    def flush_table() -> None:
        nonlocal table_rows, in_aligned
        if table_rows and current is not None:
            current[1].append({"kind": "table", "rows": table_rows})
        table_rows = None
        in_aligned = False
        pending_lines = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("\\- "):
            line = line[3:].strip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        m = re.fullmatch(r"\*\*(.+?)\*\*", line)
        if m:
            flush_pending()
            flush_table()
            sections.append((m.group(1).strip(), []))
            current = sections[-1]
            continue
        if current is None:
            current = ("Content", [])
            sections.append(current)

        if "|" in line or line.startswith("+"):
            flush_pending()
            if PIPE_SEP.fullmatch(line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if table_rows is None:
                flush_table()
                table_rows = []
            if cells and not cells[0] and len(cells) > 1:
                if table_rows:
                    table_rows[-1][1] = (
                        table_rows[-1][1] + " " + cells[1]).strip()
            else:
                table_rows.append([cells[0] if cells else "",
                                   " ".join(cells[1:]).strip()])
            in_aligned = False
            continue

        if DASH_SEP.fullmatch(line):
            runs = re.findall(r"-+", line)
            if len(runs) >= 2 and table_rows is None:
                rows_buf: list[list[str]] = []
                for bl in pending_lines:
                    cells = split_aligned_row(bl)
                    if len(cells) >= 2:
                        rows_buf.append(cells)
                    elif cells and rows_buf:
                        rows_buf[-1][-1] = (
                            rows_buf[-1][-1] + " " + cells[0]).strip()
                if rows_buf:
                    table_rows = rows_buf
                    pending = ""
                    pending_lines = []
            flush_pending()
            if len(runs) >= 2:
                if table_rows is None:
                    table_rows = []
                in_aligned = True
            continue

        if in_aligned:
            flush_pending()
            cells = split_aligned_row(line)
            if len(cells) >= 2:
                if table_rows is None:
                    table_rows = []
                table_rows.append(cells)
                continue
            if cells and table_rows:
                table_rows[-1][-1] = (
                    table_rows[-1][-1] + " " + cells[0]).strip()
                continue
            flush_table()

        if re.fullmatch(r"[\-–—.…\s]+", line):
            continue
        items = current[1]
        if line.startswith("- "):
            flush_pending()
            body = line[2:].strip()
            vocab = re.match(r"^(.*?)\s*\(([a-z]+)\)\s*[:：]\s*(.+)$", body, re.I)
            if vocab:
                items.append({"kind": "vocab", "term": vocab.group(1).strip(),
                              "def": vocab.group(3).strip()})
            else:
                pending = body
                if pending.endswith(("?", ".", "!")):
                    flush_pending()
        else:
            pending = f"{pending} {line}".strip()
            pending_lines.append(line)
            if pending.endswith(("?", ".", "!")):
                flush_pending()
    flush_table()
    flush_pending()

    return title, sections


def clean_title(title: str, stem: str) -> str:
    """Prefer an in-document title, otherwise clean the file stem."""
    if title.strip():
        return title.strip()
    clean = re.sub(r"^(ESL|BEC)[-—:： ]*", "", stem, flags=re.I)
    return clean.strip() or stem


def norm(text: str) -> str:
    return " ".join(text.split())


def display_text(text: str) -> str:
    """Remove Markdown emphasis markers from visible PDF text."""
    return re.sub(r"[*_~]+", "", text)


def semantic_segments(text: str) -> list[str]:
    """Split only at complete clauses or an explicit either/or choice."""
    clean = display_text(text)
    segments = re.split(r"(?<=\?)\s+", clean)
    if "Would you rather" in clean:
        segments = re.split(r"\s+(?=or\b)", clean, maxsplit=1)
    return [segment.strip() for segment in segments if segment.strip()]


def load_scaffolds(md_path: Path) -> dict:
    sidecar = md_path.with_suffix(".scaffold.json")
    if not sidecar.exists():
        return {"groups": [], "scaffolds": {}, "lead_in": "", "curated": False}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data.setdefault("scaffolds", {})
    data.setdefault("lead_in", "")
    data.setdefault("curated", False)
    data["scaffolds"] = {norm(k): v for k, v in data["scaffolds"].items()}
    return data


def build_questions(sections, scaffold_data: dict) -> list[dict]:
    """Return ordered questions with their scaffolds, in MD order."""
    scaffolds = scaffold_data["scaffolds"]
    ordered = []
    covered = set()
    for group in scaffold_data.get("groups", []):
        for qtext in group.get("questions", []):
            key = norm(qtext)
            ordered.append({"text": qtext, "scaffold": scaffolds.get(key)})
            covered.add(key)
    if scaffold_data.get("curated"):
        return ordered
    for _, items in sections:
        for item in items:
            if item["kind"] == "question" and norm(item["text"]) not in covered:
                ordered.append({"text": item["text"], "scaffold": None})
                covered.add(norm(item["text"]))
    return ordered


def build_sections_questions(sections) -> list[tuple[str, list[str]]]:
    """Return (section, [question texts]) pairs for questions-only output."""
    groups = []
    for name, items in sections:
        qs = [item["text"] for item in items
              if item["kind"] in ("question", "bullet")
              and "?" in item["text"]]
        if qs:
            groups.append((name, qs))
    return groups


def scaffold_lines(scaffold: dict | None) -> str:
    if not scaffold:
        return ""
    lines = []
    if scaffold.get("words"):
        items = " · ".join(f'<span class="item">{html.escape(w)}</span>'
                           for w in scaffold["words"])
        lines.append(f'<div class="sline">{items}</div>')
    if scaffold.get("phrases"):
        items = " · ".join(f'<span class="item ph">{html.escape(p)}</span>'
                           for p in scaffold["phrases"])
        lines.append(f'<div class="sline ph">{items}</div>')
    idioms = scaffold.get("idioms") or []
    if not idioms and scaffold.get("idiom"):
        idioms = [scaffold["idiom"]]
    if idioms:
        items = " · ".join(
            f'<span class="item id">{html.escape(i["text"])}</span>'
            f'<span class="zh">{html.escape(i.get("gloss", ""))}</span>'
            for i in idioms if i.get("text")
        )
        lines.append(f'<div class="sline id">{items}</div>')
    return "".join(lines)


def question_row(q: dict) -> str:
    scaffold = q.get("scaffold") or {}
    segs = scaffold.get("segments") or semantic_segments(q["text"])
    seg_html = " ".join(
        f'<span class="seg">{html.escape(display_text(s))}</span>' for s in segs
    )
    parts = [f'<div class="q">{seg_html}</div>']
    if scaffold.get("hint"):
        parts.append(
            f'<div class="hint"><b>回答路线：</b>{html.escape(scaffold["hint"])}</div>'
        )
    parts.append(f'<div class="sblock">{scaffold_lines(scaffold)}</div>')
    return f'<div class="row">{"" .join(parts)}</div>'


def render_sheet(title: str, rows_html: str, page_no: int) -> str:
    return f"""<div class="sheet">
  <div class="header"><h1>{html.escape(title)}</h1></div>
  <div class="rows">
    {rows_html}
  </div>
</div>"""


def worksheet_css(tok: dict, q_font: float, scaf_font: float,
                  gap: float) -> str:
    return f"""
@page {{
    size: A4 portrait;
    margin: 8mm 0 24mm 0;
  @bottom-right {{
    content: counter(page);
    font-size: 7.2pt; color: {tok['muted']}; margin-right: 15mm;
    font-family: {tok['font_body']};
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: {tok['canvas']}; }}
body {{
  font-family: {tok['font_body']};
  color: {tok['body']};
}}
.sheet {{
    width: 210mm; background: {tok['canvas']};
    padding: 0 10mm;
}}
.sheet:not(:last-child) {{
    break-after: page;
    page-break-after: always;
}}
.header {{
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1pt solid {tok['hairline']};
  padding-bottom: 2.5mm; margin-bottom: 3mm;
}}
.header h1 {{
  font-family: {tok['font_display']};
  font-size: 17pt; font-weight: 400;
  color: {tok['ink']};
  border-bottom: 2.5pt solid {tok['accent']};
  display: inline-block; padding-bottom: 1mm;
}}
.rows {{ display: block; }}
.row {{
    display: block; margin-bottom: {gap}mm;
  padding-bottom: 2.6mm;
    break-inside: avoid; page-break-inside: avoid;
}}
.row:last-child {{ padding-bottom: 0; }}
.q {{
    font-size: {q_font}pt; font-weight: 500; line-height: 1.35;
    color: {tok['ink']};
    white-space: nowrap;
}}
.seg {{
    display: inline-block; border: 1pt solid {tok['hairline']};
    background: {tok['surface_soft']}; border-radius: {tok['radius_md']};
    padding: 0 .5mm; margin: 0 .6mm 0 0;
}}
.hint {{ font-size: 8.5pt; color: {tok['muted']}; margin-top: 1mm; }}
.hint b {{ font-weight: 600; color: {tok['accent']}; }}
.sblock {{
  background: {tok['surface_card']}; border: 1pt solid {tok['hairline']};
  border-radius: {tok['radius_lg']}; padding: 2.4mm 2.8mm;
    margin-top: 1.5mm;
  font-family: {tok['font_body']};
  color: {tok['body']}; font-size: {scaf_font}pt; line-height: 1.5;
}}
.sline {{ margin-bottom: 1mm; }}
.sline:last-child {{ margin-bottom: 0; }}
.ph {{ font-style: italic; }}
.id {{ font-weight: 700; color: {tok['ink']}; }}
.id .zh {{ font-weight: 400; color: {tok['muted']}; }}
.zh {{ color: {tok['muted']}; margin-left: .8mm; }}
"""


def questions_css(tok: dict, q_font: float, lh: float, gap: float) -> str:
    h2_font = q_font + 2.5
    return f"""
@page {{
  size: A4 portrait;
    margin: 15mm 18mm 20mm 18mm;
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
  font-size: {q_font}pt;
}}
.masthead {{
    border-bottom: 1pt solid {tok['hairline']};
    padding-bottom: 4mm; margin-bottom: 8mm;
}}
h1 {{
    font-family: {tok['font_display']};
    font-weight: 400; font-size: 24pt; color: {tok['ink']};
    line-height: 1.05;
    border-bottom: 2.5pt solid {tok['accent']};
    display: inline-block; padding-bottom: 2mm;
}}
.sec {{ margin-top: 7mm; }}
.sec:first-of-type {{ margin-top: 0; }}
h2 {{
  break-after: avoid; page-break-after: avoid;
    font-family: {tok['font_display']};
    font-size: {h2_font:.1f}pt; font-weight: 500; color: {tok['ink']};
    margin-bottom: 3mm;
}}
ol {{ list-style: none; counter-reset: q; }}
li {{
    display: flex; align-items: baseline; gap: 3mm;
    counter-increment: q;
    margin-bottom: {gap:.2f}mm; line-height: {lh}; text-align: left;
}}
li:last-child {{ margin-bottom: 0; }}
li::before {{
    content: counter(q) ".";
    flex: 0 0 7mm; font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: {tok['accent']};
}}
.qt {{ flex: 1; color: {tok['ink']}; }}
"""


def tables_css(tok: dict, body_font: float) -> str:
    return f"""
@page {{
  size: A4 portrait;
  margin: 14mm 16mm 18mm 16mm;
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
  font-size: {body_font}pt;
}}
.masthead {{
  border-bottom: 1pt solid {tok['hairline']};
  padding-bottom: 3.5mm; margin-bottom: 6mm;
}}
h1 {{
  font-family: {tok['font_display']};
  font-weight: 400; font-size: 22pt; color: {tok['ink']};
  line-height: 1.08;
  border-bottom: 2.5pt solid {tok['accent']};
  display: inline-block; padding-bottom: 1.5mm;
}}
.sec {{ margin-bottom: 5mm; }}
h2 {{
  break-after: avoid; page-break-after: avoid;
  font-family: {tok['font_display']};
  font-size: 13pt; font-weight: 500; color: {tok['ink']};
  margin: 0 0 2.2mm 0;
}}
table {{ width: 100%; border-collapse: collapse; }}
tr {{ break-inside: avoid; page-break-inside: avoid; }}
td {{
  border: 0.55pt solid {tok['hairline']};
  padding: 1.3mm 2.4mm; vertical-align: top;
  line-height: 1.35;
}}
td.cn {{ width: 40%; color: {tok['ink']}; }}
td.en {{ width: 60%; color: {tok['body']}; }}
tr:nth-child(even) td {{ background: {tok['surface_soft']}; }}
"""


def render_tables_html(title: str, sections, design: dict,
                       body_font: float = 9.0) -> str:
    """Table reference sheet: masthead + per-section two-column tables."""
    tok = design_tokens(design)
    sections_html = []
    for name, items in sections:
        tables = [it for it in items if it.get("kind") == "table"]
        if not tables:
            continue
        rows = []
        for it in tables:
            for row in it["rows"]:
                cn = html.escape(row[0])
                en = html.escape(row[1] if len(row) > 1 else "")
                rows.append(f'<tr><td class="cn">{cn}</td>'
                            f'<td class="en">{en}</td></tr>')
        sections_html.append(
            f'<section class="sec"><h2>{html.escape(name)}</h2>'
            f'<table>{"".join(rows)}</table></section>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
{tables_css(tok, body_font)}
</style></head>
<body>
  <div class="masthead">
    <h1>{html.escape(title)}</h1>
  </div>
  {''.join(sections_html)}
</body></html>"""


def hybrid_css(tok: dict, table_font: float, q_font: float,
               li_margin: float = 6.0) -> str:
    return f"""
@page {{
  size: A4 portrait;
  margin: 11mm 13mm 16mm 13mm;
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
  font-size: {q_font}pt;
}}
.sheet {{
  break-after: page;
  page-break-after: always;
}}
.sheet:last-child {{
  break-after: auto;
  page-break-after: auto;
}}
.masthead {{
  padding-bottom: 2.2mm; margin-bottom: 3.0mm;
}}
h1 {{
  font-family: {tok['font_display']};
  font-weight: 400; font-size: 18pt; color: {tok['ink']};
  line-height: 1.08;
  border-bottom: 2.5pt solid {tok['accent']};
  display: inline-block; padding-bottom: 1.2mm;
}}
.tables {{
  display: flex;
  flex-wrap: wrap;
}}
.sec {{
  width: 48.5%;
  margin: 0 1.2mm 1.2mm 0;
  break-inside: avoid;
  page-break-inside: avoid;
}}
.sec:nth-child(2n) {{
  margin-right: 0;
}}
h2 {{
  break-after: avoid; page-break-after: avoid;
  font-family: {tok['font_display']};
  font-size: 11pt; font-weight: 500; color: {tok['ink']};
  margin: 0 0 1.0mm 0;
}}
table {{ width: 100%; border-collapse: collapse; }}
tr {{ break-inside: avoid; page-break-inside: avoid; }}
td {{
  border: 0.5pt solid {tok['hairline']};
  padding: 0.4mm 1.4mm; vertical-align: top;
  font-size: {table_font}pt; line-height: 1.1;
  white-space: nowrap;
}}
td.cn {{ width: 36%; color: {tok['ink']}; }}
td.en {{ width: 64%; color: {tok['body']}; }}
tr:nth-child(even) td {{ background: {tok['surface_soft']}; }}
ol {{ list-style: none; }}
li {{
  margin-bottom: {li_margin:.1f}mm; line-height: 1.45;
}}
.qt {{ color: {tok['ink']}; white-space: nowrap; }}
"""


def render_hybrid_html(title: str, sections, design: dict,
                       table_font: float, q_font: float) -> str:
    """Two-page sheet: page 1 vocab tables, page 2 discussion questions."""
    tok = design_tokens(design)
    tables_html = []
    for name, items in sections:
        tables = [it for it in items if it.get("kind") == "table"]
        if not tables:
            continue
        rows = []
        for it in tables:
            for row in it["rows"]:
                cn = html.escape(row[0])
                en = html.escape(row[1] if len(row) > 1 else "")
                rows.append(f'<tr><td class="cn">{cn}</td>'
                            f'<td class="en">{en}</td></tr>')
        tables_html.append(
            f'<section class="sec"><h2>{html.escape(name)}</h2>'
            f'<table>{"".join(rows)}</table></section>')
    questions = [it["text"] for _, items in sections
                 for it in items if it["kind"] == "question"]
    n = len(questions)
    line_h = q_font * 0.3528 * 1.45
    start_mm = 24.0
    target_mm = 297.0 * 0.8
    li_margin = (max(0.0, target_mm - start_mm - n * line_h)
                 / max(1, n - 1)) if n > 1 else 8.0
    q_items = "".join(
        f'<li><span class="qt">{html.escape(q)}</span></li>' for q in questions)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
{hybrid_css(tok, table_font, q_font, li_margin)}
</style></head>
<body>
  <div class="sheet">
    <div class="masthead"><h1>{html.escape(title)}</h1></div>
    <div class="tables">{''.join(tables_html)}</div>
  </div>
  <div class="sheet">
    <div class="masthead"><h1>Discussion</h1></div>
    <ol>{q_items}</ol>
  </div>
</body></html>"""


def render_html(title: str, questions, q_font: float,
                scaf_font: float, gap: float, design: dict) -> str:
    tok = design_tokens(design)
    half = (len(questions) + 1) // 2
    page1 = "".join(question_row(q) for q in questions[:half])
    page2 = "".join(question_row(q) for q in questions[half:])
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
{worksheet_css(tok, q_font, scaf_font, gap)}
</style></head>
<body>
    {render_sheet(title, page1, 1)}
    {render_sheet(title, page2, 2)}
</body></html>"""


def render_questions_html(title: str, groups, q_font: float,
                          lh: float, gap: float, design: dict) -> str:
    """Questions-only layout: design-system masthead, numbered sections."""
    tok = design_tokens(design)
    sections_html = []
    for name, qs in groups:
        items = []
        for question in qs:
            items.append(
                f'<li><span class="qt">{html.escape(question)}</span></li>')
        sections_html.append(
            f'<section class="sec">'
            f'<h2>{html.escape(name)}</h2>'
            f'<ol>{"".join(items)}</ol></section>'
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><style>
{questions_css(tok, q_font, lh, gap)}
</style></head>
<body>
  <div class="masthead">
    <h1>{html.escape(title)}</h1>
  </div>
  {''.join(sections_html)}
</body></html>"""


def page_count(html_str: str) -> int:
    return len(HTML(string=html_str).render().pages)


def fit_layout(render) -> tuple[float, float, float]:
    """Find q/scaffold font sizes and row gap that yield exactly 2 pages."""
    for q_font, scaf_font in [(11.0, 8.0), (10.5, 8.0), (11.0, 7.5),
                              (10.5, 7.5), (10.0, 7.5), (10.0, 7.0)]:
        lo, hi = 2.0, 6.0
        if render(q_font, scaf_font, 2.0) > 2:
            continue
        best = 2.0
        while hi - lo > 0.25:
            mid = (lo + hi) / 2
            pages = render(q_font, scaf_font, mid)
            if pages <= 2:
                best = mid
                lo = mid
            else:
                hi = mid
        if render(q_font, scaf_font, best) == 2:
            return q_font, scaf_font, best
    return 10.0, 7.0, 2.0


def one_line_max_font(questions: list[str]) -> float:
    """Largest font (pt) that keeps every question on a single line."""
    width_pt = 176.0 * 72.0 / 25.4  # A4 210mm minus 17mm side margins
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(r"C:\Windows\Fonts\calibri.ttf")
        cmap = font.getBestCmap()
        upem = font["head"].unitsPerEm
        hmtx = font["hmtx"]
        fallback = cmap.get(ord(" "))
        max_ratio = 0.0
        for q in questions:
            width = sum(hmtx[cmap.get(ord(ch), fallback)][0] for ch in q)
            max_ratio = max(max_ratio, width / upem)
        return width_pt * 0.96 / max_ratio
    except Exception:
        return 11.0


def fit_questions_layout(render, questions) -> tuple[float, float, float]:
    """Find a readable font and the largest gap that still fit two pages."""
    for q_font in (11.0, 10.5, 10.0, 9.5):
        lh = 1.38
        if render(q_font, lh, 1.0) > 2:
            continue
        lo, hi, best = 1.0, 8.0, 1.0
        while hi - lo > 0.1:
            mid = (lo + hi) / 2
            if render(q_font, lh, mid) <= 2:
                best = mid
                lo = mid
            else:
                hi = mid
        if render(q_font, lh, best) == 2:
            return q_font, lh, best
    return 9.5, 1.35, 1.0


def fit_tables_layout(render) -> float:
    """Largest readable table font that still fits two pages."""
    for body_font in (9.5, 9.0, 8.5, 8.0):
        if render(body_font) <= 2:
            return body_font
    return 9.0


def hybrid_cells_fit(rows: list[tuple[str, str]], table_font: float) -> bool:
    """True if every cn/en cell fits its column on one line at this font."""
    try:
        from PIL import ImageFont
    except ImportError:
        return True
    cn_mm = 184.0 * 0.485 * 0.36 - 3.4
    en_mm = 184.0 * 0.485 * 0.64 - 3.4
    fonts: dict[str, object] = {}

    def width(text: str) -> float:
        total = 0.0
        for ch in text:
            key = "cjk" if ord(ch) >= 0x2E80 else "latin"
            f = fonts.get(key)
            if f is None:
                path = (r"C:\Windows\Fonts\msyh.ttc" if key == "cjk"
                        else r"C:\Windows\Fonts\segoeui.ttf")
                f = ImageFont.truetype(path, 100)
                fonts[key] = f
            total += f.getlength(ch)
        return total * table_font / 100.0 * 25.4 / 72.0

    return all(width(cn) <= cn_mm and width(en) <= en_mm
               for cn, en in rows)


def hybrid_layout_issues(path: Path, n_questions: int) -> int:
    """Return bitmask: 1 = page-1 text overflows, 2 = page-2 wraps/overflows."""
    try:
        import pdfplumber
    except ImportError:
        return 0
    right = 595.2756 - 13.0 * 72 / 25.4 + 2.0
    issues = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 2:
            return 3
        for w in pdf.pages[0].extract_words():
            if w["x1"] > right:
                issues |= 1
                break
        words2 = pdf.pages[1].extract_words()
        for w in words2:
            if w["x1"] > right:
                issues |= 2
                break
        disc_top = next((w["bottom"] for w in words2
                         if w["text"] == "Discussion"), None)
        if disc_top is not None:
            q_words = [w for w in words2
                       if w["top"] >= disc_top - 2 and w["bottom"] < 780]
            tops = {round(w["top"]) for w in q_words}
            if len(tops) != n_questions:
                issues |= 2
    return issues


def fit_hybrid_layout(render, rows) -> tuple[float, float]:
    """Find table/discussion fonts that yield exactly two pages."""
    for table_font in (12.0, 11.5, 11.0, 10.5, 10.0, 9.5, 9.0, 8.5,
                       8.0, 7.5, 7.0, 6.5, 6.0):
        if not hybrid_cells_fit(rows, table_font):
            continue
        for q_font in (11.0, 10.5, 10.0):
            if render(table_font, q_font) == 2:
                return table_font, q_font
    return 10.5, 10.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("md_file", type=Path, help="Input .md handout")
    parser.add_argument(
        "--design", default=DEFAULT_DESIGN,
        help="Design-system name in ../awesome-design-md/design-md/ or a "
             f"DESIGN.md path (default: {DEFAULT_DESIGN})")
    parser.add_argument("--keep-html", action="store_true",
                        help="Also write the final HTML to the temp dir (QA).")
    parser.add_argument("--questions-only", action="store_true",
                        help="Render only the questions (no scaffold blocks).")
    args = parser.parse_args()

    md_path = args.md_file.resolve()
    if not md_path.exists():
        print(f"File not found: {md_path}", file=sys.stderr)
        return 1
    design = load_design(args.design)

    text = md_path.read_text(encoding="utf-8-sig")
    md_title, sections = parse_md(text)
    title = clean_title(md_title, md_path.stem)
    has_questions = any(
        item["kind"] == "question"
        for _, items in sections for item in items)
    has_tables = any(
        item["kind"] == "table"
        for _, items in sections for item in items)
    has_scaffold = md_path.with_suffix(".scaffold.json").exists()
    if has_tables and not has_scaffold and not args.questions_only:
        if has_questions:
            # Hybrid: page 1 vocab tables, page 2 discussion questions.
            all_rows = [(r[0], r[1] if len(r) > 1 else "")
                        for _, items in sections
                        for it in items if it["kind"] == "table"
                        for r in it["rows"]]
            count = sum(1 for _, items in sections
                        for it in items if it["kind"] == "question")

            def render(table_font, q_font):
                return page_count(render_hybrid_html(
                    title, sections, design, table_font, q_font))

            table_font, q_font = fit_hybrid_layout(render, all_rows)
            out = md_path.with_suffix(".pdf")
            for _ in range(6):
                final_html = render_hybrid_html(
                    title, sections, design, table_font, q_font)
                HTML(string=final_html).write_pdf(out)
                issues = hybrid_layout_issues(out, count)
                if not issues:
                    break
                if issues & 1:
                    table_font = max(6.0, table_font - 0.5)
                if issues & 2:
                    q_font = max(8.0, q_font - 0.5)
            layout_desc = f"table {table_font}pt + discussion {q_font}pt"
        else:
            # Tables-only vocabulary reference sheet.
            def render(body_font):
                return page_count(render_tables_html(
                    title, sections, design, body_font))

            body_font = fit_tables_layout(render)
            final_html = render_tables_html(
                title, sections, design, body_font)
            layout_desc = f"table {body_font}pt"
            count = sum(len(it["rows"]) for _, items in sections
                        for it in items if it["kind"] == "table")
        pages = page_count(final_html)
        out = md_path.with_suffix(".pdf")
        HTML(string=final_html).write_pdf(out)
        print(f"PDF written: {out}")
        print(f"Title     : {title}")
        print(f"Design    : {design['name']} ({design['source']})")
        print(f"Questions : {count}")
        print(f"Layout    : {layout_desc}")
        print(f"Pages     : {pages}")
        if args.keep_html:
            html_out = Path(tempfile.gettempdir()) / (md_path.stem + ".qa.html")
            html_out.write_text(final_html, encoding="utf-8")
            print(f"HTML kept : {html_out}")
        return 0 if pages >= 1 else 2
    if args.questions_only:
        groups = build_sections_questions(sections)
        flat = [q for _, qs in groups for q in qs]

        def render(q_font, lh, gap):
            return page_count(render_questions_html(
                title, groups, q_font, lh, gap, design))

        q_font, lh, gap = fit_questions_layout(render, flat)
        final_html = render_questions_html(
            title, groups, q_font, lh, gap, design)
        layout_desc = f"q {q_font}pt, line-height {lh}, row gap {gap:.1f}mm"
    else:
        scaffold_data = load_scaffolds(md_path)
        questions = build_questions(sections, scaffold_data)

        def render(q_font, scaf_font, gap):
            return page_count(
                render_html(
                    title, questions, q_font, scaf_font, gap, design))

        q_font, scaf_font, gap = fit_layout(render)
        final_html = render_html(
            title, questions, q_font, scaf_font, gap, design)
        layout_desc = (f"q {q_font}pt, scaffold {scaf_font}pt, "
                       f"row gap {gap:.1f}mm")
    pages = page_count(final_html)
    out = md_path.with_suffix(".pdf")
    HTML(string=final_html).write_pdf(out)

    print(f"PDF written: {out}")
    print(f"Title     : {title}")
    print(f"Design    : {design['name']} ({design['source']})")
    count = (sum(len(qs) for _, qs in groups)
             if args.questions_only else len(questions))
    print(f"Questions : {count}")
    print(f"Layout    : {layout_desc}")
    print(f"Pages     : {pages}")
    if args.keep_html:
        html_out = Path(tempfile.gettempdir()) / (md_path.stem + ".qa.html")
        html_out.write_text(final_html, encoding="utf-8")
        print(f"HTML kept : {html_out}")
    return 0 if pages >= 1 else 2


if __name__ == "__main__":
    sys.exit(main())
