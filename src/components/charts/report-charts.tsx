"use client";

import type { Layout, PlotData } from "plotly.js";
import Plot from "./plot";

// Gráficos del reporte. Tema oscuro portado del motor original
// (reports/report_generator.py, const DL): fondos transparentes para que
// se vea la tarjeta, grilla sutil, sin barra de herramientas.
// Reciben datos YA filtrados por el gating del servidor: aquí no se decide
// qué puede ver cada plan.

const GRID = "#27272a"; // zinc-800
const ZERO = "#3f3f46"; // zinc-700

const BASE_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "ui-sans-serif, system-ui, sans-serif", color: "#a1a1aa", size: 12 },
  margin: { t: 8, r: 8, b: 36, l: 52 },
  hoverlabel: { bgcolor: "#18181b", bordercolor: "#3f3f46", font: { color: "#e4e4e7", size: 12 } },
  // dragmode off: en móvil el arrastre de zoom secuestra el scroll de la
  // página; el hover (el valor real del "interactivo") sigue funcionando.
  dragmode: false as Layout["dragmode"],
  xaxis: { gridcolor: GRID, zerolinecolor: ZERO },
  yaxis: { gridcolor: GRID, zerolinecolor: ZERO },
};

const CONFIG = { responsive: true, displayModeBar: false };

// Paleta para series por categoría (los colores por tenant llegarán con el
// editor de mapa de productos; mientras tanto, paleta fija consistente).
const PALETTE = [
  "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6b7280",
];

function Chart({
  data,
  layout,
  height,
}: {
  data: Partial<PlotData>[];
  layout?: Partial<Layout>;
  height: number;
}) {
  return (
    <div style={{ height }} className="mt-3">
      <Plot
        data={data}
        layout={{ ...BASE_LAYOUT, ...layout, autosize: true }}
        config={CONFIG}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}

const trunc = (s: string, n = 24) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// ── Ventas diarias + media móvil ─────────────────────────────────────────

export function DailyRevenueChart({
  daily,
}: {
  daily: { date_str: string; revenue: number | null; rolling_rev: number | null }[];
}) {
  const x = daily.map((d) => d.date_str);
  return (
    <Chart
      height={280}
      data={[
        {
          x,
          y: daily.map((d) => d.revenue),
          type: "bar",
          name: "Ventas del día",
          marker: { color: "rgba(59,130,246,0.45)" },
          hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>",
        },
        {
          x,
          y: daily.map((d) => d.rolling_rev),
          type: "scatter",
          mode: "lines",
          name: "Promedio 7 días",
          line: { color: "#f59e0b", width: 2 },
          hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>",
        },
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, t: 30 },
        legend: { orientation: "h", x: 0, y: 1.18, font: { size: 11 } },
        bargap: 0.25,
      }}
    />
  );
}

// ── Ventas por día de la semana ──────────────────────────────────────────

export function DowChart({
  dow,
}: {
  dow: { day: string; revenue: number | null }[];
}) {
  return (
    <Chart
      height={220}
      data={[
        {
          x: dow.map((d) => d.day),
          y: dow.map((d) => d.revenue),
          type: "bar",
          marker: { color: "#8b5cf6" },
          hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>",
        },
      ]}
      layout={{ xaxis: { ...BASE_LAYOUT.xaxis, type: "category" } }}
    />
  );
}

// ── Heatmap día × hora ───────────────────────────────────────────────────

export function HeatmapChart({
  days,
  hours,
  z,
}: {
  days: string[];
  hours: number[];
  z: (number | null)[][];
}) {
  return (
    <Chart
      height={Math.max(240, hours.length * 22 + 80)}
      data={[
        {
          z,
          x: days,
          y: hours.map((h) => `${h}:00`),
          type: "heatmap",
          // Colorscale del motor original: noche → azul → ámbar.
          colorscale: [
            [0, "#101014"],
            [0.5, "#3b82f6"],
            [1, "#f59e0b"],
          ],
          showscale: false,
          hovertemplate: "%{x} %{y}<br>%{z:.0f} órdenes<extra></extra>",
        } as Partial<PlotData>,
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, l: 56 },
        xaxis: { ...BASE_LAYOUT.xaxis, type: "category", gridcolor: "rgba(0,0,0,0)" },
        yaxis: {
          ...BASE_LAYOUT.yaxis,
          type: "category",
          autorange: "reversed",
          gridcolor: "rgba(0,0,0,0)",
        },
      }}
    />
  );
}

// ── Ventas mensuales por categoría (barras apiladas) ─────────────────────

export function MonthlyCatChart({
  rows,
}: {
  rows: { category: string; month: string; revenue: number | null }[];
}) {
  const cats = [...new Set(rows.map((r) => r.category))];
  return (
    <Chart
      height={280}
      data={cats.map((cat, i) => {
        const mine = rows.filter((r) => r.category === cat);
        return {
          x: mine.map((r) => r.month),
          y: mine.map((r) => r.revenue),
          type: "bar",
          name: trunc(cat, 18),
          marker: { color: PALETTE[i % PALETTE.length] },
          hovertemplate: `${cat}<br>%{x}: $%{y:,.0f}<extra></extra>`,
        } as Partial<PlotData>;
      })}
      layout={{
        barmode: "stack",
        margin: { ...BASE_LAYOUT.margin, t: 34 },
        xaxis: { ...BASE_LAYOUT.xaxis, type: "category" },
        legend: { orientation: "h", x: 0, y: 1.22, font: { size: 11 } },
      }}
    />
  );
}

// ── Top productos (barras horizontales) ──────────────────────────────────

export function TopProductsChart({
  items,
}: {
  items: { name: string; revenue: number | null; revShare: number | null }[];
}) {
  // El "1." del ranking también garantiza etiquetas únicas: si dos etiquetas
  // coinciden (p. ej. tras truncar), Plotly las fusiona en una sola barra.
  const labeled = items.map((p, i) => ({ ...p, label: `${i + 1}. ${trunc(p.name, 28)}` }));
  const ordered = [...labeled].reverse(); // Plotly pinta de abajo hacia arriba
  return (
    <Chart
      height={items.length * 32 + 50}
      data={[
        {
          y: ordered.map((p) => p.label),
          x: ordered.map((p) => p.revenue),
          type: "bar",
          orientation: "h",
          marker: { color: "#10b981" },
          text: ordered.map((p) =>
            p.revShare != null ? `${p.revShare.toFixed(1)}%` : "",
          ),
          textposition: "outside",
          textfont: { size: 11, color: "#a1a1aa" },
          cliponaxis: false,
          hovertemplate: "%{y}<br>$%{x:,.0f}<extra></extra>",
        } as Partial<PlotData>,
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, l: 8, r: 48, b: 28 },
        yaxis: { ...BASE_LAYOUT.yaxis, automargin: true, gridcolor: "rgba(0,0,0,0)" },
      }}
    />
  );
}

// ── Pares de canasta (color según lift, como el motor) ───────────────────

export function PairsChart({
  pairs,
}: {
  pairs: { a: string; b: string; count: number; lift: number | null }[];
}) {
  // Ranking visible + etiquetas únicas: pares distintos pueden truncar al
  // mismo texto y Plotly fusionaría sus barras en una sola fila.
  const labeled = pairs.map((p, i) => ({
    ...p,
    label: `${i + 1}. ${trunc(p.a, 18)} + ${trunc(p.b, 18)}`,
  }));
  const ordered = [...labeled].reverse();
  const liftColor = (lift: number | null) =>
    lift != null && lift >= 1.5
      ? "#10b981"
      : lift != null && lift >= 1
        ? "#f59e0b"
        : "#ef4444";
  return (
    <Chart
      height={pairs.length * 36 + 50}
      data={[
        {
          y: ordered.map((p) => p.label),
          x: ordered.map((p) => p.count),
          type: "bar",
          orientation: "h",
          marker: { color: ordered.map((p) => liftColor(p.lift)) },
          text: ordered.map((p) =>
            p.lift != null ? `lift ${p.lift.toFixed(1)}` : "",
          ),
          textposition: "outside",
          textfont: { size: 10, color: "#71717a" },
          cliponaxis: false,
          hovertemplate: "%{y}<br>%{x} veces juntos<extra></extra>",
        } as Partial<PlotData>,
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, l: 8, r: 56, b: 28 },
        yaxis: { ...BASE_LAYOUT.yaxis, automargin: true, gridcolor: "rgba(0,0,0,0)" },
      }}
    />
  );
}

// ── Distribución del carrito ─────────────────────────────────────────────

export function CartDistChart({
  dist,
}: {
  dist: { products_in_cart: number; count: number }[];
}) {
  return (
    <Chart
      height={200}
      data={[
        {
          x: dist.map((d) => String(d.products_in_cart)),
          y: dist.map((d) => d.count),
          type: "bar",
          marker: { color: "#10b981" },
          hovertemplate: "%{x} productos<br>%{y} compras<extra></extra>",
        },
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, l: 44, b: 30 },
        xaxis: { ...BASE_LAYOUT.xaxis, type: "category" },
      }}
    />
  );
}

// ── Tendencias: barra divergente (alza verde, caída roja) ────────────────

export function TrendsChart({
  items,
}: {
  items: { product: string; pct: number }[];
}) {
  const ordered = [...items].sort((a, b) => a.pct - b.pct);
  return (
    <Chart
      height={items.length * 30 + 50}
      data={[
        {
          // Espacios de ancho cero: etiquetas únicas aunque dos nombres
          // truncados coincidan (Plotly fusionaría las barras).
          y: ordered.map((p, i) => trunc(p.product, 26) + "\u200B".repeat(i)),
          x: ordered.map((p) => p.pct),
          type: "bar",
          orientation: "h",
          marker: { color: ordered.map((p) => (p.pct >= 0 ? "#10b981" : "#ef4444")) },
          text: ordered.map((p) => `${p.pct > 0 ? "+" : ""}${p.pct.toFixed(0)}%`),
          textposition: "outside",
          textfont: { size: 11 },
          cliponaxis: false,
          hovertemplate: "%{y}<br>%{x:.0f}%<extra></extra>",
        } as Partial<PlotData>,
      ]}
      layout={{
        margin: { ...BASE_LAYOUT.margin, l: 8, r: 52, b: 28 },
        xaxis: { ...BASE_LAYOUT.xaxis, zerolinecolor: "#52525b", ticksuffix: "%" },
        yaxis: { ...BASE_LAYOUT.yaxis, automargin: true, gridcolor: "rgba(0,0,0,0)" },
      }}
    />
  );
}

// ── Ticket por hora (horas de oportunidad en ámbar) ──────────────────────

export function HourTicketChart({
  hours,
  oppHours,
}: {
  hours: { hour: number; avg_ticket: number | null; orders: number | null }[];
  oppHours: number[];
}) {
  const opp = new Set(oppHours);
  return (
    <Chart
      height={240}
      data={[
        {
          x: hours.map((h) => `${h.hour}:00`),
          y: hours.map((h) => h.avg_ticket),
          type: "bar",
          marker: {
            color: hours.map((h) => (opp.has(h.hour) ? "#f59e0b" : "#0ea5e9")),
          },
          customdata: hours.map((h) => h.orders ?? 0),
          hovertemplate:
            "%{x}<br>Ticket: $%{y:,.0f}<br>%{customdata} órdenes<extra></extra>",
        } as Partial<PlotData>,
      ]}
      layout={{ xaxis: { ...BASE_LAYOUT.xaxis, type: "category" } }}
    />
  );
}
