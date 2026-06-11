import { NextResponse } from "next/server";
import { getPool } from "@/lib/db";

// Diagnóstico: GET /api/health
// Confirma conexión a MySQL, migraciones aplicadas y max_allowed_packet
// (los payloads gzip de ~0.4-1 MB deben caber con holgura en un INSERT).
export const dynamic = "force-dynamic";

export async function GET() {
  const checks: Record<string, unknown> = {
    app: "ok",
    time: new Date().toISOString(),
  };
  try {
    const pool = getPool();
    const [[packet]] = (await pool.query(
      "SELECT @@max_allowed_packet AS maxAllowedPacket",
    )) as unknown as [[{ maxAllowedPacket: number }]];
    checks.db = "ok";
    checks.maxAllowedPacketMB =
      Math.round((packet.maxAllowedPacket / 1024 / 1024) * 10) / 10;

    const countTables = async () => {
      const [rows] = (await pool.query(
        "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = DATABASE()",
      )) as unknown as [[{ n: number }]];
      return rows[0].n;
    };

    checks.tables = await countTables();

    // Autocuración: si el esquema no existe (el migrador de arranque pudo
    // fallar sin dejar rastro visible), aplicar migraciones aquí y reportar
    // el error en la respuesta para diagnosticar sin acceso a logs.
    if ((checks.tables as number) < 10) {
      try {
        const { migrate } = await import("drizzle-orm/mysql2/migrator");
        const { getDb } = await import("@/lib/db");
        await migrate(getDb(), { migrationsFolder: "./drizzle" });
        checks.migrate = "applied";
        checks.tables = await countTables();
      } catch (err) {
        checks.migrate = "error";
        checks.migrateError =
          err instanceof Error ? err.message : String(err);
      }
    }

    return NextResponse.json({ ok: checks.migrate !== "error", ...checks });
  } catch (err) {
    checks.db = "error";
    checks.dbError = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, ...checks }, { status: 500 });
  }
}
