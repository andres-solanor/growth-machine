// Prueba anti-fuga del gating por tier: para cada plan, gatea el payload de
// muestra y verifica que NINGÚN dato de módulos bloqueados quede serializado.
// Uso:  npm run check:gating

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { salesReportPayloadSchema } from "../src/lib/payload-schema";
import { gateReport, TIER_MODULES, FREE_INSIGHTS, type Tier } from "../src/lib/gating";

const path = resolve("tests/golden/payload_slim_sample.json");
const parsed = salesReportPayloadSchema.safeParse(
  JSON.parse(readFileSync(path, "utf-8")),
);
if (!parsed.success) {
  console.error("FAIL: la muestra no cumple el schema (corre check:payload).");
  process.exit(1);
}
const payload = parsed.data;
const allModules = Object.keys(payload.analyses);

let failures = 0;
function check(cond: boolean, msg: string) {
  if (!cond) {
    failures++;
    console.error(`  ✗ ${msg}`);
  }
}

for (const tier of ["free", "pro", "premium"] as Tier[]) {
  console.log(`tier=${tier}`);
  const gated = gateReport(payload, tier);
  const allowed = new Set(TIER_MODULES[tier]);
  const lockedKeys = allModules.filter((k) => !allowed.has(k));

  // 1. analyses solo contiene módulos permitidos.
  for (const k of Object.keys(gated.analyses)) {
    check(allowed.has(k), `analyses incluye módulo no permitido: ${k}`);
  }

  // 2. Lo serializado (lo que viajaría al cliente) no contiene ningún
  //    objeto de módulo bloqueado.
  const wire = JSON.stringify(gated);
  for (const k of lockedKeys) {
    check(!wire.includes(`"${k}":{`), `fuga: "${k}" serializado en tier ${tier}`);
  }

  // 3. Hallazgos limitados en free; completos en pagos.
  if (tier === "free") {
    check(
      gated.insights.length <= FREE_INSIGHTS,
      `free muestra ${gated.insights.length} hallazgos (máx ${FREE_INSIGHTS})`,
    );
    check(
      gated.lockedInsights === payload.insights.length - gated.insights.length,
      "lockedInsights no cuadra",
    );
  } else {
    check(
      gated.insights.length === payload.insights.length,
      `${tier} debería ver todos los hallazgos`,
    );
  }

  // 4. Recomendaciones solo en premium.
  check(
    tier === "premium"
      ? gated.recommendations.length === payload.recommendations.length
      : gated.recommendations.length === 0,
    `recommendations mal gateadas en ${tier}`,
  );

  // 5. interactive_base (filas crudas) jamás aparece como teaser.
  check(
    gated.locked.every((l) => l.key !== "interactive_base"),
    "interactive_base apareció en teasers",
  );

  console.log(
    `  módulos visibles: ${Object.keys(gated.analyses).join(", ") || "(ninguno)"}`,
  );
  console.log(
    `  bloqueados con teaser: ${gated.locked.map((l) => l.key).join(", ") || "(ninguno)"}`,
  );
}

if (failures > 0) {
  console.error(`\nFAIL: ${failures} problema(s) de gating.`);
  process.exit(1);
}
console.log("\nOK: ningún dato bloqueado se filtra en ningún tier.");
