import type { GatedReport } from "@/lib/report";
import { fmtMoney, fmtNum } from "@/lib/format";
import {
  CartDistChart,
  HourTicketChart,
  PairsChart,
  TrendsChart,
} from "@/components/charts/report-charts";

// Secciones Pro del reporte (canasta, carrito, tendencias, ticket, días
// atípicos, reglas de combos). Mismo estilo que sections.tsx: server
// components puros; cada una devuelve null si el gating quitó su módulo,
// así la página las renderiza sin condicionales.

const card = "rounded-2xl border border-zinc-800 bg-zinc-900 p-6";

const fmtPct = (v: number | null | undefined, decimals = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(decimals)}%`;

const fmtHour = (h: number | null | undefined) =>
  h == null ? "—" : `${String(h).padStart(2, "0")}:00`;

// Los días atípicos llegan del motor ya formateados ("08 Mar", strftime
// '%d %b' en locale C) — NO son ISO; solo traducimos el mes al español.
const MES_ES: Record<string, string> = {
  Jan: "ene", Feb: "feb", Mar: "mar", Apr: "abr", May: "may", Jun: "jun",
  Jul: "jul", Aug: "ago", Sep: "sep", Oct: "oct", Nov: "nov", Dec: "dic",
};
const dayLabel = (s: string) =>
  s.replace(/[A-Z][a-z]{2}/, (m) => MES_ES[m] ?? m);

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

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Qué compran juntos</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Las parejas de productos que más se repiten en tus{" "}
        {fmtNum(b.total_baskets)} carritos multi-producto. Úsalas para ubicar
        productos cerca, armar combos o sugerir en caja.
      </p>
      <PairsChart
        pairs={top.map((p) => ({
          a: p.product_a,
          b: p.product_b,
          count: p.count,
          lift: p.lift,
        }))}
      />
      <p className="mt-2 text-xs text-zinc-500">
        <span className="text-emerald-400">■</span> pareja fuerte (se buscan){" "}
        · <span className="text-amber-400">■</span> moderada ·{" "}
        <span className="text-red-400">■</span> coinciden menos que el azar
      </p>
    </section>
  );
}

// ── Radiografía del carrito ───────────────────────────────────────────────

export function CartSection({ r }: { r: GatedReport }) {
  const cart = r.analyses.cart;
  if (!cart) return null;
  const c = r.meta.currency;
  const dist = cart.cart_dist.slice(0, 8);

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Radiografía del carrito</h2>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">
            ¿Cuántos productos llevan por compra?
          </h3>
          <CartDistChart
            dist={dist.map((d) => ({
              products_in_cart: d.products_in_cart,
              count: d.count,
            }))}
          />
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

  const items = [
    ...t.growing.slice(0, 6),
    ...t.declining.slice(0, 6),
  ].flatMap((p) =>
    p.growth_pct == null ? [] : [{ product: p.product, pct: p.growth_pct }],
  );
  if (items.length === 0) return null;

  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Productos en alza y en caída</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Comparando {monthLabel(t.base_month)} con {monthLabel(t.compare_month)}.
        Verde crece, rojo cae: revisa precio, exhibición o disponibilidad de
        los que caen antes de que se vuelva costumbre.
      </p>
      <TrendsChart items={items} />
    </section>
  );
}

// ── Oportunidades de ticket ──────────────────────────────────────────────

export function TicketSection({ r }: { r: GatedReport }) {
  const t = r.analyses.ticket;
  if (!t) return null;
  const c = r.meta.currency;

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

      <h3 className="mt-6 text-sm font-medium text-zinc-300">
        Ticket promedio por hora
      </h3>
      <p className="mt-1 text-xs text-zinc-500">
        Las barras ámbar son tus horas de oportunidad.
      </p>
      <HourTicketChart
        hours={t.hour_ticket.map((h) => ({
          hour: h.hour,
          avg_ticket: h.avg_ticket,
          orders: h.orders,
        }))}
        oppHours={t.opportunity_hours.map((h) => h.hour)}
      />
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
      <span className="text-zinc-300">{dayLabel(d.date)}</span>
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
