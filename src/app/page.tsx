import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 bg-zinc-950 px-6 py-24 text-center text-zinc-100">
      <p className="rounded-full border border-zinc-700 px-4 py-1 text-sm text-zinc-400">
        Acceso anticipado
      </p>
      <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-6xl">
        Analytikz
      </h1>
      <p className="max-w-xl text-lg text-zinc-400">
        Convierte los datos de tu punto de venta en decisiones que aumentan tus
        ventas. Análisis gratuito mensual para negocios de comida y retail en
        Latinoamérica.
      </p>
      <div className="mt-2 flex flex-col items-center gap-3 sm:flex-row">
        <Link
          href="/registro"
          className="rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          Crear cuenta gratis
        </Link>
        <Link
          href="/ingresar"
          className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-semibold text-zinc-300 hover:bg-zinc-800"
        >
          Ingresar
        </Link>
      </div>
      <p className="text-sm text-zinc-500">
        Tu primer reporte estará disponible muy pronto.
      </p>
    </main>
  );
}
