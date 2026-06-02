# Report Generator Manual

## 1. Purpose
This script generates an interactive HTML sales report from a cart-level CSV file.

## 2. Requirements
- Python 3.10+
- Dependencies:
  - pandas
  - numpy

Install dependencies:

```bash
pip install pandas numpy
```

## 3. Required CSV Columns
The input CSV must include these columns:

- Fecha
- Código venta
- Nombre Corregido
- Cantidad
- Individual
- Total
- Categoria Real
- Week Day
- Hour

Optional column (Phase 4 profitability):

- margin_pct (product margin percentage, 0-100)

## 4. Run

From the **repository root**, with auto-detected newest CSV in `input_data/`:

```bash
python store-report-builder/store-report-builder/report_generator.py
```

Basic execution with explicit paths (from `store-report-builder/store-report-builder/`):

```bash
python report_generator.py --input input_data/ventas.csv --output report.html
```

With custom store name:

```bash
python report_generator.py --input input_data/ventas.csv --output report.html --store "Store 900421032"
```

Verbose mode (recommended for troubleshooting):

```bash
python report_generator.py --input input_data/ventas.csv --output report.html --verbose
```

## 5. Output
The script writes an HTML file with:
- KPI summary
- Executive summary with 3 prioritized weekly actions
- Data Quality section (coverage, dropped %, missing days, incomplete weeks, partial months)
- Timeline analysis
- Product analysis
- Profitability analysis (only when `margin_pct` is available)
- Market basket analysis
- A->B basket rules (confidence, lift, conviction)
- Cart composition analysis
- Ticket opportunity analysis (ticket by day/hour and high-traffic low-ticket windows)
- Auto-generated insights

Profitability section includes:
- Profit Pareto (revenue weighted by margin)
- Product classification (Champion, Tractor, Gem, Niche)
- Margin by category
- Margin-driven insights

Time aggregation notes:
- Weekly charts now use ISO weeks (`YYYY-Www`) for consistency.
- Trend insights apply minimum base thresholds to reduce noisy percentage spikes.

Console output also includes:
- Total revenue, orders, products, and period
- Data quality summary (valid rows vs dropped rows)

## 6. Data Quality Behavior
Before analysis, the script now:
- Validates that required columns exist
- Coerces date and numeric columns safely
- Drops invalid rows for critical fields
- Logs quality metrics (kept rows, dropped rows, percentage)

Optional profitability behavior (`margin_pct`):
- If `margin_pct` is missing, report is still generated (omit + warn strategy).
- If `margin_pct` exists, values are coerced to numeric and invalid values become NaN.
- If all `margin_pct` values are invalid/missing, profitability section is shown as unavailable.

## 7. Common Errors
- Missing required columns:
  - Error message lists all missing columns.
- Empty report data after validation:
  - Usually caused by invalid date/number formats in source CSV.
- Blank charts:
  - The report depends on loading Plotly from CDN.

## 8. Recommended Operational Checklist
1. Validate CSV headers before execution.
2. Run once with --verbose and check quality metrics.
3. Open generated HTML and verify all sections render.
4. If too many rows are dropped, fix source formatting and rerun.
