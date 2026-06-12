import mysql from "mysql2/promise";
import { drizzle } from "drizzle-orm/mysql2";
import * as schema from "./schema";

// Pool singleton: en dev Next recarga módulos y sin esto se fugarían
// conexiones; en Hostinger (instancia única) simplemente se crea una vez.
const globalForDb = globalThis as unknown as {
  _mysqlPool?: mysql.Pool;
};

export function getPool(): mysql.Pool {
  if (!process.env.DATABASE_URL) {
    throw new Error(
      "DATABASE_URL no está definida (mysql://usuario:clave@host:3306/basededatos)",
    );
  }
  if (!globalForDb._mysqlPool) {
    globalForDb._mysqlPool = mysql.createPool({
      uri: process.env.DATABASE_URL,
      // Hostinger corre VARIOS procesos node y cada uno crea su propio pool:
      // conexiones ociosas abiertas mantienen vivos los procesos y agotan el
      // límite de procesos de la cuenta (→ 503). Pool chico que se vacía solo.
      connectionLimit: 3,
      maxIdle: 1,
      idleTimeout: 30_000,
      // Los payloads gzip viajan como Buffer; sin esto mysql2 los castearía.
      supportBigNumbers: true,
    });
  }
  return globalForDb._mysqlPool;
}

export function getDb() {
  return drizzle(getPool(), { schema, mode: "default" });
}

export type Db = ReturnType<typeof getDb>;
export { schema };
