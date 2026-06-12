import { gunzip as _gunzip } from "node:zlib";
import { promisify } from "node:util";
const gunzip = promisify(_gunzip);
import { NextResponse } from "next/server";
import { and, eq, isNotNull } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { verifyWorkerRequest } from "@/lib/worker-auth";
import { salesReportPayloadSchema } from "@/lib/payload-schema";
import { sendReportReadyEmail } from "@/lib/email";
import { fmtMoney, fmtNum } from "@/lib/format";

export const dynamic = "force-dynamic";

// POST /api/worker/jobs/:id/result — el worker entrega el resultado:
//   Content-Type application/gzip  -> payload.json gzip (éxito)
//   Content-Type application/json  -> { ok: false, error } (fallo)
export async function POST(
  req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await ctx.params;
  const body = Buffer.from(await req.arrayBuffer());
  if (!verifyWorkerRequest(req, `/api/worker/jobs/${jobId}/result`, body)) {
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
      status: schema.analysisJobs.status,
    })
    .from(schema.analysisJobs)
    .where(eq(schema.analysisJobs.id, id))
    .limit(1);
  const job = rows[0];
  if (!job) {
    return NextResponse.json({ error: "job not found" }, { status: 404 });
  }
  if (job.status === "succeeded") {
    return NextResponse.json({ ok: true, note: "already stored" });
  }

  const contentType = req.headers.get("content-type") ?? "";

  // Fallo reportado por el worker
  if (contentType.includes("application/json")) {
    let errorText = "El análisis falló.";
    try {
      const parsed = JSON.parse(body.toString("utf-8"));
      if (typeof parsed.error === "string") errorText = parsed.error;
    } catch {
      // cuerpo ilegible: conservar mensaje genérico
    }
    await db
      .update(schema.analysisJobs)
      .set({ status: "failed", errorText: errorText.slice(0, 60000), finishedAt: new Date() })
      .where(eq(schema.analysisJobs.id, id));
    return NextResponse.json({ ok: true });
  }

  // Éxito: payload gzip
  let payload: unknown;
  try {
    payload = JSON.parse((await gunzip(body)).toString("utf-8"));
  } catch {
    await db
      .update(schema.analysisJobs)
      .set({
        status: "failed",
        errorText: "Resultado ilegible (gzip/JSON inválido)",
        finishedAt: new Date(),
      })
      .where(eq(schema.analysisJobs.id, id));
    return NextResponse.json({ error: "bad payload encoding" }, { status: 422 });
  }

  const checked = salesReportPayloadSchema.safeParse(payload);
  if (!checked.success) {
    const issues = checked.error.issues
      .slice(0, 5)
      .map((i) => `${i.path.join(".")}: ${i.message}`)
      .join("; ");
    console.error(`[worker-result] payload inválido job ${id}: ${issues}`);
    await db
      .update(schema.analysisJobs)
      .set({
        status: "failed",
        errorText: `Payload no cumple el contrato (schema_version 1): ${issues}`.slice(0, 60000),
        finishedAt: new Date(),
      })
      .where(eq(schema.analysisJobs.id, id));
    return NextResponse.json({ error: "payload schema mismatch" }, { status: 422 });
  }

  const data = checked.data;
  // summary_json: lo que dashboards y teasers leen sin descomprimir el payload
  const summaryJson = {
    meta: {
      schema_version: data.meta.schema_version,
      report_type: data.meta.report_type,
      generated_at: data.meta.generated_at,
      store_name: data.meta.store_name,
      currency: data.meta.currency,
    },
    summary: data.summary,
    quality: data.quality,
    analyses_keys: Object.keys(data.analyses),
    n_insights: data.insights.length,
    n_recommendations: data.recommendations.length,
  };

  await db.transaction(async (tx) => {
    await tx
      .insert(schema.reportPayloads)
      .values({
        jobId: id,
        tenantId: job.tenantId,
        schemaVersion: data.meta.schema_version,
        payloadGz: body,
        summaryJson,
      })
      .onDuplicateKeyUpdate({
        set: { payloadGz: body, summaryJson, schemaVersion: data.meta.schema_version },
      });
    await tx
      .update(schema.analysisJobs)
      .set({ status: "succeeded", errorText: null, finishedAt: new Date() })
      .where(eq(schema.analysisJobs.id, id));
  });

  // Aviso "tu reporte está listo" a los dueños con correo verificado.
  // Nunca afecta la respuesta al worker: el reporte ya quedó guardado.
  try {
    const owners = await db
      .select({ email: schema.users.email, name: schema.users.name })
      .from(schema.memberships)
      .innerJoin(schema.users, eq(schema.users.id, schema.memberships.userId))
      .where(
        and(
          eq(schema.memberships.tenantId, job.tenantId),
          eq(schema.memberships.role, "owner"),
          isNotNull(schema.users.emailVerifiedAt),
        ),
      );
    const resumen = {
      storeName: data.meta.store_name ?? "tu negocio",
      totalRevenue: fmtMoney(data.summary.total_revenue, data.meta.currency),
      totalOrders: fmtNum(data.summary.total_orders),
      dateRange: data.summary.date_range,
    };
    await Promise.all(
      owners.map((o) => sendReportReadyEmail(o.email, o.name, id, resumen)),
    );
  } catch (err) {
    console.error(`[worker-result] aviso por correo falló (job ${id}):`, err);
  }

  return NextResponse.json({ ok: true });
}
