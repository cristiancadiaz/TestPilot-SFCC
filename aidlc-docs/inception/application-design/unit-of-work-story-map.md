# Unit of Work Story Map — TestPilot SFCC (actualizado 2026-05-24)

> Mapa de requisitos funcionales del PRD a unidades de trabajo. Cada RF del requirements.md tiene su unidad asignada.
>
> **Cambio mayor 2026-05-24:** se agregaron RF-14 a RF-20 cubriendo Dashboard MD0, Environment Registry, autenticación dual y endpoints en tiempo real. M13 promovido de "Simplificado" a "Completo" porque Secrets Manager se usa desde día 1.

## Mapa RF → Unidad

| RF | Descripción breve | Unidad | Prioridad PRD |
|----|-------------------|--------|---------------|
| RF-01 | pyproject.toml con dependencias, ruff, mypy + Dockerfile multi-stage | U0 | Deuda técnica crítica |
| RF-02 | src/models.py — modelos unificados (incluyendo EnvironmentConfig, credenciales duales, ResolvedEnvironment, RunStatus) | U0 | Deuda técnica crítica |
| RF-03 | Actualizar modelo Claude a `claude-haiku-4-5-20251001` | U0 | Deuda técnica |
| RF-04 | BrowserProfiles: `mobile-co`, `desktop-co`, `desktop-ec` | U1 | M3 |
| RF-05 | SFCCSelectors: catálogo centralizado (incluye `LOGIN_*` para shopper_login) | U1 | M4 (prerequisito) |
| RF-06 | Flow `checkout-full` (10 pasos: env_access_auth + shopper_login + 8 funcionales; `orders_created=0`) | U1 | M4 |
| RF-07 | Flow `checkout-card-declined` (10 pasos con `verify_decline_message` al final) | U1 | M4 |
| RF-08 | FlowRunner (orquestador local + `InfrastructureError` + `http_credentials` para env_access) | U1 | M4 |
| RF-09 | BaselineManager (p95, bootstrap, semáforo, store con clave `(environment_id, profile, flow)`) | U2 | M10, M11, M12 |
| RF-10 | ReportGenerator (JSON+MD+semáforo+invariante orders_created=0; baseline por ambiente) | U3 | M7, M8, M17 |
| RF-11 | GET /v1/runs/{run_id} | U4 | M2 |
| RF-12 | GET /v1/runs/latest (`age_seconds` + `ttl_ok`) | U4 | M2 |
| RF-13 | POST /v1/run integrado con executor real (recibe `SyntheticUserConfig` estructurado, NO NL) | U4 | M1 (completar) |
| **RF-14** | **CRUD Environment Registry (POST/GET/PUT/DELETE /v1/environments)** | U4 | **M19, M13** |
| **RF-15** | **EnvironmentResolver: resolución de credenciales `env_access` + `shopper` desde Secrets Manager** | U4 | **M13** |
| **RF-16** | **GET /v1/runs/{id}/status (estado en vivo para polling del dashboard)** | U4 | **M19** |
| **RF-17** | **GET /v1/runs (historial paginado con filtros: env, semáforo, flow, fechas)** | U4 | **M19, Journey 2** |
| **RF-18** | **GET /v1/runs/{id}/screenshots/{path} (proxy desde S3)** | U4 | **M9** |
| **RF-19** | **GET /health (verifica DynamoDB + Secrets Manager)** | U4 | **Observability** |
| **RF-20** | **Dashboard MD0 (5 pantallas: P1 Environments, P2 NewRun, P3 LiveRun, P4 RunDetail, P5 History)** | MD0 | **M19** |

## Mapa RNF → Unidad

| RNF | Descripción breve | Unidad principal |
|-----|-------------------|------------------|
| RNF-01 | Credenciales en Secrets Manager (env_access + shopper), no en código ni payloads | U0 (modelos con `repr=False`) + U4 (resolver) |
| RNF-02 | Invariante `orders_created=0` | U1 (flows) + U3 (assert en reporter) + U4 (re-verificación en POST /v1/run) |
| RNF-03 | Logging estructurado sin secretos | U1, U2, U3, U4, MD0 (transversal) |
| RNF-04 | Manejo de errores seguro (SECURITY-15) | U1 (`InfrastructureError`) + U4 (global handler) |
| RNF-05 | Validación de inputs en API (SECURITY-05) | U4 (Pydantic) + MD0 (UX en frontend) |
| RNF-06 | Autenticación X-API-Key (SECURITY-05) | U4 |
| RNF-07 | Performance: timeout configurable, sin sleep fijo, watchdog 30 min | U1, U4 |
| RNF-08 | Supply chain: versiones pinned, Dockerfile sin `:latest` (SECURITY-08, SECURITY-12) | U0 |
| RNF-09 | PBT con hypothesis para p95 y semáforo | U2 (tests) + U3 (round-trip) |
| RNF-10 | Reproducibilidad del build (multi-stage Docker + pnpm lockfile) | U0, MD0 |
| **RNF-11** | **CSP + security headers para dashboard estático** | **U4 (middleware) + MD0 (consumidor)** |
| **RNF-12** | **Caché TTL para Environment Registry (60s) y resolución de credenciales (5min)** | **U4** |
| **RNF-13** | **Polling-friendly endpoint /v1/runs/{id}/status (< 100 ms p95)** | **U4** |

## Cobertura de Must Haves del PRD

| PRD Must Have | Cubierto en | Estado |
|---------------|-------------|--------|
| M1 POST /v1/run | U4 (integración) | Diseño completo |
| M2 GET /v1/runs/ endpoints | U4 (incluyendo /status y listado paginado) | Diseño completo |
| M3 3 perfiles (`mobile-co`, `desktop-co`, `desktop-ec`) | U1 | Diseño completo |
| M4 2 flows Playwright (`checkout-full`, `checkout-card-declined`) | U1 | Diseño completo |
| M5 LLM NL→config + validación | `src/agents/` existente | Implementado; queda como funcionalidad opcional (translator NL ya no es entrada principal — ver D8 actualizada) |
| M6 Payment prueba + `@testpilot.internal` | U1 (flows) + U4 (assertion en orchestrator) | Diseño completo |
| M7 Reporte JSON + Markdown | U3 | Diseño completo |
| M8 Semáforo 3 estados | U2+U3+MD0 (vista) | Diseño completo |
| M9 Screenshots todos los módulos | U1 (flows) + U4 (proxy S3) | Diseño completo |
| M10 DynamoDB stub (InMemory) | U2 (Protocol pattern; migración a DynamoDB en sprint 3+) | Diseño completo |
| M11 Baseline p95 últimas 10 | U2 (con clave compuesta por ambiente) | Diseño completo |
| M12 Bootstrap 14 runs | U2 | Diseño completo |
| **M13 Secrets Manager** | U4 (EnvironmentResolver + SecretsManagerClient) — 8 secrets por ambiente | **Completo desde día 1** |
| M14 Logging CloudWatch | RNF-03 (JSON logger compatible con awslogs) | Simplificado MVP (CloudWatch consume stdout) |
| M15 Webhook Slack | — | Aplazado a SHOULD HAVE |
| M16 Schema versionado /v1/ | U4 (todos los endpoints bajo /v1/) | Implementado |
| M17 Distinción infra vs tienda | U1 (`InfrastructureError`) + U3 (semáforo YELLOW para infra) | Diseño completo |
| M18 Pre-flight anti-bot | Manual (operativo) + `anti_bot_whitelisted` flag en EnvironmentConfig | No aplica en código |
| **M19 Dashboard Web Interno** | MD0 (5 pantallas) + U4 (endpoints de soporte) | **Diseño completo** |

## Mapa Historias (user-stories.md) → Unidad

| Historias | Unidad | Total ACs |
|---|---|---|
| H0.1, H0.2, H0.3 | U0 | 11 |
| H1.1, H1.2, H1.3, H1.4, H1.5 | U1 | 20 |
| H2.1, H2.2, H2.3, H2.4, H2.5 | U2 | 20 |
| H3.1, H3.2, H3.3 | U3 | 11 |
| H4.1, H4.2, H4.3, H4.4, H4.5 | U4 | 21 |
| **H5.1, H5.2, H5.3, H5.4** | **MD0** | **16** |
| **Total** | **6 unidades** | **99 ACs** |
