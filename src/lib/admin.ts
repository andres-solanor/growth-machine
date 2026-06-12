import { getCurrentUser, type CurrentUser } from "@/lib/auth/user";

// Admin = correo listado en la env var ADMIN_EMAILS (separados por coma).
// Se configura solo en el panel de Hostinger, nunca en el repo.
export async function getAdminUser(): Promise<CurrentUser | null> {
  const user = await getCurrentUser();
  if (!user) return null;
  const allowed = (process.env.ADMIN_EMAILS ?? "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  return allowed.includes(user.email.toLowerCase()) ? user : null;
}
