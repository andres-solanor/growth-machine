import type { GatedReport } from "@/lib/report";
import { fmtMoney, fmtNum, fmtIsoDate } from "@/lib/format";

// Secciones Pro del reporte (canasta, carrito, tendencias, ticket, días
// atípicos, reglas de combos). Mismo estilo que sections.tsx: server
// components puros; cada una devuelve null si el gating quitó su módulo,
// así la página las renderiza sin condicionales.

const card = "rounded-2xl border border-zinc-800 bg-zinc-900 p-6";

const fmtPct = (v: number | null | undefined, decimals = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(decimals)}%`;

const fmtHour = (h: number | null | undefined) =>
  h == null ? "—" : `${String(h).padStart(2, "0")}:00`;

// "2026-04" → "abr 2026" (UTC para no correrse de mes por zona horaria).
const monthLabel = (ym: string | null) => {
  if (!ym) return "—";
  const d = new Date(`${ym}-01T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return ym;
  return new Intl.DateTimeFormat("es-CO", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
};

// ── Canasta: qué compran juntos ───────────────────────────────────────────

export function BasketSection({ r }: { r: GatedReport }) {
  const b = r.analyses.basket;
  if (!b || b.pairs.length === 0) return null;
  const top = b.pairs.slice(0, 8);
  const maxCount = Math.max(...top.map((p) => p.count), 1);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Qué compran juntos</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Las parejas de productos que más se repiten en tus{" "}
        {fmtNum(b.total_baskets)} carritos multi-producto. Úsalas para ubicar
        productos cerca, armar combos o sugerir en caja.
      </p>
      <ul className="mt-4 space-y-2">
        {top.map((p) => (
          <li key={`${p.product_a}+${p.product_b}`} className="text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-zinc-200">
                {p.product_a} <span className="text-zinc-500">+</span>{" "}
                {p.product_b}
              </span>
              <span className="shrink-0 text-zinc-400">
                {fmtNum(p.count)} veces
                {p.lift != null && p.lift >= 1.5 && (
                  <span className="ml-2 rounded-full border border-emerald-700 bg-emerald-950 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                    fuerte
                  </span>
                )}
              </span>
            </div>
            <div className="mt-1 h-1.5 rounded bg-zinc-800">
              <div
                className="h-1.5 rounded bg-emerald-600"
                style={{ width: `${(p.count / maxCount) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ── Radiografía del carrito ───────────────────────────────────────────────

export function CartSection({ r }: { r: GatedReport }) {
  const cart = r.analyses.cart;
  if (!cart) return null;
  const c = r.meta.currency;
  const dist = cart.cart_dist.slice(0, 8);
  const maxDist = Math.max(...dist.map((d) => d.count), 1);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Radiografía del carrito</h2>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">
            ¿Cuántos productos llevan por compra?
          </h3>
          <ul className="space-y-1.5">
            {dist.map((d) => (
              <li
                key={d.products_in_cart}
                className="flex items-center gap-2 text-xs"
              >
                <span className="w-6 shrink-0 text-zinc-400">
                  {d.products_in_cart}
                </span>
                <div className="h-3 flex-1 rounded bg-zinc-800">
                  <div
                    className="h-3 rounded bg-emerald-600"
                    style={{ width: `${(d.count / maxDist) * 100}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right text-zinc-400">
                  {fmtNum(d.count)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">
            Ticket promedio por segmento
          </h3>
          <ul className="divide-y divide-zinc-800 rounded-xl border border-zinc-800 bg-zinc-950">
            {cart.segment_stats.map((s) => (
              <li
                key={s.segment}
                className="flex items-center justify-between gap-3 px-3 py-2 text-xs"
              >
                <span className="text-zinc-300">{s.segment}</span>
                <span className="text-zinc-400">
                  {fmtMoney(s.avg_ticket ?? 0, c)} ·{" "}
                  {fmtNum(s.share_pct ?? 0)}% de órdenes
                </span>
              </li>
            ))}
          </ul>
          {cart.single_top_ticket.length > 0 && (
            <p className="mt-3 text-xs text-zinc-500">
              El producto &ldquo;solo&rdquo; con mejor ticket:{" "}
              <span className="text-zinc-300">
                {cart.single_top_ticket[0].product}
              </span>{" "}
              ({fmtMoney(cart.single_top_ticket[0].avg_ticket ?? 0, c)}).
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

// ── Tendencias: en alza y en caída ───────────────────────────────────────

export function TrendsSection({ r }: { r: GatedReport }) {
  const t = r.analyses.trends;
  if (!t || (t.growing.length === 0 && t.declining.length === 0)) return null;

  const signed = (v: number | null) =>
    v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Productos en alza y en caída</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Comparando {monthLabel(t.base_month)} con {monthLabel(t.compare_month)}.
      </p>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-emerald-400">
            ▲ Creciendo
          </h3>
          <ul className="space-y-1.5 text-sm">
            {t.growing.slice(0, 6).map((p) => (
              <li key={p.product} className="flex justify-between gap-3">
                <span className="truncate text-zinc-200">{p.product}</span>
                <span className="shrink-0 font-medium text-emerald-400">
                  {signed(p.growth_pct)}
                </span>
              </li>
            ))}
            {t.growing.length === 0 && (
              <li className="text-zinc-500">Ninguno este periodo.</li>
            )}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-red-400">▼ Cayendo</h3>
          <ul className="space-y-1.5 text-sm">
            {t.declining.slice(0, 6).map((p) => (
              <li key={p.product} className="flex justify-between gap-3">
                <span className="truncate text-zinc-200">{p.product}</span>
                <span className="shrink-0 font-medium text-red-400">
                  {signed(p.growth_pct)}
                </span>
              </li>
            ))}
            {t.declining.length === 0 && (
              <li className="text-zinc-500">Ninguno este periodo.</li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── Oportunidades de ticket ──────────────────────────────────────────────

export function TicketSection({ r }: { r: GatedReport }) {
  const t = r.analyses.ticket;
  if (!t) return null;
  const c = r.meta.currency;
  const hours = t.hour_ticket;
  const maxTicket = Math.max(...hours.map((h) => h.avg_ticket ?? 0), 1);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Oportunidades de ticket</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Horas con buen tráfico pero ticket por debajo de tu potencial: ahí una
        sugerencia en caja o un combo sube la venta sin traer más clientes.
      </p>

      {t.opportunity_hours.length > 0 && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {t.opportunity_hours.slice(0, 3).map((h) => (
            <div
              key={h.hour}
              className="rounded-xl border border-amber-900 bg-zinc-950 p-4"
            >
              <p className="text-lg font-bold text-amber-400">
                {fmtHour(h.hour)}
              </p>
              <p className="mt-1 text-xs text-zinc-400">
                ticket {fmtMoney(h.avg_ticket ?? 0, c)} ·{" "}
                {fmtNum(h.orders)} órdenes
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {h.gap_pct != null
                  ? `${Math.abs(h.gap_pct).toFixed(0)}% por debajo de tu promedio`
                  : ""}
              </p>
            </div>
          ))}
        </div>
      )}

      <h3 className="mt-6 mb-2 text-sm font-medium text-zinc-300">
        Ticket promedio por hora
      </h3>
      <ul className="space-y-1">
        {hours.map((h) => (
          <li key={h.hour} className="flex items-center gap-2 text-xs">
            <span className="w-10 shrink-0 text-zinc-400">{fmtHour(h.hour)}</span>
            <div className="h-2.5 flex-1 rounded bg-zinc-800">
              <div
                className="h-2.5 rounded bg-sky-600"
                style={{ width: `${((h.avg_ticket ?? 0) / maxTicket) * 100}%` }}
              />
            </div>
            <span className="w-20 shrink-0 text-right text-zinc-400">
              {fmtMoney(h.avg_ticket ?? 0, c)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ── Días atípicos ─────────────────────────────────────────────────────────

export function AnomaliesSection({ r }: { r: GatedReport }) {
  const a = r.analyses.anomalies;
  if (!a || (a.high_days.length === 0 && a.low_days.length === 0)) return null;
  const c = r.meta.currency;

  const dayRow = (d: (typeof a.high_days)[number], good: boolean) => (
    <li
      key={d.date}
      className="flex items-center justify-between gap-3 px-3 py-2 text-xs"
    >
      <span className="text-zinc-300">{fmtIsoDate(d.date)}</span>
      <span className={good ? "text-emerald-400" : "text-red-400"}>
        {fmtMoney(d.revenue ?? 0, c)}
      </span>
    </li>
  );

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Días atípicos</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Tu día normal vende {fmtMoney(a.avg_daily_revenue ?? 0, c)}. Estos días
        se salieron de lo esperado — vale la pena recordar qué pasó (clima,
        evento, promoción, festivo).
      </p>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-emerald-400">
            Días excepcionales
          </h3>
          <ul className="divide-y divide-zinc-800 rounded-xl border border-zinc-800 bg-zinc-950">
            {a.high_days.slice(0, 5).map((d) => dayRow(d, true))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-red-400">
            Días inusualmente bajos
          </h3>
          <ul className="divide-y divide-zinc-800 rounded-xl border border-zinc-800 bg-zinc-950">
            {a.low_days.slice(0, 5).map((d) => dayRow(d, false))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── Reglas para combos ────────────────────────────────────────────────────

export function BasketRulesSection({ r }: { r: GatedReport }) {
  const br = r.analyses.basket_rules;
  if (!br || br.rules.length === 0) return null;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Reglas para combos</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Si el cliente lleva el primero, esta es la probabilidad de que acepte
        el segundo. Entrena a tu equipo de caja con las primeras 3.
      </p>
      <ul className="mt-4 space-y-2">
        {br.rules.slice(0, 8).map((rule) => (
          <li
            key={`${rule.antecedent}->${rule.consequent}`}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-zinc-200">
                Lleva <strong>{rule.antecedent}</strong>{" "}
                <span className="text-zinc-500">→ ofrécele</span>{" "}
                <strong>{rule.consequent}</strong>
              </span>
              <span className="shrink-0 rounded-full border border-emerald-700 bg-emerald-950 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
                {fmtPct(rule.confidence)} acepta
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              {fmtNum(rule.count)} compras juntas
              {rule.lift != null && ` · ${rule.lift.toFixed(1)}× más que el azar`}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
