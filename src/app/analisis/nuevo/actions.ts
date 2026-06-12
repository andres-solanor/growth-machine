"use server";

import { eq } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";

const negocioSchema = z.object({
  name: z.string().trim().min(2).max(160),
  country: z.string().length(2),
  currency: z.string().length(3),
});

export async function guardarNegocio(input: {
  name: string;
  country: string;
  currency: string;
}): Promise<{ ok: boolean; error?: string }> {
  const user = await getCurrentUser();
  if (!user) return { ok: false, error: "No autenticado" };
  const parsed = negocioSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: "Datos inválidos" };
  await getDb()
    .update(schema.tenants)
    .set(parsed.data)
    .where(eq(schema.tenants.id, user.tenant.id));
  return { ok: true };
}
