// Gating por tier (server-only, puro — sin DB): qué módulos ve cada plan.
// Los módulos bloqueados se ELIMINAN antes de serializar al cliente;
// el cliente solo recibe teasers calculados aquí.
// scripts/check-gating.ts verifica que nada bloqueado se filtre.

// Import relativo (no "@/") para que tsx pueda cargar este módulo en scripts.
import type { SalesReportPayload } from "./payload-schema";

export type Tier = "free" | "pro" | "premium";

export const TIER_MODULES: Record<Tier, string[]> = {
  free: ["timeline", "products"],
  pro: ["timeline", "products", "basket", "cart", "trends", "ticket", "anomalies", "basket_rules"],
  premium: [
    "timeline", "products", "basket", "cart", "trends", "ticket",
    "anomalies", "basket_rules", "profitability", "bundles", "interactive_base",
  ],
};

export const FREE_INSIGHTS = 3;

export type GatedReport = {
  meta: SalesReportPayload["meta"];
  summary: SalesReportPayload["summary"];
  quality: SalesReportPayload["quality"];
  analyses: Partial<SalesReportPayload["analyses"]>;
  insights: SalesReportPayload["insights"];
  recommendations: SalesReportPayload["recommendations"];
  locked: { key: string; teaser: string }[];
  lockedInsights: number;
};

export function gateReport(payload: SalesReportPayload, tier: Tier): GatedReport {
  const allowed = new Set(TIER_MODULES[tier]);
  const analyses: Record<string, unknown> = {};
  const locked: { key: string; teaser: string }[] = [];

  for (const [key, value] of Object.entries(payload.analyses)) {
    if (value === undefined) continue;
    if (allowed.has(key)) {
      analyses[key] = value;
    } else if (key !== "interactive_base") {
      locked.push({ key, teaser: teaserFor(key, payload) });
    }
  }

  const insights =
    tier === "free" ? payload.insights.slice(0, FREE_INSIGHTS) : payload.insights;

  return {
    meta: payload.meta,
    summary: payload.summary,
    quality: payload.quality,
    analyses: analyses as GatedReport["analyses"],
    insights,
    recommendations: tier === "premium" ? payload.recommendations : [],
    locked,
    lockedInsights: payload.insights.length - insights.length,
  };
}

// Teaser: un dato real y atractivo del módulo bloqueado, sin revelar el detalle.
function teaserFor(key: string, p: SalesReportPayload): string {
  const a = p.analyses;
  switch (key) {
    case "basket":
      return a.basket
        ? `Detectamos ${a.basket.pairs.length} combinaciones de productos que tus clientes compran juntas.`
        : "Descubre qué productos compran juntos tus clientes.";
    case "cart":
      return a.cart
        ? `Analizamos ${p.summary.multi_item_orders.toLocaleString("es-CO")} carritos multi-producto: hay oportunidades claras para subir el ticket promedio.`
        : "Cómo se componen los carritos de tus clientes.";
    case "trends":
      return a.trends
        ? `${a.trends.growing.length} productos tuyos están creciendo y ${a.trends.declining.length} están cayendo. ¿Sabes cuáles?`
        : "Qué productos crecen y cuáles caen mes a mes.";
    case "ticket":
      return a.ticket
        ? `Encontramos ${a.ticket.opportunity_hours.length} franjas horarias con ticket por debajo de tu potencial.`
        : "Horas del día donde puedes vender más por cliente.";
    case "anomalies":
      return a.anomalies
        ? `Hubo ${a.anomalies.high_days.length} días excepcionales y ${a.anomalies.low_days.length} días inusualmente bajos en tu periodo.`
        : "Días atípicos de tus ventas, explicados.";
    case "basket_rules":
      return a.basket_rules
        ? `${a.basket_rules.rules.length} reglas de asociación con potencial de combos y promociones.`
        : "Reglas estadísticas para armar combos que funcionan.";
    case "profitability":
      return "Qué productos te dejan utilidad real (requiere ingresar márgenes — te guiamos).";
    case "bundles":
      return a.bundles && a.bundles.launch_ready.length > 0
        ? `${a.bundles.launch_ready.length} combos listos para lanzar según tus propios datos.`
        : "Combos sugeridos con base en tus ventas reales.";
    default:
      return "Análisis avanzado disponible en planes superiores.";
  }
}
