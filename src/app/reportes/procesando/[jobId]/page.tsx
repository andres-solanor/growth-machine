import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getCurrentUser } from "@/lib/auth/user";
import { Progreso } from "./progreso";

export const metadata: Metadata = { title: "Procesando — Analytikz" };

export default async function ProcesandoPage(props: {
  params: Promise<{ jobId: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/ingresar");
  const { jobId } = await props.params;

  return (
    <main className="flex flex-1 flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <Link href="/panel" className="text-lg font-bold tracking-tight">
          Analytikz
        </Link>
        <Link href="/panel" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← Volver al panel
        </Link>
      </header>
      <section className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <Progreso jobId={jobId} />
      </section>
    </main>
  );
}
