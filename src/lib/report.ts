import { gunzipSync } from "node:zlib";
import { and, desc, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import type { SalesReportPayload } from "@/lib/payload-schema";

// La lógica de gating vive en gating.ts (pura, sin DB) para que
// scripts/check-gating.ts pueda verificarla sin DATABASE_URL.
export * from "./gating";

// ── Carga de payloads ─────────────────────────────────────────────────────
// Un payload descomprimido pesa varios MB. Releer el blob, parsearlo y
// REvalidarlo con zod en cada vista disparaba CPU/memoria/I-O juntos en
// Hostinger (ráfagas de 503 al solaparse requests): el payload ya quedó
// validado con zod al guardarse (api/worker/.../result), así que aquí solo
// se parsea una vez y se cachea por proceso. El bloque interactive_base
// (filas crudas para el filtrado interactivo, aún sin UI) es la mayor parte
// del payload y se suelta antes de cachear: nadie lo renderiza todavía.

// Clave: report_payloads.id. Una fila de un job exitoso nunca se sobreescribe
// (el worker no re-entrega jobs ya succeeded), así que no hay invalidación;
// un análisis nuevo crea una fila nueva → cache miss natural.
const payloadCache = new Map<number, SalesReportPayload>();
const CACHE_MAX = 3;

function parseAndCache(rowId: number, gz: Buffer): SalesReportPayload {
  const payload = JSON.parse(
    gunzipSync(gz).toString("utf-8"),
  ) as SalesReportPayload;
  delete payload.analyses.interactive_base;
  payloadCache.set(rowId, payload);
  if (payloadCache.size > CACHE_MAX) {
    const oldest = payloadCache.keys().next().value;
    if (oldest !== undefined) payloadCache.delete(oldest);
  }
  return payload;
}

function fromCache(rowId: number): SalesReportPayload | undefined {
  const hit = payloadCache.get(rowId);
  if (hit) {
    // Map conserva orden de inserción: re-insertar = marcar como reciente.
    payloadCache.delete(rowId);
    payloadCache.set(rowId, hit);
  }
  return hit;
}

// El blob solo se trae de la DB en cache miss (primero se consulta el id,
// que es una fila diminuta).
async function loadByRowId(rowId: number): Promise<SalesReportPayload | null> {
  const hit = fromCache(rowId);
  if (hit) return hit;
  const rows = await getDb()
    .select({ payloadGz: schema.reportPayloads.payloadGz })
    .from(schema.reportPayloads)
    .where(eq(schema.reportPayloads.id, rowId))
    .limit(1);
  if (rows.length === 0) return null;
  return parseAndCache(rowId, rows[0].payloadGz);
}

// Carga y descomprime el payload de un job exitoso del tenant.
export async function loadReportPayload(
  jobId: number,
  tenantId: number,
): Promise<SalesReportPayload | null> {
  const meta = await getDb()
    .select({ id: schema.reportPayloads.id })
    .from(schema.reportPayloads)
    .where(
      and(
        eq(schema.reportPayloads.jobId, jobId),
        eq(schema.reportPayloads.tenantId, tenantId),
      ),
    )
    .limit(1);
  if (meta.length === 0) return null;
  return loadByRowId(meta[0].id);
}

// Último payload del tenant (el editor de productos saca de aquí la lista
// de productos con su revenue/frecuencia — nunca empieza en blanco).
export async function loadLatestReportPayload(
  tenantId: number,
): Promise<SalesReportPayload | null> {
  const meta = await getDb()
    .select({ id: schema.reportPayloads.id })
    .from(schema.reportPayloads)
    .where(eq(schema.reportPayloads.tenantId, tenantId))
    .orderBy(desc(schema.reportPayloads.id))
    .limit(1);
  if (meta.length === 0) return null;
  return loadByRowId(meta[0].id);
}
