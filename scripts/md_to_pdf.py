#!/usr/bin/env python3
"""Render HandoutRefiner MD content into the ESL Assistant V2 PDF format.

The layout mirrors the reference worksheet (ESL Assistant Version2, e.g.
spoken/habits/B1/Habits.pdf):
  - Two A4 pages; header with title + italic lead-in; footer page number.
  - One row per question: chunked question (question_segments) + answer hint
    on top, bordered scaffold block below; full-width row separator.
  - Scaffold typography only (no labels): keywords regular, phrases italic,
    idioms bold + Chinese gloss, frames with ellipsis.
  - Black-and-white, no fills, no icons.

Content comes from the MD (source of truth) plus an optional sidecar
"<name>.scaffold.json" that adds segments, hints and scaffolds per question.

Usage:
    python scripts/md_to_pdf.py "path/to/handout.md"

Questions-only variant (no scaffold blocks, elegant black-and-white list):
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

from weasyprint import HTML


def parse_md(text: str) -> tuple[str, list[tuple[str, list[dict]]]]:
    """Parse the markdown into (title, [(section_name, items)])."""
    title = ""
    sections: list[tuple[str, list[dict]]] = []
    current: tuple[str, list[dict]] | None = None
    pending = ""

    def flush_pending() -> None:
        nonlocal pending
        if not pending or current is None:
            pending = ""
            return
        kind = "question" if pending.endswith("?") else "para"
        current[1].append({"kind": kind, "text": pending})
        pending = ""

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
            sections.append((m.group(1).strip(), []))
            current = sections[-1]
            continue
        if current is None:
            current = ("Content", [])
            sections.append(current)
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
                items.append({"kind": "bullet", "text": body})
        else:
            pending = f"{pending} {line}".strip()
            if pending.endswith(("?", ".", "!")):
                flush_pending()
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
    idiom = scaffold.get("idiom")
    if idiom and idiom.get("text"):
        gloss = html.escape(idiom.get("gloss", ""))
        lines.append(
            f'<div class="sline id"><span class="item id">'
            f'{html.escape(idiom["text"])}</span><span class="zh">{gloss}</span></div>'
        )
    if scaffold.get("frames"):
        items = " · ".join(f'<span class="item fr">{html.escape(f)}</span>'
                           for f in scaffold["frames"])
        lines.append(f'<div class="sline fr">{items}</div>')
    return "".join(lines)


def question_row(q: dict) -> str:
    scaffold = q.get("scaffold") or {}
    segs = scaffold.get("segments") or [q["text"]]
    seg_html = " ".join(f'<span class="seg">{html.escape(s)}</span>' for s in segs)
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


def render_html(title: str, questions, q_font: float,
                scaf_font: float, gap: float) -> str:
    half = (len(questions) + 1) // 2
    page1 = "".join(question_row(q) for q in questions[:half])
    page2 = "".join(question_row(q) for q in questions[half:])
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
@page {{
  size: A4 portrait;
  margin: 0 0 24mm 0;
  @bottom-right {{
    content: counter(page) " / " counter(pages);
    font-size: 7.2pt; color: #777; margin-right: 15mm;
    font-family: "Microsoft YaHei", "SimHei", sans-serif;
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: #ffffff; }}
body {{
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  color: #111;
}}
.sheet {{
  width: 210mm; min-height: 273mm; background: #fff;
  padding: 9mm 10mm 0;
  display: flex; flex-direction: column; page-break-after: always;
}}
.sheet:last-child {{ page-break-after: auto; }}
.header {{
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1.2pt solid #000; padding-bottom: 2mm; margin-bottom: 3mm;
}}
.header h1 {{ font-size: 15pt; letter-spacing: .3px; }}
.rows {{ display: flex; flex-direction: column; gap: {gap}mm; flex: 1; }}
.row {{
  display: flex; flex-direction: column; gap: 1.6mm;
  padding-bottom: 2.6mm;
}}
.row:last-child {{ padding-bottom: 0; }}
.qblock {{ padding: 0; }}
.q {{ font-size: {q_font}pt; font-weight: 600; line-height: 1.5; }}
.seg {{
  display: inline-block; border: .15mm solid #666; border-radius: .6mm;
  padding: 0 .35mm; margin: 0 .4mm .4mm 0;
}}
.hint {{ font-size: 8.5pt; color: #777; margin-top: 1mm; }}
.hint b {{ font-weight: 600; }}
.sblock {{
  border: .35mm solid #000; padding: 2.4mm 2.8mm;
  color: #333; font-size: {scaf_font}pt; line-height: 1.5;
}}
.sline {{ margin-bottom: 1mm; }}
.sline:last-child {{ margin-bottom: 0; }}
.ph {{ font-style: italic; }}
.id {{ font-weight: 700; }}
.id .zh {{ font-weight: 400; }}
.zh {{ color: #333; font-size: {scaf_font}pt; margin-left: .8mm; }}
.fr {{ }}
</style></head>
<body>
  {render_sheet(title, page1, 1)}
  {render_sheet(title, page2, 2)}
</body></html>"""


def render_questions_html(title: str, groups, q_font: float,
                          lh: float, gap: float) -> str:
    """Questions-only layout: masthead, numbered sections, plain questions."""
    h2_font = q_font + 1.0
    sections_html = []
    for idx, (name, qs) in enumerate(groups, start=1):
        items = "".join(
            f'<li><span class="qt">{html.escape(q)}</span></li>' for q in qs
        )
        sections_html.append(
            f'<section class="sec">'
            f'<h2>{html.escape(name)}</h2>'
            f'<ol>{"".join(items)}</ol></section>'
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><style>
@page {{
  size: A4 portrait;
  margin: 16mm 17mm 21mm 17mm;
  @bottom-right {{
    content: counter(page) "/" counter(pages);
    font: 7.5pt "Calibri", "Microsoft YaHei", sans-serif;
    color: #777;
  }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: #fff; }}
body {{
  font-family: "Calibri", "Microsoft YaHei", sans-serif;
  color: #111;
  font-size: {q_font}pt;
}}
.masthead {{
  padding-bottom: 1mm; margin-bottom: 6mm;
}}
h1 {{
  font-family: "Georgia", serif; font-weight: normal;
  font-size: 24pt; color: #000; line-height: 1.05;
  text-align: center;
}}
.sec {{ margin-top: 6mm; }}
h2 {{
  break-after: avoid; page-break-after: avoid;
  font-family: "Georgia", serif; font-size: {h2_font:.1f}pt; font-weight: bold;
  color: #000; margin-bottom: 2.8mm; padding-bottom: 1.3mm;
  border-bottom: .5pt solid #000;
}}
ol {{ list-style: none; }}
li {{
  margin-bottom: {gap:.2f}mm;
  line-height: {lh}; text-align: left;
}}
li:last-child {{ margin-bottom: 0; }}
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
    """Largest one-line font and widest row gap that still yield 2 pages."""
    max_font = one_line_max_font(questions)
    fonts = [max_font]
    f = max_font
    while f - 0.5 > 9.0:
        f -= 0.5
        fonts.append(round(f, 1))
    for q_font in fonts:
        lh = 1.5
        if render(q_font, lh, 0.5) > 2:
            continue
        lo, hi, best = 0.5, 20.0, 0.5
        while hi - lo > 0.1:
            mid = (lo + hi) / 2
            if render(q_font, lh, mid) <= 2:
                best = mid
                lo = mid
            else:
                hi = mid
        if render(q_font, lh, best) == 2:
            return q_font, lh, best
    return 9.5, 1.45, 3.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("md_file", type=Path, help="Input .md handout")
    parser.add_argument("--keep-html", action="store_true",
                        help="Also write the final HTML to the temp dir (QA).")
    parser.add_argument("--questions-only", action="store_true",
                        help="Render only the questions (no scaffold blocks).")
    args = parser.parse_args()

    md_path = args.md_file.resolve()
    if not md_path.exists():
        print(f"File not found: {md_path}", file=sys.stderr)
        return 1

    text = md_path.read_text(encoding="utf-8-sig")
    md_title, sections = parse_md(text)
    title = clean_title(md_title, md_path.stem)
    if args.questions_only:
        groups = build_sections_questions(sections)
        flat = [q for _, qs in groups for q in qs]

        def render(q_font, lh, gap):
            return page_count(render_questions_html(
                title, groups, q_font, lh, gap))

        q_font, lh, gap = fit_questions_layout(render, flat)
        final_html = render_questions_html(title, groups, q_font, lh, gap)
        layout_desc = f"q {q_font}pt, line-height {lh}, row gap {gap:.1f}mm"
    else:
        scaffold_data = load_scaffolds(md_path)
        questions = build_questions(sections, scaffold_data)

        def render(q_font, scaf_font, gap):
            return page_count(
                render_html(title, questions, q_font, scaf_font, gap))

        q_font, scaf_font, gap = fit_layout(render)
        final_html = render_html(title, questions, q_font, scaf_font, gap)
        layout_desc = (f"q {q_font}pt, scaffold {scaf_font}pt, "
                       f"row gap {gap:.1f}mm")
    pages = page_count(final_html)
    out = md_path.with_suffix(".pdf")
    HTML(string=final_html).write_pdf(out)

    print(f"PDF written: {out}")
    print(f"Title     : {title}")
    count = (sum(len(qs) for _, qs in groups)
             if args.questions_only else len(questions))
    print(f"Questions : {count}")
    print(f"Layout    : {layout_desc}")
    print(f"Pages     : {pages}")
    if args.keep_html:
        html_out = Path(tempfile.gettempdir()) / (md_path.stem + ".qa.html")
        html_out.write_text(final_html, encoding="utf-8")
        print(f"HTML kept : {html_out}")
    return 0 if pages == 2 else 2


if __name__ == "__main__":
    sys.exit(main())
