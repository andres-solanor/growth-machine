"use client";

import Plotly from "plotly.js-cartesian-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

// Bundle cartesiano (~1/3 del Plotly completo): barras, líneas y heatmap,
// que es todo lo que usa el reporte. Solo se carga en el navegador (ver
// plot.tsx): Plotly toca window/document al importarse.
const Plot = createPlotlyComponent(Plotly);

export default Plot;
