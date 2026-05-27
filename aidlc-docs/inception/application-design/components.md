# Components — TestPilot SFCC

## Componentes del sistema (todos los módulos de MD0, U0 a U4)

---

## MD0 — Dashboard Web Interno

### C-D0: DashboardApp
- **Módulo**: `src/dashboard/` (React o HTML/JS estático)
- **Propósito**: Interfaz web interna para operar el sistema TestPilot sin CLI
- **Responsabilidades**:
  - **Pantalla de ambientes**: Registrar y gestionar los 3 ambientes (sandbox/development/staging) con `store_url`, `env_access_secret_path`, `shopper_secret_path`, `anti_bot_whitelisted`
  - **Pantalla de runs**: Campo JSON para `SyntheticUserConfig` (sin credenciales), botón de lanzamiento vía `POST /v1/run`
  - **Vista en tiempo real**: Mostrar agentes activos por perfil (mobile-CO, desktop-CO, desktop-EC) con estado en progreso / completado / fallido
  - **Historial**: Lista de ejecuciones anteriores con filtros por fecha, ambiente y semáforo
  - **Detalle de run**: Semáforo, screenshots por módulo (OK + FAIL), métricas de tiempo vs baseline p95
- **Interfaces**: Consume `GET /v1/runs`, `GET /v1/runs/{run_id}`, `POST /v1/run` del backend

---

### C0-A: SharedModels
- **Módulo**: `src/models.py`
- **Propósito**: Fuente única de verdad para todos los modelos Pydantic compartidos entre módulos
- **Responsabilidades**:
  - Definir `SyntheticUserConfig` (contrato de entrada de la API)
  - Definir `RunRecord` (registro de una ejecución en el baseline store)
  - Definir `StepResult` (resultado de un paso individual de Playwright)
  - Definir `FlowResult` (resultado de un flow completo en un perfil)
  - Definir `ProfileResult` (resultado de ejecutar un flow en un perfil con browser)
  - Definir `ExecutionReport` (reporte final completo — output de la API)
  - Definir `TrafficLight` enum (GREEN / YELLOW / RED)
  - Definir `BrowserProfile` (configuración de viewport, locale, user-agent)
- **Interfaces**: Importado por api/, agents/, executor/, baseline/, reporter/

### C0-B: ProjectSetup
- **Módulo**: `pyproject.toml`, `Dockerfile`
- **Propósito**: Configuración reproducible del proyecto y del entorno de ejecución
- **Responsabilidades**:
  - Declarar dependencias con versiones exactas pinned
  - Configurar ruff (formatter + linter E,F,I,UP)
  - Configurar mypy (--strict)
  - Definir imagen Docker basada en Playwright oficial para el executor

### C0-C: TranslatorAgent (actualización)
- **Módulo**: `src/agents/translator.py`
- **Propósito**: Actualizar el modelo Claude y usar `SyntheticUserConfig` de `src/models`
- **Responsabilidades**:
  - Mantener la lógica de traducción NL → SyntheticUserConfig
  - Usar constante `CLAUDE_MODEL = "claude-haiku-4-5-20251001"`
  - Importar `SyntheticUserConfig` desde `src/models` (eliminar definición local)

---

### C1-A: BrowserProfiles
- **Módulo**: `src/executor/profiles/`
- **Propósito**: Encapsular la configuración de cada perfil de usuario sintético (viewport, locale, UA)
- **Responsabilidades**:
  - Exponer instancias de `BrowserProfile` para cada uno de los 3 perfiles
  - `mobile_co`: 390×844, es-CO, Chrome mobile UA
  - `desktop_co`: 1440×900, es-CO, Chrome desktop UA
  - `desktop_ec`: 1280×800, es-EC, Chrome desktop UA
  - NO contener lógica de ejecución — son configuración pura

### C1-B: SFCCSelectors
- **Módulo**: `src/executor/selectors.py`
- **Propósito**: Catálogo centralizado y nombrado de todos los selectores del storefront SFCC/SFRA
- **Responsabilidades**:
  - Exponer constantes `SCREAMING_SNAKE_CASE` para cada elemento interactivo
  - Agrupación por sección: `SEARCH_*`, `PDP_*`, `CART_*`, `CHECKOUT_*`, `PAYMENT_*`, `LOGIN_*` (username input, password input, login submit button)
  - Usar prefijos `data-cmp-` o `data-testid-` donde estén disponibles
  - Ser el único lugar donde viven los selectores (ningún flow los hardcodea)

### C1-C: CheckoutFullFlow
- **Módulo**: `src/executor/flows/checkout_full.py`
- **Propósito**: Implementar el flow completo de checkout (auth de ambiente → login → búsqueda → PDP → carrito → checkout → pago que falla)
- **Responsabilidades**:
  - Ejecutar los 10 pasos del flow en orden: `env_access_auth` → `shopper_login` → `search_product` → `category_page` → `pdp_variant_select` → `add_to_cart` → `mini_cart_validation` → `checkout_shipping` → `checkout_payment` → `payment_failure_validation`
  - Devolver lista de `StepResult` con nombre, status, durationMs, error
  - Capturar screenshot en TODOS los módulos (ok cuando `screenshot_on_success=True`, fail cuando `screenshot_on_error=True`)
  - Garantizar que `payment_failure_validation` siempre falle (invariante)
  - Marcar steps posteriores como `skipped` si uno falla

### C1-D: CheckoutCardDeclinedFlow
- **Módulo**: `src/executor/flows/checkout_card_declined.py`
- **Propósito**: Verificar explícitamente que el mensaje de error de tarjeta rechazada aparece correctamente
- **Responsabilidades**:
  - Ejecutar los mismos pasos que checkout_full hasta fill_payment
  - Agregar paso `verify_decline_message` que valida el mensaje de error en la UI
  - Mismas garantías que checkout_full (screenshots selectivos, skipped steps)

### C1-E: FlowRunner
- **Módulo**: `src/executor/runner.py`
- **Propósito**: Orquestador local que instancia el browser con el perfil correcto y ejecuta el flow indicado
- **Responsabilidades**:
  - Recibir `BrowserProfile`, `flow_name`, `SyntheticUserConfig`
  - Lanzar Playwright con la configuración del perfil
  - Delegar al flow correspondiente (checkout_full o checkout_card_declined)
  - Capturar excepciones de Playwright y convertirlas en `infrastructure_error`
  - Retornar `ProfileResult` con todos los StepResults y durationMs total

---

### C2-A: BaselineStore (Protocol)
- **Módulo**: `src/baseline/baseline_manager.py`
- **Propósito**: Interfaz abstracta para el almacenamiento de historial de ejecuciones
- **Responsabilidades**:
  - Definir `Protocol` con métodos: `save_run`, `get_last_n_runs`, `get_run`
  - Permitir que el `InMemoryBaselineStore` (stub) sea reemplazado por un `DynamoDBBaselineStore` en futuras iteraciones sin cambiar los consumidores

### C2-B: InMemoryBaselineStore
- **Módulo**: `src/baseline/baseline_manager.py`
- **Propósito**: Implementación stub del `BaselineStore` usando dict en memoria
- **Responsabilidades**:
  - Implementar todos los métodos del Protocol
  - Almacenar runs en memoria durante la sesión (no persiste entre reinicios)
  - Servir como reemplazo local de DynamoDB durante el desarrollo

### C2-C: BaselineCalculator
- **Módulo**: `src/baseline/baseline_manager.py`
- **Propósito**: Lógica pura de cálculo estadístico sobre el historial de runs
- **Responsabilidades**:
  - `calculate_p95(runs)`: calcular percentil 95 de durationMs
  - `is_bootstrap_mode(runs)`: True si hay < 14 runs exitosos
  - `compute_traffic_light(current_ms, p95_ms, bootstrap)`: retornar GREEN/YELLOW/RED según reglas del PRD

---

### C3-A: ReportGenerator
- **Módulo**: `src/reporter/report_generator.py`
- **Propósito**: Transformar los resultados de ejecución en el reporte final estructurado
- **Responsabilidades**:
  - `generate_report(profile_results, baseline_store, config)`: construir `ExecutionReport` completo
  - Consultar baseline, calcular semáforo, poblar `baselineComparison`
  - Garantizar `orders_created=0` via assertion
  - Validar que el resultado cumple con `specs/execution_report.json`

### C3-B: MarkdownFormatter
- **Módulo**: `src/reporter/report_generator.py`
- **Propósito**: Generar el reporte en Markdown legible para humanos
- **Responsabilidades**:
  - `to_markdown(report)`: formatear el ExecutionReport como Markdown
  - Incluir emoji de semáforo (verde/amarillo/rojo)
  - Tabla de pasos por perfil con status y duración
  - Sección de comparación con baseline p95
  - Sección destacada: `orders_created: 0`

---

### C4-A: APIRouter (expansión)
- **Módulo**: `src/api/main.py`
- **Propósito**: Exponer todos los endpoints REST del sistema con autenticación y validación
- **Responsabilidades**:
  - `POST /v1/run`: orquestar translator → runner → reporter → baseline
  - `GET /v1/runs/{run_id}`: recuperar reporte por UUID
  - `GET /v1/runs/latest`: retornar último reporte con `age_seconds` y `ttl_ok`
  - Validar `X-API-Key` en todos los endpoints (401 sin key)
  - Global exception handler — nunca exponer stack traces al cliente
