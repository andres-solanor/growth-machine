import type { Metadata } from "next";
import Link from "next/link";
import { and, eq, isNull } from "drizzle-orm";
import { getDb, schema } from "@/lib/db";

export const metadata: Metadata = { title: "Verificar correo — Analytikz" };
export const dynamic = "force-dynamic";

// GET /verificar?token=... — enlace del correo de verificación.
// Token de un solo uso: al confirmar se borra. Si llega un token ya usado
// (clic repetido) o inválido, se muestra un mensaje neutro con salida al panel.
export default async function VerificarPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  let ok = false;

  if (token && /^[0-9a-f]{64}$/.test(token)) {
    const db = getDb();
    const rows = await db
      .select({ id: schema.users.id })
      .from(schema.users)
      .where(
        and(
          eq(schema.users.verificationToken, token),
          isNull(schema.users.emailVerifiedAt),
        ),
      )
      .limit(1);
    if (rows.length > 0) {
      await db
        .update(schema.users)
        .set({ emailVerifiedAt: new Date(), verificationToken: null })
        .where(eq(schema.users.id, rows[0].id));
      ok = true;
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center">
        {ok ? (
          <>
            <p className="text-3xl">✅</p>
            <h1 className="mt-3 text-xl font-bold">Correo confirmado</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Gracias. Te avisaremos por correo cuando tus reportes estén
              listos.
            </p>
          </>
        ) : (
          <>
            <p className="text-3xl">🔗</p>
            <h1 className="mt-3 text-xl font-bold">Enlace no válido</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Este enlace ya se usó o expiró. Si tu correo ya está confirmado,
              no necesitas hacer nada más; si no, puedes reenviar el correo de
              verificación desde tu panel.
            </p>
          </>
        )}
        <Link
          href="/panel"
          className="mt-6 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          Ir a mi panel
        </Link>
      </div>
    </main>
  );
}
