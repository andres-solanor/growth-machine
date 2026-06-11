import Link from "next/link";
import type { GatedReport } from "@/lib/report";
import { fmtMoney, fmtNum, fmtIsoDate } from "@/lib/format";

// Secciones del reporte (server components puros: el cliente recibe HTML).
// v1 sin Plotly: SVG/CSS livianos; gráficos interactivos llegan después.

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

// ── Línea de tiempo (SVG liviano) ────────────────────────────────────────

export function TimelineSection({ r }: { r: GatedReport }) {
  const t = r.analyses.timeline;
  if (!t) return null;
  const c = r.meta.currency;

  const revs = t.daily.map((d) => d.revenue ?? 0);
  const max = Math.max(...revs, 1);
  const W = 640;
  const H = 120;
  const step = revs.length > 1 ? W / (revs.length - 1) : W;
  const points = revs
    .map((v, i) => `${(i * step).toFixed(1)},${(H - (v / max) * H).toFixed(1)}`)
    .join(" ");

  const dowMax = Math.max(...t.dow.map((d) => d.revenue ?? 0), 1);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Ventas en el tiempo</h2>

      <svg
        viewBox={`0 0 ${W} ${H + 8}`}
        className="mt-4 w-full"
        preserveAspectRatio="none"
        aria-label="Ventas diarias"
      >
        <polyline
          points={`0,${H} ${points} ${W},${H}`}
          fill="rgba(16,185,129,0.15)"
          stroke="none"
        />
        <polyline points={points} fill="none" stroke="#10b981" strokeWidth="2" />
      </svg>
      <p className="mt-1 text-xs text-zinc-500">
        Ventas diarias · {fmtIsoDate(r.summary.date_min_iso)} —{" "}
        {fmtIsoDate(r.summary.date_max_iso)}
      </p>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">
            Ventas por día de la semana
          </h3>
          <ul className="space-y-1.5">
            {t.dow.map((d) => (
              <li key={d.day} className="flex items-center gap-2 text-xs">
                <span className="w-8 shrink-0 text-zinc-400">{d.day}</span>
                <div className="h-3 flex-1 rounded bg-zinc-800">
                  <div
                    className="h-3 rounded bg-emerald-600"
                    style={{ width: `${((d.revenue ?? 0) / dowMax) * 100}%` }}
                  />
                </div>
                <span className="w-20 shrink-0 text-right text-zinc-400">
                  {fmtMoney(d.revenue ?? 0, c)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="text-sm font-medium text-zinc-300">Tu mejor momento</h3>
          <p className="mt-2 text-2xl font-bold text-emerald-400">
            {t.best_combo ?? "—"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            La franja con más ventas del periodo. Asegura inventario y personal a
            esa hora.
          </p>
        </div>
      </div>
    </section>
  );
}

// ── Productos ─────────────────────────────────────────────────────────────

export function ProductsSection({ r }: { r: GatedReport }) {
  const p = r.analyses.products;
  if (!p) return null;
  const c = r.meta.currency;
  const top = p.top_n.slice(0, 10);
  const maxRev = Math.max(...top.map((x) => x.revenue ?? 0), 1);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Tus productos estrella</h2>
      <p className="mt-1 text-sm text-zinc-400">
        {p.n_pareto} de tus {p.total_products} productos generan el 80% de las
        ventas.
      </p>
      <ul className="mt-4 space-y-2">
        {top.map((x, i) => (
          <li key={x["Nombre Corregido"]} className="text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-zinc-200">
                <span className="mr-2 text-zinc-500">{i + 1}.</span>
                {x["Nombre Corregido"]}
              </span>
              <span className="shrink-0 text-zinc-400">
                {fmtMoney(x.revenue ?? 0, c)}
              </span>
            </div>
            <div className="mt-1 h-1.5 rounded bg-zinc-800">
              <div
                className="h-1.5 rounded bg-emerald-600"
                style={{ width: `${((x.revenue ?? 0) / maxRev) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
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

export function LockedSections({ r }: { r: GatedReport }) {
  if (r.locked.length === 0) return null;
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">
        Lo que tu análisis ya sabe (y tu plan aún no muestra)
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {r.locked.map(({ key, teaser }) => (
          <div
            key={key}
            className="rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/60 p-5"
          >
            <p className="text-sm font-semibold text-zinc-200">
              🔒 {LOCKED_TITLES[key] ?? key}
            </p>
            <p className="mt-1.5 text-sm text-zinc-400">{teaser}</p>
          </div>
        ))}
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
