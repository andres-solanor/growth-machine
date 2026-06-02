# Delta Builder Manual

## Purpose

This standalone builder creates a self-contained pre/post impact report from the sales CSV.

It is designed to answer questions such as:

- Did we sell more of a specific product after a change date?
- Did average ticket increase after introducing a combo or a product group?
- Did the product mix shift after a selected event date?

## Files

- [delta_builder.py](c:/Users/Andres.solano/Documents/Projects/store-report-builder/delta%20builder/delta_builder.py): standalone constructor
- [delta_report_config.json](c:/Users/Andres.solano/Documents/Projects/store-report-builder/delta%20builder/delta_report_config.json): runtime configuration
- `impact_delta_report.html`: generated report
- `impact_delta_report_data.json`: generated intermediate payload for debug/regression
- `impact_delta_report_discarded_rows.csv`: discarded rows after validation, when applicable

## Requirements

- Python 3.10+
- `pandas`
- `numpy`

Install if needed:

```bash
pip install pandas numpy
```

## Run

From the `delta builder` folder:

```bash
python delta_builder.py --config delta_report_config.json
```

## Configuration

Key fields in the JSON file:

- `input_csv`: source CSV path
- `default_event_date`: event date used on initial render. If left empty, the builder uses current date minus 30 days and clamps it to the available data range.
- `default_window_days`: `7`, `14`, or `30`
- `default_products`: optional initial product selection
- `product_groups`: optional named groups for combo or thematic tracking

## Output behavior

The HTML is fully self-contained and opens directly in the browser.

The page includes:

- event date selector
- 7/14/30 day switch
- multi-product selector
- KPI cards for revenue, units, orders, and average ticket
- daily trend chart
- product delta table
- category mix table
- tracked group or combo table
- narrative conclusion with quality warnings

## Notes

- If no products are selected, the report analyzes the full portfolio.
- Average ticket is calculated on full orders impacted by the selected products, not only on selected line revenue.
- Margin insights are shown only when `margin_pct` exists for the current selection.