# Business Rules — U4 API Endpoints (actualizado 2026-05-24)

## Reglas de autenticación

### BR-U4-01: Auth obligatoria en todos los endpoints `/v1/`
Cualquier request a `/v1/*` debe incluir `X-API-Key`. Sin la header → 401 `unauthorized`. Excepción: `/health` no requiere auth.

### BR-U4-02: API key vía env var, comparación constant-time
```python
expected = os.environ.get("TESTPILOT_API_KEY", "")
if not expected or not hmac.compare_digest(x_api_key, expected):
    raise HTTPException(401, ...)
```
Comparación constant-time previene timing attacks (SECURITY-05).

### BR-U4-03: Rate limiting por API key (SECURITY-11)
**MVP:** sin rate limiting (uso interno controlado).
**Post-MVP:** 100 req/min por API key, 429 si excede.

---

## Reglas de Environment Registry

### BR-U4-04: environment_id immutable
`PUT /v1/environments/{id}` debe rechazar (400) cualquier intento de cambiar `environment_id`. Solo se actualizan: `display_name`, `store_url`, `*_secret_path`, `anti_bot_whitelisted`, `active`.

### BR-U4-05: Soft delete obligatorio
`DELETE /v1/environments/{id}` ejecuta `update(active=false)` — NO borra el registro. Razón: runs históricos referencian `environment_id` y deben poder mostrarlo en el dashboard P5.

### BR-U4-06: HTTPS obligatorio en store_url
Validado por Pydantic en U0. Si el cliente envía http://, Pydantic rechaza con 422.

### BR-U4-07: Paths de Secrets validados al CREAR ambiente
Al `POST /v1/environments`, antes de devolver 201, el backend debe verificar que **ambos** paths (`env_access_secret_path`, `shopper_secret_path`) existen en Secrets Manager y tienen el JSON correcto:
- `env_access`: `{"username": str, "password": str}`
- `shopper`: `{"email": str (terminando en @testpilot.internal), "password": str}`

Si falla: 422 `invalid_secret_path` con detalle del path problemático (sin exponer el contenido).

**Razón:** detectar errores de configuración en tiempo de creación, no en tiempo de run.

---

## Reglas de POST /v1/run

### BR-U4-08: Resolver ambiente PRIMERO
El primer paso de `POST /v1/run` es `resolver.resolve(environment_id)`. Si falla, retornar inmediatamente sin gastar recursos:
- Ambiente no existe → 404 `environment_not_found`
- Ambiente desactivado → 409 `environment_inactive`
- Secret no resuelve → 502 `secret_not_found`

### BR-U4-09: Cap de concurrencia
Máximo `MAX_CONCURRENT_PROFILES=3` perfiles en paralelo (env var). Implementado con `asyncio.Semaphore`. Si `config.profiles` tiene 3 y `config.flows` tiene 2 → 6 tasks total, pero solo 3 corren en paralelo.

### BR-U4-10: Watchdog 30 min
`asyncio.wait_for(orchestrator.run(...), timeout=1800)`. Si excede: 504 `run_timeout`, run marcado como failed.

### BR-U4-11: orders_created=0 invariante reverificado
`POST /v1/run` debe assertir `report.orders_created == 0` antes de retornar 200. Si fuera != 0, retornar 500 `invariant_violated` y disparar alerta CloudWatch.

### BR-U4-12: run_id generado por servidor
`run_id` siempre lo genera el backend (uuid4). El cliente NO puede sugerir uno. Razón: garantiza unicidad y previene side-channel attacks.

---

## Reglas de GET endpoints

### BR-U4-13: 404 para run_id inexistente, no 400
`GET /v1/runs/{id}` con UUID válido pero inexistente → 404 `run_not_found`. UUID malformado → 422 (Pydantic).

### BR-U4-14: TTL del último run
`GET /v1/runs/latest` retorna `age_seconds` y `ttl_ok = age_seconds < TTL_SECONDS` (default 14400 — 4 horas). Permite a agentes CI/CD decidir si el último report aún es válido para gate-decision.

### BR-U4-15: Historial paginado, no scroll infinito
`GET /v1/runs` siempre retorna paginado. `page_size` máximo 100. Sin endpoint "dame todos" — protege contra escaneos accidentales.

### BR-U4-16: Filtros por defecto = últimos 7 días
Si `from_date` y `to_date` no se envían, default = últimos 7 días. Razón: protege contra queries accidentales de TODO el historial (que podría ser caro en DynamoDB scan).

---

## Reglas de live status

### BR-U4-17: LiveStatusTracker es ring buffer de 100
Máximo 100 runs vivos en memoria. Cuando se llena, se descartan los más viejos. Razón: simplicidad MVP; si un run lleva >100 ejecuciones desde que terminó, ya está en baseline_store.

### BR-U4-18: Redirect de status a detail
`GET /v1/runs/{id}/status` con run que ya terminó y salió del ring → 302 redirect a `/v1/runs/{id}`. Permite al dashboard hacer una sola integración: cuando recibe redirect, navega a P4.

---

## Reglas de errores

### BR-U4-19: Sin stack traces en responses (SECURITY-09)
Global exception handler captura cualquier excepción no manejada y retorna 500 con cuerpo:
```json
{"error_code": "internal_error", "message": "Internal server error"}
```
Stack trace solo se loggea, nunca se envía al cliente.

### BR-U4-20: Errores estructurados
Todas las responses de error tienen formato:
```json
{
  "error_code": "snake_case_machine_readable",
  "message": "Human-readable description",
  "details": { ... opcional ... }
}
```

### BR-U4-21: Logging estructurado de todos los requests
Cada request loguea: timestamp, method, path, status, duration_ms, api_key_hash (no la key cruda), error_code (si aplica). NO loguea body de request (puede tener `environment_id` que es benigno, pero política uniforme).

---

## Reglas de servir estáticos del dashboard

### BR-U4-22: Estáticos sirven solo si dist/ existe
Si `src/dashboard/dist/index.html` no existe (ej. tests sin build), el mount se omite. La API sigue funcional, solo no se sirve dashboard. Evita 500 en tests.

### BR-U4-23: Security headers en HTML responses
HTML responses (index.html, SPA routes) incluyen:
- `Content-Security-Policy` (configurado en middleware — ver MD0 infrastructure-design.md)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`

---

## Reglas de CORS

### BR-U4-24: Sin CORS en MVP
Dashboard y API se sirven desde el mismo origen → no requiere CORS headers. Si en el futuro el dashboard se mueve a S3+CloudFront separado, se agregará CORS allowlist (no `*`).

---

## Reglas de healthcheck

### BR-U4-25: /health verifica dependencias críticas
Retorna 200 solo si:
- DynamoDB responde a `describe_table("environments")` < 500 ms
- Secrets Manager responde a `list_secrets(MaxResults=1)` < 500 ms

Si alguna falla: 503 con detalle de qué falló (no expone configuración).

---

## Trazabilidad

| BR | Historia / Regla |
|---|---|
| BR-U4-01, BR-U4-02 | H4.4 (auth API key) — SECURITY-05 |
| BR-U4-04, BR-U4-05 | H5.1 (gestión ambientes) |
| BR-U4-07 | Detección temprana de config errors |
| BR-U4-08 | H4.1 (invocación de run) |
| BR-U4-09 | NFR-U1-P4 (concurrencia) |
| BR-U4-10 | Robustez ante runs colgados |
| BR-U4-11 | H3.3 (auditabilidad orders=0) — P1 |
| BR-U4-13 | H4.3 (consulta por run_id) |
| BR-U4-14 | H4.2 (último run + TTL) |
| BR-U4-15, BR-U4-16 | H5.4 (historial paginado) |
| BR-U4-17, BR-U4-18 | H5.3 (vista en tiempo real) |
| BR-U4-19, BR-U4-20 | H4.5 (sin stack traces) — SECURITY-09, SECURITY-15 |
| BR-U4-21 | SECURITY-10 (logging estructurado) |
| BR-U4-23 | MD0 NFR-MD0-S6 (CSP) |
| BR-U4-25 | Observability para ECS |
