"use server";

import { randomBytes } from "node:crypto";
import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";
import { destroySession } from "@/lib/auth/session";
import { sendVerificationEmail } from "@/lib/email";

export async function cerrarSesion(): Promise<void> {
  await destroySession();
  redirect("/");
}

// Reenvía el correo de verificación (banner del panel). Genera token nuevo
// en cada reenvío: el enlace anterior queda invalidado.
export async function reenviarVerificacion(): Promise<void> {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");
  if (!user.emailVerifiedAt) {
    const token = randomBytes(32).toString("hex");
    await getDb()
      .update(schema.users)
      .set({ verificationToken: token })
      .where(eq(schema.users.id, user.id));
    const ok = await sendVerificationEmail(user.email, user.name, token);
    redirect(ok ? "/panel?verificacion=enviada" : "/panel?verificacion=error");
  }
  redirect("/panel");
}
