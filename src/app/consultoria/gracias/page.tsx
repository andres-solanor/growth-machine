import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Solicitud enviada — Analytikz" };

export default function GraciasPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 bg-zinc-950 px-6 py-24 text-center text-zinc-100">
      <p className="text-4xl">🤝</p>
      <h1 className="text-2xl font-bold">¡Solicitud recibida!</h1>
      <p className="max-w-md text-sm text-zinc-400">
        Te contactaremos en menos de 24 horas para agendar tu sesión.
      </p>
      <Link
        href="/panel"
        className="mt-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
      >
        Volver al panel
      </Link>
    </main>
  );
}
