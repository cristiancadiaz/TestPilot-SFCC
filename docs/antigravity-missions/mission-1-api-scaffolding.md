# Mission 1 — FastAPI Scaffolding (`/v1/run`)

**Branch:** `feat/api-scaffolding`
**Estimated duration:** 60–90 min agentic execution
**Parallelism:** independiente de Mission 2 (toca módulos distintos)
**Owner agent:** Antigravity session #1

---

## Objetivo de la misión

Levantar el endpoint `POST /v1/run` de FastAPI con validación estricta contra el JSON Schema en `specs/`. Sin LLM aún (eso es siguiente sprint). El endpoint recibe un `SyntheticUserConfig` ya formado, lo valida, y responde con `202 Accepted` + un `run_id`.

## Contexto que el agente debe cargar antes de empezar

1. `AGENTS.md` — convenciones del proyecto.
2. `CLAUDE.md` — invariantes (zero contamination, catálogo cerrado, JSON Schema gate).
3. `specs/synthetic-user-config.schema.json` — contrato canónico.
4. `.claude/skills/validate-synthetic-config/SKILL.md` — referencia de cómo validamos.

## Criterios de aceptación

- [ ] `src/api/main.py` con app FastAPI y endpoint `POST /v1/run`.
- [ ] `src/api/schemas.py` con Pydantic models que **espejan** el JSON Schema.
- [ ] Validación contra `specs/synthetic-user-config.schema.json` antes de Pydantic (la doble validación es intencional — el schema es el contrato cross-tool, Pydantic es la conveniencia de Python).
- [ ] Endpoint devuelve `202 Accepted` con `{"run_id": "<uuid4>", "status": "queued"}` cuando el payload es válido.
- [ ] Endpoint devuelve `400` con `application/problem+json` (RFC 7807) listando todas las violaciones del schema cuando el payload es inválido.
- [ ] Endpoint devuelve `400` específicamente con código `invariant_violation` si falla un invariante del CLAUDE.md (email no `@testpilot.internal`, flow fuera del catálogo, `environment_id = "production"`).
- [ ] Tests en `tests/test_api_v1_run.py`:
  - happy path con cada uno de los 2 flows del catálogo.
  - 400 cuando email no es `@testpilot.internal`.
  - 400 cuando flow es `"checkout_partial"` (fuera del catálogo).
  - 400 cuando `environment_id = "production"`.
  - 400 cuando faltan campos required.
- [ ] `uv run pytest tests/test_api_v1_run.py -v` pasa al 100%.
- [ ] `ruff check src/api/ tests/` sin warnings.
- [ ] `mypy --strict src/api/` sin errores.

## Archivos a crear/modificar

```
src/api/
├── __init__.py         (nuevo)
├── main.py             (nuevo)
├── schemas.py          (nuevo)
└── errors.py           (nuevo - helpers RFC 7807)

tests/
└── test_api_v1_run.py  (nuevo)

pyproject.toml          (modificar — agregar fastapi, jsonschema, httpx para tests)
```

## Constraints que NO se pueden violar

- **No instancia el executor.** El endpoint solo valida y encola — la ejecución real es Mission posterior.
- **No llama a Claude API.** La traducción NL → config queda para `src/agents/` (siguiente sprint).
- **No toca `specs/`.** El schema ya está definido; se consume read-only.
- **No toca `src/executor/`, `src/baseline/`, `src/reporter/`.** Esos módulos son scope de otras misiones.
- **No agrega dependencias fuera de** `fastapi`, `pydantic`, `jsonschema`, `uvicorn`, `httpx` (test client). Si necesitas algo más, abortar y reportar.

## Cómo verificar al final

```bash
uv run pytest tests/test_api_v1_run.py -v --tb=short
uv run ruff check src/api/ tests/
uv run mypy --strict src/api/
uv run uvicorn src.api.main:app --reload &
curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d @.claude/skills/validate-synthetic-config/scripts/example_valid.json
# esperado: 202 + {"run_id": "...", "status": "queued"}

curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d @.claude/skills/validate-synthetic-config/scripts/example_invalid.json
# esperado: 400 + application/problem+json con todas las violaciones
```

## Entregable para el reviewer humano

- Diff completo en la rama `feat/api-scaffolding`.
- Output de los 4 comandos de verificación copiados al PR description.
- Una línea en `docs/api/changelog.md` registrando "v1 inicial — endpoint scaffolding".

---

## ⚠️ Nota para el agente de Antigravity

Esta misión corre **en paralelo** con Mission 2 (DynamoDB baseline). Ambas tocan `pyproject.toml` para agregar dependencias — el merge a `main` requiere coordinación manual. Si detectas que Mission 2 ya hizo cambios a `pyproject.toml`, ejecuta `git rebase main` y resuelve a favor del superset de dependencias antes de abrir PR.
