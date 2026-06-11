CREATE TABLE `analysis_jobs` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`tenant_id` bigint unsigned NOT NULL,
	`dataset_id` bigint unsigned NOT NULL,
	`type` enum('report','delta') NOT NULL DEFAULT 'report',
	`status` enum('queued','dispatched','running','succeeded','failed','timed_out') NOT NULL DEFAULT 'queued',
	`attempt` int NOT NULL DEFAULT 1,
	`config_snapshot` json NOT NULL,
	`job_token` varchar(64),
	`error_text` text,
	`dispatched_at` timestamp,
	`started_at` timestamp,
	`finished_at` timestamp,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `analysis_jobs_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `audit_log` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`actor_user_id` bigint unsigned,
	`tenant_id` bigint unsigned,
	`action` varchar(120) NOT NULL,
	`detail` json,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `audit_log_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `consulting_leads` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`tenant_id` bigint unsigned,
	`name` varchar(120) NOT NULL,
	`email` varchar(255) NOT NULL,
	`phone` varchar(40),
	`message` text,
	`status` enum('new','contacted','closed') NOT NULL DEFAULT 'new',
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `consulting_leads_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `datasets` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`tenant_id` bigint unsigned NOT NULL,
	`filename` varchar(255) NOT NULL,
	`content_gz` longblob NOT NULL,
	`sha256` varchar(64) NOT NULL,
	`size_bytes` int NOT NULL,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `datasets_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `memberships` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`user_id` bigint unsigned NOT NULL,
	`tenant_id` bigint unsigned NOT NULL,
	`role` enum('owner','member') NOT NULL DEFAULT 'owner',
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `memberships_id` PRIMARY KEY(`id`),
	CONSTRAINT `user_tenant_idx` UNIQUE(`user_id`,`tenant_id`)
);
--> statement-breakpoint
CREATE TABLE `product_map_entries` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`tenant_id` bigint unsigned NOT NULL,
	`sistema` varchar(200) NOT NULL,
	`precio_post` int,
	`fecha_desde` date,
	`nombre` varchar(200) NOT NULL,
	`categoria` varchar(100) NOT NULL,
	`subcategoria` varchar(100),
	`margen_pct` decimal(5,2),
	CONSTRAINT `product_map_entries_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `report_payloads` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`job_id` bigint unsigned NOT NULL,
	`tenant_id` bigint unsigned NOT NULL,
	`schema_version` int NOT NULL,
	`payload_gz` longblob NOT NULL,
	`summary_json` json NOT NULL,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `report_payloads_id` PRIMARY KEY(`id`),
	CONSTRAINT `report_payloads_job_id_unique` UNIQUE(`job_id`)
);
--> statement-breakpoint
CREATE TABLE `tenant_configs` (
	`tenant_id` bigint unsigned NOT NULL,
	`config_json` json NOT NULL,
	`updated_at` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `tenant_configs_tenant_id` PRIMARY KEY(`tenant_id`)
);
--> statement-breakpoint
CREATE TABLE `tenants` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`name` varchar(160) NOT NULL,
	`country` varchar(2) NOT NULL DEFAULT 'CO',
	`currency` varchar(3) NOT NULL DEFAULT 'COP',
	`tier` enum('free','pro','premium') NOT NULL DEFAULT 'free',
	`tier_expires_at` timestamp,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `tenants_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` serial AUTO_INCREMENT NOT NULL,
	`email` varchar(255) NOT NULL,
	`password_hash` varchar(255) NOT NULL,
	`name` varchar(120) NOT NULL,
	`email_verified_at` timestamp,
	`verification_token` varchar(64),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `users_id` PRIMARY KEY(`id`),
	CONSTRAINT `users_email_unique` UNIQUE(`email`)
);
--> statement-breakpoint
CREATE INDEX `job_tenant_idx` ON `analysis_jobs` (`tenant_id`);--> statement-breakpoint
CREATE INDEX `job_status_idx` ON `analysis_jobs` (`status`);--> statement-breakpoint
CREATE INDEX `ds_tenant_idx` ON `datasets` (`tenant_id`);--> statement-breakpoint
CREATE INDEX `pme_tenant_idx` ON `product_map_entries` (`tenant_id`);--> statement-breakpoint
CREATE INDEX `rp_tenant_idx` ON `report_payloads` (`tenant_id`);