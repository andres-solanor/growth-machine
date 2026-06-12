// El bundle cartesiano de Plotly (barras, líneas, heatmap) no trae tipos
// propios; reusa los de plotly.js (vía @types/plotly.js).
declare module "plotly.js-cartesian-dist-min" {
  import * as Plotly from "plotly.js";
  export = Plotly;
}
