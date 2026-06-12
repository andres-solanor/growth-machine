// Next.js ejecuta register() una vez al arrancar el servidor. Hostinger no da
// terminal, así que las migraciones de drizzle/ se aplican aquí solas: el
// migrador es idempotente (lleva registro en __drizzle_migrations) y un boot
// sin DATABASE_URL no debe tumbar la landing — solo lo deja registrado en logs.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (!process.env.DATABASE_URL) {
    console.warn("[db] DATABASE_URL no definida; se omiten migraciones.");
    return;
  }
  try {
    const { applyMigrations } = await import("./lib/db/migrator");
    const { getPool } = await import("./lib/db");
    const applied = await applyMigrations(getPool());
    console.log(
      applied.length
        ? `[db] Migraciones aplicadas: ${applied.join(", ")}`
        : "[db] Migraciones al día.",
    );
  } catch (err) {
    console.error("[db] Error aplicando migraciones:", err);
  }
}
