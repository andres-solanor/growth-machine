import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { desc, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { fmtDateTime } from "@/lib/format";
import { cerrarSesion, reenviarVerificacion } from "./actions";

export const metadata: Metadata = { title: "Panel — Analytikz" };

const TIER_LABEL: Record<string, string> = {
  free: "Plan Gratis",
  pro: "Plan Pro",
  premium: "Plan Premium",
};

const JOB_STATUS: Record<string, { label: string; cls: string }> = {
  queued: { label: "En cola", cls: "border-zinc-600 bg-zinc-800 text-zinc-300" },
  dispatched: { label: "Preparando", cls: "border-sky-700 bg-sky-950 text-sky-300" },
  running: { label: "Analizando", cls: "border-sky-700 bg-sky-950 text-sky-300" },
  succeeded: { label: "Listo", cls: "border-emerald-700 bg-emerald-950 text-emerald-300" },
  failed: { label: "Falló", cls: "border-red-800 bg-red-950 text-red-300" },
  timed_out: { label: "Expiró", cls: "border-amber-700 bg-amber-950 text-amber-300" },
};

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Promise<{ verificacion?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");
  const { verificacion } = await searchParams;

  const jobs = await getDb()
    .select({
      id: schema.analysisJobs.id,
      status: schema.analysisJobs.status,
      createdAt: schema.analysisJobs.createdAt,
      filename: schema.datasets.filename,
    })
    .from(schema.analysisJobs)
    .innerJoin(schema.datasets, eq(schema.datasets.id, schema.analysisJobs.datasetId))
    .where(eq(schema.analysisJobs.tenantId, user.tenant.id))
    .orderBy(desc(schema.analysisJobs.id))
    .limit(8);

  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <span className="text-lg font-bold tracking-tight">Analytikz</span>
        <div className="flex items-center gap-4">
          <span className="rounded-full border border-emerald-700 bg-emerald-950 px-3 py-1 text-xs font-medium text-emerald-300">
            {TIER_LABEL[user.tenant.tier]}
          </span>
          <span className="hidden text-sm text-zinc-400 sm:inline">{user.name}</span>
          <form action={cerrarSesion}>
            <button
              type="submit"
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Salir
            </button>
          </form>
        </div>
      </header>

      <section className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
        <h1 className="text-2xl font-bold">Hola, {user.name.split(" ")[0]} 👋</h1>
        <p className="mt-1 text-zinc-400">
          {user.tenant.name} · {user.tenant.currency}
        </p>

        {/* Banner informativo: la verificación NO bloquea ninguna función,
            solo habilita los avisos por correo (reporte listo, etc.). */}
        {!user.emailVerifiedAt && (
          <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-amber-800 bg-amber-950/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium text-amber-200">
                Confirma tu correo
              </p>
              <p className="mt-0.5 text-xs text-amber-200/70">
                {verificacion === "enviada"
                  ? `Correo reenviado a ${user.email}. Revisa tu bandeja (y el spam).`
                  : verificacion === "error"
                    ? "No pudimos enviar el correo. Intenta de nuevo en unos minutos."
                    : `Te enviamos un enlace a ${user.email} para poder avisarte cuando tus reportes estén listos.`}
              </p>
            </div>
            <form action={reenviarVerificacion} className="shrink-0">
              <button
                type="submit"
                className="rounded-lg border border-amber-700 px-3 py-1.5 text-xs font-medium text-amber-200 hover:bg-amber-900/50"
              >
                Reenviar correo
              </button>
            </form>
          </div>
        )}

        <div className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
          <h2 className="text-lg font-semibold">
            {jobs.length > 0
              ? "Analiza un nuevo periodo de ventas"
              : "Tu primer análisis de ventas"}
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">
            Sube el archivo de ventas de tu punto de venta (Excel o CSV) y en
            ~1 minuto tendrás tu reporte: ventas, productos estrella, horarios
            pico y oportunidades concretas.
          </p>
          <Link
            href="/analisis/nuevo"
            className="mt-6 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Subir mi archivo de ventas
          </Link>
        </div>

        {jobs.some((j) => j.status === "succeeded") && (
          <Link
            href="/productos"
            className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900 px-6 py-4 hover:border-zinc-700 hover:bg-zinc-800/60"
          >
            <div>
              <h2 className="text-sm font-semibold">
                Clasifica tus productos{" "}
                <span className="font-normal text-zinc-500">· categorías y márgenes</span>
              </h2>
              <p className="mt-1 text-xs text-zinc-400">
                Mejora tus reportes con tus propias categorías y activa el
                análisis de rentabilidad agregando márgenes.
              </p>
            </div>
            <span className="shrink-0 text-zinc-500">→</span>
          </Link>
        )}

        {jobs.length > 0 && (
          <div className="mt-8">
            <h2 className="mb-3 text-lg font-semibold">Tus análisis</h2>
            <ul className="divide-y divide-zinc-800 rounded-2xl border border-zinc-800 bg-zinc-900">
              {jobs.map((job) => {
                const st = JOB_STATUS[job.status] ?? JOB_STATUS.queued;
                return (
                  <li key={job.id}>
                    <Link
                      href={
                        job.status === "succeeded"
                          ? `/reportes/${job.id}`
                          : `/reportes/procesando/${job.id}`
                      }
                      className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-zinc-800/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm text-zinc-200">
                          {job.filename}
                        </p>
                        <p className="text-xs text-zinc-500">
                          {fmtDateTime(job.createdAt, user.tenant.country)}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-3 py-1 text-xs font-medium ${st.cls}`}
                      >
                        {st.label}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}
