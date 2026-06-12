import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { loadLatestReportPayload } from "@/lib/report";
import { ProductMapEditor, type EditorProduct } from "./editor";

export const metadata: Metadata = { title: "Mis productos — Analytikz" };

// Editor de mapa de productos: nunca empieza en blanco — la lista sale del
// último análisis del tenant (nombres, revenue y frecuencia ya conocidos),
// ordenada por impacto Pareto. Las categorías mejoran todos los reportes;
// los márgenes activan el análisis de rentabilidad (Premium).
export default async function ProductosPage(props: {
  searchParams: Promise<{ guardado?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");
  const { guardado } = await props.searchParams;

  const db = getDb();
  const [payload, entries, cfgRows] = await Promise.all([
    loadLatestReportPayload(user.tenant.id),
    db
      .select({
        sistema: schema.productMapEntries.sistema,
        categoria: schema.productMapEntries.categoria,
        margenPct: schema.productMapEntries.margenPct,
      })
      .from(schema.productMapEntries)
      .where(eq(schema.productMapEntries.tenantId, user.tenant.id)),
    db
      .select({ configJson: schema.tenantConfigs.configJson })
      .from(schema.tenantConfigs)
      .where(eq(schema.tenantConfigs.tenantId, user.tenant.id))
      .limit(1),
  ]);

  const allProducts = payload?.analyses.products?.all_products ?? [];
  const nPareto = payload?.analyses.products?.n_pareto ?? 0;

  const byName = new Map(entries.map((e) => [e.sistema, e]));
  const products: EditorProduct[] = allProducts.map((p) => {
    const saved = byName.get(p["Nombre Corregido"]);
    byName.delete(p["Nombre Corregido"]);
    return {
      sistema: p["Nombre Corregido"],
      categoria: saved
        ? saved.categoria
        : p.category && p.category !== "Otros"
          ? p.category
          : "",
      margenPct: saved?.margenPct == null ? null : Number(saved.margenPct),
      revenue: p.revenue ?? 0,
      revShare: p.rev_share ?? 0,
      orders: p.orders ?? 0,
    };
  });
  // Entradas guardadas que ya no aparecen en el último análisis: se conservan
  // (si se omitieran, el guardado las borraría en silencio).
  for (const e of byName.values()) {
    products.push({
      sistema: e.sistema,
      categoria: e.categoria,
      margenPct: e.margenPct == null ? null : Number(e.margenPct),
      revenue: 0,
      revShare: 0,
      orders: 0,
    });
  }

  const cfg = (cfgRows[0]?.configJson ?? {}) as {
    category_margins?: Record<string, number>;
  };

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

      <section className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
        <h1 className="text-3xl font-bold tracking-tight">Mis productos</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Clasifica tus productos por categoría para que tus reportes hablen tu
          idioma, y agrega márgenes (aunque sean aproximados) para activar el
          análisis de rentabilidad. Los cambios se aplican en tu{" "}
          <strong className="text-zinc-300">próximo análisis</strong>.
        </p>

        {products.length === 0 ? (
          <div className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <h2 className="text-lg font-semibold">Aún no hay productos</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">
              Esta lista se arma sola con tu primer análisis de ventas: sube tu
              archivo y vuelve aquí para clasificar tus productos.
            </p>
            <Link
              href="/analisis/nuevo"
              className="mt-6 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
            >
              Subir mi archivo de ventas
            </Link>
          </div>
        ) : (
          <ProductMapEditor
            products={products}
            nPareto={nPareto}
            categoryMargins={cfg.category_margins ?? {}}
            currency={user.tenant.currency}
            tier={user.tenant.tier}
            guardado={guardado === "1"}
          />
        )}
      </section>
    </main>
  );
}
