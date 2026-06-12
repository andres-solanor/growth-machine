"use client";

import dynamic from "next/dynamic";
import type { PlotParams } from "react-plotly.js";

// Plotly no soporta SSR (toca window al importarse), así que se carga
// dinámicamente solo en el cliente; mientras tanto, un esqueleto del
// mismo alto evita saltos de layout.
const LazyPlot = dynamic(() => import("./plot-inner"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full animate-pulse rounded-xl bg-zinc-800/40" />
  ),
});

export default function Plot(props: PlotParams) {
  return <LazyPlot {...props} />;
}
