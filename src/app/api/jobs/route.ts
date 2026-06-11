import { NextResponse } from "next/server";
import { and, eq, gte, inArray } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { CANONICAL_FIELDS } from "@/lib/csv-detect";
import { dispatchAnalysisJob } from "@/lib/github-dispatch";

export const dynamic = "force-dynamic";

const bodySchema = z.object({
  datasetId: z.number().int().positive(),
  mapping: z.record(z.string(), z.string().min(1)),
});

// POST /api/jobs — congela el mapeo de columnas en tenant_configs y crea el
// job de análisis en cola. (El despacho al worker llega en el siguiente paso
// del proyecto; por ahora el job queda "queued".)
export async function POST(req: Request) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "No autenticado" }, { status: 401 });
  }

  const parsed = bodySchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "Datos inválidos" }, { status: 400 });
  }
  const { datasetId, mapping } = parsed.data;

  // Campos obligatorios mapeados y sin columnas repetidas.
  const missing = CANONICAL_FIELDS.filter(
    (f) => f.required && !mapping[f.key],
  ).map((f) => f.label);
  if (missing.length > 0) {
    return NextResponse.json(
      { error: `Falta indicar la columna de: ${missing.join(", ")}` },
      { status: 422 },
    );
  }
  const used = Object.values(mapping);
  if (new Set(used).size !== used.length) {
    return NextResponse.json(
      { error: "Hay dos campos apuntando a la misma columna del archivo" },
      { status: 422 },
    );
  }

  const db = getDb();

  const ds = await db
    .select({ id: schema.datasets.id })
    .from(schema.datasets)
    .where(
      and(
        eq(schema.datasets.id, datasetId),
        eq(schema.datasets.tenantId, user.tenant.id),
      ),
    )
    .limit(1);
  if (ds.length === 0) {
    return NextResponse.json({ error: "Archivo no encontrado" }, { status: 404 });
  }

  // Un análisis a la vez por negocio.
  const active = await db
    .select({ id: schema.analysisJobs.id })
    .from(schema.analysisJobs)
    .where(
      and(
        eq(schema.analysisJobs.tenantId, user.tenant.id),
        inArray(schema.analysisJobs.status, ["queued", "dispatched", "running"]),
      ),
    )
    .limit(1);
  if (active.length > 0) {
    return NextResponse.json(
      { error: "Ya tienes un análisis en curso. Espera a que termine.", jobId: active[0].id },
      { status: 409 },
    );
  }

  // Cuota free: 1 análisis exitoso por mes calendario (servidor manda).
  if (user.tenant.tier === "free") {
    const monthStart = new Date();
    monthStart.setUTCDate(1);
    monthStart.setUTCHours(0, 0, 0, 0);
    const succeeded = await db
      .select({ id: schema.analysisJobs.id })
      .from(schema.analysisJobs)
      .where(
        and(
          eq(schema.analysisJobs.tenantId, user.tenant.id),
          eq(schema.analysisJobs.status, "succeeded"),
          gte(schema.analysisJobs.createdAt, monthStart),
        ),
      )
      .limit(1);
    if (succeeded.length > 0) {
      return NextResponse.json(
        {
          error:
            "Tu plan gratis incluye 1 análisis al mes y ya lo usaste. Vuelve el próximo mes o conoce los planes Pro.",
        },
        { status: 403 },
      );
    }
  }

  const configJson = {
    columns: mapping,
    currency: user.tenant.currency,
    store_name: user.tenant.name,
    country: user.tenant.country,
  };

  const jobId = await db.transaction(async (tx) => {
    await tx
      .insert(schema.tenantConfigs)
      .values({ tenantId: user.tenant.id, configJson })
      .onDuplicateKeyUpdate({ set: { configJson } });
    const [job] = await tx
      .insert(schema.analysisJobs)
      .values({
        tenantId: user.tenant.id,
        datasetId,
        type: "report",
        status: "queued",
        configSnapshot: configJson,
      })
      .$returningId();
    await tx.insert(schema.auditLog).values({
      actorUserId: user.id,
      tenantId: user.tenant.id,
      action: "job.created",
      detail: { jobId: job.id, datasetId },
    });
    return job.id;
  });

  // Despachar al worker (GitHub Actions). Si aún no hay credenciales
  // configuradas, el job queda "queued" y la página de progreso lo explica.
  const dispatched = await dispatchAnalysisJob(jobId);
  if (dispatched.ok) {
    await db
      .update(schema.analysisJobs)
      .set({ status: "dispatched", dispatchedAt: new Date() })
      .where(eq(schema.analysisJobs.id, jobId));
  } else {
    console.warn(`[jobs] dispatch job ${jobId}: ${dispatched.error}`);
  }

  return NextResponse.json({ jobId });
}
