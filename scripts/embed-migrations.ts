// Convierte las migraciones SQL de drizzle/ en un módulo TS bundleable.
// Hostinger no despliega la carpeta drizzle/ junto al runtime (solo la app
// compilada), así que el SQL debe viajar dentro del bundle.
// Se ejecuta automáticamente con: npm run db:generate

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

type JournalEntry = { tag: string };

const root = resolve(__dirname, "..");
const journal = JSON.parse(
  readFileSync(resolve(root, "drizzle/meta/_journal.json"), "utf-8"),
) as { entries: JournalEntry[] };

const migrations = journal.entries.map(({ tag }) => {
  const sql = readFileSync(resolve(root, `drizzle/${tag}.sql`), "utf-8");
  const statements = sql
    .split("--> statement-breakpoint")
    .map((s) => s.trim())
    .filter(Boolean);
  return { tag, statements };
});

const out = `// GENERADO por scripts/embed-migrations.ts — NO EDITAR A MANO.
// Regenerar con: npm run db:generate

export type EmbeddedMigration = { tag: string; statements: string[] };

export const MIGRATIONS: EmbeddedMigration[] = ${JSON.stringify(migrations, null, 2)};
`;

const target = resolve(root, "src/lib/db/migrations.generated.ts");
writeFileSync(target, out, "utf-8");
console.log(
  `OK: ${migrations.length} migracion(es) embebidas en src/lib/db/migrations.generated.ts`,
);
