# Code Quality Assessment — TestPilot SFCC

## Test Coverage

| Módulo | Tests Existentes | Cobertura Estimada | Estado |
|--------|-----------------|-------------------|--------|
| `src/agents/translator.py` | test_translator.py (5 clases, 9 tests) | ~80% | Buena |
| `src/api/main.py` | No existen tests directos de la API | ~0% | Ausente |
| `specs/synthetic_user_config.json` | test_schemas.py (8 tests) | 100% | Completa |
| `specs/execution_report.schema.json` | test_schemas.py (8 tests) | 100% | Completa |
| `src/executor/` | N/A (no implementado) | N/A | Pendiente |
| `src/baseline/` | N/A (no implementado) | N/A | Pendiente |
| `src/reporter/` | N/A (no implementado) | N/A | Pendiente |
| `src/classifier/` | N/A (no implementado) | N/A | Pendiente |

- **Unit Tests**: Parciales — bien cubiertos los schemas y el translator; API sin tests
- **Integration Tests**: Ninguno — no hay tests end-to-end de POST /v1/run
- **E2E Tests**: Ninguno (Playwright tests del sistema son el objetivo del producto, no tests del código)

## Code Quality Indicators

### Linting
- **Estado**: Configurado en AGENTS.md (ruff E,F,I,UP) pero sin `pyproject.toml` — no se puede ejecutar `ruff check` sin configuración explícita
- **Riesgo**: Los hooks de ruff declarados en AGENTS.md no pueden ejecutarse sin el archivo de config

### Code Style
- **Estado**: Consistente en el código existente
- **Buenas prácticas observadas**:
  - Type hints en todos los parámetros y retornos
  - Docstrings ausentes (acorde a las convenciones del proyecto — AGENTS.md no los exige)
  - Naming conventions seguidas (snake_case funciones, PascalCase clases)
  - Constantes en SCREAMING_SNAKE_CASE (FLOWS, PROFILES, MAX_RETRIES)

### Documentation
- **Calidad**: Buena a nivel de arquitectura (AGENTS.md, CLAUDE.md, PRD)
- **Calidad en código**: Mínima intencionalmente (sin comments en código — correcto según AGENTS.md)
- **Gap**: No hay docstrings en funciones públicas del translator (puede dificultar onboarding)

## Technical Debt

### TD1 — Sin requirements.txt ni pyproject.toml (ALTA PRIORIDAD)
- **Ubicación**: Workspace root
- **Impacto**: Sin versiones pinned, el build Docker puede ser no-reproducible
- **Acción**: Crear `pyproject.toml` con dependencias y configuración de ruff + mypy

### TD2 — Modelo Claude desactualizado en translator.py
- **Ubicación**: `src/agents/translator.py:translate()` — usa `claude-3-haiku-20240307`
- **Impacto**: Modelo puede quedar deprecated; hay versiones más capaces disponibles
- **Acción**: Actualizar a `claude-haiku-4-5-20251001` (latest per sistema)

### TD3 — POST /v1/run no ejecuta nada real (por diseño de sprint)
- **Ubicación**: `src/api/main.py:run_test()` — retorna "queued" sin lanzar ejecución
- **Impacto**: La API es un stub; no conecta con Step Functions ni executor
- **Acción**: Integrar con executor cuando esté implementado (pendiente sprint 1+)

### TD4 — Sin tests de integración para POST /v1/run
- **Ubicación**: `tests/` — faltan tests de la API con TestClient de FastAPI
- **Impacto**: Los validators Pydantic de la API no están cubiertos por tests automáticos
- **Acción**: Agregar `tests/test_api.py` con FastAPI TestClient

### TD5 — SyntheticUserConfig duplicada entre api/main.py y agents/translator.py
- **Ubicación**: Clase definida en ambos módulos con leve diferencia
- **Impacto**: Inconsistencia potencial si se modifica uno sin el otro
- **Acción**: Mover a `src/models.py` o `src/schemas.py` compartido y re-importar

### TD6 — Sin manejo de errores en endpoints GET (no implementados)
- **Ubicación**: Pendiente en src/api/main.py
- **Impacto**: Cuando se implemente GET /v1/runs/{run_id}, necesita manejo 404/500
- **Acción**: Incluir en implementación de endpoints GET

## Patterns and Anti-patterns

### Good Patterns
- **Closed Catalog**: Enums en specs/ + Literal types en Pydantic evitan flores arbitrarios del LLM
- **Separation of Concerns**: translator.py separa prompt building, schema validation y API call
- **Retry Bounded**: MAX_RETRIES=3 con re-raise del último error — no loop infinito
- **Zero Contamination**: email validator en API y auto-assign en translator son dos capas independientes
- **Schema as Source of Truth**: specs/ es el contrato primario; Pydantic lo refuerza, no lo reemplaza

### Anti-patterns (Minor)
- **Model Duplication** (TD5): SyntheticUserConfig en dos módulos — acceptable por ahora, resolver antes de escalar
- **No Dependency File** (TD1): Ausencia de pyproject.toml es el anti-patrón más impactante del código actual
- **Hardcoded Model Name**: `claude-3-haiku-20240307` en translator.py sin constante ni env var — difícil de actualizar
