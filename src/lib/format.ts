// Formateo es-LatAm. El payload trae fechas ISO y números crudos; el formateo
// vive en la web (Intl), nunca en el motor (riesgo de locale del servidor).

const COUNTRY_TZ: Record<string, string> = {
  CO: "America/Bogota",
  MX: "America/Mexico_City",
  PE: "America/Lima",
  CL: "America/Santiago",
  AR: "America/Argentina/Buenos_Aires",
  EC: "America/Guayaquil",
  UY: "America/Montevideo",
  GT: "America/Guatemala",
  CR: "America/Costa_Rica",
  DO: "America/Santo_Domingo",
  BO: "America/La_Paz",
  PY: "America/Asuncion",
  PA: "America/Panama",
  US: "America/New_York",
  ES: "Europe/Madrid",
};

export function tzForCountry(country: string): string {
  return COUNTRY_TZ[country] ?? "America/Bogota";
}

export function fmtMoney(n: number, currency: string): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(n);
}

export function fmtNum(n: number): string {
  return new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 }).format(n);
}

export function fmtDateTime(d: Date | string, country = "CO"): string {
  return new Date(d).toLocaleString("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: tzForCountry(country),
  });
}

export function fmtIsoDate(iso: string): string {
  // "2026-01-02" -> "2 ene 2026" sin sorpresas de zona horaria
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
