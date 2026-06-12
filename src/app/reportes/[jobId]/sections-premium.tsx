import Link from "next/link";
import type { GatedReport } from "@/lib/report";
import { fmtMoney, fmtNum } from "@/lib/format";
import { ProfitChart } from "@/components/charts/report-charts";

// Secciones Premium del reporte: rentabilidad, combos sugeridos y plan de
// acción. Mismo contrato que sections-pro.tsx: server components puros que
// devuelven null si el gating quitó su módulo.

const card = "rounded-2xl border border-zinc-800 bg-zinc-900 p-6";

const fmtPct = (v: number | null | undefined, decimals = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(decimals)}%`;

// Clasificación del motor: volumen vs margen contra sus medianas.
const CLASS_INFO: Record<string, { icon: string; desc: string }> = {
  Champion: { icon: "👑", desc: "alto volumen y alto margen: protégelo y promuévelo" },
  Tractor: { icon: "🚜", desc: "alto volumen, bajo margen: atrae clientes, súbele margen con combos" },
  Gem: { icon: "💎", desc: "alto margen, bajo volumen: dale visibilidad para crecer" },
  Niche: { icon: "🎯", desc: "bajo volumen y margen: evalúa su lugar en el catálogo" },
};

// ── Rentabilidad: qué te deja utilidad real ───────────────────────────────

export function ProfitabilitySection({
  r,
  marginEstimated,
}: {
  r: GatedReport;
  marginEstimated: boolean;
}) {
  const p = r.analyses.profitability;
  if (!p) return null;
  const c = r.meta.currency;

  // Sin márgenes no hay análisis: en vez de una sección vacía, la guía
  // para activarlo (el editor de productos es el camino).
  if (!p.has_margin_data || !p.margin_available) {
    return (
      <section className={card}>
        <h2 className="text-lg font-semibold">Rentabilidad real</h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-400">
          Tu plan incluye el análisis de utilidad por producto, pero necesita
          los márgenes de tus productos. Con un estimado por categoría
          (2 minutos) ya puedes empezar.
        </p>
        <Link
          href="/productos"
          className="mt-4 inline-block rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          Agregar márgenes a mis productos
        </Link>
      </section>
    );
  }

  const top = p.products_by_profitability.slice(0, 10);
  const classification = (p.product_classification ?? {}) as Record<string, string>;
  const counts: Record<string, number> = {};
  for (const cls of Object.values(classification)) {
    counts[cls] = (counts[cls] ?? 0) + 1;
  }
  const coverage = p.margin_row_coverage_pct;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Rentabilidad: qué te deja utilidad real</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Vender mucho no es lo mismo que ganar mucho.{" "}
        {p.n_profit_pareto > 0 && (
          <>
            <strong className="text-zinc-200">{p.n_profit_pareto} productos
            concentran ~80% de tu utilidad</strong>; aquí están los que más
            aportan.
          </>
        )}
      </p>
      <ProfitChart
        items={top.map((x) => ({
          name: x["Nombre Corregido"],
          profit: x.profit,
          avgMargin: x.avg_margin,
        }))}
      />

      {Object.keys(counts).length > 0 && (
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {Object.entries(CLASS_INFO)
            .filter(([cls]) => counts[cls])
            .map(([cls, info]) => (
              <div
                key={cls}
                className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3"
              >
                <p className="text-sm font-medium text-zinc-200">
                  {info.icon} {counts[cls]} {cls}
                  {counts[cls] === 1 ? "" : cls === "Niche" ? "" : "s"}
                </p>
                <p className="mt-0.5 text-xs text-zinc-500">{info.desc}</p>
              </div>
            ))}
        </div>
      )}

      {(marginEstimated || (coverage != null && coverage < 100)) && (
        <p className="mt-4 text-xs text-zinc-500">
          {marginEstimated && (
            <>
              Incluye <em className="text-zinc-400">márgenes estimados por
              categoría</em> donde el producto no tiene margen propio.{" "}
            </>
          )}
          {coverage != null && coverage < 100 && (
            <>Tus márgenes cubren el {fmtNum(coverage)}% de tus ventas. </>
          )}
          <Link href="/productos" className="text-emerald-400 hover:underline">
            Ajustar márgenes →
          </Link>
        </p>
      )}
      {top.length > 0 && top[0].profit != null && (
        <p className="mt-2 text-xs text-zinc-500">
          Tu producto más rentable deja {fmtMoney(top[0].profit, c)} de
          utilidad en el periodo.
        </p>
      )}
    </section>
  );
}

// ── Combos sugeridos con tus propios datos ────────────────────────────────

export function BundlesSection({ r }: { r: GatedReport }) {
  const b = r.analyses.bundles;
  if (!b || !b.has_data) return null;
  const featured = b.launch_ready.length > 0 ? b.launch_ready : b.balanced;
  if (featured.length === 0) return null;
  const ready = b.launch_ready.length > 0;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Combos sugeridos</h2>
      <p className="mt-1 text-sm text-zinc-400">
        {ready
          ? "Estos combos salen de tus propias ventas: parejas con adopción comprobada y aporte de margen. Listos para probar en mostrador."
          : "Las mejores parejas de tus ventas para probar como combo, balanceando adopción y margen."}
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {featured.slice(0, 6).map((x) => (
          <div
            key={`${x.anchor}+${x.target}`}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3"
          >
            <p className="text-sm font-medium text-zinc-200">
              {x.anchor} <span className="text-zinc-500">+</span> {x.target}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              {fmtPct(x.confidence)} de quienes llevan el primero aceptarían el
              segundo · lift {x.lift == null ? "—" : x.lift.toFixed(1)}
              {b.has_margin_data && x.target_margin != null && (
                <> · margen del agregado {fmtNum(x.target_margin)}%</>
              )}
            </p>
            {x.launch_ready && (
              <span className="mt-2 inline-block rounded-full border border-emerald-800 bg-emerald-950 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                listo para lanzar
              </span>
            )}
          </div>
        ))}
      </div>
      {b.notes && <p className="mt-3 text-xs text-zinc-600">{b.notes}</p>}
    </section>
  );
}

// ── Plan de acción (recomendaciones del motor) ────────────────────────────

export function RecommendationsSection({ r }: { r: GatedReport }) {
  if (r.recommendations.length === 0) return null;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Tu plan de acción</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Lo más importante que harías esta semana según tus datos, en orden.
      </p>
      <ol className="mt-4 space-y-3">
        {r.recommendations.slice(0, 6).map((rec, i) => (
          <li
            key={i}
            className="flex gap-3 rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3"
          >
            <span className="mt-0.5 text-sm font-semibold text-emerald-400">
              {i + 1}.
            </span>
            <div>
              <p className="text-sm text-zinc-200">{rec.action}</p>
              <p className="mt-1 text-xs text-zinc-500">
                {rec.impact}
                {rec.owner && <> · responsable: {rec.owner}</>}
                {rec.horizon && <> · plazo: {rec.horizon}</>}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
