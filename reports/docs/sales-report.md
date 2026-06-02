# Sales report generator

Generates an interactive HTML sales report from a cart-level CSV export.

## Quick run

From the repository root:

```bash
python reports/report_generator.py
```

See the [root README](../../README.md) for setup (`pip install -r requirements.txt`).

## Required CSV columns

- Fecha
- Código venta
- Nombre Corregido
- Cantidad
- Individual
- Total
- Categoria Real
- Week Day
- Hour

Optional (profitability section):

- `margin_pct` — product margin percentage (0–100)

## CLI options

```bash
python reports/report_generator.py --input reports/input_data/your.csv --output reports/report.html
python reports/report_generator.py --store "Your store name" --verbose
```

## Output

- `reports/report.html` — main report
- `reports/report_filas_descartadas.csv` — dropped rows log (when applicable)

Sections include KPIs, executive summary, data quality, timeline, products, profitability (when margins exist), market basket, cart composition, and auto insights.

## Data quality

The script validates required columns, coerces dates and numbers, and logs kept vs dropped rows. Run with `--verbose` to inspect quality metrics.

If `margin_pct` is missing, the report still generates; profitability sections show as unavailable.
