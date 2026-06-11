"use server";

import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { verifyPassword } from "@/lib/auth/password";
import { createSession } from "@/lib/auth/session";

const loginSchema = z.object({
  email: z.email("Correo no válido").transform((s) => s.toLowerCase().trim()),
  password: z.string().min(1, "Escribe tu contraseña"),
});

export type LoginState = { error?: string };

// Mensaje único para correo inexistente y contraseña mala: no revelar cuál.
const CREDENCIALES = "Correo o contraseña incorrectos.";

export async function ingresar(
  _prev: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const parsed = loginSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }

  let userId: number | null = null;
  try {
    const db = getDb();
    const rows = await db
      .select({ id: schema.users.id, passwordHash: schema.users.passwordHash })
      .from(schema.users)
      .where(eq(schema.users.email, parsed.data.email))
      .limit(1);
    if (rows.length === 0) return { error: CREDENCIALES };
    const ok = await verifyPassword(parsed.data.password, rows[0].passwordHash);
    if (!ok) return { error: CREDENCIALES };
    userId = rows[0].id;
  } catch (err) {
    console.error("[ingresar] error:", err);
    return { error: "No pudimos validar tus datos. Intenta de nuevo en un momento." };
  }

  await createSession(userId);
  redirect("/panel");
}
