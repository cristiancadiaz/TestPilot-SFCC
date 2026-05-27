# Logging Strategy — TestPilot SFCC

**Fecha**: 2026-05-22
**Propósito**: Estrategia única de logging para todo el sistema. Cubre librería, formato, niveles, correlación, redacción de secretos y destino.
**Origen**: consolida decisión D12 (H4.5 AC4) de `inception/user-stories/user-stories.md` + cierra gap A2 de `audits/2026-05-22/dependencies-and-design-gaps.md`.

---

## 1. Decisiones canónicas

| Aspecto | Decisión | Justificación |
|---|---|---|
| Librería | stdlib `logging` | Sin dependencia externa; ECS Fargate / CloudWatch lo consumen sin configuración adicional |
| Formato de salida | JSON line por evento | Estructurado, parseable por agentes y dashboards; compatible con CloudWatch Logs Insights |
| Formatter | `JSONFormatter` custom (sin dependencia de `python-json-logger`) | Control total sobre los campos; sin riesgo de cambios de versión upstream |
| Destino | `stdout` (StreamHandler) | ECS task definition lleva stdout a CloudWatch via `awslogs` driver — M14 simplificado |
| Nivel default | `INFO` | Override via env var `LOG_LEVEL` (ver `env-vars-catalog.md`) |
| Correlación | `request_id` (UUID4) por request HTTP | Inyectado por middleware, propagado vía `contextvars` a todos los logs del request |
| Redacción de secretos | Filtro `RedactionFilter` aplicado a todos los handlers | SECURITY-08 blocking — falla cerrada |

---

## 2. Estructura de un log line (JSON)

Ejemplo de un evento típico:

```json
{
  "ts": "2026-05-22T14:03:22.481Z",
  "level": "INFO",
  "logger": "testpilot.executor.runner",
  "message": "profile_completed",
  "request_id": "9f3c1c4e-2a5d-4f8b-9c3e-7b8a1f0d4c5e",
  "test_run_id": "a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "profile": "mobile-co",
  "flow_name": "checkout-full",
  "environment_id": "staging",
  "duration_ms": 4321,
  "status": "success"
}
```

### Campos obligatorios (en todos los logs)
| Campo | Tipo | Significado |
|---|---|---|
| `ts` | ISO 8601 UTC | Timestamp del evento |
| `level` | string | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `logger` | string | Nombre del logger (módulo Python, ej. `testpilot.executor.runner`) |
| `message` | string | Identificador del evento — **snake_case**, no oración libre |

### Campos contextuales (cuando aplican)
| Campo | Cuándo |
|---|---|
| `request_id` | En cualquier log dentro de un request HTTP |
| `run_id` | En cualquier log dentro de un `POST /v1/run` o relacionado a un run específico |
| `environment_id` | En logs que tocan resolución de credenciales, runs, baseline (★ NUEVO 2026-05-24) |
| `profile` | En logs del executor por perfil (catálogo con guion: `mobile-co`, `desktop-co`, `desktop-ec`) |
| `flow_name` | En logs del executor de un flow específico (catálogo con guion: `checkout-full`, `checkout-card-declined`) |
| `duration_ms` | Para eventos de "X completed" |
| `status` | Para eventos terminales (`success` / `failed` / `error`) |
| `error_code` | Para logs de nivel ERROR (ver `error-taxonomy.md`) |

### Anti-patrón
**NO** se hace `logger.info(f"User {user_email} did X")` — el mensaje libre se vuelve difícil de buscar y agrega cardinalidad. **SÍ** se hace `logger.info("user_action", extra={"action": "X", "user_email": user_email})` para que `message` sea estable.

---

## 3. Niveles por componente (guía)

| Componente | Nivel típico | Ejemplos de eventos |
|---|---|---|
| `testpilot.api` (U4) | INFO | `request_received`, `request_completed`, `auth_failed` |
| `testpilot.api` errores 5xx | ERROR | `internal_error`, `infrastructure_error_uncaught` |
| `testpilot.executor` (U1) | INFO | `profile_started`, `step_completed`, `profile_completed` |
| `testpilot.executor` fallos | WARNING | `step_failed`, `screenshot_captured` |
| `testpilot.executor` infra | ERROR | `infrastructure_error`, `browser_launch_failed` |
| `testpilot.baseline` (U2) | DEBUG | `p95_calculated`, `bootstrap_check` |
| `testpilot.reporter` (U3) | INFO | `report_generated`, `markdown_formatted` |
| `testpilot.reporter` invariantes | CRITICAL | `orders_created_violation` (defense-in-depth H3.3) |
| `testpilot.agents` (translator) | INFO | `translation_started`, `translation_completed` |
| `testpilot.agents` validation | WARNING | `translation_validation_failed` |

**Regla general**: WARNING o superior debe poder accionarse (alguien hace algo). DEBUG es opcional para troubleshooting profundo. INFO es la traza normal de operación.

---

## 4. Redacción de secretos (CRÍTICO — SECURITY-08)

### Política
**Falla cerrada**: la redacción se aplica antes de que el log llegue al handler. Si el filtro falla, el log se descarta (no se emite plain text como fallback).

### Patrón de implementación

```python
# src/api/logging_config.py — pseudocódigo
import logging
import re

REDACTION_PATTERNS = [
    re.compile(r"(?i)x-api-key"),
    re.compile(r"(?i)anthropic[_-]?api[_-]?key"),
    re.compile(r"(?i)testpilot[_-]?api[_-]?key"),
    re.compile(r"(?i)(password|token|card|key|secret)"),
    # ★ NUEVO 2026-05-24 — credenciales duales y paths de Secrets Manager
    re.compile(r"(?i)env_access"),         # env_access_credentials, env_access_secret_path
    re.compile(r"(?i)shopper.*password"),  # shopper.password (pero NO shopper.email — útil para debug)
]

REDACTED = "***REDACTED***"

class RedactionFilter(logging.Filter):
    def filter(self, record):
        # Recursivo sobre extra dict y args
        record.msg = self._redact(record.msg)
        if hasattr(record, "extra"):
            record.extra = self._redact_dict(record.extra)
        return True

    def _redact_dict(self, d):
        if not isinstance(d, dict):
            return d
        return {
            k: REDACTED if any(p.search(k) for p in REDACTION_PATTERNS) else self._redact(v)
            for k, v in d.items()
        }

    def _redact(self, value):
        if isinstance(value, dict):
            return self._redact_dict(value)
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        return value  # primitivos no se redactan por valor, solo por clave
```

### Qué se redacta
| Clave / patrón | Acción |
|---|---|
| Header `X-API-Key` | Valor → `***REDACTED***` |
| Env vars `ANTHROPIC_API_KEY`, `TESTPILOT_API_KEY` | Valor → `***REDACTED***` |
| Cualquier key cuyo nombre matchee `(?i)(password\|token\|card\|key\|secret)` | Valor → `***REDACTED***` |
| Numéricos / strings que parezcan PAN (`4000...`) | **NO se redactan automáticamente** — la redacción es por nombre de clave, no por valor |

**Por qué no redactar por valor de PAN**: complejo y propenso a falsos positivos. La política es: si vas a loguear datos de tarjeta (incluso falsos), pásalos en una clave cuyo nombre contenga `card`.

### Test obligatorio
Antes de mergear cualquier código que toque logging, debe pasar un test:
- Loguea un dict `{"x-api-key": "secret123", "user_email": "test@example.com"}`
- Captura el output
- Aserta que `secret123` NO aparece y `***REDACTED***` SÍ aparece
- Aserta que `user_email` value SÍ aparece (no se redacta)

Ubicación sugerida: `tests/test_logging_redaction.py`.

---

## 5. Correlación con `request_id`

### Cómo se inyecta
Middleware en `src/api/main.py` (pseudocódigo):

```python
from contextvars import ContextVar
import uuid

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response
```

### Cómo se propaga al log
El `JSONFormatter` lee `request_id_var.get()` y lo agrega al output. **No hay que pasarlo manualmente** en cada `logger.info(...)`. Esto evita olvidos.

### Relación con `run_id`
- `request_id` = un request HTTP individual (siempre existe)
- `run_id` = un run de TestPilot (UUID4 generado server-side para `POST /v1/run`)

Un `GET /v1/runs/{id}` tiene `request_id` y consulta un `run_id` existente. Un `POST /v1/run` tiene ambos (request_id del request + run_id generado). Un polling del dashboard a `GET /v1/runs/{id}/status` correlaciona ambos en logs.

---

## 6. Eventos que SE deben loguear (rúbrica MVP)

| Evento | Nivel | Logger | Por qué importa |
|---|---|---|---|
| Request recibido | INFO | `testpilot.api` | Audit trail de invocaciones |
| Auth fallida (401) | WARNING | `testpilot.api` | Detectar abuso / config errada |
| Translator invocado | INFO | `testpilot.agents` | Latencia del LLM |
| Translator validation failed (422) | WARNING | `testpilot.agents` | Calibración del prompt |
| Profile run start | INFO | `testpilot.executor` | Timeline del run |
| Step completed (cada uno) | DEBUG | `testpilot.executor` | Troubleshooting profundo |
| Step failed | WARNING | `testpilot.executor` | Bug en tienda o test |
| InfrastructureError | ERROR | `testpilot.executor` | R1 del CLAUDE.md |
| Profile run completed | INFO | `testpilot.executor` | Cierre del timeline |
| Baseline p95 calculated | DEBUG | `testpilot.baseline` | Visibilidad estadística |
| Bootstrap mode active | INFO | `testpilot.baseline` | Saber si estamos en bootstrap |
| Report generated | INFO | `testpilot.reporter` | Cierre del request |
| `orders_created != 0` (assertion fail) | CRITICAL | `testpilot.reporter` | INVARIANT VIOLATION (P1) |
| Unhandled exception (500) | ERROR | `testpilot.api` | Bugs en código de aplicación |
| Run timeout (504) | WARNING | `testpilot.api` | Investigación operativa |

---

## 7. Eventos que NO se deben loguear

- Valores brutos de headers de auth (incluso si "parecen redactados")
- Stack traces a nivel WARNING o INFO (solo a ERROR/CRITICAL, y solo server-side, **nunca** al cliente — H4.5 AC1)
- Contenido del body de la response (puede ser grande y contener PII)
- Datos de tarjeta (incluso `TEST_DECLINE_CARD`) — pasar como `{"card_last4": "0002"}` si se necesita
- **Passwords** de `EnvironmentAccessCredentials` o `ShopperCredentials` (★ NUEVO — garantizado por `repr=False` y `__str__` redactado en modelos Pydantic de U0; defense-in-depth via filtro `(?i)env_access` y `(?i)shopper.*password`)
- **Username de env_access** — aunque no es tan sensible como un password, política de redacción uniforme
- Email completo del shopper — `@testpilot.internal` es OK, pero usar redacción local-part (`q***@testpilot.internal`) para logs frecuentes
- **Paths completos de Secrets Manager** en `details` de errores — exponer `environment_id` solamente (defensa en profundidad)

---

## 8. Configuración en código (referencia)

```python
# src/api/main.py — configuración esquemática (pseudocódigo)
import logging
import os
from contextlib import asynccontextmanager

def configure_logging():
    handler = logging.StreamHandler()  # stdout
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    root.handlers.clear()
    root.addHandler(handler)

    # Silenciar loggers ruidosos de librerías
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("playwright").setLevel("WARNING")

@asynccontextmanager
async def lifespan(app):
    configure_logging()
    yield
```

---

## 9. Out of scope MVP (documentado para futuro)

| Capacidad | Estado | Cuándo agregar |
|---|---|---|
| Sampling de logs DEBUG | Out of scope | Cuando los costos de CloudWatch sean medibles |
| OpenTelemetry / tracing | Out of scope | Cuando se agregue un segundo servicio (multi-process) |
| Métricas (Prometheus / CloudWatch metrics) | Out of scope | Cuando el equipo defina SLOs explícitos |
| Log shipping a Datadog / Elastic | Out of scope | Solo si CloudWatch resulta insuficiente |
| Redacción por valor (regex sobre el contenido) | Out of scope | Si se detecta filtración de PII en post-mortem |

---

## 10. Validación al cerrar U4

Antes de marcar U4 como completo, verificar:
- `tests/test_logging_redaction.py` pasa (redacción funcional)
- `tests/test_api.py` incluye al menos un test que verifica que un log de error 500 NO contiene stack trace en el body de la response
- Búsqueda manual en logs de una request real: ningún valor de `X-API-Key` ni `ANTHROPIC_API_KEY` aparece en plain text
- Los `request_id` y `test_run_id` aparecen correlacionados en logs del mismo run
