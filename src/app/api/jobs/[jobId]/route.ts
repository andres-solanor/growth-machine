import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";

export const dynamic = "force-dynamic";

// GET /api/jobs/:jobId — estado del job para la página de progreso (poll 3 s).
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "No autenticado" }, { status: 401 });
  }
  const { jobId } = await ctx.params;
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Job inválido" }, { status: 400 });
  }

  const rows = await getDb()
    .select({
      id: schema.analysisJobs.id,
      status: schema.analysisJobs.status,
      attempt: schema.analysisJobs.attempt,
      errorText: schema.analysisJobs.errorText,
      createdAt: schema.analysisJobs.createdAt,
      finishedAt: schema.analysisJobs.finishedAt,
    })
    .from(schema.analysisJobs)
    .where(
      and(
        eq(schema.analysisJobs.id, id),
        eq(schema.analysisJobs.tenantId, user.tenant.id),
      ),
    )
    .limit(1);

  if (rows.length === 0) {
    return NextResponse.json({ error: "Job no encontrado" }, { status: 404 });
  }
  return NextResponse.json(rows[0]);
}
