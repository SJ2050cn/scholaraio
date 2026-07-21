# DOCX Generation Reference

Use this reference only when the requested deliverable is a Word document.

## Required Pattern

1. Use `python-docx`.
2. Create the output parent directory under `workspace/`.
3. Set page size, margins, document properties, and semantic heading styles before adding content.
4. Keep tables within the printable width and add captions to figures.
5. Save, inspect, fix, and regenerate from the same script.

## Minimal Skeleton

```python
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt

out = Path("workspace/reports/report.docx")
out.parent.mkdir(parents=True, exist_ok=True)

doc = Document()
doc.core_properties.title = "Research brief"
doc.core_properties.author = "ScholarAIO"

section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.5)
section.bottom_margin = Cm(2.5)
section.left_margin = Cm(3)
section.right_margin = Cm(3)

doc.add_heading("Research brief", level=0)
doc.add_heading("Key findings", level=1)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
run = p.add_run("Evidence-backed content goes here.")
run.font.size = Pt(11)

figure = Path("workspace/_system/figures/figure.png")
if figure.is_file():
    doc.add_picture(str(figure), width=Inches(5.5))
    caption = doc.add_paragraph("Figure 1. Verified caption.")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.save(out)
```

## Non-Obvious Rules

- Use `doc.add_heading(..., level=N)` so the structure remains navigable and inspectable.
- For CJK documents, set both the western font and the OOXML east-Asia font on the relevant style; setting only `run.font.name` is not sufficient in every Word renderer.
- `python-docx` can insert a TOC field, but Word or LibreOffice still needs to update that field. Do not claim the displayed TOC is current unless it was rendered and refreshed.
- Use a page-number field in the footer rather than literal page numbers.
- Do not use blank paragraphs as the primary spacing system; configure paragraph spacing and styles.
- Prefer PNG for broad Office compatibility. Use SVG only after confirming the target Office version renders it correctly.

## Verification

Run:

```bash
scholaraio document inspect workspace/reports/report.docx
```

Confirm the expected heading levels, table dimensions, image count, styles, and section orientation. If visual fidelity matters, render or open the document with an available Office-compatible viewer and inspect every page.
