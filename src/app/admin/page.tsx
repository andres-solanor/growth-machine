import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { desc, eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getAdminUser } from "@/lib/admin";
import { fmtDateTime } from "@/lib/format";
import { cambiarTier, cambiarEstadoLead } from "./actions";

export const metadata: Metadata = { title: "Admin — Analytikz" };

const JOB_STATUS_CLS: Record<string, string> = {
  queued: "text-zinc-400",
  dispatched: "text-sky-400",
  running: "text-sky-400",
  succeeded: "text-emerald-400",
  failed: "text-red-400",
  timed_out: "text-amber-400",
};

export default async function AdminPage() {
  const admin = await getAdminUser();
  if (!admin) redirect("/panel");

  const db = getDb();
  const [tenants, jobs, leads] = await Promise.all([
    db
      .select({
        id: schema.tenants.id,
        name: schema.tenants.name,
        country: schema.tenants.country,
        tier: schema.tenants.tier,
        createdAt: schema.tenants.createdAt,
        ownerEmail: schema.users.email,
      })
      .from(schema.tenants)
      .leftJoin(
        schema.memberships,
        eq(schema.memberships.tenantId, schema.tenants.id),
      )
      .leftJoin(schema.users, eq(schema.users.id, schema.memberships.userId))
      .orderBy(desc(schema.tenants.id))
      .limit(100),
    db
      .select({
        id: schema.analysisJobs.id,
        status: schema.analysisJobs.status,
        attempt: schema.analysisJobs.attempt,
        errorText: schema.analysisJobs.errorText,
        createdAt: schema.analysisJobs.createdAt,
        finishedAt: schema.analysisJobs.finishedAt,
        tenantName: schema.tenants.name,
        filename: schema.datasets.filename,
      })
      .from(schema.analysisJobs)
      .innerJoin(schema.tenants, eq(schema.tenants.id, schema.analysisJobs.tenantId))
      .innerJoin(schema.datasets, eq(schema.datasets.id, schema.analysisJobs.datasetId))
      .orderBy(desc(schema.analysisJobs.id))
      .limit(20),
    db
      .select({
        id: schema.consultingLeads.id,
        name: schema.consultingLeads.name,
        email: schema.consultingLeads.email,
        phone: schema.consultingLeads.phone,
        message: schema.consultingLeads.message,
        status: schema.consultingLeads.status,
        createdAt: schema.consultingLeads.createdAt,
        tenantName: schema.tenants.name,
      })
      .from(schema.consultingLeads)
      .leftJoin(schema.tenants, eq(schema.tenants.id, schema.consultingLeads.tenantId))
      .orderBy(desc(schema.consultingLeads.id))
      .limit(50),
  ]);

  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <span className="text-lg font-bold tracking-tight">
          Analytikz <span className="text-sm font-normal text-amber-400">admin</span>
        </span>
        <Link href="/panel" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← Mi panel
        </Link>
      </header>

      <section className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
        <h1 className="text-2xl font-bold">Administración</h1>

        {/* ── Tenants ────────────────────────────────────────────── */}
        <h2 className="mt-8 mb-3 text-lg font-semibold">
          Negocios ({tenants.length})
        </h2>
        <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-zinc-900">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr className="border-b border-zinc-800">
                <th className="px-4 py-2.5">Negocio</th>
                <th className="px-4 py-2.5">Dueño</th>
                <th className="px-4 py-2.5">País</th>
                <th className="px-4 py-2.5">Creado</th>
                <th className="px-4 py-2.5">Plan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {tenants.map((t) => (
                <tr key={t.id}>
                  <td className="px-4 py-2.5">{t.name}</td>
                  <td className="px-4 py-2.5 text-zinc-400">{t.ownerEmail}</td>
                  <td className="px-4 py-2.5 text-zinc-400">{t.country}</td>
                  <td className="px-4 py-2.5 text-zinc-400">
                    {fmtDateTime(t.createdAt, t.country)}
                  </td>
                  <td className="px-4 py-2.5">
                    <form action={cambiarTier} className="flex items-center gap-2">
                      <input type="hidden" name="tenantId" value={t.id} />
                      <select
                        name="tier"
                        defaultValue={t.tier}
                        className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                      >
                        <option value="free">free</option>
                        <option value="pro">pro</option>
                        <option value="premium">premium</option>
                      </select>
                      <button
                        type="submit"
                        className="rounded-lg border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-800"
                      >
                        Guardar
                      </button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Jobs ───────────────────────────────────────────────── */}
        <h2 className="mt-10 mb-3 text-lg font-semibold">Últimos análisis</h2>
        <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-zinc-900">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr className="border-b border-zinc-800">
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">Negocio</th>
                <th className="px-4 py-2.5">Archivo</th>
                <th className="px-4 py-2.5">Estado</th>
                <th className="px-4 py-2.5">Intento</th>
                <th className="px-4 py-2.5">Creado</th>
                <th className="px-4 py-2.5">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td className="px-4 py-2.5 text-zinc-500">{j.id}</td>
                  <td className="px-4 py-2.5">{j.tenantName}</td>
                  <td className="max-w-44 truncate px-4 py-2.5 text-zinc-400">
                    {j.filename}
                  </td>
                  <td className={`px-4 py-2.5 ${JOB_STATUS_CLS[j.status] ?? ""}`}>
                    {j.status}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{j.attempt}</td>
                  <td className="px-4 py-2.5 text-zinc-400">
                    {fmtDateTime(j.createdAt, "CO")}
                  </td>
                  <td className="max-w-56 truncate px-4 py-2.5 text-xs text-red-400">
                    {j.errorText ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Leads ──────────────────────────────────────────────── */}
        <h2 className="mt-10 mb-3 text-lg font-semibold">
          Solicitudes de consultoría ({leads.length})
        </h2>
        {leads.length === 0 ? (
          <p className="rounded-2xl border border-zinc-800 bg-zinc-900 px-5 py-4 text-sm text-zinc-500">
            Aún no hay solicitudes.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-800 rounded-2xl border border-zinc-800 bg-zinc-900">
            {leads.map((l) => (
              <li key={l.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">
                      {l.name}
                      {l.tenantName && (
                        <span className="ml-2 text-xs text-zinc-500">
                          ({l.tenantName})
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {l.email}
                      {l.phone ? ` · ${l.phone}` : ""} ·{" "}
                      {fmtDateTime(l.createdAt, "CO")}
                    </p>
                  </div>
                  <form action={cambiarEstadoLead} className="flex items-center gap-2">
                    <input type="hidden" name="leadId" value={l.id} />
                    <select
                      name="status"
                      defaultValue={l.status}
                      className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                    >
                      <option value="new">nuevo</option>
                      <option value="contacted">contactado</option>
                      <option value="closed">cerrado</option>
                    </select>
                    <button
                      type="submit"
                      className="rounded-lg border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-800"
                    >
                      Guardar
                    </button>
                  </form>
                </div>
                {l.message && (
                  <p className="mt-2 text-sm text-zinc-400">{l.message}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
