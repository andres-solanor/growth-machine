import { defineConfig } from "drizzle-kit";

// `db:generate` solo necesita el schema (sin conexión). `db:migrate`/`db:push`
// usan DATABASE_URL (mysql://user:pass@host:3306/dbname) desde el entorno —
// en Hostinger va en el panel de variables, nunca en el repo.
export default defineConfig({
  dialect: "mysql",
  schema: "./src/lib/db/schema.ts",
  out: "./drizzle",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "mysql://placeholder@localhost:3306/placeholder",
  },
});
