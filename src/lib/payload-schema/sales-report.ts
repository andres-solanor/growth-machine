import { z } from "zod";

// Contrato del payload que produce el motor Python (reports/report_generator.py,
// PAYLOAD_SCHEMA_VERSION = 1). Validar SIEMPRE el payload del worker contra este
// schema antes de guardarlo. Si el motor cambia el shape, subir schema_version
// allá y actualizar esto en el mismo PR (regenerar con scripts/check-payload.ts).
//
// Convenciones del motor:
//  - to_jsonable() convierte NaN/NaT/inf -> null, por eso los numéricos de
//    análisis son .nullable().
//  - Objetos "loose": el motor puede añadir campos sin romper el web app.

const num = z.number();
const numN = z.number().nullable();

// ── meta ──────────────────────────────────────────────────────────────────

export const metaConfigSchema = z.looseObject({
  store_name: z.string().nullable(),
  brand: z.string(),
  currency: z.string(),
});

export const metaSchema = z.looseObject({
  schema_version: z.literal(1),
  report_type: z.literal("sales_report"),
  generated_at: z.string(),
  store_name: z.string().nullable(),
  currency: z.string(),
  config: metaConfigSchema,
});

// ── summary / quality ─────────────────────────────────────────────────────

export const summarySchema = z.looseObject({
  total_revenue: num,
  total_orders: num,
  total_units: num,
  avg_ticket: num,
  avg_items_per_order: num,
  unique_products: num,
  multi_item_pct: num,
  multi_item_orders: num,
  date_min: z.string(),
  date_max: z.string(),
  date_range: z.string(),
  date_min_iso: z.string(),
  date_max_iso: z.string(),
});

export const qualitySchema = z.looseObject({
  initial_rows: num,
  valid_rows: num,
  dropped_pct: num,
  invalid_dates: num,
  invalid_numeric: z.record(z.string(), num),
  missing_days: num,
  incomplete_weeks: num,
  partial_months: z.array(
    z.looseObject({ month: z.string(), month_days: num, observed_days: num }),
  ),
  coverage_note: z.string(),
  risk_level: z.enum(["low", "medium", "high"]),
});

// ── analyses: filas por módulo ────────────────────────────────────────────

export const interactiveRowSchema = z.looseObject({
  order_id: z.union([z.string(), z.number()]),
  product: z.string(),
  category: z.string(),
  date_str: z.string(),
  day: z.string(),
  hour: numN,
  quantity: numN,
  unit_price: numN,
  total: numN,
  margin_pct: numN,
  year_month: z.string(),
  year_week: z.string(),
});

export const interactiveBaseSchema = z.looseObject({
  rows: z.array(interactiveRowSchema),
});

export const timelineSchema = z.looseObject({
  daily: z.array(
    z.looseObject({
      date_str: z.string(),
      orders: numN,
      revenue: numN,
      rolling_orders: numN,
      rolling_rev: numN,
    }),
  ),
  weekly: z.array(
    z.looseObject({ year_week: z.string(), orders: numN, revenue: numN }),
  ),
  dow: z.array(z.looseObject({ day: z.string(), orders: numN, revenue: numN })),
  heatmap_days: z.array(z.string()),
  heatmap_hours: z.array(num),
  heatmap_z: z.array(z.array(numN)),
  hourly: z.array(z.looseObject({ hour: num, orders: numN, revenue: numN })),
  monthly_cat: z.array(
    z.looseObject({ category: z.string(), month: z.string(), revenue: numN }),
  ),
  best_hour: numN,
  best_day: z.string().nullable(),
  best_combo: z.string().nullable(),
});

export const productRowSchema = z.looseObject({
  "Nombre Corregido": z.string(),
  category: z.string(),
  avg_price: numN,
  cum_rev_pct: numN,
  orders: numN,
  rev_share: numN,
  revenue: numN,
  units: numN,
});

export const productsSchema = z.looseObject({
  all_products: z.array(productRowSchema),
  top_n: z.array(productRowSchema),
  n_pareto: num,
  total_products: num,
  cat_totals: z.array(numN),
});

export const basketPairSchema = z.looseObject({
  product_a: z.string(),
  product_b: z.string(),
  count: num,
  lift: numN,
  support: numN,
});

export const basketSchema = z.looseObject({
  pairs: z.array(basketPairSchema),
  cat_pairs: z.array(
    z.looseObject({ cat_a: z.string(), cat_b: z.string(), count: num }),
  ),
  total_baskets: num,
  high_lift_pairs: z.array(basketPairSchema),
});

export const cartSchema = z.looseObject({
  cart_dist: z.array(z.looseObject({ products_in_cart: num, count: num })),
  ticket_stats: z.record(z.string(), numN),
  ticket_dist: z.array(z.looseObject({ bucket: z.string(), count: num })),
  cart_weekly: z.array(z.looseObject({ week: z.string(), avg_items: numN })),
  segment_stats: z.array(
    z.looseObject({
      segment: z.string(),
      orders: num,
      avg_ticket: numN,
      share_pct: numN,
    }),
  ),
  multi_bucket_stats: z.array(
    z.looseObject({
      bucket: z.string(),
      orders: num,
      avg_ticket: numN,
      share_multi_pct: numN,
    }),
  ),
  single_top_ticket: z.array(
    z.looseObject({ product: z.string(), orders: num, avg_ticket: numN }),
  ),
});

export const trendsSchema = z.looseObject({
  growing: z.array(z.looseObject({ product: z.string(), growth_pct: numN })),
  declining: z.array(z.looseObject({ product: z.string(), growth_pct: numN })),
  base_month: z.string().nullable(),
  compare_month: z.string().nullable(),
  eligible_count: num,
});

const anomalyDaySchema = z.looseObject({
  date: z.string(),
  orders: num,
  revenue: numN,
  z_score: numN,
});

export const anomaliesSchema = z.looseObject({
  high_days: z.array(anomalyDaySchema),
  low_days: z.array(anomalyDaySchema),
  avg_daily_revenue: numN,
  std_daily_revenue: numN,
});

export const ticketSchema = z.looseObject({
  day_ticket: z.array(
    z.looseObject({ day: z.string(), orders: num, avg_ticket: numN }),
  ),
  hour_ticket: z.array(
    z.looseObject({ hour: num, orders: num, avg_ticket: numN }),
  ),
  opportunity_hours: z.array(
    z.looseObject({ hour: num, orders: num, avg_ticket: numN, gap_pct: numN }),
  ),
});

export const basketRulesSchema = z.looseObject({
  rules: z.array(
    z.looseObject({
      antecedent: z.string(),
      consequent: z.string(),
      count: num,
      support: numN,
      confidence: numN,
      lift: numN,
      conviction: numN,
      score: numN,
    }),
  ),
});

export const profitabilityRowSchema = z.looseObject({
  "Nombre Corregido": z.string(),
  category: z.string(),
  avg_margin: numN,
  cum_profit_pct: numN,
  orders: numN,
  profit: numN,
  profit_share: numN,
  revenue: numN,
  units: numN,
});

export const profitabilitySchema = z.looseObject({
  has_margin_data: z.boolean(),
  margin_available: z.boolean(),
  products_by_profitability: z.array(profitabilityRowSchema),
  profit_pareto: z.array(profitabilityRowSchema),
  n_profit_pareto: num,
  product_classification: z.record(z.string(), z.unknown()),
  classification_thresholds: z.record(z.string(), z.unknown()),
  margin_by_category: z.array(numN),
  margin_weighted_pairs: z.array(
    z.looseObject({
      antecedent: z.string(),
      consequent: z.string(),
      margin_weighted_score: numN,
      original_lift: numN,
    }),
  ),
  margin_row_coverage_pct: numN,
});

export const bundleRowSchema = z.looseObject({
  anchor: z.string(),
  target: z.string(),
  anchor_category: z.string(),
  target_category: z.string(),
  anchor_class: z.string(),
  target_class: z.string(),
  launch_ready: z.boolean(),
  count: num,
  support: numN,
  confidence: numN,
  lift: numN,
  conviction: numN,
  combined_margin: numN,
  target_margin: numN,
  adoption_score: numN,
  adoption_score_norm: numN,
  margin_score: numN,
  margin_score_norm: numN,
  balanced_score: numN,
});

export const bundlesSchema = z.looseObject({
  has_data: z.boolean(),
  has_margin_data: z.boolean(),
  margin_row_coverage_pct: numN,
  launch_ready: z.array(bundleRowSchema),
  test_candidates: z.array(bundleRowSchema),
  balanced: z.array(bundleRowSchema),
  margin_focus: z.array(bundleRowSchema),
  conversion_focus: z.array(bundleRowSchema),
  notes: z.string(),
});

// Todos los módulos son opcionales: el motor puede omitir módulos cuando los
// datos no alcanzan (p. ej. trends con <2 meses). El gating decide qué mostrar.
export const analysesSchema = z.looseObject({
  interactive_base: interactiveBaseSchema.optional(),
  timeline: timelineSchema.optional(),
  products: productsSchema.optional(),
  basket: basketSchema.optional(),
  cart: cartSchema.optional(),
  trends: trendsSchema.optional(),
  anomalies: anomaliesSchema.optional(),
  ticket: ticketSchema.optional(),
  basket_rules: basketRulesSchema.optional(),
  profitability: profitabilitySchema.optional(),
  bundles: bundlesSchema.optional(),
});

export const ALL_MODULE_KEYS = [
  "interactive_base",
  "timeline",
  "products",
  "basket",
  "cart",
  "trends",
  "anomalies",
  "ticket",
  "basket_rules",
  "profitability",
  "bundles",
] as const;

export type ModuleKey = (typeof ALL_MODULE_KEYS)[number];

// ── insights / recommendations ────────────────────────────────────────────

export const insightSchema = z.looseObject({
  title: z.string(),
  body: z.string(), // puede contener HTML simple (<strong>) generado por el motor
  category: z.string(),
  severity: z.string(),
  priority: num,
  action: z.string(),
  owner: z.string(),
  horizon: z.string(),
});

export const recommendationSchema = z.looseObject({
  action: z.string(),
  impact: z.string(),
  owner: z.string(),
  horizon: z.string(),
});

// ── payload completo ──────────────────────────────────────────────────────

export const salesReportPayloadSchema = z.looseObject({
  meta: metaSchema,
  summary: summarySchema,
  quality: qualitySchema,
  analyses: analysesSchema,
  insights: z.array(insightSchema),
  recommendations: z.array(recommendationSchema),
});

export type SalesReportPayload = z.infer<typeof salesReportPayloadSchema>;
export type SalesReportSummary = z.infer<typeof summarySchema>;
export type SalesReportQuality = z.infer<typeof qualitySchema>;
export type SalesReportInsight = z.infer<typeof insightSchema>;
