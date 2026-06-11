import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getSessionUserId } from "@/lib/auth/session";
import { AuthCard } from "@/components/auth-card";
import { RegistroForm } from "./registro-form";

export const metadata: Metadata = { title: "Crear cuenta â€” Analytikz" };

export default async function RegistroPage() {
  if (await getSessionUserId()) redirect("/panel");
  return (
    <AuthCard
      title="Crea tu cuenta"
      subtitle="Tu primer anÃ¡lisis de ventas es gratis. Sin tarjeta."
    >
      <RegistroForm />
    </AuthCard>
  );
}
