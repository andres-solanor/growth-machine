"use server";

import { redirect } from "next/navigation";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth/user";

const leadSchema = z.object({
  name: z.string().trim().min(2, "Escribe tu nombre"),
  email: z.email("Correo no válido"),
  phone: z.string().trim().max(40).optional(),
  message: z.string().trim().max(2000).optional(),
});

export type LeadState = { error?: string };

export async function enviarLead(
  _prev: LeadState,
  formData: FormData,
): Promise<LeadState> {
  const parsed = leadSchema.safeParse({
    name: formData.get("name"),
    email: formData.get("email"),
    phone: formData.get("phone") || undefined,
    message: formData.get("message") || undefined,
  });
  if (!parsed.success) return { error: parsed.error.issues[0].message };

  try {
    const user = await getCurrentUser();
    await getDb().insert(schema.consultingLeads).values({
      tenantId: user?.tenant.id ?? null,
      name: parsed.data.name,
      email: parsed.data.email.toLowerCase(),
      phone: parsed.data.phone ?? null,
      message: parsed.data.message ?? null,
    });
  } catch (err) {
    console.error("[consultoria] error guardando lead:", err);
    return { error: "No pudimos enviar tu solicitud. Intenta de nuevo." };
  }
  redirect("/consultoria/gracias");
}
