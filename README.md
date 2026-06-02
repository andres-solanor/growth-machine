# growth-machine

CSV-to-HTML analytics for store sales: an executive sales report and a pre/post event delta report.

## Quick start

**Requirements:** Python 3.10+

```powershell
python -m pip install -r requirements.txt
python reports/report_generator.py
python reports/delta_builder/delta_builder.py
```

On Windows, run both reports:

```powershell
.\run_reports.ps1
```

## Reports

| Report | Script | Output |
|--------|--------|--------|
| Sales | [`reports/report_generator.py`](reports/report_generator.py) | `reports/report.html` |
| Delta (pre/post event) | [`reports/delta_builder/delta_builder.py`](reports/delta_builder/delta_builder.py) | `reports/delta_builder/impact_delta_report.html` |

## Data

- Put your exports in [`reports/input_data/`](reports/input_data/) (see [README there](reports/input_data/README.md)).
- Demo file committed: `reports/input_data/sales_carts_sample.csv`.
- Additional test fixtures: [`reports/fixtures/`](reports/fixtures/).

Without `--input`, the sales report uses the newest `.csv` in `input_data/`.

## Documentation

- [Sales report details](reports/docs/sales-report.md)
- [Delta report details](reports/delta_builder/README.md)
- [Architecture overview](reports/docs/architecture.md)

## License

Internal / project use—adjust as needed for your organization.
