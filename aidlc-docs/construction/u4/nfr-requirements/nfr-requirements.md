# NFR Requirements — U4 API Endpoints (actualizado 2026-05-24)

## Performance

### NFR-U4-P1: Latencia de endpoints rápidos
GET endpoints (sin run completo) deben responder en **< 200 ms p95**:
- `GET /v1/environments` (con caché 60s)
- `GET /v1/runs/{id}` (lookup en baseline_store o DynamoDB)
- `GET /v1/runs/{id}/status` (lookup en live_tracker)
- `GET /v1/runs?filters` (DynamoDB query con GSI)

### NFR-U4-P2: POST /v1/run — bloqueante y latencia esperada
`POST /v1/run` es sincrónico — el caller espera la response completa. Latencia esperada: **8–12 min** (depende de flow + perfil + red de SFCC). Watchdog absoluto: 30 min.

### NFR-U4-P3: Concurrencia de runs paralelos
Max 3 perfiles × N flows en paralelo por run (controlado por semaphore). Múltiples runs simultáneos: hasta 5 runs paralelos en una task ECS (~15 browsers Chromium activos). Si excede: 429 `too_many_concurrent_runs`.

### NFR-U4-P4: Healthcheck rápido
`GET /health` responde en **< 1 s** incluyendo los checks de DynamoDB y Secrets Manager. Si alguno tarda más, marca degraded y retorna 503.

### NFR-U4-P5: Polling-friendly endpoints
`GET /v1/runs/{id}/status` debe responder en **< 100 ms** (lookup in-memory). Diseñado para soportar dashboards de N usuarios polleando cada 3 s — esperado throughput: 60 req/min por dashboard activo.

---

## Security

### NFR-U4-S1: SECURITY-01 — Sin secrets en código
TESTPILOT_API_KEY, AWS credentials → solo env vars. Validado por gitleaks en CI.

### NFR-U4-S2: SECURITY-02 — Secrets desde Secrets Manager
Credenciales de ambiente (`env_access`, `shopper`) resueltas en runtime, nunca persisted, nunca logueadas.

### NFR-U4-S3: SECURITY-03 — Input validation
Pydantic en TODO request body + query params. Sin endpoint que reciba `dict` o `Any`. Cualquier campo inválido → 422 con detalle de Pydantic.

### NFR-U4-S4: SECURITY-04 — Sin SQL injection
No hay SQL. DynamoDB queries usan parámetros estructurados (boto3 Table.query/scan con `KeyConditionExpression` parametrizada).

### NFR-U4-S5: SECURITY-05 — Auth en cada request
`X-API-Key` obligatorio en todos los `/v1/*`. Comparación con `hmac.compare_digest` (constant-time).

### NFR-U4-S6: SECURITY-06 — Authorization
**MVP:** sin RBAC. Cualquier portador de API key puede todo. Post-MVP: roles read/write/admin.

### NFR-U4-S7: SECURITY-07 — TLS
TLS termina en ALB de AWS (handled out-of-band). FastAPI escucha HTTP en port 8000 dentro del task — el ALB nunca expone HTTP al exterior.

### NFR-U4-S8: SECURITY-08 — Dependencias auditadas
Heredado de U0 (pip-audit en CI). U4 no agrega dependencias nuevas significativas (usa FastAPI, Pydantic, boto3 ya pinned).

### NFR-U4-S9: SECURITY-09 — Sin stack traces
Global exception handler garantiza no exposición. Tests verifican que 500 responses NO contienen líneas `File "..."` ni `Traceback`.

### NFR-U4-S10: SECURITY-10 — Logging sin secrets
`RedactingJsonFormatter` aplicado a todos los loggers. Tests verifican que un run con credenciales en Secrets Manager no las loggea.

### NFR-U4-S11: SECURITY-11 — Rate limiting
MVP: ninguno. Post-MVP: 100 req/min por API key.

### NFR-U4-S12: SECURITY-12/13 — Image hardening + non-root
Heredado de U0 Dockerfile.

### NFR-U4-S13: SECURITY-14 — Network policies
ECS task corre en subnet privada. Solo el ALB es público. Egress restringido a:
- Dominios SFCC de ambientes registrados (validados por allowlist)
- AWS services (DynamoDB, S3, Secrets Manager) vía VPC endpoint

### NFR-U4-S14: SECURITY-15 — Error handling seguro
Cubierto por NFR-U4-S9 + BR-U4-19, BR-U4-20.

---

## Reliability

### NFR-U4-R1: Manejo de fallos de Secrets Manager
Si Secrets Manager está caído o el path no existe → 502 `secret_not_found` con mensaje genérico. NO retry automático (Secrets Manager tiene SLA 99.9% — si está caído, esperar no ayuda).

### NFR-U4-R2: Manejo de fallos de DynamoDB
Si DynamoDB falla en read → 503. En write → reintento con backoff exponencial (max 3 intentos) — boto3 lo hace por default con configuración custom.

### NFR-U4-R3: Run timeout vs orchestrator
Watchdog `asyncio.wait_for(timeout=1800)`. Si vence, cancelar todos los browsers Playwright en curso y retornar 504 sin corromper estado.

### NFR-U4-R4: Live tracker no pierde runs en transit
Si una task ECS muere mientras un run está corriendo, el live_tracker pierde su estado (in-memory). MVP: aceptado — el cliente verá 504 timeout y puede reintentar.

### NFR-U4-R5: Idempotencia de POST /v1/run
**MVP:** sin idempotency keys. Doble-click en dashboard mitigado en frontend (NFR-MD0-R2).
**Post-MVP:** soportar `Idempotency-Key` header.

---

## Maintainability

### NFR-U4-M1: Tests de cada endpoint con FastAPI TestClient
Cobertura mínima: cada endpoint con:
- Caso éxito
- Caso 401 (sin API key)
- Caso 422 (input inválido)
- Caso 404/409/etc según endpoint
- Caso 500 (excepción inesperada → handler captura)

### NFR-U4-M2: Inyección de dependencias para testeo
Todos los services se inyectan vía `Depends(get_xxx)`. Tests pueden overridear cualquier dependency con mocks.

### NFR-U4-M3: Documentación OpenAPI auto-generada
FastAPI genera `/docs` (Swagger UI) y `/openapi.json`. **Disponibles solo en development** — desactivados en producción (env var `DOCS_ENABLED=false`).

---

## Observability

### NFR-U4-O1: Logging estructurado por request
Cada request loguea (JSON): `timestamp`, `level`, `method`, `path`, `status`, `duration_ms`, `api_key_hash`, `error_code` (si aplica), `run_id` (si aplica).

### NFR-U4-O2: Métricas CloudWatch
Métricas custom por endpoint: count, latency p95, error rate. Implementadas con `boto3 cloudwatch.put_metric_data` (batch cada 60 s para reducir cost).

### NFR-U4-O3: Tracing
**MVP:** sin tracing distribuido. Post-MVP: AWS X-Ray.

---

## Aplicabilidad Security Baseline a U4

| Regla | Aplica | Implementación |
|---|---|---|
| SECURITY-01 | ✅ | NFR-U4-S1 |
| SECURITY-02 | ✅ | NFR-U4-S2 |
| SECURITY-03 | ✅ | NFR-U4-S3 |
| SECURITY-04 | ✅ | NFR-U4-S4 |
| SECURITY-05 | ✅ | NFR-U4-S5, BR-U4-01, BR-U4-02 |
| SECURITY-06 | Parcial | MVP: sin RBAC (justificado) |
| SECURITY-07 | ✅ | TLS en ALB (NFR-U4-S7) |
| SECURITY-08 | ✅ | Heredado de U0 |
| SECURITY-09 | ✅ | NFR-U4-S9, BR-U4-19 |
| SECURITY-10 | ✅ | NFR-U4-S10, BR-U4-21 |
| SECURITY-11 | Parcial | MVP: sin rate limiting (justificado por uso interno) |
| SECURITY-12 | ✅ | Heredado de U0 Dockerfile |
| SECURITY-13 | ✅ | Heredado de U0 |
| SECURITY-14 | ✅ | NFR-U4-S13 |
| SECURITY-15 | ✅ | NFR-U4-S14, BR-U4-19 |

**Resumen U4:** 13/15 ✅ implementados, 2/15 (SECURITY-06, SECURITY-11) parciales con justificación documentada para MVP.

---

## Aplicabilidad PBT a U4

PBT aplica de forma limitada a U4 (es código de orquestación, no algorítmico):
- **PBT-08 (round-trip):** ✅ para cualquier `EnvironmentConfig` válido, `model_dump → model_validate` debe ser identidad (parcialmente cubierto en U0).
- Resto de PBT: N/A (U2 los cubre).
