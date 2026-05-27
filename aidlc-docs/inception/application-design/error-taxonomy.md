# Error Taxonomy — TestPilot SFCC (actualizado 2026-05-24)

**Propósito**: Fuente única de verdad para todos los errores del sistema. Define cuándo cada error se lanza, qué `status` produce en los modelos, qué HTTP code retorna el API, y qué `TrafficLight` resulta.

**Cambio mayor 2026-05-24:** se agregan 5 nuevos error codes para Environment Registry, EnvironmentResolver y validación de Secrets Manager. Bloque de captura `try/except` actualizado para usar `ResolvedEnvironment` en lugar de `storefront_url`.

---

## 1. Status enums (semántica de cada nivel)

### `StepResult.status` — un paso individual de Playwright
| Valor | Significado | Cuándo se asigna |
|---|---|---|
| `success` | El paso completó sin error | Selector encontrado, acción ejecutada, validación OK |
| `failed` | El paso falló por razón del app (no infra) | Selector no apareció en timeout, texto esperado no match, validación de UI falló |
| `skipped` | El paso no se ejecutó porque un paso anterior falló | El runner marca todos los pasos posteriores a un `failed` como `skipped` |

### `FlowResult.status` — un flow completo en un perfil
| Valor | Significado | Regla de cálculo |
|---|---|---|
| `success` | Todos los pasos del flow fueron `success` | `all(s.status == "success" for s in steps)` |
| `failed` | Al menos un paso del flow fue `failed` (sin `InfrastructureError`) | `any(s.status == "failed")` y NO se lanzó `InfrastructureError` |
| `error` | Se lanzó `InfrastructureError` en algún paso de navegación o autenticación | `InfrastructureError` capturado por `runner.py` |

### `RunRecord.status` — el run completo (todos los perfiles agregados)
| Valor | Significado | Regla de cálculo |
|---|---|---|
| `success` | Todos los `FlowResult` de los perfiles fueron `success` | `all(p.flow_result.status == "success" for p in profile_results)` |
| `failed` | Al menos un `FlowResult` fue `failed` | `any(p.flow_result.status == "failed")` y ningún `error` |
| `error` | Al menos un `FlowResult` fue `error` (infra) | `any(p.flow_result.status == "error")` — gana sobre `failed` |

**Regla de precedencia**: `error` > `failed` > `success`.

---

## 2. Tabla maestra de errores

| Error code (string) | Excepción Python | HTTP code | StepResult.status | FlowResult.status | RunRecord.status | TrafficLight | Screenshot | Cuándo se produce |
|---|---|---|---|---|---|---|---|---|
| (sin error) | — | 200 | `success` | `success` | `success` | computado por baseline | según `screenshot_on_success` | Path feliz completo |
| `decline_message_not_found` | — | 200 | `failed` | `failed` | `failed` (o peor) | **RED** o computado | SÍ (step failed) | H1.3 AC3 — regex no aparece en 5s |
| (selector timeout en step de app) | `playwright.TimeoutError` capturado | 200 | `failed` | `failed` | `failed` (o peor) | **RED** o computado | SÍ (step failed) | `wait_for_selector` excede timeout — app está roto |
| `infrastructure_error` | `InfrastructureError` (custom) | 200 (en respuesta del run) / 503 (si escapa al middleware) | `failed` (el step donde se lanza) | `error` | `error` (precedencia sobre `failed`) | **YELLOW** | SÍ (step failed) | H1.4 AC1 — `playwright.TimeoutError` en `page.goto`, `wait_for_load_state`, `page.reload`; HTTP 401 en `env_access_auth`; browser crash |
| `run_timeout` | `asyncio.TimeoutError` capturado en endpoint | 504 | — | — | — | — | — | H4.1 AC5 — duración total del run > `RUN_TIMEOUT_SECONDS` (default 1800s = 30 min) |
| `validation_failed` | `pydantic.ValidationError` en POST /v1/run | 422 | — | — | — | — | — | Payload no valida contra `SyntheticUserConfig` (D8 actualizada — el translator NL ya no es entrada principal) |
| `unauthorized` | — | 401 | — | — | — | — | — | H4.4 AC4 — header `X-API-Key` ausente o incorrecto |
| `run_not_found` | — | 404 | — | — | — | — | — | H4.3 AC3 — `GET /v1/runs/{id}` con UUID no existente |
| `no_runs_yet` | — | 404 | — | — | — | — | — | H4.2 AC3 — `GET /v1/runs/latest` cuando store está vacío |
| **`environment_not_found`** ★ | `EnvironmentNotFoundError` | 404 | — | — | — | — | — | **`POST /v1/run` o `PUT /v1/environments` con `environment_id` no registrado** |
| **`environment_inactive`** ★ | `EnvironmentInactiveError` | 409 | — | — | — | — | — | **`POST /v1/run` contra ambiente con `active=false`** |
| **`secret_not_found`** ★ | `SecretNotFoundError` | 502 | — | — | — | — | — | **EnvironmentResolver no puede recuperar `env_access` o `shopper` desde Secrets Manager** |
| **`invalid_secret_path`** ★ | `InvalidSecretPathError` | 422 | — | — | — | — | — | **`POST /v1/environments`: el path apunta a un secret que existe pero su JSON no cumple shape esperado (validación Pydantic falla)** |
| **`invariant_violated`** ★ | `InvariantViolatedError` | 500 | — | — | — | — | — | **`orders_created != 0` detectado — INCIDENTE CRÍTICO (alerta CloudWatch + log CRITICAL)** |
| `internal_error` | cualquier `Exception` no esperada | 500 | — | — | — | — | — | H4.5 AC1 — caught en middleware global |

**Notas**:
- "computado por baseline" → `compute_traffic_light(current_ms, p95_ms, bootstrap)` (ver H2.1)
- TrafficLight para `RunRecord.status="error"` siempre es **YELLOW** (H1.4 AC3) — nunca RED.
- TrafficLight para `RunRecord.status="failed"` (app-error) es **RED** salvo que el baseline lo modere (caso raro).

---

## 3. Mapeo body de respuesta de error (HTTP ≥400)

Todos los errores HTTP retornan el mismo formato:

```json
{
  "error_code": "<código de la tabla>",
  "message": "<descripción legible para humanos>",
  "request_id": "<UUID4 generado por middleware>",
  "details": { "<opcional, descriptivo, sin info sensible>" }
}
```

**Reglas**:
- `error_code` es siempre uno de los códigos definidos en la tabla maestra.
- `request_id` se correlaciona con los logs estructurados (ver `logging-strategy.md`).
- `details` es legible pero **NUNCA** incluye: stack traces, paths de archivos del servidor, valores de env vars, contenido de headers de auth, datos de tarjeta, paths de Secrets Manager (defensa en profundidad — solo `environment_id` aceptable).

---

## 4. La excepción `InfrastructureError`

Definición canónica (en `src/executor/_core.py`):

```python
class InfrastructureError(Exception):
    """
    Lanzada cuando un paso falla por timeout de red, DNS, TLS, autenticación de
    ambiente (env_access) rechazada, o crash del browser.

    NO se lanza por timeout esperando un selector (wait_for_selector) ni por
    rechazo del shopper_login form (esos son app-error).

    Distinción clave (D4 / H1.4 AC1):
      - InfrastructureError → el problema NO es de la tienda SFCC
      - StepResult failed   → el problema SÍ es de la tienda SFCC
    """
```

**Captura en `runner.py`** (actualizado 2026-05-24 — usa `ResolvedEnvironment`):

```python
try:
    # env_access_auth step
    env_step = await _execute_step(
        page, "env_access_auth",
        lambda: page.goto(str(env.config.store_url)),
        config, run_id, profile.name, flow_name,
    )
    if env_step.status == "failed":
        raise InfrastructureError(f"env_access rejected: {env_step.error}")
    
    # shopper_login step (form interactivo — puede ser app-error)
    login_step = await shopper_login(page, env.shopper, config, run_id, profile.name, flow_name)
    
    # Flow funcional
    flow_result = await flow_fn(page, config, env, run_id, profile.name)
    flow_result.steps = [env_step, login_step] + flow_result.steps
    
    return ProfileResult(profile=profile, flow_result=flow_result, traffic_light=...)

except InfrastructureError as e:
    return ProfileResult(
        profile=profile,
        flow_result=FlowResult(
            flow_name=flow_name, status="error",
            steps=[], duration_ms=0, orders_created=0,
        ),
        traffic_light=TrafficLight.YELLOW,
    )
```

**Captura en middleware global del API**:

Si por alguna razón `InfrastructureError` no se capturó en `runner.py` y escapa al endpoint, el middleware retorna 503 con `error_code: "infrastructure_error"` (H4.5 AC2). Defense-in-depth.

---

## 5. Jerarquía de excepciones de la API

```python
class TestPilotApiError(Exception):
    """Base para todas las excepciones HTTP-mapeable."""
    status_code: int = 500
    error_code: str = "internal_error"

class EnvironmentNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "environment_not_found"

class EnvironmentInactiveError(TestPilotApiError):
    status_code = 409
    error_code = "environment_inactive"

class SecretNotFoundError(TestPilotApiError):
    status_code = 502
    error_code = "secret_not_found"

class InvalidSecretPathError(TestPilotApiError):
    status_code = 422
    error_code = "invalid_secret_path"

class RunNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "run_not_found"

class RunTimeoutError(TestPilotApiError):
    status_code = 504
    error_code = "run_timeout"

class InvariantViolatedError(TestPilotApiError):
    """orders_created != 0 — incidente crítico. Alerta inmediata."""
    status_code = 500
    error_code = "invariant_violated"
```

Single exception handler registrado vía `app.add_exception_handler(TestPilotApiError, ...)` retorna 4xx/5xx con body estructurado de §3.

---

## 6. Decisiones implícitas explicitadas

### 6.1. Múltiples errores en un mismo run
Si el perfil `mobile-co` falla con app-error y `desktop-co` falla con infra-error, el run completo es `error` (precedencia). El reporte Markdown debe identificar qué perfil tuvo cada tipo.

### 6.2. Step que falla validación de monto/precio
Si en el futuro se agrega un step que valida montos del carrito (Journey 4 del PRD aplazado), se marca como `failed` con `error="amount_mismatch"`. MVP no implementa esto.

### 6.3. Translator timeout (Claude API down)
Si la llamada al translator (funcionalidad opcional post-D8) excede su propio timeout interno, se propaga como `internal_error` (500). **NO** como `validation_failed` (422). Razón: 422 implica "tu input es malo", pero un timeout del LLM es un fallo del servidor.

### 6.4. Pydantic ValidationError en el body de POST
Si el cliente envía body inválido (ej. `environment_id="produccion"` no en el catálogo), FastAPI/Pydantic retornan 422 con formato propio de Pydantic. Estos se mapean al `error_code: "validation_failed"` para uniformidad con el resto del API.

### 6.5. UUID inválido en path
`GET /v1/runs/abc` (no es UUID) retorna 422 (Pydantic), NO 404.

### 6.6. Run con todos los perfiles infra-error
Si los 3 perfiles fallan con `InfrastructureError` (ej. internet caído), `RunRecord.status = "error"` y `TrafficLight = YELLOW`. Sigue siendo infra — no se promueve a RED.

### 6.7. `env_access` rechazado vs `shopper_login` rechazado
- `env_access` rechazado (HTTP 401 en `page.goto`): **InfrastructureError** → YELLOW. Causa típica: credenciales mal configuradas en Secrets Manager.
- `shopper_login` rechazado (form submit falla, MY_ACCOUNT no aparece): **StepResult failed** → flow_result `failed` → RED. Causa típica: cambio del flujo de login en SFCC o credenciales del shopper desactualizadas en Secrets Manager.

**Por qué la distinción:** un problema de `env_access` no debe disparar alertas de regresión de UX. Un problema de `shopper_login` puede ser tanto credenciales (infra) como cambio funcional (regresión) — en MVP los tratamos como funcionales para no enmascarar regresiones reales.

### 6.8. Invariante `orders_created != 0` (CRÍTICO)
Si en cualquier punto se detecta `orders_created > 0`:
1. `InvariantViolatedError` → 500
2. Log CRITICAL con `run_id`, `environment_id`, `profile`, `flow`
3. Métrica CloudWatch `testpilot.invariant_violated` += 1 → alerta inmediata PagerDuty/Slack
4. El reporte aún se intenta generar para auditoría, pero con flag bloqueante visible

Esta es la única regla de oro del sistema: viola P1 (cero contaminación).

---

## 7. Test de cobertura

Cada error en la tabla debe tener al menos un test que lo provoque y verifique:
- (Para errores HTTP) que retorna el código correcto y el `error_code` en el body
- (Para errores de step/flow/run) que el `status` se propaga correctamente
- (Para `InfrastructureError`) que `TrafficLight = YELLOW`
- (Para 5xx) que el body NO incluye stack traces ni paths
- (Para `invariant_violated`) que dispara métrica CloudWatch + log CRITICAL

Ubicación sugerida: `tests/test_error_taxonomy.py` (a crear en U4).

---

## 8. Cómo agregar un error nuevo

1. Agregar fila a la **Tabla maestra** con todos los campos completos.
2. Definir excepción Python heredando de `TestPilotApiError` si aplica.
3. Definir el `error_code` (snake_case, descriptivo, sin info sensible).
4. Mapear el HTTP code apropiado.
5. Decidir el `TrafficLight` resultante si es un error de ejecución (no API-level).
6. Agregar test de cobertura.
