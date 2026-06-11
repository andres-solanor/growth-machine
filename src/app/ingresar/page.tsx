import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getSessionUserId } from "@/lib/auth/session";
import { AuthCard } from "@/components/auth-card";
import { IngresarForm } from "./ingresar-form";

export const metadata: Metadata = { title: "Ingresar â€” Analytikz" };

export default async function IngresarPage() {
  if (await getSessionUserId()) redirect("/panel");
  return (
    <AuthCard title="Ingresar" subtitle="Bienvenido de vuelta.">
      <IngresarForm />
    </AuthCard>
  );
}
