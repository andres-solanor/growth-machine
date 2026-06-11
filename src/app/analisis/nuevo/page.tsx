import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getCurrentUser } from "@/lib/auth/user";
import { Wizard } from "./wizard";

export const metadata: Metadata = { title: "Nuevo análisis — Analytikz" };

export default async function NuevoAnalisisPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");

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
      <section className="mx-auto w-full max-w-2xl flex-1 px-6 py-10">
        <Wizard
          tenant={{
            name: user.tenant.name,
            country: user.tenant.country,
            currency: user.tenant.currency,
          }}
        />
      </section>
    </main>
  );
}
