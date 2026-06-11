// Esquema MySQL (Hostinger managed) — fuente de verdad para drizzle-kit.
// Migraciones: npm run db:generate (SQL en drizzle/), aplicar con npm run db:migrate.
// Todo estado durable vive aquí: el filesystem de la app se reconstruye en cada deploy.

import {
  bigint,
  boolean,
  customType,
  date,
  decimal,
  int,
  json,
  mysqlEnum,
  mysqlTable,
  text,
  timestamp,
  uniqueIndex,
  index,
  varchar,
} from "drizzle-orm/mysql-core";

// Uploads y payloads van gzip en LONGBLOB (drizzle no lo trae de fábrica).
const longblob = customType<{ data: Buffer }>({
  dataType() {
    return "longblob";
  },
});

// No usar serial(): emite `serial AUTO_INCREMENT` y MariaDB (Hostinger) lo
// rechaza; bigint unsigned autoincrement es válido en MySQL y MariaDB.
const id = () =>
  bigint("id", { mode: "number", unsigned: true })
    .autoincrement()
    .primaryKey();
const ref = (name: string) => bigint(name, { mode: "number", unsigned: true });
const createdAt = () => timestamp("created_at").defaultNow().notNull();

export const users = mysqlTable("users", {
  id: id(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  passwordHash: varchar("password_hash", { length: 255 }).notNull(),
  name: varchar("name", { length: 120 }).notNull(),
  emailVerifiedAt: timestamp("email_verified_at"),
  verificationToken: varchar("verification_token", { length: 64 }),
  createdAt: createdAt(),
});

export const tenants = mysqlTable("tenants", {
  id: id(),
  name: varchar("name", { length: 160 }).notNull(),
  country: varchar("country", { length: 2 }).notNull().default("CO"),
  currency: varchar("currency", { length: 3 }).notNull().default("COP"),
  tier: mysqlEnum("tier", ["free", "pro", "premium"]).notNull().default("free"),
  tierExpiresAt: timestamp("tier_expires_at"),
  createdAt: createdAt(),
});

export const memberships = mysqlTable(
  "memberships",
  {
    id: id(),
    userId: ref("user_id").notNull(),
    tenantId: ref("tenant_id").notNull(),
    role: mysqlEnum("role", ["owner", "member"]).notNull().default("owner"),
    createdAt: createdAt(),
  },
  (t) => [uniqueIndex("user_tenant_idx").on(t.userId, t.tenantId)],
);

// Mapeo de columnas, normalización de categorías, colores, bins… (ReportConfig.from_dict)
export const tenantConfigs = mysqlTable("tenant_configs", {
  tenantId: ref("tenant_id").primaryKey(),
  configJson: json("config_json").notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
});

// Espejo de product_map.csv, por tenant (editor en Fase 2).
export const productMapEntries = mysqlTable(
  "product_map_entries",
  {
    id: id(),
    tenantId: ref("tenant_id").notNull(),
    sistema: varchar("sistema", { length: 200 }).notNull(),
    precioPost: int("precio_post"),
    fechaDesde: date("fecha_desde"),
    nombre: varchar("nombre", { length: 200 }).notNull(),
    categoria: varchar("categoria", { length: 100 }).notNull(),
    subcategoria: varchar("subcategoria", { length: 100 }),
    margenPct: decimal("margen_pct", { precision: 5, scale: 2 }),
  },
  (t) => [index("pme_tenant_idx").on(t.tenantId)],
);

// Archivo POS subido, gzip. Límite de subida 20 MB (validado en API).
export const datasets = mysqlTable(
  "datasets",
  {
    id: id(),
    tenantId: ref("tenant_id").notNull(),
    filename: varchar("filename", { length: 255 }).notNull(),
    contentGz: longblob("content_gz").notNull(),
    sha256: varchar("sha256", { length: 64 }).notNull(),
    sizeBytes: int("size_bytes").notNull(),
    createdAt: createdAt(),
  },
  (t) => [index("ds_tenant_idx").on(t.tenantId)],
);

export const analysisJobs = mysqlTable(
  "analysis_jobs",
  {
    id: id(),
    tenantId: ref("tenant_id").notNull(),
    datasetId: ref("dataset_id").notNull(),
    type: mysqlEnum("type", ["report", "delta"]).notNull().default("report"),
    status: mysqlEnum("status", [
      "queued",
      "dispatched",
      "running",
      "succeeded",
      "failed",
      "timed_out",
    ])
      .notNull()
      .default("queued"),
    attempt: int("attempt").notNull().default(1),
    // Config del tenant congelada al crear el job (reproducibilidad).
    configSnapshot: json("config_snapshot").notNull(),
    // Token de un solo uso con el que el worker autentica el callback.
    jobToken: varchar("job_token", { length: 64 }),
    errorText: text("error_text"),
    dispatchedAt: timestamp("dispatched_at"),
    startedAt: timestamp("started_at"),
    finishedAt: timestamp("finished_at"),
    createdAt: createdAt(),
  },
  (t) => [
    index("job_tenant_idx").on(t.tenantId),
    index("job_status_idx").on(t.status),
  ],
);

export const reportPayloads = mysqlTable(
  "report_payloads",
  {
    id: id(),
    jobId: ref("job_id").notNull().unique(),
    tenantId: ref("tenant_id").notNull(),
    schemaVersion: int("schema_version").notNull(),
    payloadGz: longblob("payload_gz").notNull(),
    // summary + teasers precalculados: dashboards y tier free leen esto,
    // nunca el payload completo.
    summaryJson: json("summary_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [index("rp_tenant_idx").on(t.tenantId)],
);

export const consultingLeads = mysqlTable("consulting_leads", {
  id: id(),
  tenantId: ref("tenant_id"),
  name: varchar("name", { length: 120 }).notNull(),
  email: varchar("email", { length: 255 }).notNull(),
  phone: varchar("phone", { length: 40 }),
  message: text("message"),
  status: mysqlEnum("status", ["new", "contacted", "closed"])
    .notNull()
    .default("new"),
  createdAt: createdAt(),
});

export const auditLog = mysqlTable("audit_log", {
  id: id(),
  actorUserId: ref("actor_user_id"),
  tenantId: ref("tenant_id"),
  action: varchar("action", { length: 120 }).notNull(),
  detail: json("detail"),
  createdAt: createdAt(),
});
