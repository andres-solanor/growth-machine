# Analytikz (growth-machine)

SaaS de análisis de ventas para negocios de comida/retail en LatAm, en producción en
**analytikz.com.co** (Hostinger Managed Node.js + worker Python en GitHub Actions).
El dueño (Andrés) no es desarrollador: explica en lenguaje claro, sin jerga.
Chat en inglés; TODO el producto en español. Moneda COP.

## Fuentes de verdad

- **docs/SAAS-PLAN.md** — plan maestro + Decision Log. Regla: toda decisión que cambie
  alcance/arquitectura/tiers se anota en el Decision Log Y se actualiza la sección
  afectada en el mismo commit.
- El estado vivo del roadmap (qué se hizo, qué sigue) está en la memoria persistente
  de Claude (next-run-plan); consúltala al iniciar sesión.

## Ramas — REGLA DURA

- `saas` = rama de producción del SaaS y default de GitHub. **Cada push a `saas`
  despliega automáticamente** el sitio.
- `main` = SOLO entregas semanales de La Panettería (el cliente original). NUNCA
  recibe cambios del SaaS.

## Deploy

- Agrupar cambios en UN solo push: tras cada deploy el edge de Hostinger puede dar
  503 a todo el sitio 12–45 min (se recupera solo; hard refresh para chunks viejos).
- Verificación antes de pushear: `npx eslint <archivos>`, `npm run check:gating`,
  `npm run check:payload`, `npm run build` (webpack; si sale exit 134, reintentar).
- Diagnóstico en producción: `/api/health` (DB/migraciones) y `/api/health?smtp=1` (correo).
- Commits con comillas en el mensaje: escribir el mensaje a `.git/COMMIT_MSG_TMP.txt`
  con el tool Write y usar `git commit -F` (PowerShell 5.1 rompe las comillas inline).

## Trampas técnicas (ganadas a pulso)

- La DB es **MariaDB** (no MySQL): nada de `serial()`; JSON llega como STRING →
  schema.ts usa un customType json con JSON.parse (no volver al `json()` de drizzle);
  conectar a `127.0.0.1`, no `localhost`; migraciones embebidas en el bundle.
- Lectura de payloads (src/lib/report.ts): zod SOLO al escribir; `interactive_base`
  se descarta al parsear; caché de 3 payloads por proceso. NO revalidar en lectura
  ni cargar interactive_base por vista (causó las ráfagas de 503).
- Plotly jamás se importa server-side — solo vía src/components/charts/plot.tsx.
- Scripts de `scripts/` usan imports relativos, no `@/` (corren con tsx).
- El gating vive puro en src/lib/gating.ts (sin DB) y se verifica con check:gating.

## Seguridad — NO NEGOCIABLE

- Exports del POS (reports/input_data/) son datos de clientes: jamás se commitean.
- Secretos SOLO en el panel de Hostinger / GitHub Secrets — nunca en repo ni chat.
  Los valores de env vars de Hostinger deben ser alfanuméricos (+`-`): los símbolos
  `#`, `$` y comillas se corrompen en su panel.
- Datos de ventas jamás en logs del worker/CI.
- Los demos borrosos de secciones bloqueadas son 100% sintéticos
  (locked-demos.tsx no importa nada del payload — mantenerlo así).
