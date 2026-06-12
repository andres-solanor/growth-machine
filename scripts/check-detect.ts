// Prueba rápida de la autodetección de columnas con encabezados reales.
// Uso: npx tsx scripts/check-detect.ts

import { readFileSync } from "node:fs";
import { detectColumns } from "../src/lib/csv-detect";
import { parsePreview } from "../src/lib/file-parse";

// Encabezados del POS de La Panettería (caso real conocido)
const panetteria = [
  "Fecha", "Hora", "Código venta", "Producto", "Cantidad", "Individual", "Total",
];
console.log("Panetteria:", detectColumns(panetteria));

// Variante genérica de otro POS
const generico = [
  "FECHA", "No. Factura", "Descripción", "Cant.", "Precio Unitario", "Valor Total",
];
console.log("Generico:", detectColumns(generico));

// CSV de muestra commiteado en el repo
const buf = readFileSync("reports/input_data/sales_carts_sample.csv");
const prev = parsePreview(buf, "sales_carts_sample.csv");
console.log("Sample CSV headers:", prev.headers);
console.log("Sample CSV rows:", prev.rowCount);
console.log("Sample CSV automap:", detectColumns(prev.headers));
