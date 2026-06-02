# Delta report builder

Pre/post event impact analysis from cart-level sales CSV data.

## Quick run

From the repository root:

```bash
python reports/delta_builder/delta_builder.py
```

## Configuration

Edit [`delta_report_config.json`](delta_report_config.json):

| Field | Description |
|-------|-------------|
| `input_csv` | Path to source CSV (relative to this folder) |
| `default_event_date` | Initial event date; empty = auto (today − 30 days, clamped to data) |
| `default_window_days` | `7`, `14`, or `30` |
| `default_products` | Optional initial product filter |
| `product_groups` | Named product groups for combo/thematic tracking |

## Output

- `impact_delta_report.html` — interactive report (gitignored; regenerate locally)
- `impact_delta_report_data.json` — payload for debugging
- `impact_delta_report_discarded_rows.csv` — invalid rows, when any

## Behavior notes

- Empty product selection analyzes the full portfolio.
- Average ticket uses full orders that include selected products.
- Margin insights require `margin_pct` on selected lines.
