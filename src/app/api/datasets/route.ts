import { createHash } from "node:crypto";
import { gzip as _gzip } from "node:zlib";
import { promisify } from "node:util";
const gzip = promisify(_gzip);
import { NextResponse } from "next/server";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { detectColumns } from "@/lib/csv-detect";
import { isAllowedFilename, parsePreview } from "@/lib/file-parse";

export const dynamic = "force-dynamic";

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB

// POST /api/datasets — sube el archivo de ventas, lo guarda gzip en MySQL y
// devuelve encabezados + muestra + mapeo autodetectado para el asistente.
export async function POST(req: Request) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "No autenticado" }, { status: 401 });
  }

  let file: File | null = null;
  try {
    const form = await req.formData();
    const f = form.get("file");
    if (f instanceof File) file = f;
  } catch {
    // body inválido
  }
  if (!file) {
    return NextResponse.json({ error: "Falta el archivo" }, { status: 400 });
  }
  if (!isAllowedFilename(file.name)) {
    return NextResponse.json(
      { error: "Formato no soportado. Sube un archivo .csv, .xls o .xlsx" },
      { status: 422 },
    );
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      { error: "El archivo supera el límite de 20 MB" },
      { status: 422 },
    );
  }

  const buf = Buffer.from(await file.arrayBuffer());

  let preview;
  try {
    preview = parsePreview(buf, file.name);
  } catch (err) {
    console.error("[datasets] error al leer archivo:", err);
    preview = { headers: [], sample: [], rowCount: 0 };
  }
  if (preview.headers.length === 0 || preview.rowCount === 0) {
    return NextResponse.json(
      {
        error:
          "No pudimos leer columnas en el archivo. Verifica que sea el export de ventas de tu POS (con encabezados en la primera fila).",
      },
      { status: 422 },
    );
  }

  const db = getDb();
  const [ds] = await db
    .insert(schema.datasets)
    .values({
      tenantId: user.tenant.id,
      filename: file.name.slice(0, 255),
      contentGz: await gzip(buf),
      sha256: createHash("sha256").update(buf).digest("hex"),
      sizeBytes: buf.length,
    })
    .$returningId();

  return NextResponse.json({
    datasetId: ds.id,
    filename: file.name,
    rowCount: preview.rowCount,
    headers: preview.headers,
    sample: preview.sample,
    autoMap: detectColumns(preview.headers),
  });
}
