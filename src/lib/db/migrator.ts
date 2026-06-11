import type { Pool } from "mysql2/promise";
import { MIGRATIONS } from "./migrations.generated";

// Migrador propio sobre SQL embebido: idempotente, registra cada migración
// aplicada en __app_migrations. Sustituye al migrador de drizzle porque ese
// lee drizzle/meta/_journal.json del disco y esa carpeta no existe en el
// runtime de Hostinger.
export async function applyMigrations(pool: Pool): Promise<string[]> {
  await pool.query(
    `CREATE TABLE IF NOT EXISTS __app_migrations (
      tag VARCHAR(255) PRIMARY KEY,
      applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`,
  );
  const [rows] = (await pool.query(
    "SELECT tag FROM __app_migrations",
  )) as unknown as [{ tag: string }[]];
  const done = new Set(rows.map((r) => r.tag));

  const applied: string[] = [];
  for (const { tag, statements } of MIGRATIONS) {
    if (done.has(tag)) continue;
    for (const statement of statements) {
      await pool.query(statement);
    }
    await pool.query("INSERT INTO __app_migrations (tag) VALUES (?)", [tag]);
    applied.push(tag);
  }
  return applied;
}
