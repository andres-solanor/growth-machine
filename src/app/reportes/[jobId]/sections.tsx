import Link from "next/link";
import type { GatedReport } from "@/lib/report";
import { TIER_MODULES } from "@/lib/gating";
import { fmtMoney, fmtNum, fmtIsoDate } from "@/lib/format";
import { LOCKED_DEMOS } from "./locked-demos";
import {
  DailyRevenueChart,
  DowChart,
  HeatmapChart,
  MonthlyCatChart,
  TopProductsChart,
} from "@/components/charts/report-charts";

// Secciones del reporte. Server components que pasan datos YA filtrados por
// el gating a los gráficos Plotly (client components en components/charts).

const card = "rounded-2xl border border-zinc-800 bg-zinc-900 p-6";

// ── KPIs ──────────────────────────────────────────────────────────────────

export function KpiGrid({ r }: { r: GatedReport }) {
  const c = r.meta.currency;
  const kpis: [string, string][] = [
    ["Ventas totales", fmtMoney(r.summary.total_revenue, c)],
    ["Órdenes", fmtNum(r.summary.total_orders)],
    ["Ticket promedio", fmtMoney(r.summary.avg_ticket, c)],
    ["Unidades vendidas", fmtNum(r.summary.total_units)],
    ["Productos distintos", fmtNum(r.summary.unique_products)],
    ["Carritos multi-producto", `${fmtNum(r.summary.multi_item_pct)}%`],
  ];
  return (
    <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {kpis.map(([label, value]) => (
        <div key={label} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="mt-1 text-xl font-bold tracking-tight">{value}</p>
        </div>
      ))}
    </section>
  );
}

// ── Calidad de datos ──────────────────────────────────────────────────────

const RISK_LABEL: Record<string, [string, string]> = {
  low: ["Cobertura buena", "border-emerald-700 bg-emerald-950 text-emerald-300"],
  medium: ["Cobertura parcial", "border-amber-700 bg-amber-950 text-amber-300"],
  high: ["Cobertura limitada", "border-red-800 bg-red-950 text-red-300"],
};

export function QualitySection({ r }: { r: GatedReport }) {
  const [label, cls] = RISK_LABEL[r.quality.risk_level] ?? RISK_LABEL.medium;
  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Tus datos</h2>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${cls}`}>
          {label}
        </span>
      </div>
      <p className="mt-2 text-sm text-zinc-400">
        Periodo: {fmtIsoDate(r.summary.date_min_iso)} —{" "}
        {fmtIsoDate(r.summary.date_max_iso)} · {fmtNum(r.quality.valid_rows)} filas
        válidas de {fmtNum(r.quality.initial_rows)} ({fmtNum(r.quality.dropped_pct)}%
        descartadas)
      </p>
      <p className="mt-1 text-sm text-zinc-500">{r.quality.coverage_note}</p>
    </section>
  );
}

// ── Línea de tiempo ───────────────────────────────────────────────────────

export function TimelineSection({ r }: { r: GatedReport }) {
  const t = r.analyses.timeline;
  if (!t) return null;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Ventas en el tiempo</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Ventas diarias del {fmtIsoDate(r.summary.date_min_iso)} al{" "}
        {fmtIsoDate(r.summary.date_max_iso)}. La línea ámbar es tu promedio
        móvil: si las barras quedan debajo varios días seguidos, algo cambió.
      </p>
      <DailyRevenueChart daily={t.daily} />

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium text-zinc-300">
            Ventas por día de la semana
          </h3>
          <DowChart dow={t.dow} />
        </div>
        <div className="flex flex-col justify-center rounded-xl border border-zinc-800 bg-zinc-950 p-5">
          <h3 className="text-sm font-medium text-zinc-300">Tu mejor momento</h3>
          <p className="mt-2 text-3xl font-bold tracking-tight text-emerald-400">
            {t.best_combo ?? "—"}
          </p>
          <p className="mt-2 text-xs text-zinc-500">
            La franja con más ventas del periodo. Asegura inventario y personal
            a esa hora.
          </p>
        </div>
      </div>

      {t.heatmap_z.length > 0 && t.heatmap_hours.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-medium text-zinc-300">
            Mapa de calor: día × hora
          </h3>
          <p className="mt-1 text-xs text-zinc-500">
            Dónde se concentran tus órdenes. Las zonas ámbar son tus horas
            pico; las oscuras, donde sobra personal o falta tráfico.
          </p>
          <HeatmapChart
            days={t.heatmap_days}
            hours={t.heatmap_hours}
            z={t.heatmap_z}
          />
        </div>
      )}

      {t.monthly_cat.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-medium text-zinc-300">
            Ventas por categoría, mes a mes
          </h3>
          <MonthlyCatChart rows={t.monthly_cat} />
        </div>
      )}
    </section>
  );
}

// ── Productos ─────────────────────────────────────────────────────────────

export function ProductsSection({ r }: { r: GatedReport }) {
  const p = r.analyses.products;
  if (!p) return null;
  const top = p.top_n.slice(0, 10);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Tus productos estrella</h2>
      <p className="mt-1 text-sm text-zinc-400">
        {p.n_pareto} de tus {p.total_products} productos generan el 80% de las
        ventas. El porcentaje es la participación de cada uno en tus ventas.
      </p>
      <TopProductsChart
        items={top.map((x) => ({
          name: x["Nombre Corregido"],
          revenue: x.revenue,
          revShare: x.rev_share,
        }))}
      />
    </section>
  );
}

// ── Insights ──────────────────────────────────────────────────────────────

const SEVERITY_CLS: Record<string, string> = {
  critical: "border-red-800 bg-red-950 text-red-300",
  warning: "border-amber-700 bg-amber-950 text-amber-300",
  info: "border-sky-700 bg-sky-950 text-sky-300",
};

export function InsightsSection({ r }: { r: GatedReport }) {
  if (r.insights.length === 0) return null;
  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Hallazgos accionables</h2>
      <ul className="mt-4 space-y-3">
        {r.insights.map((ins) => (
          <li
            key={ins.title}
            className="rounded-xl border border-zinc-800 bg-zinc-950 p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${SEVERITY_CLS[ins.severity] ?? SEVERITY_CLS.info}`}
              >
                {ins.category}
              </span>
              <h3 className="text-sm font-semibold text-zinc-100">{ins.title}</h3>
            </div>
            {/* body trae HTML simple (<strong>) generado por nuestro motor */}
            <p
              className="mt-2 text-sm text-zinc-400"
              dangerouslySetInnerHTML={{ __html: ins.body }}
            />
            <p className="mt-2 text-xs text-zinc-500">
              → {ins.action} · {ins.horizon}
            </p>
          </li>
        ))}
      </ul>
      {r.lockedInsights > 0 && (
        <p className="mt-4 rounded-xl border border-dashed border-zinc-700 bg-zinc-950 p-4 text-sm text-zinc-400">
          🔒 Hay <strong className="text-zinc-200">{r.lockedInsights} hallazgos
          más</strong> en tu análisis, disponibles en los planes Pro y Premium.
        </p>
      )}
    </section>
  );
}

// ── Secciones bloqueadas (teasers) ───────────────────────────────────────

const LOCKED_TITLES: Record<string, string> = {
  basket: "Qué compran juntos",
  cart: "Radiografía del carrito",
  trends: "Productos en alza y en caída",
  ticket: "Oportunidades de ticket",
  anomalies: "Días atípicos",
  basket_rules: "Reglas para combos",
  profitability: "Rentabilidad real",
  bundles: "Combos sugeridos",
};

// Plan más barato que desbloquea cada módulo (para el botón de la tarjeta).
const PRO_MODULES = new Set(TIER_MODULES.pro);
const planFor = (key: string) => (PRO_MODULES.has(key) ? "Pro" : "Premium");

export function LockedSections({ r }: { r: GatedReport }) {
  if (r.locked.length === 0) return null;
  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">
        Lo que tu análisis ya sabe (y tu plan aún no muestra)
      </h2>
      <p className="mb-4 text-sm text-zinc-500">
        Las cifras de cada título son tuyas; la vista borrosa es un ejemplo de
        cómo se ve la sección completa.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {r.locked.map(({ key, teaser }) => {
          const plan = planFor(key);
          return (
            <div
              key={key}
              className="flex flex-col overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900"
            >
              <div className="p-5 pb-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-zinc-200">
                    🔒 {LOCKED_TITLES[key] ?? key}
                  </p>
                  <span className="shrink-0 rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                    Plan {plan}
                  </span>
                </div>
                {/* El gancho: una cifra REAL del análisis (lib/gating.ts) */}
                <p className="mt-1.5 text-sm text-zinc-400">{teaser}</p>
              </div>
              <div className="relative mt-auto px-5 pb-4">
                <p className="mb-1 text-right text-[10px] uppercase tracking-wide text-zinc-600">
                  vista de ejemplo — no son tus datos
                </p>
                <div
                  aria-hidden
                  className="pointer-events-none select-none [mask-image:linear-gradient(to_bottom,black_25%,transparent_97%)]"
                >
                  {LOCKED_DEMOS[key]}
                </div>
                <div className="absolute inset-x-0 bottom-3 flex justify-center">
                  <Link
                    href="/#planes"
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-950/60 hover:bg-emerald-500"
                  >
                    Desbloquéalo con {plan}
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── CTA consultoría ───────────────────────────────────────────────────────

export function ConsultingCta() {
  return (
    <section className="rounded-2xl border border-emerald-900 bg-gradient-to-br from-emerald-950 to-zinc-900 p-6">
      <h2 className="text-lg font-semibold">
        ¿Quieres que un experto interprete esto contigo?
      </h2>
      <p className="mt-1 max-w-xl text-sm text-zinc-400">
        Sesión 1:1 con quien construyó este análisis: revisamos tu reporte,
        priorizamos acciones y armamos un plan concreto para subir tus ventas.
      </p>
      <Link
        href="/consultoria"
        className="mt-4 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
      >
        Quiero mi sesión
      </Link>
    </section>
  );
}
