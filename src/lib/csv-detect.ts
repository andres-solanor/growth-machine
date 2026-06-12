// Autodetección de columnas del archivo de ventas del POS.
// Espeja las columnas canónicas que entiende el motor Python
// (ReportConfig._COLUMN_ALIASES en reports/report_generator.py):
// las claves de aquí viajan tal cual en config_json.columns.

export const CANONICAL_FIELDS = [
  { key: "date", label: "Fecha de la venta", required: true },
  { key: "time", label: "Hora", required: false },
  { key: "order_id", label: "Código / número de venta", required: true },
  { key: "product", label: "Producto", required: true },
  { key: "quantity", label: "Cantidad", required: true },
  { key: "unit_price", label: "Precio unitario", required: false },
  { key: "total", label: "Total de la línea", required: true },
  { key: "categoria", label: "Categoría del producto", required: false },
  { key: "subcategoria", label: "Subcategoría", required: false },
  { key: "margen_pct", label: "Margen (%)", required: false },
] as const;

export type FieldKey = (typeof CANONICAL_FIELDS)[number]["key"];
export type ColumnMapping = Partial<Record<FieldKey, string>>;

// Sinónimos habituales en exports de POS LatAm (orden = prioridad).
const SYNONYMS: Record<FieldKey, string[]> = {
  date: ["fecha", "fecha venta", "fecha de venta", "dia", "date"],
  time: ["hora", "hora venta", "time"],
  order_id: [
    "codigo venta", "venta", "factura", "ticket", "orden", "pedido",
    "comprobante", "recibo", "consecutivo", "numero venta", "nro venta",
    "id venta", "transaccion", "order",
  ],
  product: [
    "producto", "articulo", "item", "descripcion", "nombre producto",
    "detalle", "product",
  ],
  quantity: ["cantidad", "cant", "unidades", "qty", "und", "uds"],
  unit_price: [
    "individual", "precio unitario", "valor unitario", "precio unit",
    "vlr unitario", "p unit", "punit", "precio", "unit price",
  ],
  total: [
    "total", "valor total", "importe", "total linea", "vlr total",
    "subtotal", "monto",
  ],
  categoria: [
    "categoria", "categoria real", "category", "familia", "linea",
    "tipo producto", "grupo",
  ],
  subcategoria: [
    "subcategoria", "sub categoria", "subcategory", "sub category",
    "subfamilia", "sub linea", "sublinea",
  ],
  margen_pct: [
    "margen", "margen pct", "margen %", "margin", "margin pct",
    "margin %", "rentabilidad", "margen porcentaje",
  ],
};

function normalize(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // sin tildes
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Dos pasadas: igualdad exacta primero (gana siempre), luego "contiene".
// Una columna del archivo solo puede quedar asignada a un campo.
export function detectColumns(headers: string[]): ColumnMapping {
  const norm = headers.map(normalize);
  const mapping: ColumnMapping = {};
  const taken = new Set<number>();

  for (const { key } of CANONICAL_FIELDS) {
    const idx = norm.findIndex(
      (h, i) => !taken.has(i) && SYNONYMS[key].includes(h),
    );
    if (idx >= 0) {
      mapping[key] = headers[idx];
      taken.add(idx);
    }
  }
  for (const { key } of CANONICAL_FIELDS) {
    if (mapping[key]) continue;
    const idx = norm.findIndex(
      (h, i) => !taken.has(i) && SYNONYMS[key].some((syn) => h.includes(syn)),
    );
    if (idx >= 0) {
      mapping[key] = headers[idx];
      taken.add(idx);
    }
  }
  return mapping;
}
