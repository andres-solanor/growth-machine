import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { verifyWorkerRequest } from "@/lib/worker-auth";

export const dynamic = "force-dynamic";

// GET /api/worker/jobs/:id/dataset — bytes gzip del archivo original del
// tenant, solo para el worker (HMAC).
export async function GET(
  req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await ctx.params;
  if (!verifyWorkerRequest(req, `/api/worker/jobs/${jobId}/dataset`)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "bad job id" }, { status: 400 });
  }

  const rows = await getDb()
    .select({ contentGz: schema.datasets.contentGz })
    .from(schema.analysisJobs)
    .innerJoin(schema.datasets, eq(schema.datasets.id, schema.analysisJobs.datasetId))
    .where(eq(schema.analysisJobs.id, id))
    .limit(1);

  if (rows.length === 0) {
    return NextResponse.json({ error: "job not found" }, { status: 404 });
  }

  return new NextResponse(new Uint8Array(rows[0].contentGz), {
    headers: {
      "Content-Type": "application/gzip",
      "Cache-Control": "no-store",
    },
  });
}
