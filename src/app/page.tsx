import Link from "next/link";

const PASOS = [
  {
    n: "1",
    t: "Sube tu archivo de ventas",
    d: "El export de tu punto de venta (Excel o CSV), tal cual sale. Nosotros detectamos las columnas.",
  },
  {
    n: "2",
    t: "Espera ~1 minuto",
    d: "Nuestro motor analiza tus ventas: productos, horarios, combinaciones, oportunidades.",
  },
  {
    n: "3",
    t: "Recibe tu reporte",
    d: "KPIs claros y hallazgos accionables en español, pensados para dueños de negocio, no para analistas.",
  },
];

const PLANES: {
  nombre: string;
  precio: string;
  nota: string;
  destacado?: boolean;
  premium?: boolean;
  bullets: string[];
  cta: { label: string; href: string };
}[] = [
  {
    nombre: "Gratis",
    precio: "$0",
    nota: "para siempre",
    bullets: [
      "1 análisis al mes",
      "KPIs de ventas y calidad de datos",
      "Línea de tiempo y días pico",
      "Top 10 productos (Pareto)",
      "3 hallazgos accionables",
    ],
    cta: { label: "Crear cuenta gratis", href: "/registro" },
  },
  {
    nombre: "Pro",
    precio: "$79.900/mes",
    nota: "precio de lanzamiento · normal $119.900",
    destacado: true,
    bullets: [
      "Todo lo del plan Gratis",
      "10 análisis al mes",
      "Todos los hallazgos (15 reglas)",
      "Qué productos se compran juntos",
      "Tendencias: qué crece y qué cae",
      "Horas con ticket por debajo del potencial",
      "Días atípicos explicados",
    ],
    cta: { label: "Hablar con nosotros", href: "/consultoria" },
  },
  {
    nombre: "Premium",
    precio: "$199.900/mes",
    nota: "precio de lanzamiento · normal $299.900",
    premium: true,
    bullets: [
      "Todo lo del plan Pro",
      "Análisis ilimitados",
      "Rentabilidad real por producto",
      "Combos listos para lanzar",
      "Impacto de eventos y promociones",
      "Sesión de estrategia 1:1 trimestral incluida (valor $260.000)",
    ],
    cta: { label: "Hablar con nosotros", href: "/consultoria" },
  },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="text-lg font-bold tracking-tight">Analytikz</span>
        <div className="flex items-center gap-3">
          <Link
            href="/ingresar"
            className="rounded-lg px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Ingresar
          </Link>
          <Link
            href="/registro"
            className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Crear cuenta
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="flex flex-col items-center gap-6 px-6 pt-20 pb-16 text-center">
        <p className="rounded-full border border-zinc-700 px-4 py-1 text-sm text-zinc-400">
          Acceso anticipado
        </p>
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
          Tus ventas ya saben cómo crecer.{" "}
          <span className="text-emerald-400">Nosotros las hacemos hablar.</span>
        </h1>
        <p className="max-w-xl text-lg text-zinc-400">
          Sube el archivo de ventas de tu punto de venta y en ~1 minuto recibe
          un reporte con decisiones concretas. Para negocios de comida y retail
          en Latinoamérica.
        </p>
        <div className="mt-2 flex flex-col items-center gap-3 sm:flex-row">
          <Link
            href="/registro"
            className="rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Analizar mis ventas gratis
          </Link>
          <Link
            href="/consultoria"
            className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-semibold text-zinc-300 hover:bg-zinc-800"
          >
            Consultoría 1:1
          </Link>
        </div>
        <p className="text-sm text-zinc-500">
          Sin tarjeta. Tu primer reporte es gratis cada mes.
        </p>
      </section>

      {/* Cómo funciona */}
      <section className="mx-auto w-full max-w-4xl px-6 py-12">
        <h2 className="text-center text-2xl font-bold">Cómo funciona</h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          {PASOS.map((p) => (
            <div
              key={p.n}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white">
                {p.n}
              </span>
              <h3 className="mt-4 font-semibold">{p.t}</h3>
              <p className="mt-2 text-sm text-zinc-400">{p.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Planes — ancla #planes: destino de los botones "Desbloquéalo" */}
      <section id="planes" className="mx-auto w-full max-w-5xl scroll-mt-16 px-6 py-12">
        <h2 className="text-center text-2xl font-bold">Planes</h2>
        <p className="mx-auto mt-2 max-w-md text-center text-sm text-zinc-400">
          Empieza gratis. Sube de plan cuando quieras ver más profundo.
        </p>
        <p className="mx-auto mt-1 max-w-md text-center text-xs text-zinc-500">
          Quienes entren con precio de lanzamiento lo conservan para siempre ·
          Plan anual: 2 meses gratis
        </p>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {PLANES.map((plan) => (
            <div
              key={plan.nombre}
              className={`flex flex-col rounded-2xl border p-6 ${
                plan.destacado
                  ? "border-emerald-600 bg-zinc-900"
                  : plan.premium
                    ? "border-amber-700 bg-zinc-900"
                    : "border-zinc-800 bg-zinc-900"
              }`}
            >
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">{plan.nombre}</h3>
                {plan.destacado && (
                  <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs font-semibold text-white">
                    Popular
                  </span>
                )}
              </div>
              <p className="mt-3 text-xl font-bold">{plan.precio}</p>
              <p className="text-xs text-zinc-500">{plan.nota}</p>
              <ul className="mt-5 flex-1 space-y-2.5 text-sm text-zinc-300">
                {plan.bullets.map((b) => (
                  <li key={b} className="flex gap-2">
                    <span className="text-emerald-400">✓</span>
                    {b}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.cta.href}
                className={`mt-6 rounded-lg px-4 py-2.5 text-center text-sm font-semibold ${
                  plan.destacado
                    ? "bg-emerald-600 text-white hover:bg-emerald-500"
                    : plan.premium
                      ? "bg-gradient-to-r from-amber-400 to-orange-500 text-zinc-950 hover:from-amber-300 hover:to-orange-400"
                      : "border border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                {plan.cta.label}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Consultoría */}
      <section className="mx-auto w-full max-w-3xl px-6 py-12">
        <div className="rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 to-zinc-950 p-8 text-center">
          <h2 className="text-xl font-bold">¿Prefieres que lo veamos juntos?</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">
            En una sesión 1:1 revisamos tu reporte, priorizamos las
            oportunidades de mayor impacto y salimos con un plan de acción para
            tu negocio.
          </p>
          <Link
            href="/consultoria"
            className="mt-5 inline-block rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Agendar consultoría
          </Link>
        </div>
      </section>

      <footer className="border-t border-zinc-800 px-6 py-8 text-center text-xs text-zinc-500">
        Analytikz · Análisis de ventas para negocios de LatAm ·{" "}
        <Link href="/consultoria" className="hover:text-zinc-300">
          Contacto
        </Link>
      </footer>
    </main>
  );
}
