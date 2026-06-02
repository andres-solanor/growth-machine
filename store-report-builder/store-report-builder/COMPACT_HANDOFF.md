# Compact Handoff - Store Report Builder

## Scope
Project: sales-to-HTML report generator with executive insights and profitability layer.
Goal: keep continuity for a new conversation thread with minimal context loss.

## Current Status
- Phase 1 complete: validation, sanitization, logging, data quality tracking.
- Phase 2 complete: core bug fixes (Pareto, trends robustness, consistency).
- Phase 3 complete: executive/actionable report sections + explainers.
- Phase 4 complete (margins): optional margin support and profitability analysis.

## Key Files
- report_generator.py
- REPORT_GENERATOR_MANUAL.md
- STRATEGIC_WRAP_UP.md
- STRATEGIC_ONE_PAGER.md
- test_data_with_margins.csv
- test_data_with_margins_normalized.csv
- report_phase4_no_margin_test.html
- report_phase4_with_margins_simulation_fixed.html

## Important Decisions Already Taken
- External enrichment priority: margins first.
- Optional margin column: margin_pct.
- Backward compatibility: omit + warn when margin_pct is absent.
- Top-5 category blocks: categories ordered by total orders descending.
- Layout fix: Top-5 blocks constrained to max 2 columns desktop, 1 column mobile.

## Profitability Model (Active)
- Product-level metrics: revenue, orders, avg_margin, profit.
- Profit formula: revenue x (avg_margin / 100).
- Product classes based on medians:
  - Champion: high volume + high margin
  - Tractor: high volume + low margin
  - Gem: low volume + high margin
  - Niche: low volume + low margin

## Recent UX/Report Enhancements
- Rentabilidad section includes:
  - Classification summary badges
  - Margin by category table
  - Profit Pareto table
  - Top 5 products by category (with class, orders, margin, profit)
- Added transparent algorithm explanation in-report with actual threshold values.
- Category blocks show total orders in header.

## Known Issues
- Windows console may throw UnicodeEncodeError when printing checkmark symbol.
- This does not block HTML output generation.
- Recommended fix next: replace non-cp1252 symbol in terminal print.

## Last Verified Outputs
- report_phase4_with_margins_simulation_fixed.html generated successfully.
- No-margin mode still works and does not crash when margin_pct is missing.

## Suggested Next Iteration
1. Make terminal final print encoding-safe.
2. Add ranking mode selector for Top 5 blocks (profit/orders/margin/revenue).
3. Add margin trend insights by category/product.
4. Expand profitability-aware bundle recommendation scoring.

## Run Commands
powershell
& 'C:\ProgramData\anaconda3\python.exe' report_generator.py --input test_data_with_margins_normalized.csv --output store_report_with_margins.html

powershell
& 'C:\ProgramData\anaconda3\python.exe' report_generator.py --input "$env:USERPROFILE\Downloads\Análisis Ventas - Carritos.csv" --output store_report_no_margins.html

---
Generated: 2026-04-23
Purpose: compact context handoff for starting a new thread.
