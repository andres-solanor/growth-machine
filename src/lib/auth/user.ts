import { eq } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";
import { getSessionUserId } from "./session";

export type CurrentUser = {
  id: number;
  name: string;
  email: string;
  emailVerifiedAt: Date | null;
  tenant: {
    id: number;
    name: string;
    tier: "free" | "pro" | "premium";
    currency: string;
    country: string;
  };
  role: "owner" | "member";
};

// Usuario de la sesión + su tenant (MVP: un tenant por usuario).
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const uid = await getSessionUserId();
  if (!uid) return null;
  const db = getDb();
  const rows = await db
    .select({
      id: schema.users.id,
      name: schema.users.name,
      email: schema.users.email,
      emailVerifiedAt: schema.users.emailVerifiedAt,
      role: schema.memberships.role,
      tenantId: schema.tenants.id,
      tenantName: schema.tenants.name,
      tier: schema.tenants.tier,
      currency: schema.tenants.currency,
      country: schema.tenants.country,
    })
    .from(schema.users)
    .innerJoin(schema.memberships, eq(schema.memberships.userId, schema.users.id))
    .innerJoin(schema.tenants, eq(schema.tenants.id, schema.memberships.tenantId))
    .where(eq(schema.users.id, uid))
    .limit(1);
  const r = rows[0];
  if (!r) return null;
  return {
    id: r.id,
    name: r.name,
    email: r.email,
    emailVerifiedAt: r.emailVerifiedAt,
    role: r.role,
    tenant: {
      id: r.tenantId,
      name: r.tenantName,
      tier: r.tier,
      currency: r.currency,
      country: r.country,
    },
  };
}
