# Store Report Builder - Strategic One-Pager

## Objective
Convert transactional CSV data into a decision-first report that prioritizes profitable growth, not only volume.

## Current State (Today)
- The report is stable and operational with local CSV input.
- It supports graceful degradation when optional margin data is missing.
- Profitability layer is active when `margin_pct` is available.

## What Changed Strategically
1. The report moved from descriptive analytics to actionable guidance.
2. Profitability became a first-class lens (Phase 4).
3. Product decisions are now transparent through explicit classification rules.

## Core Decision Model
Classification uses dataset medians:
- High volume: product orders >= median orders
- High margin: avg margin >= median margin

Resulting classes:
- Champion = high volume + high margin
- Tractor = high volume + low margin
- Gem = low volume + high margin
- Niche = low volume + low margin

## Why This Matters for the Business
- Protect and scale Champions.
- Use Tractors for traffic but recover margin with pricing/bundles.
- Grow Gems with visibility and placement.
- Reevaluate Niche products to simplify catalog and improve mix quality.

## Current Report Outputs Supporting Decisions
- Executive summary and prioritized weekly actions.
- Data quality section with explicit coverage and dropped rows.
- Profitability section with:
  - Profit Pareto
  - Category margin table
  - Top 5 products per category
  - Categories sorted by total orders (most relevant first)

## Risks to Keep in View
- Windows terminal encoding can fail on checkmark print, while HTML still generates.
- Margin quality depends on normalized numeric format (decimal dot preferred).
- Classification thresholds are median-based; may need percentile controls later.

## Next Iteration (Priority)
1. Make final console output encoding-safe in Windows.
2. Add configurable ranking mode for Top 5 by category (`profit`, `orders`, `margin`, `revenue`).
3. Add margin trend alerts by category/product (improving vs deteriorating).
4. Add profitability-aware bundle recommendations (lift x confidence x margin).

## Success Criteria for Next Iteration
- No terminal encoding error in standard Windows shell.
- Clear ranking-mode switch in profitability section.
- New trend insight appears when margin signal exists.
- Backward compatibility remains intact without `margin_pct`.

---
Last updated: 2026-04-23
