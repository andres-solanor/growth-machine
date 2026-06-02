# growth-machine

Automation machine for making money!

Two HTML report builders live under `store-report-builder/store-report-builder/`:

| Script | Purpose |
|--------|---------|
| `report_generator.py` | Full sales report (timeline, products, basket, profitability, bundles) |
| `delta builder/delta_builder.py` | Pre/post event impact comparison (delta report) |

## Prerequisites

- **Python 3.10+** ([python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`)
- On Windows, use `python` / `python -m pip` (not the Microsoft Store stub unless Python is installed)

## Setup

From the **repository root**:

```powershell
python -m pip install -r store-report-builder/store-report-builder/requirements.txt
```

Dependencies: `pandas>=2.0`, `numpy>=1.24`.

## Run reports

All commands below are run from the **repository root**. Scripts resolve paths relative to their project folder, so you do not need to `cd` into subdirectories.

**Sales report** — auto-picks the newest CSV in `input_data/`:

```powershell
python store-report-builder/store-report-builder/report_generator.py
```

Output: `store-report-builder/store-report-builder/report.html` (and `report_filas_descartadas.csv` if rows were dropped).

**Delta report** — reads `delta builder/delta_report_config.json`:

```powershell
python "store-report-builder/store-report-builder/delta builder/delta_builder.py"
```

Output: `store-report-builder/store-report-builder/delta builder/impact_delta_report.html`

### Run both (Windows)

```powershell
.\run_reports.ps1
```

### Optional flags

```powershell
# Sales: explicit CSV and output
python store-report-builder/store-report-builder/report_generator.py `
  --input store-report-builder/store-report-builder/input_data/your-file.csv `
  --output store-report-builder/store-report-builder/report.html

# Delta: alternate config file
python "store-report-builder/store-report-builder/delta builder/delta_builder.py" --config path/to/config.json
```

## Input data

Place cart export CSVs in:

`store-report-builder/store-report-builder/input_data/`

The sales report uses the **most recently modified** `.csv` in that folder when `--input` is omitted.

## Generated outputs (gitignored)

Regenerate with the commands above; these are not committed:

- `report.html`, `report_filas_descartadas.csv`
- `delta builder/impact_delta_report.html`, `impact_delta_report_data.json`, `impact_delta_report_discarded_rows.csv`
