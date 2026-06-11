// GENERADO por scripts/embed-migrations.ts — NO EDITAR A MANO.
// Regenerar con: npm run db:generate

export type EmbeddedMigration = { tag: string; statements: string[] };

export const MIGRATIONS: EmbeddedMigration[] = [
  {
    "tag": "0000_curious_the_liberteens",
    "statements": [
      "CREATE TABLE `analysis_jobs` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`dataset_id` bigint unsigned NOT NULL,\n\t`type` enum('report','delta') NOT NULL DEFAULT 'report',\n\t`status` enum('queued','dispatched','running','succeeded','failed','timed_out') NOT NULL DEFAULT 'queued',\n\t`attempt` int NOT NULL DEFAULT 1,\n\t`config_snapshot` json NOT NULL,\n\t`job_token` varchar(64),\n\t`error_text` text,\n\t`dispatched_at` timestamp,\n\t`started_at` timestamp,\n\t`finished_at` timestamp,\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `analysis_jobs_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `audit_log` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`actor_user_id` bigint unsigned,\n\t`tenant_id` bigint unsigned,\n\t`action` varchar(120) NOT NULL,\n\t`detail` json,\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `audit_log_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `consulting_leads` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`tenant_id` bigint unsigned,\n\t`name` varchar(120) NOT NULL,\n\t`email` varchar(255) NOT NULL,\n\t`phone` varchar(40),\n\t`message` text,\n\t`status` enum('new','contacted','closed') NOT NULL DEFAULT 'new',\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `consulting_leads_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `datasets` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`filename` varchar(255) NOT NULL,\n\t`content_gz` longblob NOT NULL,\n\t`sha256` varchar(64) NOT NULL,\n\t`size_bytes` int NOT NULL,\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `datasets_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `memberships` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`user_id` bigint unsigned NOT NULL,\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`role` enum('owner','member') NOT NULL DEFAULT 'owner',\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `memberships_id` PRIMARY KEY(`id`),\n\tCONSTRAINT `user_tenant_idx` UNIQUE(`user_id`,`tenant_id`)\n);",
      "CREATE TABLE `product_map_entries` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`sistema` varchar(200) NOT NULL,\n\t`precio_post` int,\n\t`fecha_desde` date,\n\t`nombre` varchar(200) NOT NULL,\n\t`categoria` varchar(100) NOT NULL,\n\t`subcategoria` varchar(100),\n\t`margen_pct` decimal(5,2),\n\tCONSTRAINT `product_map_entries_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `report_payloads` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`job_id` bigint unsigned NOT NULL,\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`schema_version` int NOT NULL,\n\t`payload_gz` longblob NOT NULL,\n\t`summary_json` json NOT NULL,\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `report_payloads_id` PRIMARY KEY(`id`),\n\tCONSTRAINT `report_payloads_job_id_unique` UNIQUE(`job_id`)\n);",
      "CREATE TABLE `tenant_configs` (\n\t`tenant_id` bigint unsigned NOT NULL,\n\t`config_json` json NOT NULL,\n\t`updated_at` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,\n\tCONSTRAINT `tenant_configs_tenant_id` PRIMARY KEY(`tenant_id`)\n);",
      "CREATE TABLE `tenants` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`name` varchar(160) NOT NULL,\n\t`country` varchar(2) NOT NULL DEFAULT 'CO',\n\t`currency` varchar(3) NOT NULL DEFAULT 'COP',\n\t`tier` enum('free','pro','premium') NOT NULL DEFAULT 'free',\n\t`tier_expires_at` timestamp,\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `tenants_id` PRIMARY KEY(`id`)\n);",
      "CREATE TABLE `users` (\n\t`id` serial AUTO_INCREMENT NOT NULL,\n\t`email` varchar(255) NOT NULL,\n\t`password_hash` varchar(255) NOT NULL,\n\t`name` varchar(120) NOT NULL,\n\t`email_verified_at` timestamp,\n\t`verification_token` varchar(64),\n\t`created_at` timestamp NOT NULL DEFAULT (now()),\n\tCONSTRAINT `users_id` PRIMARY KEY(`id`),\n\tCONSTRAINT `users_email_unique` UNIQUE(`email`)\n);",
      "CREATE INDEX `job_tenant_idx` ON `analysis_jobs` (`tenant_id`);",
      "CREATE INDEX `job_status_idx` ON `analysis_jobs` (`status`);",
      "CREATE INDEX `ds_tenant_idx` ON `datasets` (`tenant_id`);",
      "CREATE INDEX `pme_tenant_idx` ON `product_map_entries` (`tenant_id`);",
      "CREATE INDEX `rp_tenant_idx` ON `report_payloads` (`tenant_id`);"
    ]
  }
];
