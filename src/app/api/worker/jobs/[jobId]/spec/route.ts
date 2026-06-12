import { NextResponse } from "next/server";
import { and, eq, inArray } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { verifyWorkerRequest } from "@/lib/worker-auth";

export const dynamic = "force-dynamic";

// GET /api/worker/jobs/:id/spec — el worker recoge el spec y el job pasa a
// "running". Solo HMAC; nunca expone datos a navegadores.
export async function GET(
  req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await ctx.params;
  if (!verifyWorkerRequest(req, `/api/worker/jobs/${jobId}/spec`)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "bad job id" }, { status: 400 });
  }

  const db = getDb();
  const rows = await db
    .select({
      id: schema.analysisJobs.id,
      tenantId: schema.analysisJobs.tenantId,
      type: schema.analysisJobs.type,
      status: schema.analysisJobs.status,
      configSnapshot: schema.analysisJobs.configSnapshot,
      datasetId: schema.analysisJobs.datasetId,
      filename: schema.datasets.filename,
    })
    .from(schema.analysisJobs)
    .innerJoin(schema.datasets, eq(schema.datasets.id, schema.analysisJobs.datasetId))
    .where(
      and(
        eq(schema.analysisJobs.id, id),
        inArray(schema.analysisJobs.status, ["queued", "dispatched", "running"]),
      ),
    )
    .limit(1);

  const job = rows[0];
  if (!job) {
    return NextResponse.json({ error: "job not found or finished" }, { status: 404 });
  }

  await db
    .update(schema.analysisJobs)
    .set({ status: "running", startedAt: new Date() })
    .where(eq(schema.analysisJobs.id, id));

  const snap = (job.configSnapshot ?? {}) as {
    columns?: Record<string, string>;
    currency?: string;
    store_name?: string;
    category_margins?: Record<string, number>;
  };

  // Mapa de productos del tenant (editor /productos). margen_pct llega como
  // string del driver (DECIMAL) — se convierte a número para el worker.
  const pmRows = await db
    .select({
      sistema: schema.productMapEntries.sistema,
      nombre: schema.productMapEntries.nombre,
      categoria: schema.productMapEntries.categoria,
      subcategoria: schema.productMapEntries.subcategoria,
      margenPct: schema.productMapEntries.margenPct,
    })
    .from(schema.productMapEntries)
    .where(eq(schema.productMapEntries.tenantId, job.tenantId));

  const productMap = pmRows.map((r) => ({
    sistema: r.sistema,
    precio_post: null,
    fecha_desde: null,
    nombre: r.nombre,
    categoria: r.categoria,
    subcategoria: r.subcategoria,
    margen_pct: r.margenPct == null ? null : Number(r.margenPct),
  }));

  return NextResponse.json({
    job_id: job.id,
    type: job.type,
    dataset_filename: job.filename,
    column_mapping: snap.columns ?? null,
    tenant_config: {
      store_name: snap.store_name ?? null,
      currency: snap.currency ?? "COP",
    },
    product_map: productMap.length > 0 ? productMap : null,
    // Fallback de margen por categoría (congelado en el snapshot del job).
    category_margins: snap.category_margins ?? null,
    delta_config: null,
  });
}
