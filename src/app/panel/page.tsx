import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth/user";
import { cerrarSesion } from "./actions";

export const metadata: Metadata = { title: "Panel — Analytikz" };

const TIER_LABEL: Record<string, string> = {
  free: "Plan Gratis",
  pro: "Plan Pro",
  premium: "Plan Premium",
};

export default async function PanelPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");

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

        <div className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
          <h2 className="text-lg font-semibold">Tu primer análisis de ventas</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">
            Sube el archivo de ventas de tu punto de venta (Excel o CSV) y en
            ~1 minuto tendrás tu reporte: ventas, productos estrella, horarios
            pico y oportunidades concretas.
          </p>
          <button
            disabled
            className="mt-6 cursor-not-allowed rounded-lg bg-zinc-700 px-5 py-2.5 text-sm font-semibold text-zinc-400"
          >
            Muy pronto — estamos construyendo esta parte
          </button>
        </div>
      </section>
    </main>
  );
}
