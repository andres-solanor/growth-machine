import * as XLSX from "xlsx";

// Lectura ligera del archivo SOLO para el asistente de mapeo: encabezados,
// filas de muestra y conteo aproximado. El parseo real y la limpieza los
// hace el motor Python en el worker.

export type FilePreview = {
  headers: string[];
  sample: string[][]; // hasta 5 filas
  rowCount: number;
};

const SAMPLE_ROWS = 5;

export function isAllowedFilename(name: string): boolean {
  return /\.(csv|xls|xlsx)$/i.test(name);
}

export function parsePreview(buf: Buffer, filename: string): FilePreview {
  if (/\.csv$/i.test(filename)) return parseCsvPreview(buf);
  return parseSheetPreview(buf);
}

function decodeText(buf: Buffer): string {
  const utf8 = buf.toString("utf-8");
  // Muchos POS exportan en Windows-1252; si la decodificación UTF-8 dejó
  // demasiados caracteres de reemplazo, reintentar como latin1.
  const bad = (utf8.match(/�/g) ?? []).length;
  if (bad > 5 || (utf8.length > 0 && bad / utf8.length > 0.001)) {
    return buf.toString("latin1");
  }
  return utf8;
}

function detectDelimiter(line: string): string {
  const counts: [string, number][] = [";", ",", "\t"].map((d) => [
    d,
    line.split(d).length - 1,
  ]);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 0 ? counts[0][0] : ",";
}

// Parser CSV mínimo con soporte de comillas (suficiente para previsualizar).
function splitCsvLine(line: string, delim: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === delim) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

function parseCsvPreview(buf: Buffer): FilePreview {
  const text = decodeText(buf);
  const lines = text.split(/\r\n|\n|\r/).filter((l) => l.trim() !== "");
  if (lines.length === 0) return { headers: [], sample: [], rowCount: 0 };
  const delim = detectDelimiter(lines[0]);
  const headers = splitCsvLine(lines[0], delim);
  const sample = lines
    .slice(1, 1 + SAMPLE_ROWS)
    .map((l) => splitCsvLine(l, delim));
  return { headers, sample, rowCount: lines.length - 1 };
}

function parseSheetPreview(buf: Buffer): FilePreview {
  // sheetRows limita lo que se materializa; el conteo real lo hará Python.
  const wb = XLSX.read(buf, { type: "buffer", sheetRows: 5000 });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  if (!sheet) return { headers: [], sample: [], rowCount: 0 };
  const rows = XLSX.utils.sheet_to_json<string[]>(sheet, {
    header: 1,
    raw: false,
    defval: "",
  });
  const nonEmpty = rows.filter((r) =>
    r.some((c) => String(c ?? "").trim() !== ""),
  );
  if (nonEmpty.length === 0) return { headers: [], sample: [], rowCount: 0 };
  const headers = nonEmpty[0].map((h) => String(h ?? "").trim());
  const sample = nonEmpty
    .slice(1, 1 + SAMPLE_ROWS)
    .map((r) => headers.map((_, i) => String(r[i] ?? "")));
  return { headers, sample, rowCount: nonEmpty.length - 1 };
}
