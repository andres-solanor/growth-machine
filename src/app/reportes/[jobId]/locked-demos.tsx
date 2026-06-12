import type { ReactNode } from "react";

// Contenido DEMO de las secciones bloqueadas (teasers con blur).
// SEGURIDAD: todo lo de este archivo es SINTÉTICO e idéntico para todos los
// tenants — el gating server-side (src/lib/gating.ts) jamás envía el dato
// real al navegador y eso no cambia aquí. Cada tarjeta lo declara con la
// etiqueta "vista de ejemplo". No importar nada del payload en este archivo.

// La primera fila se ve nítida y el resto se desvanece con blur; el fade
// final lo pone la máscara de gradiente del wrapper en sections.tsx.
const row = (i: number) =>
  `flex items-center gap-3 py-1.5 ${i === 0 ? "" : "blur-[2px]"}`;

function Bar({ pct, cls }: { pct: number; cls: string }) {
  return (
    <span className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
      <span className={`block h-full ${cls}`} style={{ width: `${pct}%` }} />
    </span>
  );
}

function BasketDemo() {
  const pairs = [
    { p: "Café americano + Croissant", n: 41, lift: 2.3, w: 100 },
    { p: "Jugo natural + Sándwich de pollo", n: 33, lift: 1.9, w: 80 },
    { p: "Capuchino + Brownie", n: 27, lift: 2.6, w: 66 },
    { p: "Té chai + Galletas", n: 19, lift: 1.4, w: 46 },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {pairs.map((x, i) => (
        <li key={x.p} className={row(i)}>
          <span className="w-44 shrink-0 truncate text-zinc-300">{x.p}</span>
          <Bar pct={x.w} cls="bg-emerald-500" />
          <span className="w-20 shrink-0 text-right">
            {x.n}× · lift {x.lift}
          </span>
        </li>
      ))}
    </ul>
  );
}

function CartDemo() {
  const dist = [
    { seg: "1 producto", pct: 52 },
    { seg: "2 productos", pct: 31 },
    { seg: "3 productos", pct: 12 },
    { seg: "4 o más", pct: 5 },
  ];
  return (
    <div className="text-xs text-zinc-400">
      <ul>
        {dist.map((x, i) => (
          <li key={x.seg} className={row(i)}>
            <span className="w-24 shrink-0 text-zinc-300">{x.seg}</span>
            <Bar pct={x.pct * 1.8} cls="bg-sky-500" />
            <span className="w-10 shrink-0 text-right">{x.pct}%</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 blur-[2px]">
        Ticket promedio: 1 ítem $9.500 · 2+ ítems $21.300 (2,2× más)
      </p>
    </div>
  );
}

function TrendsDemo() {
  const items = [
    { p: "Cold brew", v: "+38%", up: true },
    { p: "Croissant de almendras", v: "+21%", up: true },
    { p: "Muffin de arándanos", v: "−17%", up: false },
    { p: "Limonada natural", v: "−12%", up: false },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {items.map((x, i) => (
        <li key={x.p} className={`${row(i)} justify-between`}>
          <span className="truncate text-zinc-300">
            {x.up ? "↑" : "↓"} {x.p}
          </span>
          <span className={x.up ? "text-emerald-400" : "text-red-400"}>
            {x.v} vs. mes anterior
          </span>
        </li>
      ))}
    </ul>
  );
}

function TicketDemo() {
  const hours = [
    { h: "16:00", gap: 24, n: 210 },
    { h: "10:00", gap: 18, n: 340 },
    { h: "20:00", gap: 11, n: 95 },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {hours.map((x, i) => (
        <li key={x.h} className={row(i)}>
          <span className="w-12 shrink-0 font-medium text-zinc-300">{x.h}</span>
          <Bar pct={x.gap * 4} cls="bg-amber-500" />
          <span className="w-44 shrink-0 text-right">
            ticket {x.gap}% bajo su potencial · {x.n} órdenes
          </span>
        </li>
      ))}
    </ul>
  );
}

function AnomaliesDemo() {
  const days = [
    { d: "sáb 14 jun", v: "+85% sobre lo esperado", up: true },
    { d: "dom 22 jun", v: "+61% sobre lo esperado", up: true },
    { d: "mar 03 jun", v: "−47% (día inusualmente bajo)", up: false },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {days.map((x, i) => (
        <li key={x.d} className={`${row(i)} justify-between`}>
          <span className="text-zinc-300">{x.d}</span>
          <span className={x.up ? "text-emerald-400" : "text-red-400"}>
            {x.v}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RulesDemo() {
  const rules = [
    { si: "Café americano", ent: "Croissant", conf: 38, lift: 2.1 },
    { si: "Sándwich de pollo", ent: "Jugo natural", conf: 31, lift: 1.8 },
    { si: "Brownie", ent: "Capuchino", conf: 27, lift: 2.4 },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {rules.map((x, i) => (
        <li key={x.si} className={row(i)}>
          <span className="truncate">
            Quien lleva <span className="text-zinc-300">{x.si}</span> →{" "}
            {x.conf}% también lleva{" "}
            <span className="text-zinc-300">{x.ent}</span> · lift {x.lift}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ProfitabilityDemo() {
  const items = [
    { p: "Capuchino 👑", u: "$4,1 M", m: 62, w: 100 },
    { p: "Sándwich de pollo 🚜", u: "$3,2 M", m: 38, w: 78 },
    { p: "Torta de zanahoria 💎", u: "$1,9 M", m: 71, w: 46 },
  ];
  return (
    <ul className="text-xs text-zinc-400">
      {items.map((x, i) => (
        <li key={x.p} className={row(i)}>
          <span className="w-40 shrink-0 truncate text-zinc-300">{x.p}</span>
          <Bar pct={x.w} cls="bg-amber-500" />
          <span className="w-32 shrink-0 text-right">
            {x.u} utilidad · {x.m}% margen
          </span>
        </li>
      ))}
    </ul>
  );
}

function BundlesDemo() {
  const combos = [
    {
      n: "Combo Mañana",
      d: "Café americano + Croissant",
      m: "margen 54% · listo para lanzar",
    },
    {
      n: "Combo Tarde",
      d: "Té chai + Galletas",
      m: "margen 48% · lift 1.9",
    },
  ];
  return (
    <div className="space-y-2 text-xs text-zinc-400">
      {combos.map((x, i) => (
        <div
          key={x.n}
          className={`rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 ${i === 0 ? "" : "blur-[2px]"}`}
        >
          <p className="font-medium text-zinc-300">{x.n}</p>
          <p>
            {x.d} · {x.m}
          </p>
        </div>
      ))}
    </div>
  );
}

export const LOCKED_DEMOS: Record<string, ReactNode> = {
  basket: <BasketDemo />,
  cart: <CartDemo />,
  trends: <TrendsDemo />,
  ticket: <TicketDemo />,
  anomalies: <AnomaliesDemo />,
  basket_rules: <RulesDemo />,
  profitability: <ProfitabilityDemo />,
  bundles: <BundlesDemo />,
};
