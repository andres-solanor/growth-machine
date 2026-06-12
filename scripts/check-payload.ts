// Valida un payload JSON del motor Python contra el schema zod.
// Uso:  npm run check:payload [-- ruta\al\payload.json]
// Sin argumento valida la muestra slim commiteada en tests/golden/.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  salesReportPayloadSchema,
  ALL_MODULE_KEYS,
} from "../src/lib/payload-schema";

const path = resolve(
  process.argv[2] ?? "tests/golden/payload_slim_sample.json",
);
const payload = JSON.parse(readFileSync(path, "utf-8"));

const result = salesReportPayloadSchema.safeParse(payload);
if (!result.success) {
  console.error(`FAIL: ${path} no cumple el schema. Problemas:`);
  for (const issue of result.error.issues.slice(0, 20)) {
    console.error(`  - [${issue.path.join(".")}] ${issue.message}`);
  }
  if (result.error.issues.length > 20) {
    console.error(`  ... y ${result.error.issues.length - 20} más`);
  }
  process.exit(1);
}

const present = Object.keys(result.data.analyses);
const missing = ALL_MODULE_KEYS.filter((k) => !present.includes(k));
console.log(`OK: ${path}`);
console.log(`  schema_version=${result.data.meta.schema_version}`);
console.log(`  módulos presentes: ${present.join(", ")}`);
if (missing.length) {
  console.log(`  módulos ausentes (válido, pero revisar): ${missing.join(", ")}`);
}
