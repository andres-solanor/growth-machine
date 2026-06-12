"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";

const margen = z.number().min(0).max(99);

const payloadSchema = z.object({
  products: z
    .array(
      z.object({
        sistema: z.string().min(1).max(200),
        categoria: z.string().max(100),
        margenPct: margen.nullable(),
      }),
    )
    .min(1)
    .max(3000),
  categoryMargins: z.record(z.string().min(1).max(100), margen),
});

// Guarda el mapa de productos completo del tenant: reemplaza sus
// product_map_entries y funde los márgenes por categoría en tenant_configs
// (fallback que el worker aplica a productos sin margen propio).
export async function guardarMapaProductos(formData: FormData) {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");

  let raw: unknown;
  try {
    raw = JSON.parse(String(formData.get("data") ?? ""));
  } catch {
    return;
  }
  const parsed = payloadSchema.safeParse(raw);
  if (!parsed.success) return;
  const { products, categoryMargins } = parsed.data;

  const db = getDb();
  const tenantId = user.tenant.id;

  // Config existente: se preserva todo (columns, currency…) y solo se
  // actualiza category_margins. /api/jobs hace el merge simétrico.
  const prevCfg = await db
    .select({ configJson: schema.tenantConfigs.configJson })
    .from(schema.tenantConfigs)
    .where(eq(schema.tenantConfigs.tenantId, tenantId))
    .limit(1);
  const configJson = {
    ...((prevCfg[0]?.configJson as Record<string, unknown>) ?? {}),
    category_margins: categoryMargins,
  };

  await db.transaction(async (tx) => {
    await tx
      .delete(schema.productMapEntries)
      .where(eq(schema.productMapEntries.tenantId, tenantId));

    // Sin categoría elegida → "Otros": así TODOS los productos quedan en el
    // mapa y el motor nunca ve filas sin clasificar.
    const rows = products.map((p) => ({
      tenantId,
      sistema: p.sistema,
      nombre: p.sistema,
      categoria: p.categoria.trim() || "Otros",
      subcategoria: null,
      margenPct: p.margenPct === null ? null : p.margenPct.toFixed(2),
    }));
    for (let i = 0; i < rows.length; i += 500) {
      await tx.insert(schema.productMapEntries).values(rows.slice(i, i + 500));
    }

    await tx
      .insert(schema.tenantConfigs)
      .values({ tenantId, configJson })
      .onDuplicateKeyUpdate({ set: { configJson } });

    await tx.insert(schema.auditLog).values({
      actorUserId: user.id,
      tenantId,
      action: "product_map.saved",
      detail: {
        products: rows.length,
        categorized: rows.filter((r) => r.categoria !== "Otros").length,
        withMargin: rows.filter((r) => r.margenPct !== null).length,
        categoryMargins: Object.keys(categoryMargins).length,
      },
    });
  });

  revalidatePath("/productos");
  redirect("/productos?guardado=1");
}
