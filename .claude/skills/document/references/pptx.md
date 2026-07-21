# PPTX Generation Reference

Use this reference only when the requested deliverable is a PowerPoint presentation.

## Required Pattern

1. Use `python-pptx` and set the slide size explicitly.
2. Build a coherent story before laying out slides.
3. Use a stable grid, consistent typography, and a small set of reusable layout helpers.
4. Prefer editable text, tables, and vector/raster figures over screenshot-heavy slides.
5. Save, inspect, fix, and regenerate from the same script.

## Minimal Skeleton

```python
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

out = Path("workspace/reports/presentation.pptx")
out.parent.mkdir(parents=True, exist_ok=True)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

slide = prs.slides.add_slide(prs.slide_layouts[6])
title = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.7))
paragraph = title.text_frame.paragraphs[0]
paragraph.text = "One claim per slide"
paragraph.font.size = Pt(28)
paragraph.font.bold = True
paragraph.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
paragraph.alignment = PP_ALIGN.LEFT

body = slide.shapes.add_textbox(Inches(0.9), Inches(1.6), Inches(5.0), Inches(4.8))
body.text_frame.text = "Use evidence, a figure, or a concise comparison to support the claim."

figure = Path("workspace/_system/figures/figure.png")
if figure.is_file():
    slide.shapes.add_picture(str(figure), Inches(6.3), Inches(1.5), width=Inches(6.0))

prs.save(out)
```

## Non-Obvious Rules

- Do not assume layout indices from a user-provided template match the default template. Inspect layout names or use blank slides with explicit geometry.
- Use 16:9 unless the user or destination template requires another ratio.
- Keep one primary claim per slide; put evidence next to the claim it supports.
- Use real text boxes and tables when editability matters. Avoid flattening the entire slide to an image.
- Preserve image aspect ratio and crop deliberately; never stretch figures to fill a box.
- Treat `document inspect` text-overflow results as heuristics. A successful structural check is not a visual proof.

## Verification

Run:

```bash
scholaraio document inspect workspace/reports/presentation.pptx
```

Fix every out-of-bounds shape and investigate every text-overflow warning. When rendering or preview capability is available, inspect every slide at presentation size for contrast, clipping, density, and alignment.
