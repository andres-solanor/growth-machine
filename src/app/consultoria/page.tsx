import type { Metadata } from "next";
import Link from "next/link";
import { getCurrentUser } from "@/lib/auth/user";
import { LeadForm } from "./lead-form";

export const metadata: Metadata = { title: "Consultoría 1:1 — Analytikz" };

export default async function ConsultoriaPage() {
  const user = await getCurrentUser();
  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <Link href={user ? "/panel" : "/"} className="text-lg font-bold tracking-tight">
          Analytikz
        </Link>
        <Link
          href={user ? "/panel" : "/"}
          className="text-sm text-zinc-400 hover:text-zinc-200"
        >
          ← Volver
        </Link>
      </header>
      <section className="mx-auto w-full max-w-xl flex-1 px-6 py-12">
        <h1 className="text-2xl font-bold">Consultoría 1:1</h1>
        <p className="mt-2 text-sm text-zinc-400">
          Una sesión personalizada: revisamos tu reporte juntos, priorizamos las
          oportunidades de mayor impacto y salimos con un plan de acción
          concreto para tu negocio. Te contactamos en menos de 24 horas.
        </p>
        <p className="mt-3 text-sm text-zinc-300">
          Tarifa: <span className="font-semibold">$260.000 COP por hora</span>.
          <span className="text-zinc-400">
            {" "}
            El plan Premium incluye una sesión de estrategia cada trimestre.
          </span>
        </p>
        <LeadForm
          defaults={{ name: user?.name ?? "", email: user?.email ?? "" }}
        />
      </section>
    </main>
  );
}
