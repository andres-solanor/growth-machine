# SAAS-PLAN.md — Growth Machine → Tiered-Access SaaS

> **This is the source of truth for the SaaS project.**
>
> **Maintenance rule:** whenever a significant decision changes scope, architecture, tiers,
> stack, or hosting during implementation, the change MUST be recorded in the
> [Decision Log](#decision-log) **and** the affected section updated **in the same commit**.
> Claude sessions working on this repo: read this file before SaaS work and keep it current.
>
> Sibling doc: [BRANCHING.md](./BRANCHING.md) — plain-language branch strategy.

---

## 1. Context & business goal

The repo started as a local Python/pandas analytics tool (~5,500 LOC) built for La Panettería
(bakery, Colombia): `reports/report_generator.py` (KPIs, timeline, Pareto, market basket,
profitability, 15-rule insight engine, bundle recommendations → self-contained HTML),
`reports/delta_builder/delta_builder.py` (pre/post event impact), and
`reports/normalize_products.py` (POS export consolidation + product_map enrichment).

**Goal:** an online, layered-access SaaS for retail/food businesses in LatAm (Spanish-first),
working as a funnel:

- **Free** — 1 self-serve monthly analysis: genuinely useful basics + locked teasers of deeper sections.
- **Pro / Premium** — predefined deeper analyses (market basket, cart, trends, profitability, bundles, delta reports).
- **Consulting 1:1** — premium service promoted via CTAs throughout (lead form; no online payments yet — tiers activated manually by admin).

**Hosting (purchased 2026-06-10):** Hostinger Business 48-month plan — 5 managed **Node.js-only**
web apps (no Python runtime), 2 CPU / 3 GB RAM, 50 GB NVMe, managed MySQL, GitHub auto-deploy,
SSL, SMTP mailboxes, CDN, free domain 1 year.

## 2. Architecture

```
[User browser] ⇄ [Next.js app @ Hostinger (auth, upload, gating, report UI, admin)]
                        ⇅ MySQL (users, tenants, uploads LONGBLOB, jobs, payloads gzip)
                        ⇅ HMAC-signed API
[GitHub Actions worker: python worker/run_job.py → JSON payload → POST back]
```

- **Web:** Next.js 15 App Router, `output: 'standalone'`, one Hostinger managed Node app,
  GitHub auto-deploy. Server-side tier gating (locked data never serialized to the client).
  Drizzle ORM (mysql2), Auth.js (credentials + email verification via Hostinger SMTP), zod.
- **Worker:** the existing Python engine, headless (JSON payload output), triggered by
  GitHub Actions `repository_dispatch`. Free, no extra infra; jobs run ~30–90 s.
  Revisit only if GHA queue latency proves painful.
- **Storage:** all durable state in MySQL (Hostinger redeploys rebuild the app filesystem).
  Uploads and payloads gzip'd in LONGBLOB; a small `summary_json` per report for
  dashboards/teasers without decompressing blobs.

### Monorepo layout (on `saas` branch only)

```
apps/web/                  # Next.js: (marketing) landing ES + pricing; (app) dashboard,
                           #   onboarding, reports/[id]; api/ (auth, uploads, jobs, worker, admin)
packages/payload-schema/   # zod schemas + TS types for payload JSON (schema_version'd)
worker/run_job.py          # job-spec → normalize → engine → payload.json
worker/engine/             # moved: report_generator.py, delta_builder/, normalize_products.py
reports/input_data/        # stays — local bakery mode keeps working
.github/workflows/analysis-job.yml
```

### Key code seams (verified)

- `ReportGenerator.run()` (report_generator.py:3100) builds `summary`, `analyses`, `quality`,
  `insights`, `recommendations` as plain data **before** HTML rendering — the JSON-mode seam.
  `analyses` contains live DataFrames serialized by `ReportRenderer._j()` (:1781).
- `DeltaPayloadBuilder.build()` already emits pure JSON; `BuilderConfig.from_dict` already
  takes external config.
- XLS (SpreadsheetML) support exists: `normalize_products.py:_read_spreadsheetml()` / `_read_file()`.
- All tenant knobs are `ReportConfig` dataclass fields (:56–132): columns, categories,
  currency, store_name, ticket_bins, colors, day order.
- Real payload sizes: report HTML 5.8 MB (row-level `BASE_ROWS` dominates), delta JSON 9.4 MB
  → gzip in DB + free-tier slimming.

## 3. Tier matrix

| Capability | free | pro | premium |
|---|---|---|---|
| KPIs, quality, timeline, top-10 products | ✓ | ✓ | ✓ |
| Insights | 3 basic | all 15 | all 15 |
| Row-level interactive filtering | — | ✓ | ✓ |
| basket, cart, trends, ticket, rules, anomalies | teaser | ✓ | ✓ |
| profitability, bundles, recommendations | teaser | teaser | ✓ |
| Delta (event-impact) reports | — | — | ✓ |
| Analyses/month | 1 | 10 | unlimited |
| Consulting | CTA | CTA | CTA + included-session framing |

Gating is exclusively server-side (`lib/gating.ts`): locked module keys are stripped from the
payload and replaced with `{locked, teaser}` built from precomputed `summary_json` stats
(e.g. "Detectamos 23 combinaciones con lift > 1.5"). A test asserts free-tier responses
contain zero locked keys.

## 4. Phases

### Phase 0 — Python headless refactor — ✅ DONE (2026-06-10)

0. ✅ `saas` branch; this doc + BRANCHING.md; `.gitignore` for `.xls` exports.
1. ✅ `ReportGenerator.build_payload()` + `to_jsonable()`; HTML verified **byte-identical**
   to pre-refactor on fixture data (md5 match).
2. ✅ CLI `--format json|html|both`, `--payload-out`, `--config`; `ReportConfig.from_dict()`
   (incl. `columns` aliases); `date_min_iso`/`date_max_iso` in `summary()`.
3. ✅ Pure `normalize()`/`consolidate()`/`prepare_product_map()`; output byte-identical
   on real POS exports (23,478 rows).
4. ✅ `delta_builder --json-only`; meta gains schemaVersion/reportType/currency.
5. ✅ `worker/run_job.py` (report + delta + no-product-map onboarding fallback tested
   end-to-end on the real .xls). `openpyxl`/`xlrd` in requirements.
6. ✅ `tests/test_payload.py` (9 tests) + golden snapshot + `tests/regen_golden.py`.

Note: the zod schema (`packages/payload-schema`) moves to Phase 1 day 1 — it needs the
npm workspace that the monorepo scaffold creates.

### Phase 1 — MVP funnel (~3–4 weeks)

✅ 2026-06-11: Next.js scaffold (repo root) **deployed live to Hostinger** from `saas` via
GitHub auto-deploy (temporary domain; switch to analytikz.com.co pending — the domain must
first be detached from the placeholder website in hPanel). Hostinger MySQL database created
(`u727350056_growthdb`); password reset + `max_allowed_packet`/LONGBLOB verification still
pending before first migration.

✅ 2026-06-11: **MySQL wired end-to-end in production.** Fresh DB `u727350056_grwth_mchne_db`
(old one retired), `DATABASE_URL` env var in Hostinger panel. All 10 tables + migration
tracker live (verified via `/api/health`: ok, 11 tables, `max_allowed_packet` = 1024 MB —
day-1 LONGBLOB check passed). Hard-won Hostinger facts: connect via `127.0.0.1` (not
`localhost`, IPv6 ::1 is denied); the DB is **MariaDB** (drizzle `serial()` invalid →
bigint unsigned autoincrement); the runtime does **not** ship repo files like `drizzle/`,
so migration SQL is embedded in the bundle (`scripts/embed-migrations.ts`, runs inside
`npm run db:generate`) and applied idempotently at boot + by `/api/health` self-heal.

✅ 2026-06-11: **PIPELINE COMPLETO VERIFICADO EN PRODUCCIÓN** 🎉 — usuario real subió el
.xls crudo de La Panettería por el wizard → dispatch → GitHub Actions corrió el motor
Python (10k+ filas normalizadas, fallback sin product_map) → payload devuelto por API
HMAC → validado contra el contrato zod → guardado gzip en report_payloads → "¡Listo!"
en la página de progreso. Bugs cazados en el camino: timeout medía desde createdAt y no
desde dispatchedAt; `classification_thresholds` ausente sin márgenes rompía el contrato;
auto-redespacho check-on-read añadido para jobs huérfanos.

✅ 2026-06-11: **Página del reporte free-tier completa** (`/reportes/[jobId]`). Server
components puros (sin Plotly aún): KPIs (6), calidad de datos (chip de riesgo + cobertura),
hallazgos con severidad (free ve 3 + contador de bloqueados), línea de tiempo (SVG diario +
barras por día de semana + mejor combinación), top-10 productos con barras de revenue +
línea Pareto. Gating 100 % server-side en `src/lib/report.ts` (`gateReport`): los módulos
bloqueados se eliminan antes de serializar y se reemplazan por teasers con datos reales
(`TIER_MODULES` free/pro/premium). Secciones bloqueadas → tarjetas con CTA. Página de
consultoría `/consultoria` (lead form → `consulting_leads`, funciona logueado o anónimo).
Botón "Ver mi reporte →" al terminar el progreso; enlaces del panel van al reporte si
`succeeded`. Fix de zona horaria: fechas se muestran en hora local del país del tenant
(`src/lib/format.ts`, `tzForCountry`), no UTC. Workflow bump: checkout@v5, setup-python@v6.
Falta para tier toggle visible: render de Basket/Cart (Phase 2 port).

✅ 2026-06-11: **Admin + landing con planes + prueba anti-fuga.** `/admin` (gate por env var
`ADMIN_EMAILS`, lista de correos separados por coma — configurar en Hostinger): negocios con
dropdown de plan (free/pro/premium, escribe `audit_log`), monitor de últimos 20 análisis
(estado/intento/error), inbox de leads de consultoría (nuevo/contactado/cerrado). Landing
nueva con hero + cómo funciona + 3 planes + banda de consultoría (sin precios publicados
para Pro/Premium — pendiente decisión de pricing; CTA "Hablar con nosotros" → /consultoria).
Gating extraído a `src/lib/gating.ts` (puro, sin DB) y `npm run check:gating` verifica que
ningún dato bloqueado se serialice en ningún tier (pasa: free solo ve timeline+products).

✅ 2026-06-11: **Secciones Pro del reporte** (`sections-pro.tsx`, server components sin
Plotly): canasta (parejas que se compran juntas + badge "fuerte" si lift ≥ 1.5),
radiografía del carrito (distribución de productos por compra + ticket por segmento),
tendencias (en alza/en caída entre meses), oportunidades de ticket (horas con ticket bajo
+ barras por hora), días atípicos (excepcionales/bajos vs promedio), reglas para combos
("lleva A → ofrécele B" con % de aceptación y lift). Cada sección devuelve null si el
gating quitó su módulo → subir el plan en /admin las desbloquea de inmediato. Con esto el
contenido Pro está completo; Premium aún muestra teasers de rentabilidad/combos (Fase 2:
editor de product map + márgenes).

✅ 2026-06-11: **Auth + onboarding wizard live.** Registration (`/registro`: user + tenant
free + membership + audit in one tx), login (`/ingresar`), stateless JWT sessions (30 d,
`AUTH_SECRET` env), protected `/panel`. Upload wizard `/analisis/nuevo` (3 pasos: negocio →
archivo → columnas): datasets stored gzip+sha256 in LONGBLOB, column auto-detect
(`src/lib/csv-detect.ts`, verified vs real POS headers), `POST /api/jobs` enforces free
quota (1/mes) + 1 job activo, snapshot de config; progreso con polling 3 s. Job queda
`queued` — falta despachar al worker (GitHub Actions + HMAC), siguiente bloque.

✅ 2026-06-11: zod payload contract in `src/lib/payload-schema/` (validated against the real
fixture payload, all 11 modules; check with `npm run check:payload`, regen sample with
`tests/regen_payload_sample.py`). Drizzle schema for all 10 tables in `src/lib/db/schema.ts`
+ initial SQL migration in `drizzle/` (`npm run db:generate` / `db:migrate`; migrate needs
`DATABASE_URL` env var — set in Hostinger panel only, never in the repo).

Remaining: app scaffold extras + MySQL **day 1** checks (verify
`max_allowed_packet`/LONGBLOB early); Drizzle schema (`users`, `tenants(tier)`, `memberships`,
`tenant_configs`, `product_map_entries`, `datasets`, `analysis_jobs`, `report_payloads`,
`consulting_leads`, `audit_log`); Auth.js register/login/verify; 4-step onboarding wizard
(business info → upload → column mapping with auto-detect → first analysis; categories/margins
deliberately post-first-report); job pipeline (`repository_dispatch`, HMAC-SHA256 worker API,
check-on-read timeouts, ≤3 retries); progress page polling 3 s; ~~report page free sections +
locked teasers + consulting CTA~~ (✅ hecho); ~~`BasketSection`/`CartSection` (so tier toggle
visibly unlocks)~~ (✅ hecho, + trends/ticket/anomalies/rules); ~~`/admin` (tenants, tier dropdown, job monitor, leads)~~
(✅ hecho); ~~landing ES with pricing~~ (✅ hecho, sin precios publicados); verificación de
email (necesita dominio + SMTP); decidir precios de Pro/Premium.

**Verify:** stranger registers → uploads real POS .xls → free report in <2 min; admin flips
tier → sections unlock; gating leak test passes.

### Phase 2 — Paid content (~3 weeks)

**Diseño acordado del editor de product map (2026-06-11):** nunca empieza en blanco —
se genera desde las ventas del tenant (productos + frecuencia + revenue ya conocidos).
Orden por impacto Pareto ("estos N productos son el 80% de tus ventas, clasifícalos
primero"); categorías con auto-sugerencia (confirmar, no escribir); resto puede quedar
"Otros". Márgenes en 3 niveles: (0) sin margen → teasers bloqueados, nada se rompe;
(1) margen aproximado POR CATEGORÍA (sliders, ~2 min) aplicado como fallback a productos
sin margen propio — reportes lo marcan "margen estimado"; (2) override por producto,
opcional. Cambio de motor requerido: aplicar margen de categoría como fallback en la
normalización del worker. El editor es a la vez el funnel de upgrade (categorías mejoran
free/pro; márgenes desbloquean premium).

Port remaining sections (trends, ticket, rules, profitability, bundles, recommendations);
product map editor (auto-suggest categories, margin entry → unlocks profitability);
delta report flow (event picker → BuilderConfig → job → ported delta sections);
transactional email (Hostinger SMTP); consulting lead inbox polish.

### Phase 3 — Deferred

Mercado Pago subscriptions (webhooks → `tenants.tier`); incremental TypeScript port of
`AnalysisModules` behind per-job `engine=ts|py` flag; multi-store tenants.

## 5. Risks & mitigations

- **Hostinger managed Node:** filesystem rebuilt on deploy → all state in MySQL; no
  daemons/websockets → polling + check-on-read timeouts; shared 2 CPU/3 GB → small free-tier
  responses, streaming decompression.
- **GH Actions:** 2,000 free min/mo ≈ ~700 jobs — fine for MVP; surface usage in admin;
  honest "~1 minuto" UX copy for queue latency.
- **Payload size:** gzip ~10:1 + `summary_json` + free tier gets aggregates only
  (no `interactive_base` rows).
- **Serialization traps:** numpy scalars/NaN (hidden today by `_j(default=str)`) →
  explicit `to_jsonable` + golden-fixture test.
- **Locale:** web formats from ISO dates + `Intl.NumberFormat(currency)`, never
  server-locale strings.
- **Scope guard:** one store per tenant for MVP (`DEDUP_KEY` assumes single store).
- **Onboarding is the churn point:** every POS exports differently; column-mapping wizard and
  product-map editor quality decide tenant success. Treat them as product, not plumbing.

## 6. Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-06-10 | Hybrid architecture: Node.js web app on Hostinger + existing Python engine as external headless worker (GitHub Actions); TypeScript port deferred to Phase 3 | Hostinger managed apps are Node-only; preserves 5,500 LOC of working analytics; ships fastest |
| 2026-06-10 | Target market: any retail/food business in LatAm (Spanish-first, per-tenant currency/categories/column mapping) | Larger funnel than bakeries-only; config knobs already exist in ReportConfig |
| 2026-06-10 | Payments deferred; free tier first, tiers activated manually by admin (invoice via WhatsApp/transfer) | Validate pricing before billing code; manual B2B billing is normal in Colombia; Stripe unavailable to CO merchants — Mercado Pago planned for Phase 3 |
| 2026-06-10 | Free tier = self-serve upload with instant-ish report (~1 min, GH Actions worker) | Product-led funnel; batch worker keeps Python unmodified |
| 2026-06-10 | Same repo, long-lived `saas` branch; `main` reserved for La Panettería deliveries; Hostinger deploys from `saas`, never `main` | Protects weekly customer deliveries; engine fixes flow main→saas with cheap merges |
| 2026-06-10 | All durable state in MySQL LONGBLOB (gzip), nothing on app filesystem | Hostinger redeploys rebuild the filesystem; MySQL is the only backed-up persistence |
| 2026-06-10 | Next.js 15 (App Router, standalone) over Express; Drizzle + Auth.js + zod | RSC = natural server-side gating; one app covers landing+app+API under the 5-app cap |
| 2026-06-10 | Brand: **Analytikz** · Domain: **analytikz.com.co** (registered; Hostinger Node.js site created) | .com taken, .co not free; .com.co credible for CO/LatAm market; domain kept in env config, never hard-coded — cheap to migrate later |
| 2026-06-10 | No npm-workspace monorepo: Next.js app lives at **repo root** (`src/app`, `package.json`); zod payload schemas in `src/lib/payload-schema/`; Python engine stays in `reports/` + `worker/` | Hostinger managed Node.js auto-detects/builds apps at repo root only (no documented subdirectory setting); worker is Python, so a shared TS package had no second consumer |
| 2026-06-11 | Auth hecha a mano (bcryptjs + JWT firmado con jose en cookie httpOnly, server actions) en lugar de Auth.js | Solo necesitamos credenciales + verificación de email custom; Auth.js añade superficie/beta-churn sin beneficio hasta que haya OAuth (reconsiderar entonces). Sesión sin estado sobrevive redeploys de Hostinger. Requiere env var `AUTH_SECRET` |
| 2026-06-11 | GitHub **default branch** switched from `main` to `saas` | Hostinger's repo import scans the *default* branch for framework detection (no branch picker shown); `main` has no Node.js app, so detection failed with "el marco no es compatible". Changes no code — `main` and the weekly La Panettería workflow are untouched. `saas` stays default going forward (it is the production branch) |
| 2026-06-11 | Admin gateado por env var `ADMIN_EMAILS` (lista de correos), no por rol en DB | Cero migraciones y cero UI extra para un solo admin; el correo vive solo en el panel de Hostinger. Si algún día hay más admins, migrar a rol en `memberships` |
| 2026-06-11 | Landing publica los 3 planes SIN precio para Pro/Premium ("precio de lanzamiento — escríbenos" → /consultoria) | Los precios aún no están decididos; el CTA a consultoría convierte la duda de precio en conversación de venta. Cuando se decidan, actualizar `PLANES` en `src/app/page.tsx` |
