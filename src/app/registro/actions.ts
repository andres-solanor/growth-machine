"use server";

import { randomBytes } from "node:crypto";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { hashPassword } from "@/lib/auth/password";
import { createSession } from "@/lib/auth/session";
import { sendVerificationEmail } from "@/lib/email";

const registroSchema = z.object({
  name: z.string().trim().min(2, "Escribe tu nombre"),
  email: z.email("Correo no válido").transform((s) => s.toLowerCase().trim()),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres"),
  businessName: z.string().trim().min(2, "Escribe el nombre de tu negocio"),
});

export type RegistroState = { error?: string };

export async function registrar(
  _prev: RegistroState,
  formData: FormData,
): Promise<RegistroState> {
  const parsed = registroSchema.safeParse({
    name: formData.get("name"),
    email: formData.get("email"),
    password: formData.get("password"),
    businessName: formData.get("businessName"),
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0].message };
  }
  const { name, email, password, businessName } = parsed.data;

  let userId: number;
  try {
    const db = getDb();
    const existing = await db
      .select({ id: schema.users.id })
      .from(schema.users)
      .where(eq(schema.users.email, email))
      .limit(1);
    if (existing.length > 0) {
      return { error: "Ya existe una cuenta con ese correo. ¿Quieres ingresar?" };
    }

    const passwordHash = await hashPassword(password);
    const verificationToken = randomBytes(32).toString("hex");
    userId = await db.transaction(async (tx) => {
      const [u] = await tx
        .insert(schema.users)
        .values({ name, email, passwordHash, verificationToken })
        .$returningId();
      const [t] = await tx
        .insert(schema.tenants)
        .values({ name: businessName })
        .$returningId();
      await tx.insert(schema.memberships).values({
        userId: u.id,
        tenantId: t.id,
        role: "owner",
      });
      await tx.insert(schema.auditLog).values({
        actorUserId: u.id,
        tenantId: t.id,
        action: "user.registered",
        detail: { email },
      });
      return u.id;
    });

    // El correo de verificación nunca bloquea el registro: si el SMTP falla,
    // el usuario puede reenviarlo desde el panel.
    sendVerificationEmail(email, name, verificationToken).catch(() => {});
  } catch (err) {
    console.error("[registro] error:", err);
    return { error: "No pudimos crear tu cuenta. Intenta de nuevo en un momento." };
  }

  await createSession(userId);
  redirect("/panel");
}
