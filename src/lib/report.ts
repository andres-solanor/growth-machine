import { gunzipSync } from "node:zlib";
import { and, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import {
  salesReportPayloadSchema,
  type SalesReportPayload,
} from "@/lib/payload-schema";

// La lógica de gating vive en gating.ts (pura, sin DB) para que
// scripts/check-gating.ts pueda verificarla sin DATABASE_URL.
export * from "./gating";

// Carga y descomprime el payload de un job exitoso del tenant.
export async function loadReportPayload(
  jobId: number,
  tenantId: number,
): Promise<SalesReportPayload | null> {
  const rows = await getDb()
    .select({ payloadGz: schema.reportPayloads.payloadGz })
    .from(schema.reportPayloads)
    .where(
      and(
        eq(schema.reportPayloads.jobId, jobId),
        eq(schema.reportPayloads.tenantId, tenantId),
      ),
    )
    .limit(1);
  if (rows.length === 0) return null;
  const parsed = salesReportPayloadSchema.safeParse(
    JSON.parse(gunzipSync(rows[0].payloadGz).toString("utf-8")),
  );
  return parsed.success ? parsed.data : null;
}
