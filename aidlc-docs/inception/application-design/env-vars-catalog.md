# Environment Variables Catalog — TestPilot SFCC (actualizado 2026-05-24)

**Propósito**: Fuente única de verdad para todas las variables de entorno del sistema. Cualquier variable nueva debe agregarse aquí antes de usarse en código.

**Cambio mayor 2026-05-24:** se agregan 6 env vars nuevas para los servicios de U4 (DynamoDB, S3, Secrets Manager, dashboard, docs). `RUN_TIMEOUT_S` renombrado a `RUN_TIMEOUT_SECONDS` con valor actualizado de 480 → **1800** (30 min) por el flow con dos autenticaciones + 10 pasos × 3 perfiles. Catálogo de naming actualizado a guion en strings canónicos.

---

## Tabla maestra

| Variable | Tipo | Default | Requerida en startup | Validada en | Consumida por | Decisión / Razón |
|---|---|---|---|---|---|---|
| `TESTPILOT_API_KEY` | string | — | **SÍ siempre** (falla loud) | `src/api/main.py` (lifespan) | `verify_api_key` (C4-A) | D11 (H4.4 AC3) |
| `ANTHROPIC_API_KEY` | string | — | Solo si translator se usa (opcional post-D8) | `src/agents/translator.py` (lazy) | C0-C TranslatorAgent | Heredado NFR-01 |
| `ENV` | enum `development`\|`production` | `development` | No | `src/api/main.py` (lifespan) | Lógica condicional | D5 (H1.5 AC3) |
| `AWS_REGION` | string | `us-east-1` | No | `src/api/services/*` | boto3 clients | Multi-env design |
| **`DYNAMODB_TABLE_ENVIRONMENTS`** ★ | string | — | **SÍ en producción** | `src/api/services/environment_registry.py` | EnvironmentRegistry | Multi-env design |
| **`DYNAMODB_TABLE_RUNS`** ★ | string | — | **SÍ en sprint 3+** (cuando se migre de InMemoryBaselineStore) | `src/api/services/baseline_dynamodb.py` | DynamoDBBaselineStore | Persistencia post-MVP |
| **`S3_BUCKET_SCREENSHOTS`** ★ | string | — | **SÍ en producción** | `src/api/services/screenshots.py` + `src/executor/runner.py` | Upload + proxy | Almacenamiento screenshots |
| **`SECRETS_MANAGER_PREFIX`** ★ | string | `testpilot/` | No | `src/api/services/secrets_manager.py` | SecretsManagerClient | Defensa en profundidad: bloquea acceso a secrets fuera del prefijo |
| **`MAX_CONCURRENT_PROFILES`** | int | `3` | No | `src/api/services/run_orchestrator.py` | RunOrchestrator (`asyncio.Semaphore`) | D1 (H1.1 AC3) |
| **`RUN_TIMEOUT_SECONDS`** | int (segundos) | `1800` (30 min) | No | `src/api/services/run_orchestrator.py` | `asyncio.wait_for` watchdog | D10 actualizada (H4.1 AC5) — antes era `RUN_TIMEOUT_S=480` |
| `LOG_LEVEL` | enum `DEBUG`\|`INFO`\|`WARNING`\|`ERROR` | `INFO` | No | `src/api/main.py` (lifespan) | Transversal | D12 (`logging-strategy.md`) |
| **`SCREENSHOT_DIR`** | path | `./screenshots` si `ENV=development`; — si `ENV=production` | **SÍ si `ENV=production`** y `S3_BUCKET_SCREENSHOTS` no usado | `src/executor/runner.py` | Fallback local en dev | D5 (H1.5 AC3) — en prod se prefiere S3 |
| `TEST_DECLINE_CARD` | string (PAN test) | `4000000000000002` | No | `src/executor/selectors.py` (constante) | C1-C, C1-D Flows | D2 (H1.2 AC2) |
| **`DOCS_ENABLED`** ★ | bool | `false` | No | `src/api/main.py` | Toggle de `/docs` (Swagger) | NFR-U4-M3 — desactivado en prod por info disclosure |
| **`GIT_SHA`** ★ | string | — | No (informativo) | `src/api/main.py` | `HealthResponse.git_sha` | Inyectado por CI para correlación bug↔versión |

---

## Reglas de carga y validación

### Patrón canónico
Toda env var se lee **una vez en startup** dentro del `lifespan` de FastAPI (no en cada request). Excepciones documentadas: `ANTHROPIC_API_KEY` (lazy, primer call al translator) y `TEST_DECLINE_CARD` (lazy, dentro del flow).

```python
# src/api/main.py — patrón ejemplo (pseudocódigo)
from contextlib import asynccontextmanager
import os
import sys

@asynccontextmanager
async def lifespan(app):
    # Variables requeridas siempre
    if not os.environ.get("TESTPILOT_API_KEY"):
        sys.exit("FATAL: TESTPILOT_API_KEY not set")
    
    env = os.environ.get("ENV", "development")
    
    # Variables requeridas en producción
    if env == "production":
        for var in ["DYNAMODB_TABLE_ENVIRONMENTS", "S3_BUCKET_SCREENSHOTS"]:
            if not os.environ.get(var):
                sys.exit(f"FATAL: {var} required when ENV=production")
    
    # Variables con default
    app.state.max_concurrent = int(os.environ.get("MAX_CONCURRENT_PROFILES", "3"))
    app.state.run_timeout = int(os.environ.get("RUN_TIMEOUT_SECONDS", "1800"))
    app.state.docs_enabled = os.environ.get("DOCS_ENABLED", "false").lower() == "true"
    
    yield
```

### Falla loud, no silenciosa
Si una variable requerida no está seteada, la app debe **no aceptar requests** y salir con un mensaje claro a stderr. No usar defaults silenciosos para variables de seguridad o de infraestructura crítica.

### Variables NO env vars (constantes en código)
Estas se manejan como constantes en `src/models.py` o módulos correspondientes, NO como env vars:

| Constante | Valor | Ubicación |
|---|---|---|
| `CLAUDE_MODEL` | `"claude-haiku-4-5-20251001"` | `src/agents/translator.py` |
| `BOOTSTRAP_MIN_RUNS` | `14` | `src/baseline/baseline_manager.py` |
| `BASELINE_WINDOW` | `10` | `src/baseline/baseline_manager.py` |
| `YELLOW_THRESHOLD` | `1.2` | `src/baseline/baseline_manager.py` |
| `RED_THRESHOLD` | `1.5` | `src/baseline/baseline_manager.py` |
| `FLOWS` | `("checkout-full", "checkout-card-declined")` | `src/models.py` (Literal) |
| `PROFILES` | `("mobile-co", "desktop-co", "desktop-ec")` | `src/models.py` (Literal) |
| `ENVIRONMENTS` | `("sandbox", "development", "staging")` | `src/models.py` (Literal) |
| `DECLINE_MESSAGE_PATTERN` | `r"tarjeta.*(rechaz\|declin)"` (regex, case-insensitive) | `src/executor/selectors.py` |
| `RUN_LIVE_MAX` | `100` | `src/api/services/live_status_tracker.py` |
| `ENV_REGISTRY_CACHE_TTL` | `60` (segundos) | `src/api/services/environment_registry.py` |
| `ENV_RESOLVER_CACHE_TTL` | `300` (segundos = 5 min) | `src/api/services/environment_resolver.py` |

**Por qué no son env vars**: cambiar estos valores cambia el contrato del producto (qué cuenta como bootstrap, qué flows existen, qué se cachea cuánto). No son ajustes operativos por deployment — requieren PR con justificación.

### Convención de naming (★ actualizada 2026-05-24)

**Strings canónicos (Literal, JSON, URLs, logs, screenshots paths):** usar **guion**.
- `"checkout-full"`, `"checkout-card-declined"`
- `"mobile-co"`, `"desktop-co"`, `"desktop-ec"`
- `"sandbox"`, `"development"`, `"staging"`

**Archivos Python:** usar **underscore** (restricción del lenguaje — no permite guion en módulos).
- `checkout_full.py`, `checkout_card_declined.py`
- `mobile_co.py`, `desktop_co.py`, `desktop_ec.py`

**Constantes Python:** usar **SCREAMING_SNAKE_CASE** con underscore (PEP 8).
- `MOBILE_CO`, `DESKTOP_CO`, `DESKTOP_EC`
- `BOOTSTRAP_MIN_RUNS`, `MAX_CONCURRENT_PROFILES`

**Funciones / variables Python:** usar **snake_case** con underscore (PEP 8).
- `is_bootstrap_mode`, `calculate_p95`, `run_profile`

**Env vars:** usar **SCREAMING_SNAKE_CASE** con underscore (estándar Unix).
- `TESTPILOT_API_KEY`, `DYNAMODB_TABLE_ENVIRONMENTS`, `RUN_TIMEOUT_SECONDS`

**Regla mnemotécnica:** el guion es para el "mundo exterior" (JSON, URLs, valores que el dashboard y agentes CI/CD consumen). El underscore es para el "mundo interior" Python.

---

## Variables NO incluidas y por qué

| Variable propuesta | Decisión | Razón |
|---|---|---|
| `STOREFRONT_URL` | NO env var | Resuelta desde Environment Registry vía `environment_id`. No va en el payload ni como env var — es parte del registro de ambientes en DynamoDB. |
| `SHOPPER_EMAIL` | NO env var | Va en Secrets Manager como parte de `shopper_credentials` del ambiente. Nunca en env vars. |
| `ENV_ACCESS_USERNAME/PASSWORD` | NO env var | Idem — Secrets Manager. |
| `CLOUDWATCH_LOG_GROUP` | NO necesaria | Logging va a stdout (M14 simplificado). CloudWatch agent del task definition se encarga de la ingesta vía `awslogs` driver. |
| `IDEMPOTENCY_KEY_TTL` | NO en MVP | Idempotencia aplazada a SHOULD HAVE (D9). |
| `SLACK_WEBHOOK_URL` | NO en MVP | Slack aplazado a SHOULD HAVE (M15). |
| `CORS_ALLOWED_ORIGINS` | NO en MVP | Dashboard y API en mismo origen (FastAPI sirve estáticos). Sin CORS. |

---

## Test de cobertura

Cada variable debe tener al menos un test que verifique:
- (Para variables requeridas) la app falla en startup si la variable no está seteada
- (Para variables con default) el default se aplica correctamente si no está seteada
- (Para variables tipadas como int/enum) parseo correcto y rechazo de valores inválidos
- (Para `SECRETS_MANAGER_PREFIX`) el SecretsManagerClient rechaza paths fuera del prefijo

Ubicación sugerida: `tests/test_env_vars.py` (a crear en U4).

---

## Cómo agregar una nueva variable

1. Agregar fila a la **Tabla maestra** con todos los campos completos.
2. Documentar en qué decisión / historia / RNF se justifica.
3. Implementar la carga siguiendo el patrón canónico.
4. Agregar test de cobertura.
5. Si rompe el contrato del producto, considerar si debería ser constante en lugar de env var.
6. Actualizar el Dockerfile/task definition si requiere inyección desde Secrets Manager.
