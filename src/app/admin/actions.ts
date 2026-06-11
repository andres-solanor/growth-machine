"use server";

import { revalidatePath } from "next/cache";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "@/lib/db";
import { getAdminUser } from "@/lib/admin";

const tierSchema = z.object({
  tenantId: z.coerce.number().int().positive(),
  tier: z.enum(["free", "pro", "premium"]),
});

export async function cambiarTier(formData: FormData) {
  const admin = await getAdminUser();
  if (!admin) return;
  const parsed = tierSchema.safeParse({
    tenantId: formData.get("tenantId"),
    tier: formData.get("tier"),
  });
  if (!parsed.success) return;
  const { tenantId, tier } = parsed.data;

  const db = getDb();
  const prev = await db
    .select({ tier: schema.tenants.tier })
    .from(schema.tenants)
    .where(eq(schema.tenants.id, tenantId))
    .limit(1);
  if (prev.length === 0 || prev[0].tier === tier) return;

  await db.update(schema.tenants).set({ tier }).where(eq(schema.tenants.id, tenantId));
  await db.insert(schema.auditLog).values({
    actorUserId: admin.id,
    tenantId,
    action: "admin.tier_change",
    detail: { from: prev[0].tier, to: tier },
  });
  revalidatePath("/admin");
}

const leadSchema = z.object({
  leadId: z.coerce.number().int().positive(),
  status: z.enum(["new", "contacted", "closed"]),
});

export async function cambiarEstadoLead(formData: FormData) {
  const admin = await getAdminUser();
  if (!admin) return;
  const parsed = leadSchema.safeParse({
    leadId: formData.get("leadId"),
    status: formData.get("status"),
  });
  if (!parsed.success) return;

  const db = getDb();
  await db
    .update(schema.consultingLeads)
    .set({ status: parsed.data.status })
    .where(eq(schema.consultingLeads.id, parsed.data.leadId));
  await db.insert(schema.auditLog).values({
    actorUserId: admin.id,
    action: "admin.lead_status",
    detail: { leadId: parsed.data.leadId, to: parsed.data.status },
  });
  revalidatePath("/admin");
}
