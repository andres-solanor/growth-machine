import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { and, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { gateReport, loadReportPayload } from "@/lib/report";
import {
  ConsultingCta,
  InsightsSection,
  KpiGrid,
  LockedSections,
  ProductsSection,
  QualitySection,
  TimelineSection,
} from "./sections";
import {
  AnomaliesSection,
  BasketRulesSection,
  BasketSection,
  CartSection,
  TicketSection,
  TrendsSection,
} from "./sections-pro";
import {
  BundlesSection,
  ProfitabilitySection,
  RecommendationsSection,
} from "./sections-premium";

export const metadata: Metadata = { title: "Tu reporte — Analytikz" };

export default async function ReportePage(props: {
  params: Promise<{ jobId: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");

  const { jobId } = await props.params;
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) notFound();

  const jobs = await getDb()
    .select({
      status: schema.analysisJobs.status,
      configSnapshot: schema.analysisJobs.configSnapshot,
    })
    .from(schema.analysisJobs)
    .where(
      and(
        eq(schema.analysisJobs.id, id),
        eq(schema.analysisJobs.tenantId, user.tenant.id),
      ),
    )
    .limit(1);
  if (jobs.length === 0) notFound();
  if (jobs[0].status !== "succeeded") redirect(`/reportes/procesando/${id}`);

  const payload = await loadReportPayload(id, user.tenant.id);
  if (!payload) notFound();

  // Gating server-side: lo bloqueado jamás llega al navegador.
  const r = gateReport(payload, user.tenant.tier);

  // Si el job corrió con márgenes estimados por categoría, la sección de
  // rentabilidad lo declara (el snapshot congela la config de ese análisis).
  const snap = (jobs[0].configSnapshot ?? {}) as {
    category_margins?: Record<string, number>;
  };
  const marginEstimated = Object.keys(snap.category_margins ?? {}).length > 0;

  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <Link href="/panel" className="text-lg font-bold tracking-tight">
          Analytikz
        </Link>
        <Link href="/panel" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← Volver al panel
        </Link>
      </header>

      <div className="mx-auto w-full max-w-4xl flex-1 space-y-8 px-6 py-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Reporte de ventas — {r.meta.store_name ?? user.tenant.name}
          </h1>
          <p className="mt-2 text-sm text-zinc-400">
            {r.summary.date_range} · moneda {r.meta.currency}
          </p>
        </div>

        <KpiGrid r={r} />
        <QualitySection r={r} />
        <InsightsSection r={r} />
        <TimelineSection r={r} />
        <ProductsSection r={r} />
        {/* Secciones Pro: devuelven null si el gating quitó su módulo */}
        <BasketSection r={r} />
        <CartSection r={r} />
        <TrendsSection r={r} />
        <TicketSection r={r} />
        <AnomaliesSection r={r} />
        <BasketRulesSection r={r} />
        {/* Secciones Premium */}
        <ProfitabilitySection r={r} marginEstimated={marginEstimated} />
        <BundlesSection r={r} />
        <RecommendationsSection r={r} />
        <LockedSections r={r} />
        <ConsultingCta />
      </div>
    </main>
  );
}
