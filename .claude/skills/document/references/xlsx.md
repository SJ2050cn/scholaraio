# XLSX Generation Reference

Use this reference only when the requested deliverable is an Excel workbook.

## Required Pattern

1. Use `openpyxl`.
2. Separate raw data, derived analysis, and presentation sheets when the workbook is non-trivial.
3. Preserve numeric values as numbers; apply display formatting instead of writing formatted strings.
4. Freeze headers, enable filters, choose readable widths, and label every chart.
5. Save, inspect, fix, and regenerate from the same script.

## Minimal Skeleton

```python
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

out = Path("workspace/reports/data.xlsx")
out.parent.mkdir(parents=True, exist_ok=True)

wb = Workbook()
ws = wb.active
ws.title = "Data"

headers = ["Title", "Year", "Citations"]
ws.append(headers)
ws.append(["Example paper", 2025, 42])

for cell in ws[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4A90D9")
    cell.alignment = Alignment(horizontal="center")

ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
ws.column_dimensions["A"].width = 42
ws.column_dimensions["B"].width = 12
ws.column_dimensions["C"].width = 14

wb.save(out)
```

## Non-Obvious Rules

- Keep identifiers such as DOI, ORCID, and leading-zero codes as text.
- Use explicit number formats for dates, percentages, currency, and scientific notation.
- Avoid merged cells inside machine-readable data tables; reserve merges for presentation-only headings.
- Formulas are not calculated by `openpyxl`. Do not report cached formula results as freshly computed unless an Excel-compatible calculation engine has recalculated the workbook.
- Validate row counts and totals against the source data before formatting.
- Use charts only when they add decision value; always set titles, axis labels, and source ranges explicitly.

## Verification

Run:

```bash
scholaraio document inspect workspace/reports/data.xlsx
```

Confirm sheet names, dimensions, headers, preview rows, frozen panes, merged ranges, and chart metadata. If formulas or print layout are important, open or recalculate the workbook with an available Excel-compatible engine before final delivery.
